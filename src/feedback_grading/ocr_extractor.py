"""
Mistral OCR extraction utilities for the feedback/grading workflow.

This module is intentionally independent from Streamlit so it can be used
from the UI, CLI scripts, or tests.

Supported input formats:
- PDF
- PNG
- JPG / JPEG

Typical output:
{
    "raw_text": "...",
    "pages": [
        {"page_index": 0, "markdown": "..."}
    ],
    "source_filename": "copy_001.pdf"
}
"""

from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class OCRExtractionError(RuntimeError):
    """Raised when OCR extraction fails in a controlled way."""


def _get_value(obj: Any, *names: str, default: Any = None) -> Any:
    """Read a value from either a dict-like object or an SDK response object."""
    for name in names:
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _make_mistral_client() -> Any:
    """
    Create a Mistral client.

    Preference order:
    1. Reuse the project's existing mistral_client.py helper if it exposes one.
    2. Fall back to the SDK import that works in the user's environment:
       from mistralai.client import Mistral
    3. Fall back to the newer SDK import:
       from mistralai import Mistral
    """
    try:
        from src.feedback_grading import mistral_client as project_mistral_client
    except Exception:
        try:
            from . import mistral_client as project_mistral_client  # type: ignore
        except Exception:
            project_mistral_client = None

    if project_mistral_client is not None:
        for factory_name in (
            "get_mistral_client",
            "create_mistral_client",
            "get_client",
            "create_client",
            "build_client",
        ):
            factory = getattr(project_mistral_client, factory_name, None)
            if callable(factory):
                try:
                    return factory()
                except TypeError:
                    continue

        existing_client = getattr(project_mistral_client, "client", None)
        if existing_client is not None:
            return existing_client

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise OCRExtractionError(
            "MISTRAL_API_KEY is missing. Add it to .env or to the environment."
        )

    try:
        from mistralai.client import Mistral  # type: ignore
    except Exception:
        try:
            from mistralai import Mistral  # type: ignore
        except Exception as exc:
            raise OCRExtractionError(
                "Could not import the Mistral SDK. Install or check the mistralai package."
            ) from exc

    return Mistral(api_key=api_key)


