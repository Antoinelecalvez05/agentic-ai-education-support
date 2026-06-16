"""
AI parser for OCR text extracted from student copies.

Modes:
- corrected_reference_copy
- new_student_submission

The parser converts OCR text into structured JSON using the configured Mistral
text model. Human validation is required before the output is used by the
feedback/grading pipeline.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Mapping, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


VALID_MODES = {"corrected_reference_copy", "new_student_submission"}


class CopyAIParserError(RuntimeError):
    """Raised when AI-based copy parsing fails in a controlled way."""


def _get_value(obj: Any, *names: str, default: Any = None) -> Any:
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
    1. Reuse the project's existing mistral_client.py helper if available.
    2. Fall back to from mistralai.client import Mistral.
    3. Fall back to from mistralai import Mistral.
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
        raise CopyAIParserError(
            "MISTRAL_API_KEY is missing. Add it to .env or to the environment."
        )

    try:
        from mistralai.client import Mistral  # type: ignore
    except Exception:
        try:
            from mistralai import Mistral  # type: ignore
        except Exception as exc:
            raise CopyAIParserError(
                "Could not import the Mistral SDK. Install or check the mistralai package."
            ) from exc

    return Mistral(api_key=api_key)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _parse_json_response(text: str) -> Dict[str, Any]:
    cleaned = _strip_code_fences(text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first < 0 or last <= first:
            raise
        parsed = json.loads(cleaned[first:last + 1])

    if not isinstance(parsed, dict):
        raise CopyAIParserError("The AI response was valid JSON but not a JSON object.")

    return parsed


def _normalise_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _normalise_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [str(value).strip()] if str(value).strip() else []


class CopyAIParser:
    """
    Convert OCR text into structured JSON using the Mistral text model.

    The model is explicitly instructed not to invent unreadable scores or text.
    Human validation is still required before adding extracted data to the app.
    """

    def __init__(self, client: Optional[Any] = None, model: Optional[str] = None) -> None:
        self.client = client or _make_mistral_client()
        self.model = model or os.getenv("MISTRAL_TEXT_MODEL", "mistral-medium-latest")

    def parse(
        self,
        ocr_text: str,
        mode: str,
        source_filename: Optional[str] = None,
        suggested_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if mode not in VALID_MODES:
            raise CopyAIParserError(f"Unsupported parser mode: {mode}")
        if not ocr_text or not ocr_text.strip():
            raise CopyAIParserError("No OCR text was provided to the copy parser.")

        messages = self._build_messages(
            ocr_text=ocr_text,
            mode=mode,
            source_filename=source_filename,
            suggested_id=suggested_id,
        )

        response = self._chat_complete(messages)
        content = self._extract_message_content(response)
        parsed = _parse_json_response(content)

        if mode == "corrected_reference_copy":
            return self._normalise_corrected_reference_copy(parsed, suggested_id)

        return self._normalise_new_student_submission(parsed, suggested_id)

    def _build_messages(
        self,
        ocr_text: str,
        mode: str,
        source_filename: Optional[str],
        suggested_id: Optional[str],
    ) -> list[dict[str, str]]:
        system = (
            "You are an academic document extraction assistant. "
            "You extract structured data from OCR text for lecturer review. "
            "Return only valid JSON. Do not wrap JSON in markdown. "
            "Do not invent unreadable information. If a score, ID, comment, or answer segment "
            "is unclear, set the relevant field to null or an empty string and add an uncertainty. "
            "Human validation is required before use."
        )

        if mode == "corrected_reference_copy":
            schema_instruction = """
Return exactly this JSON object shape:
{
  "copy_id": "copy_A001 or suggested id if no explicit id is visible",
  "student_answer": "full extracted student answer text",
  "detected_score": 5.5,
  "max_score": 6,
  "grader_id": "unknown",
  "grader_comment": "text",
  "correction_marks": ["text"],
  "uncertainties": ["text"]
}

Rules:
- If the score is unreadable or ambiguous, set detected_score to null.
- If the maximum score is unreadable, set max_score to null.
- Do not infer a score from comments alone.
- Preserve the student's answer as fully as possible.
- Extract teacher/grader comments separately when visible.
- Put handwritten or OCR uncertainty into uncertainties.
""".strip()
        else:
            schema_instruction = """
