# extractors/ocr_extractor.py

import base64
import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral


class OCRExtractor:
    """
    Real OCR extractor using Mistral OCR.

    Role:
    - receive an uploaded 2D plan image or PDF
    - send it to Mistral OCR
    - extract readable text / markdown
    - parse simple engineering dimensions from the OCR text
    - return structured evidence to the aggregator

    Important:
    This class does not generate CAD operations.
    It only extracts evidence from the uploaded drawing.
    """

    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.ocr_model = os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

        if not self.api_key:
            raise ValueError(
                "MISTRAL_API_KEY is missing. Add it to your .env file."
            )

        self.client = Mistral(api_key=self.api_key)

    def extract(self, plan_file):
        """
        Main OCR entry point used by the orchestrator.

        Returns a dictionary compatible with the rest of the CAD pipeline.
        """

        try:
            file_path = self._resolve_file_path(plan_file)

            if not file_path:
                return self._error_result(
                    "Could not resolve uploaded plan file path."
                )

            if not os.path.exists(file_path):
                return self._error_result(
                    f"Plan file does not exist: {file_path}"
                )

            document_payload = self._build_document_payload(file_path)

            ocr_response = self.client.ocr.process(
                model=self.ocr_model,
                document=document_payload,
                include_image_base64=False,
                confidence_scores_granularity="page",
            )

            detected_text = self._extract_text_from_response(ocr_response)
            detected_dimensions = self._extract_dimensions(detected_text)
            detected_symbols = self._extract_engineering_symbols(detected_text)

            warnings = []

            if detected_text:
                status = "success"
            else:
                status = "no_text_detected"
                warnings.append(
                    "Mistral OCR ran successfully, but no readable text was detected."
                )

            return {
                "tool": "ocr_extractor",
                "engine": self.ocr_model,
                "status": status,
                "source_file": os.path.basename(file_path),
                "detected_text": detected_text,
                "detected_dimensions": detected_dimensions,
                "detected_symbols": detected_symbols,
                "warnings": warnings,
            }

        except Exception as error:
            return self._error_result(str(error))

    # ----------------------------------------------------
    # File handling
    # ----------------------------------------------------

    def _resolve_file_path(self, plan_file):
        """
        Supports:
        - direct string path
        - pathlib.Path
        - Streamlit UploadedFile object
        """

        if plan_file is None:
            return None

        if isinstance(plan_file, (str, Path)):
            return str(plan_file)

        if hasattr(plan_file, "name") and hasattr(plan_file, "getbuffer"):
            suffix = Path(plan_file.name).suffix

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as temp_file:
                temp_file.write(plan_file.getbuffer())
                return temp_file.name

        return None

    def _build_document_payload(self, file_path):
        """
        Converts a local image/PDF into a base64 data URL payload for Mistral OCR.

        Images use:
        {
            "type": "image_url",
            "image_url": "data:image/png;base64,..."
        }

        PDFs use:
        {
            "type": "document_url",
            "document_url": "data:application/pdf;base64,..."
        }
        """

        suffix = Path(file_path).suffix.lower()

        with open(file_path, "rb") as file:
            encoded_file = base64.b64encode(file.read()).decode("utf-8")

        if suffix == ".pdf":
            return {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{encoded_file}",
            }

        mime_type = self._mime_type_from_suffix(suffix)

        return {
            "type": "image_url",
            "image_url": f"data:{mime_type};base64,{encoded_file}",
        }

    def _mime_type_from_suffix(self, suffix):
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
        }

        return mapping.get(suffix, "image/png")

    # ----------------------------------------------------
    # Mistral OCR response parsing
    # ----------------------------------------------------

    def _extract_text_from_response(self, ocr_response):
        """
        Mistral OCR response usually contains:

        response.pages[index].markdown

        This method is defensive so it works whether the SDK returns
        objects or dictionaries.
        """

        pages = self._safe_get(ocr_response, "pages", default=[])

        text_blocks = []

        for page in pages:
            markdown = self._safe_get(page, "markdown", default="")

            if markdown:
                text_blocks.append(str(markdown).strip())

        return "\n\n".join(text_blocks).strip()

    def _safe_get(self, obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    # ----------------------------------------------------
    # Dimension extraction
    # ----------------------------------------------------

    def _extract_dimensions(self, text):
        """
        Extracts simple technical dimensions from OCR text.

        Examples detected:
        - 160 mm
        - 100mm
        - Ø10
        - Ø 8 mm
        - diameter 12 mm
        - R5
        - 40 x 20
        - 160 x 100 x 12
        """

        if not text:
            return []

        normalized_text = self._normalize_ocr_text(text)

        dimensions = []

        dimensions.extend(self._extract_compound_dimensions(normalized_text))
        dimensions.extend(self._extract_diameter_dimensions(normalized_text))
        dimensions.extend(self._extract_radius_dimensions(normalized_text))
        dimensions.extend(self._extract_linear_dimensions(normalized_text))

        return self._deduplicate_dimensions(dimensions)

    def _normalize_ocr_text(self, text):
        return (
            text.replace("×", "x")
            .replace("X", "x")
            .replace("ø", "Ø")
            .replace("⌀", "Ø")
            .replace("—", "-")
            .replace("–", "-")
        )

    def _extract_linear_dimensions(self, text):
        """
        Extracts dimensions like:
        160 mm
        12.5 mm

        It intentionally requires a unit to avoid treating every number
        in the drawing as a dimension.
        """

        results = []

        pattern = re.compile(
            r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m)\b",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            value = self._to_number(match.group("value"))
            unit = match.group("unit")

            if value is None:
                continue

            results.append(
                {
                    "type": "linear",
                    "value": value,
                    "unit": unit.lower(),
                    "raw": match.group(0),
                }
            )

        return results

    def _extract_diameter_dimensions(self, text):
        """
        Extracts dimensions like:
        Ø10
        Ø 10 mm
        diameter 10
        dia. 10 mm
        """

        results = []

        pattern = re.compile(
            r"(?:Ø|diameter|dia\.?)\s*"
            r"(?P<value>\d+(?:\.\d+)?)\s*"
            r"(?P<unit>mm|cm|m)?",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            value = self._to_number(match.group("value"))
            unit = match.group("unit") or "mm"

            if value is None:
                continue

            results.append(
                {
                    "type": "diameter",
                    "value": value,
                    "unit": unit.lower(),
                    "raw": match.group(0),
                }
            )

        return results

    def _extract_radius_dimensions(self, text):
        """
        Extracts dimensions like:
        R5
        R 5 mm
        """

        results = []

        pattern = re.compile(
            r"\bR\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m)?",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            value = self._to_number(match.group("value"))
            unit = match.group("unit") or "mm"

            if value is None:
                continue

            results.append(
                {
                    "type": "radius",
                    "value": value,
                    "unit": unit.lower(),
                    "raw": match.group(0),
                }
            )

        return results

    def _extract_compound_dimensions(self, text):
        """
        Extracts dimensions like:
        40 x 20
        160 x 100 x 12
        160 x 100 x 12 mm
        """

        results = []

        pattern = re.compile(
            r"(?P<a>\d+(?:\.\d+)?)\s*x\s*"
            r"(?P<b>\d+(?:\.\d+)?)"
            r"(?:\s*x\s*(?P<c>\d+(?:\.\d+)?))?"
            r"\s*(?P<unit>mm|cm|m)?",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            values = [
                self._to_number(match.group("a")),
                self._to_number(match.group("b")),
            ]

            if match.group("c") is not None:
                values.append(self._to_number(match.group("c")))

            unit = match.group("unit") or "mm"

            if any(value is None for value in values):
                continue

            results.append(
                {
                    "type": "compound",
                    "values": values,
                    "unit": unit.lower(),
                    "raw": match.group(0),
                }
            )

        return results

    def _extract_engineering_symbols(self, text):
        """
        Extracts useful technical flags from the OCR text.
        """

        if not text:
            return {}

        normalized_text = self._normalize_ocr_text(text)

        return {
            "has_diameter_symbol": (
                "Ø" in normalized_text
                or "diameter" in normalized_text.lower()
                or "dia" in normalized_text.lower()
            ),
            "has_radius_symbol": bool(
                re.search(r"\bR\s*\d", normalized_text, re.IGNORECASE)
            ),
            "has_mm": bool(
                re.search(r"\bmm\b", normalized_text, re.IGNORECASE)
            ),
            "has_degree_symbol": "°" in normalized_text,
            "mentions_through": bool(
                re.search(r"\b(thru|through)\b", normalized_text, re.IGNORECASE)
            ),
            "mentions_counterbore": bool(
                re.search(
                    r"\b(counterbore|counter bore|c'bore|cbore)\b",
                    normalized_text,
                    re.IGNORECASE,
                )
            ),
            "mentions_countersink": bool(
                re.search(
                    r"\b(countersink|counter sink|c'sink|csink)\b",
                    normalized_text,
                    re.IGNORECASE,
                )
            ),
        }

    def _deduplicate_dimensions(self, dimensions):
        seen = set()
        unique = []

        for item in dimensions:
            key = (
                item.get("type"),
                item.get("value"),
                tuple(item.get("values", [])),
                item.get("unit"),
                item.get("raw"),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return unique

    def _to_number(self, value):
        try:
            number = float(value)

            if number.is_integer():
                return int(number)

            return number

        except Exception:
            return None

    # ----------------------------------------------------
    # Error handling
    # ----------------------------------------------------

    def _error_result(self, message):
        return {
            "tool": "ocr_extractor",
            "engine": self.ocr_model if hasattr(self, "ocr_model") else "unknown",
            "status": "error",
            "reason": message,
            "detected_text": "",
            "detected_dimensions": [],
            "detected_symbols": {},
            "warnings": [message],
        }