class MistralOCRExtractor:
    """
    Extract text/markdown from local files using Mistral OCR.

    The primary path uploads the file with purpose='ocr', obtains a signed URL,
    then calls client.ocr.process(model=..., document={...}).

    For image files, a base64 image fallback is also attempted because some SDK
    versions support direct base64 image OCR more reliably than uploaded-image
    signed URLs.
    """

    def __init__(self, client: Optional[Any] = None, model: Optional[str] = None) -> None:
        self.client = client or _make_mistral_client()
        self.model = model or os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

    def extract_from_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract OCR markdown/text from bytes, for Streamlit uploads."""
        if not isinstance(file_bytes, (bytes, bytearray)) or not file_bytes:
            raise OCRExtractionError("No file bytes were provided for OCR extraction.")

        suffix = Path(filename).suffix.lower()
        self._validate_extension(suffix)

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        try:
            return self.extract_from_path(
                tmp_path,
                source_filename=filename,
                mime_type=mime_type,
                original_bytes=bytes(file_bytes),
            )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def extract_from_path(
        self,
        file_path: Union[str, Path],
        source_filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        original_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Extract OCR markdown/text from a local file path."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise OCRExtractionError(f"OCR source file does not exist: {path}")

        suffix = path.suffix.lower()
        self._validate_extension(suffix)

        filename = source_filename or path.name
        mime = mime_type or mimetypes.guess_type(filename)[0] or self._default_mime(suffix)

        errors: List[str] = []

        try:
            uploaded_file = self._upload_file(path=path, filename=filename)
            file_id = self._extract_file_id(uploaded_file)
            signed_url = self._get_signed_url(file_id)
            response = self._process_document_url(signed_url)
            return self._normalise_response(response, filename)
        except Exception as exc:
            errors.append(f"signed-url OCR failed: {exc}")

        if suffix in IMAGE_EXTENSIONS:
            try:
                image_bytes = original_bytes if original_bytes is not None else path.read_bytes()
                response = self._process_base64_image(image_bytes, mime)
                return self._normalise_response(response, filename)
            except Exception as exc:
                errors.append(f"base64 image OCR fallback failed: {exc}")

        raise OCRExtractionError(
            "Mistral OCR extraction failed. " + " | ".join(errors)
        )

    def _validate_extension(self, suffix: str) -> None:
        if suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise OCRExtractionError(
                f"Unsupported OCR file type '{suffix}'. Supported types: PDF, PNG, JPG, JPEG."
            )

    def _default_mime(self, suffix: str) -> str:
        if suffix == ".pdf":
            return "application/pdf"
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        return "application/octet-stream"

    def _upload_file(self, path: Path, filename: str) -> Any:
        files_api = getattr(self.client, "files", None)
        if files_api is None or not hasattr(files_api, "upload"):
            raise OCRExtractionError("This Mistral client does not expose files.upload(...).")

        upload = files_api.upload
        last_error: Optional[Exception] = None

        payload_variants = [
            lambda handle: {"file_name": filename, "content": handle},
            lambda handle: {"file_name": str(path), "content": handle},
            lambda handle: {"filename": filename, "content": handle},
        ]

        for build_payload in payload_variants:
            try:
                with open(path, "rb") as handle:
                    return upload(file=build_payload(handle), purpose="ocr")
            except Exception as exc:
                last_error = exc

        raise OCRExtractionError(f"Could not upload file to Mistral for OCR: {last_error}")

    def _extract_file_id(self, uploaded_file: Any) -> str:
        file_id = _get_value(uploaded_file, "id", "file_id")
        if not file_id:
            raise OCRExtractionError(
                f"Mistral upload response did not include a file id: {uploaded_file}"
            )
        return str(file_id)

    def _get_signed_url(self, file_id: str) -> str:
        files_api = getattr(self.client, "files", None)
        if files_api is None or not hasattr(files_api, "get_signed_url"):
            raise OCRExtractionError("This Mistral client does not expose files.get_signed_url(...).")

        get_signed_url = files_api.get_signed_url
        last_error: Optional[Exception] = None

        for attempt in (
            lambda: get_signed_url(file_id=file_id),
            lambda: get_signed_url(id=file_id),
            lambda: get_signed_url(file_id),
        ):
            try:
                signed = attempt()
                url = _get_value(signed, "url", "signed_url", "document_url")
                if isinstance(url, str) and url.strip():
                    return url
                if isinstance(signed, str) and signed.strip():
                    return signed
            except Exception as exc:
                last_error = exc

        raise OCRExtractionError(f"Could not get signed URL from Mistral: {last_error}")

    def _process_document_url(self, signed_url: str) -> Any:
        ocr_api = getattr(self.client, "ocr", None)
        if ocr_api is None or not hasattr(ocr_api, "process"):
            raise OCRExtractionError("This Mistral client does not expose ocr.process(...).")

        process = ocr_api.process
        last_error: Optional[Exception] = None

        attempts = [
            lambda: process(
                model=self.model,
                document={"type": "document_url", "document_url": signed_url},
            ),
            lambda: process(
                model=self.model,
                document={"type": "document_url", "document_url": {"url": signed_url}},
            ),
            lambda: process(
                model=self.model,
                document={"document_url": signed_url, "type": "document_url"},
            ),
        ]

        for attempt in attempts:
            try:
                return attempt()
            except Exception as exc:
                last_error = exc

        raise OCRExtractionError(f"client.ocr.process(document_url=...) failed: {last_error}")

    def _process_base64_image(self, image_bytes: bytes, mime_type: str) -> Any:
        ocr_api = getattr(self.client, "ocr", None)
        if ocr_api is None or not hasattr(ocr_api, "process"):
            raise OCRExtractionError("This Mistral client does not expose ocr.process(...).")

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"
        process = ocr_api.process
        last_error: Optional[Exception] = None

        attempts = [
            lambda: process(
                model=self.model,
                document={"type": "image_url", "image_url": data_url},
            ),
            lambda: process(
                model=self.model,
                document={"type": "image_url", "image_url": {"url": data_url}},
            ),
        ]

        for attempt in attempts:
            try:
                return attempt()
            except Exception as exc:
                last_error = exc

        raise OCRExtractionError(f"client.ocr.process(base64 image) failed: {last_error}")

    def _normalise_response(self, response: Any, source_filename: str) -> Dict[str, Any]:
        pages_obj = _get_value(response, "pages", default=None)

        pages: List[Dict[str, Any]] = []

        if isinstance(pages_obj, Sequence) and not isinstance(pages_obj, (str, bytes, bytearray)):
            for index, page in enumerate(pages_obj):
                markdown = _get_value(page, "markdown", "text", "content", default="")
                page_index = _get_value(page, "page_index", "index", "page_number", default=index)
                try:
                    page_index_int = int(page_index)
                except Exception:
                    page_index_int = index

                pages.append(
                    {
                        "page_index": page_index_int,
                        "markdown": str(markdown or ""),
                    }
                )

        if not pages:
            markdown = _get_value(response, "markdown", "text", "content", default="")
            if isinstance(response, str):
                markdown = response
            pages.append({"page_index": 0, "markdown": str(markdown or "")})

        raw_text = "\n\n".join(page["markdown"] for page in pages if page.get("markdown"))

        if not raw_text.strip():
            raise OCRExtractionError(
                "Mistral OCR returned an empty text result. The scan may be unreadable."
            )

        return {
            "raw_text": raw_text,
            "pages": pages,
            "source_filename": source_filename,
        }


def extract_ocr_from_path(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Convenience function for local paths."""
    return MistralOCRExtractor().extract_from_path(file_path)


def extract_ocr_from_bytes(
    file_bytes: bytes,
    filename: str,
    mime_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function for Streamlit uploaded file bytes."""
    return MistralOCRExtractor().extract_from_bytes(
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
    )