Return exactly this JSON object shape:
{
  "student_id": "student_001 or suggested id if no explicit id is visible",
  "answer": "full extracted student answer text",
  "metadata": {},
  "uncertainties": ["text"]
}

Rules:
- Preserve the student's answer as fully as possible.
- Do not grade the answer.
- Do not invent metadata.
- If handwriting or OCR is unclear, add uncertainty notes.
""".strip()

        user = f"""
Mode: {mode}
Source filename: {source_filename or "unknown"}
Suggested ID if no ID is visible: {suggested_id or "none"}

{schema_instruction}

OCR text:
{ocr_text}
""".strip()

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _chat_complete(self, messages: list[dict[str, str]]) -> Any:
        chat_api = getattr(self.client, "chat", None)
        if chat_api is None:
            raise CopyAIParserError("This Mistral client does not expose a chat API.")

        last_error: Optional[Exception] = None

        if hasattr(chat_api, "complete"):
            complete = chat_api.complete
            attempts = [
                lambda: complete(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                    response_format={"type": "json_object"},
                ),
                lambda: complete(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                ),
                lambda: complete(
                    model=self.model,
                    messages=messages,
                ),
            ]

            for attempt in attempts:
                try:
                    return attempt()
                except Exception as exc:
                    last_error = exc

        if callable(chat_api):
            try:
                return chat_api(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                )
            except Exception as exc:
                last_error = exc

        raise CopyAIParserError(f"Mistral chat completion failed: {last_error}")

    def _extract_message_content(self, response: Any) -> str:
        choices = _get_value(response, "choices", default=None)
        if choices and isinstance(choices, list):
            first = choices[0]
            message = _get_value(first, "message", default=None)
            content = _get_value(message, "content", default=None)
            if content is None:
                content = _get_value(first, "content", "text", default=None)
            if isinstance(content, list):
                parts = []
                for item in content:
                    part = _get_value(item, "text", "content", default="")
                    if part:
                        parts.append(str(part))
                content = "\n".join(parts)
            if isinstance(content, str) and content.strip():
                return content

        content = _get_value(response, "content", "text", "output_text", default=None)
        if isinstance(content, str) and content.strip():
            return content

        if isinstance(response, str) and response.strip():
            return response

        raise CopyAIParserError(f"Could not extract text content from AI response: {response}")

    def _normalise_corrected_reference_copy(
        self,
        parsed: Dict[str, Any],
        suggested_id: Optional[str],
    ) -> Dict[str, Any]:
        copy_id = parsed.get("copy_id") or suggested_id or "copy_unknown"
        student_answer = parsed.get("student_answer") or parsed.get("answer") or ""
        detected_score = _normalise_number(parsed.get("detected_score"))
        max_score = _normalise_number(parsed.get("max_score"))
        uncertainties = _normalise_list(parsed.get("uncertainties"))

        if parsed.get("detected_score") not in (None, "") and detected_score is None:
            uncertainties.append("Detected score could not be converted to a number.")

        if parsed.get("max_score") not in (None, "") and max_score is None:
            uncertainties.append("Maximum score could not be converted to a number.")

        if detected_score is None:
            uncertainties.append("Detected score is missing or unclear; lecturer must enter it manually.")

        return {
            "copy_id": str(copy_id),
            "student_answer": str(student_answer),
            "detected_score": detected_score,
            "max_score": max_score,
            "grader_id": str(parsed.get("grader_id") or "unknown"),
            "grader_comment": str(parsed.get("grader_comment") or parsed.get("lecturer_comment") or ""),
            "correction_marks": _normalise_list(parsed.get("correction_marks")),
            "uncertainties": uncertainties,
        }

    def _normalise_new_student_submission(
        self,
        parsed: Dict[str, Any],
        suggested_id: Optional[str],
    ) -> Dict[str, Any]:
        student_id = parsed.get("student_id") or suggested_id or "student_unknown"
        metadata = parsed.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return {
            "student_id": str(student_id),
            "answer": str(parsed.get("answer") or parsed.get("student_answer") or ""),
            "metadata": metadata,
            "uncertainties": _normalise_list(parsed.get("uncertainties")),
        }


def parse_copy_ocr_text(
    ocr_text: str,
    mode: str,
    source_filename: Optional[str] = None,
    suggested_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function for one-off parsing."""
    return CopyAIParser().parse(
        ocr_text=ocr_text,
        mode=mode,
        source_filename=source_filename,
        suggested_id=suggested_id,
    )