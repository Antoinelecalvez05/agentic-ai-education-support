# core/aggregator.py

import copy
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union


SUPPORTED_OPERATIONS = {
    "create_box",
    "create_rounded_rectangle_plate",
    "create_cylinder",

    "create_hole",
    "create_threaded_hole",
    "create_counterbore_hole",
    "create_countersink_hole",

    "create_slot",
    "create_rectangular_cutout",
    "create_rectangular_pocket",
    "create_circular_pocket",

    "create_rectangular_boss",
    "create_cylindrical_boss",

    "create_edge_notch",

    "create_hole_pattern",
    "create_linear_pattern",
    "create_circular_pattern",

    "mirror_feature",

    "create_fillet",
    "create_chamfer",
}


OPERATION_ALIASES = {
    "box": "create_box",
    "base_plate": "create_box",
    "rectangular_plate": "create_box",
    "plate": "create_box",
    "create_box": "create_box",

    "rounded_rectangle_plate": "create_rounded_rectangle_plate",
    "rounded_plate": "create_rounded_rectangle_plate",
    "create_rounded_rectangle_plate": "create_rounded_rectangle_plate",

    "cylinder": "create_cylinder",
    "create_cylinder": "create_cylinder",

    "hole": "create_hole",
    "circular_hole": "create_hole",
    "through_hole": "create_hole",
    "drilled_hole": "create_hole",
    "create_hole": "create_hole",

    "threaded_hole": "create_threaded_hole",
    "thread": "create_threaded_hole",
    "tapped_hole": "create_threaded_hole",
    "create_threaded_hole": "create_threaded_hole",

    "counterbore": "create_counterbore_hole",
    "counterbore_hole": "create_counterbore_hole",
    "create_counterbore_hole": "create_counterbore_hole",

    "countersink": "create_countersink_hole",
    "countersink_hole": "create_countersink_hole",
    "create_countersink_hole": "create_countersink_hole",

    "slot": "create_slot",
    "rounded_slot": "create_slot",
    "through_slot": "create_slot",
    "create_slot": "create_slot",

    "rectangular_cutout": "create_rectangular_cutout",
    "rectangle_cutout": "create_rectangular_cutout",
    "cutout": "create_rectangular_cutout",
    "through_cutout": "create_rectangular_cutout",
    "through_rectangular_cutout": "create_rectangular_cutout",
    "create_rectangular_cutout": "create_rectangular_cutout",

    "rectangular_pocket": "create_rectangular_pocket",
    "pocket": "create_rectangular_pocket",
    "rectangle_pocket": "create_rectangular_pocket",
    "create_rectangular_pocket": "create_rectangular_pocket",

    "circular_pocket": "create_circular_pocket",
    "round_pocket": "create_circular_pocket",
    "create_circular_pocket": "create_circular_pocket",

    "rectangular_boss": "create_rectangular_boss",
    "box_boss": "create_rectangular_boss",
    "cube_boss": "create_rectangular_boss",
    "create_rectangular_boss": "create_rectangular_boss",

    "cylindrical_boss": "create_cylindrical_boss",
    "round_boss": "create_cylindrical_boss",
    "cylinder_boss": "create_cylindrical_boss",
    "create_cylindrical_boss": "create_cylindrical_boss",

    "edge_notch": "create_edge_notch",
    "notch": "create_edge_notch",
    "side_notch": "create_edge_notch",
    "create_edge_notch": "create_edge_notch",

    "hole_pattern": "create_hole_pattern",
    "circular_hole_pattern": "create_hole_pattern",
    "create_hole_pattern": "create_hole_pattern",

    "linear_pattern": "create_linear_pattern",
    "linear_array": "create_linear_pattern",
    "rectangular_array": "create_linear_pattern",
    "rectangular_pattern": "create_linear_pattern",
    "create_linear_pattern": "create_linear_pattern",

    "circular_pattern": "create_circular_pattern",
    "radial_pattern": "create_circular_pattern",
    "radial_circular_pattern": "create_circular_pattern",
    "polar_pattern": "create_circular_pattern",
    "create_circular_pattern": "create_circular_pattern",

    "mirror": "mirror_feature",
    "mirror_feature": "mirror_feature",
    "mirrored_feature": "mirror_feature",

    "fillet": "create_fillet",
    "round_edges": "create_fillet",
    "create_fillet": "create_fillet",

    "chamfer": "create_chamfer",
    "bevel": "create_chamfer",
    "create_chamfer": "create_chamfer",
}


SUPPORTED_SCOPES = {
    "base_top_outer_edges",
    "base_bottom_outer_edges",
    "base_outer_vertical_edges",
    "base_all_outer_edges",
    "global_top_edges",
    "global_bottom_edges",
    "global_vertical_edges",
}


SCOPE_ALIASES = {
    "top_outer_edges": "base_top_outer_edges",
    "bottom_outer_edges": "base_bottom_outer_edges",
    "outer_vertical_edges": "base_outer_vertical_edges",
    "all_outer_edges": "base_all_outer_edges",

    "vertical_outer_edges": "base_outer_vertical_edges",
    "base_vertical_edges": "base_outer_vertical_edges",
    "top_edges": "base_top_outer_edges",
    "bottom_edges": "base_bottom_outer_edges",

    "base_top_outer_edges": "base_top_outer_edges",
    "base_bottom_outer_edges": "base_bottom_outer_edges",
    "base_outer_vertical_edges": "base_outer_vertical_edges",
    "base_all_outer_edges": "base_all_outer_edges",
    "global_top_edges": "global_top_edges",
    "global_bottom_edges": "global_bottom_edges",
    "global_vertical_edges": "global_vertical_edges",
}


DEPTH_OPERATIONS = {
    "create_hole",
    "create_threaded_hole",
    "create_counterbore_hole",
    "create_countersink_hole",
    "create_slot",
    "create_rectangular_cutout",
    "create_rectangular_pocket",
    "create_circular_pocket",
    "create_edge_notch",
    "create_hole_pattern",
}


BOSS_OPERATIONS = {
    "create_rectangular_boss",
    "create_cylindrical_boss",
}


DIAMETER_OPERATIONS = {
    "create_hole",
    "create_threaded_hole",
    "create_circular_pocket",
    "create_cylindrical_boss",
}


FEATURE_OPERATIONS = {
    "create_hole",
    "create_threaded_hole",
    "create_counterbore_hole",
    "create_countersink_hole",
    "create_slot",
    "create_rectangular_cutout",
    "create_rectangular_pocket",
    "create_circular_pocket",
    "create_rectangular_boss",
    "create_cylindrical_boss",
    "create_edge_notch",
    "create_hole_pattern",
    "create_linear_pattern",
    "create_circular_pattern",
    "mirror_feature",
    "create_fillet",
    "create_chamfer",
}


class Aggregator:
    """
    Aggregator layer.

    It combines:
    - user prompt
    - OCR result
    - geometry result
    - Excel result

    into one canonical intermediate input for the Mistral CAD agent.

    Priority rule:
    1. Structured Excel data
    2. Explicit user prompt
    3. OCR extracted text/dimensions
    4. Geometry pixel estimates

    The aggregator is intentionally less strict than the validator.
    It preserves evidence and builds a best-effort cad_plan_hint.
    """

    def build(self, prompt, ocr_result, geometry_result, excel_result):
        prompt = prompt or ""
        units = self._choose_units(excel_result, ocr_result)

        canonical = {
            "task": "generate_3d_cad_model",
            "user_prompt": prompt,
            "units": units,
            "object_type": "mechanical_part",
            "geometry": {
                "base_shape": {},
                "features": [],
                "base_objects": [],
            },
            "constraints": (
                excel_result.get("constraints", {})
                if isinstance(excel_result, dict)
                else {}
            ),
            "missing_information": [],
            "conflicts": [],
            "warnings": [],
            "calibration": {
                "status": "not_run",
            },
            "geometry_checks": [],
            "reasoning_instruction": {},
            "ready_for_reasoning": False,
            "evidence": {
                "prompt": {
                    "raw": prompt,
                    "parsed": {},
                },
                "ocr": ocr_result,
                "geometry": geometry_result,
                "excel": excel_result,
            },
            "cad_plan_hint": {
                "units": units,
                "steps": [],
            },
        }

        prompt_data = self._parse_prompt(prompt)
        canonical["evidence"]["prompt"]["parsed"] = prompt_data

        self._merge_excel_data(canonical, excel_result)
        self._merge_prompt_data(canonical, prompt_data)
        self._merge_ocr_data(canonical, ocr_result)
        self._merge_geometry_data(canonical, geometry_result)

        self._dedupe_base_objects(canonical)
        self._dedupe_features(canonical)
        self._derive_depths_from_base(canonical)
        self._sync_legacy_base_shape(canonical)

        self._add_geometry_calibration(canonical, geometry_result)
        self._compare_expected_vs_detected_geometry(canonical)

        self._detect_missing_information(canonical)
        self._detect_basic_conflicts(canonical)
        self._build_reasoning_instruction(canonical)
        self._build_cad_plan_hint(canonical)

        canonical["ready_for_reasoning"] = (
            len(canonical["missing_information"]) == 0
            and len(canonical["conflicts"]) == 0
        )

        return canonical

    # ------------------------------------------------------------------
    # Merge sources
    # ------------------------------------------------------------------

    def _merge_excel_data(self, canonical, excel_result):
        if not isinstance(excel_result, dict):
            return

        status = excel_result.get("status")
        if status not in {"success", "no_usable_data", "skipped", None}:
            canonical["warnings"].append(f"Excel parser status: {status}")

        if excel_result.get("warnings"):
            canonical["warnings"].extend(self._as_list(excel_result.get("warnings")))

        excel_constraints = excel_result.get("constraints", {}) or {}
        canonical["constraints"].update(
            excel_constraints if isinstance(excel_constraints, dict) else {}
        )

        base_candidates = []
        for key in ("base_objects", "objects", "bases"):
            value = excel_result.get(key)
            if isinstance(value, list):
                base_candidates.extend(value)

        for base in base_candidates:
            if not isinstance(base, dict):
                continue
            normalized = self._normalize_base_object(base, source="excel")
            canonical["geometry"]["base_objects"].append(normalized)

        if not canonical["geometry"]["base_objects"]:
            base_from_constraints = self._base_from_constraints(excel_constraints)
            if base_from_constraints:
                canonical["geometry"]["base_objects"].append(base_from_constraints)

        feature_candidates = []
        for key in ("features", "operations", "steps"):
            value = excel_result.get(key)
            if isinstance(value, list):
                feature_candidates.extend(value)

        for feature in feature_candidates:
            if not isinstance(feature, dict):
                continue

            normalized = self._normalize_feature(feature, source="excel")

            if normalized.get("operation") == "create_box":
                canonical["geometry"]["base_objects"].append(
                    self._normalize_base_object(normalized, source="excel")
                )
            else:
                canonical["geometry"]["features"].append(normalized)

    def _merge_prompt_data(self, canonical, prompt_data):
        if not isinstance(prompt_data, dict):
            return

        base = prompt_data.get("base_object")
        if base and not canonical["geometry"]["base_objects"]:
            canonical["geometry"]["base_objects"].append(
                self._normalize_base_object(base, source="prompt")
            )

        for feature in prompt_data.get("features", []) or []:
            if not isinstance(feature, dict):
                continue
            canonical["geometry"]["features"].append(
                self._normalize_feature(feature, source="prompt")
            )

    def _merge_ocr_data(self, canonical, ocr_result):
        if not isinstance(ocr_result, dict):
            return

        if ocr_result.get("warnings"):
            canonical["warnings"].extend(self._as_list(ocr_result.get("warnings")))

        status = ocr_result.get("status")
        if status not in {"success", "no_text_detected", "skipped", None}:
            canonical["warnings"].append(f"OCR extractor status: {status}")

        dimensions = ocr_result.get("detected_dimensions", []) or []

        if not canonical["geometry"]["base_objects"]:
            base_from_ocr = self._base_from_ocr_dimensions(dimensions)
            if base_from_ocr:
                canonical["geometry"]["base_objects"].append(base_from_ocr)

        # OCR features are only fallback evidence. Avoid duplicating prompt/Excel features.
        if not canonical["geometry"]["features"]:
            features_from_ocr = self._features_from_ocr_dimensions(dimensions)
            canonical["geometry"]["features"].extend(features_from_ocr)

    def _merge_geometry_data(self, canonical, geometry_result):
        if not isinstance(geometry_result, dict):
            return

        status = geometry_result.get("status")
        if status in {"not_implemented", "skipped"}:
            return

        if geometry_result.get("warnings"):
            canonical["warnings"].extend(self._as_list(geometry_result.get("warnings")))

        detected_shapes = geometry_result.get("detected_shapes", []) or []

        canonical["evidence"]["geometry_summary"] = {
            "status": status,
            "detected_shape_count": len(detected_shapes),
            "shape_types": [
                shape.get("type") or shape.get("shape")
                for shape in detected_shapes
                if isinstance(shape, dict)
            ],
        }

    # ------------------------------------------------------------------
    # Prompt parsing
    # ------------------------------------------------------------------

    def _parse_prompt(self, prompt):
        result = {
            "base_object": None,
            "features": [],
        }

        if not prompt:
            return result

        text = self._normalize_text(prompt)

        base = self._parse_base_from_prompt(text)
        result["base_object"] = base

        parsers = [
            self._parse_rectangular_cutouts_from_prompt,
            self._parse_rectangular_pockets_from_prompt,
            self._parse_circular_pockets_from_prompt,
            self._parse_rectangular_bosses_from_prompt,
            self._parse_cylindrical_bosses_from_prompt,
            self._parse_threaded_holes_from_prompt,
            self._parse_counterbore_holes_from_prompt,
            self._parse_countersink_holes_from_prompt,
            self._parse_hole_patterns_from_prompt,
            self._parse_slots_from_prompt,
            self._parse_edge_notches_from_prompt,
            self._parse_single_holes_from_prompt,
            self._parse_linear_patterns_from_prompt,
            self._parse_circular_patterns_from_prompt,
            self._parse_mirror_features_from_prompt,
        ]

        for parser in parsers:
            try:
                result["features"].extend(parser(text, base))
            except Exception as error:
                # Prompt parsing is heuristic. Do not crash the pipeline.
                result["features"].append(
                    {
                        "operation": "parse_warning",
                        "source": "prompt",
                        "note": f"{parser.__name__} failed: {error}",
                    }
                )

        result["features"].extend(self._parse_fillets_from_prompt(text))
        result["features"].extend(self._parse_chamfers_from_prompt(text))

        # Remove parser warning pseudo-features from features and return them as ignored.
        result["features"] = [
            feature for feature in result["features"]
            if isinstance(feature, dict) and feature.get("operation") != "parse_warning"
        ]

        return result

    def _parse_base_from_prompt(self, text):
        patterns = [
            r"(?:base\s+plate|rectangular\s+plate|plate).*?"
            r"(?P<length>\d+(?:\.\d+)?)\s*mm\s+long.*?"
            r"(?P<width>\d+(?:\.\d+)?)\s*mm\s+wide.*?"
            r"(?P<height>\d+(?:\.\d+)?)\s*mm\s+(?:thick|high|height)",

            r"(?:base\s+plate|rectangular\s+plate|plate).*?"
            r"(?P<length>\d+(?:\.\d+)?)\s*[x×]\s*"
            r"(?P<width>\d+(?:\.\d+)?)\s*[x×]\s*"
            r"(?P<height>\d+(?:\.\d+)?)\s*mm",

            r"(?:base\s+plate|rectangular\s+plate|plate).*?"
            r"length\s*(?:=|is)?\s*(?P<length>\d+(?:\.\d+)?)\s*mm.*?"
            r"width\s*(?:=|is)?\s*(?P<width>\d+(?:\.\d+)?)\s*mm.*?"
            r"(?:height|thickness|depth)\s*(?:=|is)?\s*(?P<height>\d+(?:\.\d+)?)\s*mm",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return {
                    "operation": "create_box",
                    "name": "base_plate",
                    "length": self._to_number(match.group("length")),
                    "width": self._to_number(match.group("width")),
                    "height": self._to_number(match.group("height")),
                    "position": [0, 0, 0],
                    "source": "prompt",
                }

        return None

    def _parse_rectangular_cutouts_from_prompt(self, text, base):
        if "cutout" not in text or "rectangular" not in text:
            return []

        length = self._first_regex_number(text, [
            r"rectangular\s+(?:through\s*)?cutout.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+long",
            r"cutout.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+long",
            r"cutout.*?length\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        width = self._first_regex_number(text, [
            r"rectangular\s+(?:through\s*)?cutout.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+wide",
            r"cutout.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+wide",
            r"cutout.*?width\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        position = self._parse_center_position_near(text, keyword="cutout")

        if length is None and width is None:
            return []

        return [{
            "operation": "create_rectangular_cutout",
            "target": "base_plate",
            "length": length,
            "width": width,
            "depth": self._base_height(base),
            "position": position,
            "source": "prompt",
        }]

    def _parse_rectangular_pockets_from_prompt(self, text, base):
        if "pocket" not in text or "rectangular" not in text:
            return []

        length = self._first_regex_number(text, [
            r"rectangular\s+pocket.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+long",
            r"pocket.*?length\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        width = self._first_regex_number(text, [
            r"rectangular\s+pocket.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+wide",
            r"pocket.*?width\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        depth = self._first_regex_number(text, [
            r"rectangular\s+pocket.*?(?:depth|deep)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"pocket.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+deep",
        ])
        position = self._parse_center_position_near(text, keyword="pocket")

        if length is None and width is None and depth is None:
            return []

        return [{
            "operation": "create_rectangular_pocket",
            "target": "base_plate",
            "length": length,
            "width": width,
            "depth": depth,
            "position": position,
            "source": "prompt",
        }]

    def _parse_circular_pockets_from_prompt(self, text, base):
        if "pocket" not in text or not ("circular" in text or "round" in text):
            return []

        diameter = self._first_regex_number(text, [
            r"circular\s+pocket.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"round\s+pocket.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"circular\s+pocket.*?ø\s*(?P<value>\d+(?:\.\d+)?)",
        ])
        depth = self._first_regex_number(text, [
            r"circular\s+pocket.*?(?:depth|deep)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"pocket.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+deep",
        ])
        position = self._parse_center_position_near(text, keyword="pocket")

        if diameter is None and depth is None:
            return []

        return [{
            "operation": "create_circular_pocket",
            "target": "base_plate",
            "diameter": diameter,
            "depth": depth,
            "position": position,
            "source": "prompt",
        }]

    def _parse_rectangular_bosses_from_prompt(self, text, base):
        if "boss" not in text or "rectangular" not in text:
            return []

        length = self._first_regex_number(text, [
            r"rectangular\s+boss.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+long",
            r"boss.*?length\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        width = self._first_regex_number(text, [
            r"rectangular\s+boss.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+wide",
            r"boss.*?width\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        height = self._first_regex_number(text, [
            r"rectangular\s+boss.*?(?:height|high)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"boss.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+high",
        ])
        position = self._parse_center_position_near(text, keyword="boss")

        if length is None and width is None and height is None:
            return []

        return [{
            "operation": "create_rectangular_boss",
            "target": "base_plate",
            "length": length,
            "width": width,
            "height": height,
            "position": position,
            "source": "prompt",
        }]

    def _parse_cylindrical_bosses_from_prompt(self, text, base):
        if "boss" not in text or not ("cylindrical" in text or "round" in text or "cylinder" in text):
            return []

        diameter = self._first_regex_number(text, [
            r"cylindrical\s+boss.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"round\s+boss.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"boss.*?ø\s*(?P<value>\d+(?:\.\d+)?)",
        ])
        height = self._first_regex_number(text, [
            r"cylindrical\s+boss.*?(?:height|high)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"boss.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+high",
        ])
        position = self._parse_center_position_near(text, keyword="boss")

        if diameter is None and height is None:
            return []

        return [{
            "operation": "create_cylindrical_boss",
            "target": "base_plate",
            "diameter": diameter,
            "height": height,
            "position": position,
            "source": "prompt",
        }]

    def _parse_threaded_holes_from_prompt(self, text, base):
        if "thread" not in text and not re.search(r"\bm\d+\b", text):
            return []

        thread_match = re.search(r"\b(m\d+(?:x\d+(?:\.\d+)?)?)\b", text, re.IGNORECASE)
        thread = thread_match.group(1).upper() if thread_match else None

        diameter = self._first_regex_number(text, [
            r"threaded\s+hole.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"tap\s+drill.*?(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])

        depth = self._first_regex_number(text, [
            r"threaded\s+hole.*?(?:depth|deep)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"thread.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+deep",
        ])

        position = self._parse_center_position_near(text, keyword="thread")

        if thread is None and diameter is None:
            return []

        return [{
            "operation": "create_threaded_hole",
            "target": "base_plate",
            "thread": thread,
            "diameter": diameter,
            "depth": depth if depth is not None else self._base_height(base),
            "position": position,
            "source": "prompt",
        }]

    def _parse_counterbore_holes_from_prompt(self, text, base):
        if "counterbore" not in text:
            return []

        hole_diameter = self._first_regex_number(text, [
            r"hole\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"counterbore.*?hole.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        counterbore_diameter = self._first_regex_number(text, [
            r"counterbore\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"head\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        counterbore_depth = self._first_regex_number(text, [
            r"counterbore\s+depth\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"head\s+depth\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        position = self._parse_center_position_near(text, keyword="counterbore")

        return [{
            "operation": "create_counterbore_hole",
            "target": "base_plate",
            "hole_diameter": hole_diameter,
            "depth": self._base_height(base),
            "counterbore_diameter": counterbore_diameter,
            "counterbore_depth": counterbore_depth,
            "position": position,
            "source": "prompt",
        }]

    def _parse_countersink_holes_from_prompt(self, text, base):
        if "countersink" not in text:
            return []

        hole_diameter = self._first_regex_number(text, [
            r"hole\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"countersink.*?hole.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        countersink_diameter = self._first_regex_number(text, [
            r"countersink\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"head\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        countersink_angle = self._first_regex_number(text, [
            r"countersink\s+angle\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)",
            r"(?P<value>\d+(?:\.\d+)?)\s*degree\s+countersink",
        ])
        position = self._parse_center_position_near(text, keyword="countersink")

        return [{
            "operation": "create_countersink_hole",
            "target": "base_plate",
            "hole_diameter": hole_diameter,
            "depth": self._base_height(base),
            "countersink_diameter": countersink_diameter,
            "countersink_angle": countersink_angle if countersink_angle is not None else 90,
            "position": position,
            "source": "prompt",
        }]

    def _parse_hole_patterns_from_prompt(self, text, base):
        if "pattern" not in text or "hole" not in text:
            return []

        if any(word in text for word in ["radial", "circular pattern", "around a circle", "revolved"]):
            return []

        rows = self._first_regex_int(text, [
            r"pattern\s+has\s+(?P<value>\d+)\s+rows?",
            r"(?P<value>\d+)\s+rows?",
        ])
        columns = self._first_regex_int(text, [
            r"and\s+(?P<value>\d+)\s+columns?",
            r"(?P<value>\d+)\s+columns?",
        ])
        diameter = self._first_regex_number(text, [
            r"each\s+hole\s+has\s+diameter\s+(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"hole\s+diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"diameter\s+(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"ø\s*(?P<value>\d+(?:\.\d+)?)",
        ])
        spacing_x = self._first_regex_number(text, [
            r"spacing\s+in\s+x\s+is\s+(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"spacing_x\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)",
        ])
        spacing_y = self._first_regex_number(text, [
            r"spacing\s+in\s+y\s+is\s+(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"spacing_y\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)",
        ])
        first_position = self._parse_first_hole_position(text)

        if rows is None and columns is None and diameter is None:
            return []

        return [{
            "operation": "create_hole_pattern",
            "target": "base_plate",
            "rows": rows,
            "columns": columns,
            "diameter": diameter,
            "depth": self._base_height(base),
            "first_position": first_position,
            "spacing_x": spacing_x,
            "spacing_y": spacing_y,
            "source": "prompt",
        }]

    def _parse_slots_from_prompt(self, text, base):
        if "slot" not in text:
            return []

        length = self._first_regex_number(text, [
            r"slot.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+long",
            r"slot\s+length\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        width = self._first_regex_number(text, [
            r"slot.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+wide",
            r"slot\s+width\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        depth = self._first_regex_number(text, [
            r"slot.*?(?:depth|deep)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"slot.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+deep",
        ])
        position = self._parse_center_position_near(text, keyword="slot")
        orientation = "y" if ("orientation y" in text or "along y" in text) else "x"

        if length is None and width is None:
            return []

        return [{
            "operation": "create_slot",
            "target": "base_plate",
            "length": length,
            "width": width,
            "depth": depth if depth is not None else self._base_height(base),
            "position": position,
            "orientation": orientation,
            "source": "prompt",
        }]

    def _parse_edge_notches_from_prompt(self, text, base):
        if "notch" not in text:
            return []

        edge = None
        for candidate in ("left", "right", "top", "bottom", "front", "back", "x_min", "x_max", "y_min", "y_max"):
            if candidate in text:
                edge = candidate
                break

        length = self._first_regex_number(text, [
            r"notch.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+long",
            r"notch.*?length\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        width = self._first_regex_number(text, [
            r"notch.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+wide",
            r"notch.*?width\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        depth = self._first_regex_number(text, [
            r"notch.*?(?:depth|deep)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"notch.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+deep",
        ])
        position = self._parse_center_position_near(text, keyword="notch")

        if length is None and width is None and depth is None:
            return []

        return [{
            "operation": "create_edge_notch",
            "target": "base_plate",
            "length": length,
            "width": width,
            "depth": depth,
            "position": position,
            "edge": edge,
            "source": "prompt",
        }]

    def _parse_single_holes_from_prompt(self, text, base):
        if "hole pattern" in text or "pattern of circular through-holes" in text:
            return []
        if any(word in text for word in ["counterbore", "countersink", "threaded hole"]):
            return []
        if "hole" not in text:
            return []

        diameter = self._first_regex_number(text, [
            r"hole.*?diameter\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"diameter\s+(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"ø\s*(?P<value>\d+(?:\.\d+)?)",
        ])
        depth = self._first_regex_number(text, [
            r"hole.*?(?:depth|deep)\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"hole.*?(?P<value>\d+(?:\.\d+)?)\s*mm\s+deep",
        ])
        position = self._parse_center_position_near(text, keyword="hole")

        if diameter is None:
            return []

        return [{
            "operation": "create_hole",
            "target": "base_plate",
            "diameter": diameter,
            "depth": depth if depth is not None else self._base_height(base),
            "position": position,
            "source": "prompt",
        }]

    def _parse_linear_patterns_from_prompt(self, text, base):
        if "linear pattern" not in text and "linear array" not in text:
            return []

        count = self._first_regex_int(text, [
            r"(?:linear\s+pattern|linear\s+array).*?(?P<value>\d+)\s+(?:instances|copies|times|features)",
            r"count\s*(?:=|is)?\s*(?P<value>\d+)",
        ])

        spacing = None
        spacing_value = self._first_regex_number(text, [
            r"spacing\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])
        if spacing_value is not None:
            if "along y" in text or "direction y" in text:
                spacing = [0, spacing_value, 0]
            elif "along z" in text or "direction z" in text:
                spacing = [0, 0, spacing_value]
            else:
                spacing = [spacing_value, 0, 0]

        return [{
            "operation": "create_linear_pattern",
            "count": count,
            "spacing": spacing,
            "feature": None,
            "source": "prompt",
            "note": "Prompt mentioned a linear pattern. Nested feature may need Mistral reasoning if not provided by Excel.",
        }]

    def _parse_circular_patterns_from_prompt(self, text, base):
        if not any(word in text for word in ["circular pattern", "radial pattern", "radial array", "around a circle"]):
            return []

        count = self._first_regex_int(text, [
            r"(?:circular\s+pattern|radial\s+pattern|radial\s+array).*?(?P<value>\d+)\s+(?:instances|copies|holes|features)",
            r"count\s*(?:=|is)?\s*(?P<value>\d+)",
        ])
        center = self._parse_center_position_near(text, keyword="center")
        total_angle = self._first_regex_number(text, [
            r"total\s+angle\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)",
            r"over\s+(?P<value>\d+(?:\.\d+)?)\s*degrees",
        ])

        return [{
            "operation": "create_circular_pattern",
            "count": count,
            "center": center,
            "axis": "Z",
            "total_angle": total_angle if total_angle is not None else 360,
            "feature": None,
            "source": "prompt",
            "note": "Prompt mentioned a circular/radial pattern. Nested feature may need Mistral reasoning if not provided by Excel.",
        }]

    def _parse_mirror_features_from_prompt(self, text, base):
        if "mirror" not in text and "mirrored" not in text:
            return []

        mirror_plane = "YZ"
        for plane in ("YZ", "XZ", "XY", "X", "Y", "Z"):
            if plane.lower() in text:
                mirror_plane = plane
                break

        plane_origin = self._parse_plane_origin(text) or [0, 0, 0]

        return [{
            "operation": "mirror_feature",
            "mirror_plane": mirror_plane,
            "plane_origin": plane_origin,
            "include_original": True,
            "feature": None,
            "source": "prompt",
            "note": "Prompt mentioned a mirror feature. Nested feature may need Mistral reasoning if not provided by Excel.",
        }]

    def _parse_fillets_from_prompt(self, text):
        if "fillet" not in text and "round edges" not in text:
            return []

        radius = self._first_regex_number(text, [
            r"fillet\s+radius\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"radius\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"\br\s*(?P<value>\d+(?:\.\d+)?)",
        ])

        if radius is None:
            return []

        return [{
            "operation": "create_fillet",
            "target": "base_plate",
            "radius": radius,
            "scope": self._parse_scope(text, default="base_outer_vertical_edges"),
            "source": "prompt",
        }]

    def _parse_chamfers_from_prompt(self, text):
        if "chamfer" not in text and "bevel" not in text:
            return []

        distance = self._first_regex_number(text, [
            r"chamfer\s+distance\s*(?:=|is)?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"chamfer.*?(?P<value>\d+(?:\.\d+)?)\s*mm",
            r"bevel.*?(?P<value>\d+(?:\.\d+)?)\s*mm",
        ])

        if distance is None:
            return []

        return [{
            "operation": "create_chamfer",
            "target": "base_plate",
            "distance": distance,
            "scope": self._parse_scope(text, default="base_top_outer_edges"),
            "source": "prompt",
        }]

    # ------------------------------------------------------------------
    # OCR fallback
    # ------------------------------------------------------------------

    def _base_from_ocr_dimensions(self, dimensions):
        for item in dimensions:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type") or item.get("kind")
            values = item.get("values", [])

            if item_type == "compound" and isinstance(values, list) and len(values) >= 3:
                return {
                    "operation": "create_box",
                    "name": "base_plate",
                    "length": self._to_number(values[0]),
                    "width": self._to_number(values[1]),
                    "height": self._to_number(values[2]),
                    "position": [0, 0, 0],
                    "source": "ocr",
                }

        return None

    def _features_from_ocr_dimensions(self, dimensions):
        features = []

        for item in dimensions:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type") or item.get("kind")
            value = self._to_number(item.get("value"))

            if item_type == "diameter" and isinstance(value, (int, float)):
                features.append({
                    "operation": "create_hole",
                    "target": "base_plate",
                    "diameter": value,
                    "depth": None,
                    "position": None,
                    "source": "ocr",
                    "note": "OCR detected a diameter, but position needs prompt, Excel, or geometry evidence.",
                })

        return features

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_base_object(self, base, source):
        if not isinstance(base, dict):
            return {}

        operation = self._normalize_operation(
            base.get("operation")
            or base.get("type")
            or base.get("shape")
            or base.get("kind")
            or "create_box"
        )

        if operation not in {"create_box", "create_rounded_rectangle_plate", "create_cylinder"}:
            operation = "create_box"

        height = (
            base.get("height")
            if base.get("height") is not None
            else base.get("thickness")
            if base.get("thickness") is not None
            else base.get("depth")
        )

        position = self._normalize_position(
            base.get("position")
            or base.get("origin")
            or base.get("center"),
            default=[0, 0, 0],
        )

        normalized = {
            "operation": operation,
            "name": base.get("name", "base_plate"),
            "length": self._number_or_none(base.get("length")),
            "width": self._number_or_none(base.get("width")),
            "height": self._number_or_none(height),
            "position": position,
            "source": base.get("source", source),
        }

        if operation == "create_rounded_rectangle_plate":
            normalized["corner_radius"] = self._number_or_none(
                base.get("corner_radius") or base.get("radius") or base.get("fillet_radius")
            )

        if operation == "create_cylinder":
            normalized["radius"] = self._number_or_none(base.get("radius"))
            normalized["diameter"] = self._number_or_none(base.get("diameter"))

        return self._drop_none_values(normalized, keep_none_for=set())

    def _normalize_feature(self, feature, source):
        if not isinstance(feature, dict):
            return {}

        normalized = copy.deepcopy(feature)

        operation = self._normalize_operation(
            normalized.get("operation")
            or normalized.get("type")
            or normalized.get("shape")
            or normalized.get("kind")
            or normalized.get("action")
        )

        normalized["operation"] = operation
        normalized.pop("type", None)
        normalized.pop("shape", None)
        normalized.pop("kind", None)
        normalized.pop("action", None)

        if operation in FEATURE_OPERATIONS and operation not in {"create_fillet", "create_chamfer"}:
            normalized.setdefault("target", "base_plate")
        elif operation in {"create_fillet", "create_chamfer"}:
            normalized.setdefault("target", "base_plate")

        normalized["source"] = normalized.get("source", source)

        self._normalize_common_numeric_fields(normalized)

        if "position" not in normalized:
            position_source = normalized.get("center") or normalized.get("origin") or normalized.get("location")
            if position_source is not None:
                normalized["position"] = position_source

        if "position" in normalized and normalized.get("position") is not None:
            normalized["position"] = self._normalize_position(normalized.get("position"))

        if "first_position" in normalized and normalized.get("first_position") is not None:
            normalized["first_position"] = self._normalize_position(normalized.get("first_position"))

        if "pattern_center" in normalized:
            center = self._normalize_position(normalized.get("pattern_center"))
            if center is not None:
                normalized["center"] = center
            normalized.pop("pattern_center", None)

        if operation == "create_circular_pattern":
            if "center" in normalized and normalized.get("center") is not None:
                normalized["center"] = self._normalize_position(normalized.get("center"))
            normalized["axis"] = str(normalized.get("axis", normalized.get("rotation_axis", "Z"))).upper()
            normalized.pop("rotation_axis", None)
            normalized.setdefault("total_angle", 360)

        if operation == "create_linear_pattern":
            normalized = self._normalize_linear_pattern_fields(normalized)

        if operation == "mirror_feature":
            normalized = self._normalize_mirror_fields(normalized)

        if operation in {"create_fillet", "create_chamfer"}:
            normalized["scope"] = self._normalize_scope(
                normalized.get("scope"),
                default=(
                    "base_outer_vertical_edges"
                    if operation == "create_fillet"
                    else "base_top_outer_edges"
                ),
            )

        if operation in DIAMETER_OPERATIONS:
            radius = normalized.get("radius")
            diameter = normalized.get("diameter")
            if diameter is None and isinstance(radius, (int, float)):
                normalized["diameter"] = radius * 2

        if operation in BOSS_OPERATIONS:
            if normalized.get("height") is None and normalized.get("depth") is not None:
                normalized["height"] = normalized.get("depth")
            normalized.pop("depth", None)

        if operation in DEPTH_OPERATIONS:
            if normalized.get("depth") is None and normalized.get("height") is not None:
                normalized["depth"] = normalized.get("height")

        if operation == "create_counterbore_hole":
            if normalized.get("hole_diameter") is None and normalized.get("diameter") is not None:
                normalized["hole_diameter"] = normalized.get("diameter")
            if normalized.get("counterbore_diameter") is None and normalized.get("head_diameter") is not None:
                normalized["counterbore_diameter"] = normalized.get("head_diameter")
            if normalized.get("counterbore_depth") is None and normalized.get("head_depth") is not None:
                normalized["counterbore_depth"] = normalized.get("head_depth")

        if operation == "create_countersink_hole":
            if normalized.get("hole_diameter") is None and normalized.get("diameter") is not None:
                normalized["hole_diameter"] = normalized.get("diameter")
            if normalized.get("countersink_diameter") is None and normalized.get("head_diameter") is not None:
                normalized["countersink_diameter"] = normalized.get("head_diameter")
            normalized.setdefault("countersink_angle", 90)

        if isinstance(normalized.get("feature"), dict):
            normalized["feature"] = self._normalize_feature(normalized["feature"], source=source)

        return self._drop_none_values(
            normalized,
            keep_none_for={
                "position",
                "feature",
                "length",
                "width",
                "height",
                "depth",
                "diameter",
                "radius",
                "rows",
                "columns",
                "spacing_x",
                "spacing_y",
                "spacing",
                "first_position",
                "center",
                "hole_diameter",
                "counterbore_diameter",
                "counterbore_depth",
                "countersink_diameter",
            },
        )

    def _normalize_linear_pattern_fields(self, normalized):
        if "spacing" in normalized and normalized.get("spacing") is not None:
            parsed = self._normalize_position(normalized.get("spacing"))
            if parsed is not None:
                normalized["spacing"] = parsed

        if "spacing" not in normalized or normalized.get("spacing") is None:
            sx = self._number_or_none(normalized.get("spacing_x"))
            sy = self._number_or_none(normalized.get("spacing_y"))
            sz = self._number_or_none(normalized.get("spacing_z"))
            if sx is not None or sy is not None or sz is not None:
                normalized["spacing"] = [
                    sx if sx is not None else 0,
                    sy if sy is not None else 0,
                    sz if sz is not None else 0,
                ]

        for key in ("spacing_x", "spacing_y", "spacing_z"):
            normalized.pop(key, None)

        return normalized

    def _normalize_mirror_fields(self, normalized):
        if "mirror_plane" not in normalized:
            normalized["mirror_plane"] = normalized.get("plane") or normalized.get("symmetry_plane")

        if "plane_origin" not in normalized:
            normalized["plane_origin"] = (
                normalized.get("plane_position")
                or normalized.get("mirror_origin")
                or normalized.get("origin")
                or [0, 0, 0]
            )

        normalized["plane_origin"] = self._normalize_position(
            normalized.get("plane_origin"),
            default=[0, 0, 0],
        )

        normalized["include_original"] = normalized.get("include_original", True)

        for key in ("plane", "plane_position", "mirror_origin", "symmetry_plane"):
            normalized.pop(key, None)

        return normalized

    def _normalize_operation(self, value):
        if value is None:
            return "unknown_operation"

        key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        return OPERATION_ALIASES.get(key, key)

    def _normalize_scope(self, value, default=None):
        if value is None:
            return default

        key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        return SCOPE_ALIASES.get(key, key)

    def _normalize_common_numeric_fields(self, data):
        numeric_fields = [
            "length", "width", "height", "depth", "diameter", "radius",
            "corner_radius", "distance", "rows", "columns", "count",
            "spacing_x", "spacing_y", "spacing_z", "total_angle", "angle_step",
            "hole_diameter", "counterbore_diameter", "counterbore_depth",
            "countersink_diameter", "countersink_depth", "countersink_angle",
            "head_diameter", "head_depth",
        ]

        for field in numeric_fields:
            if field in data:
                data[field] = self._number_or_none(data.get(field))

    def _base_from_constraints(self, constraints):
        if not isinstance(constraints, dict):
            return None

        length = self._first_constraint_number(
            constraints,
            ["length", "length_mm", "plate_length", "plate_length_mm", "base_length"],
        )
        width = self._first_constraint_number(
            constraints,
            ["width", "width_mm", "plate_width", "plate_width_mm", "base_width"],
        )
        height = self._first_constraint_number(
            constraints,
            ["height", "height_mm", "thickness", "thickness_mm", "plate_thickness", "plate_thickness_mm"],
        )

        if length is None or width is None or height is None:
            return None

        return {
            "operation": "create_box",
            "name": "base_plate",
            "length": length,
            "width": width,
            "height": height,
            "position": [0, 0, 0],
            "source": "excel_constraints",
        }

    # ------------------------------------------------------------------
    # Derived values and CAD hint
    # ------------------------------------------------------------------

    def _derive_depths_from_base(self, canonical):
        base_height = self._base_height(
            canonical["geometry"]["base_objects"][0]
            if canonical["geometry"]["base_objects"]
            else None
        )

        if not isinstance(base_height, (int, float)):
            return

        def apply(feature):
            if not isinstance(feature, dict):
                return

            operation = feature.get("operation")

            if operation in DEPTH_OPERATIONS and feature.get("depth") is None:
                feature["depth"] = base_height
                feature["depth_source"] = "derived_from_base_height"

            if operation in {"create_linear_pattern", "create_circular_pattern", "mirror_feature"}:
                if isinstance(feature.get("feature"), dict):
                    apply(feature["feature"])

        for feature in canonical["geometry"]["features"]:
            apply(feature)

    def _sync_legacy_base_shape(self, canonical):
        base_objects = canonical["geometry"]["base_objects"]

        if not base_objects:
            canonical["geometry"]["base_shape"] = {"operation": "create_box"}
            return

        base = base_objects[0]

        canonical["geometry"]["base_shape"] = {
            "operation": base.get("operation", "create_box"),
            "shape": "rectangle",
            "width_mm": base.get("width"),
            "height_mm": base.get("length"),
            "depth_mm": base.get("height"),
            "source": base.get("source"),
        }

    def _build_cad_plan_hint(self, canonical):
        steps = []

        for base in canonical["geometry"]["base_objects"]:
            if not isinstance(base, dict):
                continue

            step = {
                "operation": base.get("operation", "create_box"),
                "name": base.get("name", "base_plate"),
                "length": base.get("length"),
                "width": base.get("width"),
                "height": base.get("height"),
                "position": base.get("position", [0, 0, 0]),
            }

            if base.get("operation") == "create_rounded_rectangle_plate":
                step["corner_radius"] = base.get("corner_radius")

            if base.get("operation") == "create_cylinder":
                if base.get("radius") is not None:
                    step["radius"] = base.get("radius")
                if base.get("diameter") is not None:
                    step["diameter"] = base.get("diameter")

            if base.get("source") is not None:
                step["source"] = base.get("source")

            steps.append(self._drop_none_values(step, keep_none_for=set()))

        for feature in canonical["geometry"]["features"]:
            step = self._feature_to_hint_step(feature)
            if step:
                steps.append(step)

        canonical["cad_plan_hint"] = {
            "units": canonical.get("units", "mm"),
            "steps": steps,
        }

    def _feature_to_hint_step(self, feature):
        if not isinstance(feature, dict):
            return None

        operation = feature.get("operation")
        if operation not in SUPPORTED_OPERATIONS:
            return None

        allowed_keys = {
            "operation",
            "name",
            "target",
            "position",
            "first_position",
            "center",
            "length",
            "width",
            "height",
            "depth",
            "diameter",
            "radius",
            "thread",
            "hole_diameter",
            "counterbore_diameter",
            "counterbore_depth",
            "countersink_diameter",
            "countersink_depth",
            "countersink_angle",
            "rows",
            "columns",
            "spacing_x",
            "spacing_y",
            "spacing",
            "count",
            "axis",
            "total_angle",
            "angle_step",
            "orientation",
            "edge",
            "side",
            "distance",
            "scope",
            "mirror_plane",
            "plane_origin",
            "include_original",
            "feature",
            "source",
            "note",
        }

        step = {}
        for key in allowed_keys:
            if key not in feature:
                continue

            value = feature.get(key)
            if key == "feature" and isinstance(value, dict):
                step[key] = self._feature_to_hint_step(value) or self._normalize_feature(value, source=value.get("source", "unknown"))
            else:
                step[key] = value

        step["operation"] = operation

        return self._drop_none_values(
            step,
            keep_none_for={
                "position",
                "first_position",
                "center",
                "feature",
                "spacing",
            },
        )

    # ------------------------------------------------------------------
    # Geometry calibration
    # ------------------------------------------------------------------

    def _add_geometry_calibration(self, canonical, geometry_result):
        if not isinstance(geometry_result, dict):
            canonical["calibration"] = {
                "status": "skipped",
                "reason": "No valid geometry result provided.",
            }
            return

        if geometry_result.get("status") != "success":
            canonical["calibration"] = {
                "status": "skipped",
                "reason": f"Geometry extractor status is {geometry_result.get('status')}.",
            }
            return

        base = self._get_primary_base_for_calibration(canonical)
        if not base:
            canonical["calibration"] = {
                "status": "failed",
                "reason": "No base object with length and width was available for calibration.",
            }
            return

        base_length_mm = self._calib_number(base.get("length"))
        base_width_mm = self._calib_number(base.get("width"))

        if base_length_mm is None or base_width_mm is None:
            canonical["calibration"] = {
                "status": "failed",
                "reason": "Base object does not contain valid length and width in mm.",
            }
            return

        outer_rectangle = self._get_outer_rectangle_from_geometry(geometry_result)
        if not outer_rectangle:
            canonical["calibration"] = {
                "status": "failed",
                "reason": "No outer rectangle was detected in the geometry result.",
            }
            return

        outer_bbox = outer_rectangle.get("bounding_box_px", {}) or {}
        outer_x = self._calib_number(outer_bbox.get("x"))
        outer_y = self._calib_number(outer_bbox.get("y"))
        outer_width_px = self._calib_number(outer_bbox.get("width"))
        outer_height_px = self._calib_number(outer_bbox.get("height"))

        if (
            outer_x is None
            or outer_y is None
            or outer_width_px is None
            or outer_height_px is None
            or outer_width_px <= 0
            or outer_height_px <= 0
        ):
            canonical["calibration"] = {
                "status": "failed",
                "reason": "Outer rectangle has invalid pixel dimensions.",
            }
            return

        scale_x = base_length_mm / outer_width_px
        scale_y = base_width_mm / outer_height_px
        average_scale = (scale_x + scale_y) / 2

        scale_difference = abs(scale_x - scale_y)
        non_uniformity_percent = (
            scale_difference / average_scale * 100
            if average_scale > 0
            else None
        )

        calibrated_shapes = []
        for shape in geometry_result.get("detected_shapes", []) or []:
            calibrated_shape = self._calibrate_shape_to_mm(
                shape=shape,
                outer_x=outer_x,
                outer_y=outer_y,
                base_width_mm=base_width_mm,
                scale_x=scale_x,
                scale_y=scale_y,
                average_scale=average_scale,
            )
            if calibrated_shape:
                calibrated_shapes.append(calibrated_shape)

        calibrated_patterns = self._calibrate_hole_patterns_to_mm(
            geometry_result=geometry_result,
            outer_x=outer_x,
            outer_y=outer_y,
            base_width_mm=base_width_mm,
            scale_x=scale_x,
            scale_y=scale_y,
            average_scale=average_scale,
        )

        canonical["calibration"] = {
            "status": "success",
            "method": "outer_rectangle_to_known_base_dimensions",
            "units": "mm",
            "base_reference": {
                "length_mm": base_length_mm,
                "width_mm": base_width_mm,
                "source": base.get("source", "unknown"),
            },
            "outer_rectangle_px": {
                "x": outer_x,
                "y": outer_y,
                "width": outer_width_px,
                "height": outer_height_px,
            },
            "scale": {
                "x_mm_per_px": round(scale_x, 6),
                "y_mm_per_px": round(scale_y, 6),
                "average_mm_per_px": round(average_scale, 6),
                "non_uniformity_percent": (
                    round(non_uniformity_percent, 3)
                    if non_uniformity_percent is not None
                    else None
                ),
            },
            "coordinate_system": {
                "image_origin": "top_left",
                "cad_origin_assumption": "bottom_left_of_base_plate",
                "note": "Image Y coordinates are flipped into CAD-style Y coordinates.",
            },
            "calibrated_shapes_mm": calibrated_shapes,
            "calibrated_hole_patterns_mm": calibrated_patterns,
        }

        if non_uniformity_percent is not None and non_uniformity_percent > 5:
            canonical["warnings"].append(
                "Geometry calibration scale_x and scale_y differ by more than 5%. "
                "The image may be distorted, cropped, or not perfectly aligned."
            )

    def _get_primary_base_for_calibration(self, canonical):
        base_objects = canonical.get("geometry", {}).get("base_objects", []) or []
        for base in base_objects:
            if (
                isinstance(base, dict)
                and self._calib_number(base.get("length")) is not None
                and self._calib_number(base.get("width")) is not None
            ):
                return base
        return None

    def _get_outer_rectangle_from_geometry(self, geometry_result):
        for shape in geometry_result.get("detected_shapes", []) or []:
            if not isinstance(shape, dict):
                continue
            if shape.get("type") == "outer_rectangle" or shape.get("role") == "outer_rectangle":
                return shape
        return None

    def _calibrate_shape_to_mm(self, shape, outer_x, outer_y, base_width_mm, scale_x, scale_y, average_scale):
        if not isinstance(shape, dict):
            return None

        shape_type = shape.get("type") or shape.get("shape")

        if shape_type == "outer_rectangle":
            return None

        center_px = shape.get("center_px")
        if not isinstance(center_px, list) or len(center_px) != 2:
            return None

        center_x_px = self._calib_number(center_px[0])
        center_y_px = self._calib_number(center_px[1])

        if center_x_px is None or center_y_px is None:
            return None

        relative_x_px = center_x_px - outer_x
        relative_y_px_from_top = center_y_px - outer_y

        x_mm = relative_x_px * scale_x
        y_mm = base_width_mm - (relative_y_px_from_top * scale_y)

        bbox = shape.get("bounding_box_px", {}) or {}
        bbox_width_px = self._calib_number(bbox.get("width"))
        bbox_height_px = self._calib_number(bbox.get("height"))

        calibrated = {
            "type": shape_type,
            "source": shape.get("source"),
            "confidence": shape.get("confidence"),
            "center_px": center_px,
            "center_mm": [round(x_mm, 3), round(y_mm, 3), 0],
        }

        if bbox_width_px is not None:
            calibrated["width_mm_estimate"] = round(bbox_width_px * scale_x, 3)

        if bbox_height_px is not None:
            calibrated["height_mm_estimate"] = round(bbox_height_px * scale_y, 3)

        if shape_type == "circle":
            radius_px = self._calib_number(shape.get("radius_px"))
            diameter_px = self._calib_number(shape.get("diameter_px"))

            if radius_px is not None:
                calibrated["radius_mm_estimate"] = round(radius_px * average_scale, 3)

            if diameter_px is not None:
                calibrated["diameter_mm_estimate"] = round(diameter_px * average_scale, 3)

        if shape_type == "rectangle":
            if bbox_width_px is not None:
                calibrated["length_mm_estimate"] = round(bbox_width_px * scale_x, 3)
            if bbox_height_px is not None:
                calibrated["width_mm_estimate"] = round(bbox_height_px * scale_y, 3)

        if shape_type == "slot":
            calibrated["orientation"] = shape.get("orientation", "x")

            if bbox_width_px is not None and bbox_height_px is not None:
                if calibrated["orientation"] == "y":
                    calibrated["length_mm_estimate"] = round(bbox_height_px * scale_y, 3)
                    calibrated["width_mm_estimate"] = round(bbox_width_px * scale_x, 3)
                else:
                    calibrated["length_mm_estimate"] = round(bbox_width_px * scale_x, 3)
                    calibrated["width_mm_estimate"] = round(bbox_height_px * scale_y, 3)

        return calibrated

    def _calibrate_hole_patterns_to_mm(self, geometry_result, outer_x, outer_y, base_width_mm, scale_x, scale_y, average_scale):
        detected_geometry = geometry_result.get("detected_geometry", {}) or {}
        patterns = detected_geometry.get("hole_patterns", []) or []

        calibrated_patterns = []

        for pattern in patterns:
            if not isinstance(pattern, dict):
                continue

            first_position_px = pattern.get("first_position_px")
            first_position_mm = None

            if isinstance(first_position_px, list) and len(first_position_px) == 2:
                first_x_px = self._calib_number(first_position_px[0])
                first_y_px = self._calib_number(first_position_px[1])

                if first_x_px is not None and first_y_px is not None:
                    relative_x_px = first_x_px - outer_x
                    relative_y_px_from_top = first_y_px - outer_y

                    first_position_mm = [
                        round(relative_x_px * scale_x, 3),
                        round(base_width_mm - relative_y_px_from_top * scale_y, 3),
                        0,
                    ]

            spacing_x_px = self._calib_number(pattern.get("spacing_x_px"))
            spacing_y_px = self._calib_number(pattern.get("spacing_y_px"))
            average_diameter_px = self._calib_number(pattern.get("average_diameter_px"))

            calibrated = {
                "type": pattern.get("type", "circle_pattern"),
                "rows": pattern.get("rows"),
                "columns": pattern.get("columns"),
                "actual_circle_count": pattern.get("actual_circle_count"),
                "expected_grid_count": pattern.get("expected_grid_count"),
                "confidence": pattern.get("confidence"),
                "first_position_mm": first_position_mm,
            }

            if spacing_x_px is not None:
                calibrated["spacing_x_mm_estimate"] = round(spacing_x_px * scale_x, 3)

            if spacing_y_px is not None:
                calibrated["spacing_y_mm_estimate"] = round(spacing_y_px * scale_y, 3)

            if average_diameter_px is not None:
                calibrated["average_diameter_mm_estimate"] = round(average_diameter_px * average_scale, 3)

            calibrated_patterns.append(calibrated)

        return calibrated_patterns

    # ------------------------------------------------------------------
    # Geometry checks
    # ------------------------------------------------------------------

    def _compare_expected_vs_detected_geometry(self, canonical):
        calibration = canonical.get("calibration", {})

        if calibration.get("status") != "success":
            canonical["geometry_checks"].append({
                "status": "skipped",
                "severity": "info",
                "reason": "Calibration was not successful.",
            })
            return

        features = canonical.get("geometry", {}).get("features", []) or []
        calibrated_shapes = calibration.get("calibrated_shapes_mm", []) or []
        calibrated_patterns = calibration.get("calibrated_hole_patterns_mm", []) or []

        expected = self._expand_expected_geometry_features(features)

        detected = {
            "holes": [shape for shape in calibrated_shapes if shape.get("type") == "circle"],
            "rectangular_cutouts": [shape for shape in calibrated_shapes if shape.get("type") == "rectangle"],
            "slots": [shape for shape in calibrated_shapes if shape.get("type") == "slot"],
            "hole_patterns": calibrated_patterns,
        }

        issues = []
        matches = []

        self._compare_geometry_counts(expected, detected, issues)
        self._compare_holes(expected["holes"], detected["holes"], matches, issues)
        self._compare_rectangular_cutouts(expected["rectangular_cutouts"], detected["rectangular_cutouts"], matches, issues)
        self._compare_slots(expected["slots"], detected["slots"], matches, issues)
        self._compare_hole_patterns(expected["hole_patterns"], detected["hole_patterns"], matches, issues)

        decision = self._geometry_confidence_decision(issues)

        canonical["geometry_checks"].append({
            "status": decision["status"],
            "severity": decision["severity"],
            "message": decision["message"],
            "expected_from_structured_input": {
                "holes": len(expected["holes"]),
                "rectangular_cutouts": len(expected["rectangular_cutouts"]),
                "slots": len(expected["slots"]),
                "hole_patterns": len(expected["hole_patterns"]),
            },
            "detected_from_geometry": {
                "holes": len(detected["holes"]),
                "rectangular_cutouts": len(detected["rectangular_cutouts"]),
                "slots": len(detected["slots"]),
                "hole_patterns": len(detected["hole_patterns"]),
            },
            "matches": matches,
            "issues": issues,
            "tolerances": {
                "position_pass_mm": 3.0,
                "position_warning_mm": 8.0,
                "diameter_pass_mm": 1.5,
                "diameter_warning_mm": 4.0,
                "linear_pass_mm": 3.0,
                "linear_warning_mm": 8.0,
                "pattern_spacing_pass_mm": 3.0,
                "pattern_spacing_warning_mm": 8.0,
            },
        })

        if decision["status"] in {"warning", "failed"}:
            canonical["warnings"].append(decision["message"])

        if decision["status"] == "failed":
            canonical["conflicts"].append({
                "type": "geometry_consistency_failed",
                "message": decision["message"],
                "issues": issues,
            })

    def _expand_expected_geometry_features(self, features):
        result = {
            "holes": [],
            "rectangular_cutouts": [],
            "slots": [],
            "hole_patterns": [],
        }

        for feature_index, feature in enumerate(features):
            if not isinstance(feature, dict):
                continue

            operation = feature.get("operation")

            if operation == "create_hole":
                result["holes"].append({
                    "feature_index": feature_index,
                    "type": "hole",
                    "position": feature.get("position"),
                    "diameter": self._calib_number(feature.get("diameter")),
                    "source": feature.get("source"),
                })

            elif operation == "create_hole_pattern":
                pattern = {
                    "feature_index": feature_index,
                    "type": "hole_pattern",
                    "rows": self._calib_int(feature.get("rows")),
                    "columns": self._calib_int(feature.get("columns")),
                    "diameter": self._calib_number(feature.get("diameter")),
                    "first_position": feature.get("first_position"),
                    "spacing_x": self._calib_number(feature.get("spacing_x")),
                    "spacing_y": self._calib_number(feature.get("spacing_y")),
                    "source": feature.get("source"),
                }
                result["hole_patterns"].append(pattern)
                result["holes"].extend(self._expand_hole_pattern_for_check(pattern))

            elif operation in {"create_rectangular_cutout", "create_rectangular_pocket"}:
                result["rectangular_cutouts"].append({
                    "feature_index": feature_index,
                    "type": operation,
                    "position": feature.get("position"),
                    "length": self._calib_number(feature.get("length")),
                    "width": self._calib_number(feature.get("width")),
                    "source": feature.get("source"),
                })

            elif operation == "create_slot":
                result["slots"].append({
                    "feature_index": feature_index,
                    "type": "slot",
                    "position": feature.get("position"),
                    "length": self._calib_number(feature.get("length")),
                    "width": self._calib_number(feature.get("width")),
                    "orientation": feature.get("orientation", "x"),
                    "source": feature.get("source"),
                })

            elif operation in {"create_counterbore_hole", "create_countersink_hole"}:
                result["holes"].append({
                    "feature_index": feature_index,
                    "type": operation,
                    "position": feature.get("position"),
                    "diameter": self._calib_number(feature.get("hole_diameter")),
                    "source": feature.get("source"),
                })

        return result

    def _expand_hole_pattern_for_check(self, pattern):
        rows = pattern.get("rows")
        columns = pattern.get("columns")
        first_position = pattern.get("first_position")
        spacing_x = pattern.get("spacing_x")
        spacing_y = pattern.get("spacing_y")
        diameter = pattern.get("diameter")

        if not (
            isinstance(rows, int)
            and isinstance(columns, int)
            and isinstance(first_position, list)
            and len(first_position) == 3
            and isinstance(spacing_x, (int, float))
            and isinstance(spacing_y, (int, float))
        ):
            return []

        first_x, first_y, first_z = first_position
        holes = []

        for row in range(rows):
            for column in range(columns):
                holes.append({
                    "feature_index": pattern.get("feature_index"),
                    "type": "hole_from_pattern",
                    "pattern_index": pattern.get("feature_index"),
                    "row": row,
                    "column": column,
                    "position": [
                        first_x + column * spacing_x,
                        first_y + row * spacing_y,
                        first_z,
                    ],
                    "diameter": diameter,
                    "source": pattern.get("source"),
                })

        return holes

    def _compare_geometry_counts(self, expected, detected, issues):
        expected_counts = {
            "holes": len(expected["holes"]),
            "rectangular_cutouts": len(expected["rectangular_cutouts"]),
            "slots": len(expected["slots"]),
            "hole_patterns": len(expected["hole_patterns"]),
        }
        detected_counts = {
            "holes": len(detected["holes"]),
            "rectangular_cutouts": len(detected["rectangular_cutouts"]),
            "slots": len(detected["slots"]),
            "hole_patterns": len(detected["hole_patterns"]),
        }

        for key in expected_counts:
            if expected_counts[key] != detected_counts[key]:
                issues.append({
                    "type": "count_mismatch",
                    "severity": "warning",
                    "feature": key,
                    "expected": expected_counts[key],
                    "detected": detected_counts[key],
                })

    def _compare_holes(self, expected_holes, detected_holes, matches, issues):
        used_detected = set()

        for expected_index, expected in enumerate(expected_holes):
            nearest = self._find_nearest_detected_shape(expected, detected_holes, used_detected)

            if nearest is None:
                issues.append({
                    "type": "missing_detected_hole",
                    "severity": "warning",
                    "expected_index": expected_index,
                    "expected": expected,
                })
                continue

            detected_index, detected, distance = nearest
            used_detected.add(detected_index)

            expected_diameter = self._calib_number(expected.get("diameter"))
            detected_diameter = self._calib_number(detected.get("diameter_mm_estimate"))
            diameter_delta = None

            if expected_diameter is not None and detected_diameter is not None:
                diameter_delta = abs(expected_diameter - detected_diameter)
                self._append_tolerance_issue(
                    issues, "hole_diameter_mismatch", "diameter", diameter_delta,
                    1.5, 4.0, expected_diameter, detected_diameter, expected, detected
                )

            if distance is not None:
                self._append_tolerance_issue(
                    issues, "hole_position_mismatch", "position", distance,
                    3.0, 8.0, expected.get("position"), detected.get("center_mm"), expected, detected
                )

            matches.append({
                "type": "hole_match",
                "expected": expected,
                "detected": detected,
                "position_distance_mm": round(distance, 3) if distance is not None else None,
                "diameter_delta_mm": round(diameter_delta, 3) if diameter_delta is not None else None,
            })

    def _compare_rectangular_cutouts(self, expected_cutouts, detected_cutouts, matches, issues):
        used_detected = set()

        for expected_index, expected in enumerate(expected_cutouts):
            nearest = self._find_nearest_detected_shape(expected, detected_cutouts, used_detected)

            if nearest is None:
                issues.append({
                    "type": "missing_detected_rectangular_feature",
                    "severity": "warning",
                    "expected_index": expected_index,
                    "expected": expected,
                })
                continue

            detected_index, detected, distance = nearest
            used_detected.add(detected_index)

            self._compare_linear_value(
                issues,
                "rectangular_feature_length_mismatch",
                expected.get("length"),
                detected.get("length_mm_estimate"),
                expected,
                detected,
            )
            self._compare_linear_value(
                issues,
                "rectangular_feature_width_mismatch",
                expected.get("width"),
                detected.get("width_mm_estimate"),
                expected,
                detected,
            )

            if distance is not None:
                self._append_tolerance_issue(
                    issues, "rectangular_feature_position_mismatch", "position", distance,
                    3.0, 8.0, expected.get("position"), detected.get("center_mm"), expected, detected
                )

            matches.append({
                "type": "rectangular_feature_match",
                "expected": expected,
                "detected": detected,
                "position_distance_mm": round(distance, 3) if distance is not None else None,
            })

    def _compare_slots(self, expected_slots, detected_slots, matches, issues):
        used_detected = set()

        for expected_index, expected in enumerate(expected_slots):
            nearest = self._find_nearest_detected_shape(expected, detected_slots, used_detected)

            if nearest is None:
                issues.append({
                    "type": "missing_detected_slot",
                    "severity": "warning",
                    "expected_index": expected_index,
                    "expected": expected,
                })
                continue

            detected_index, detected, distance = nearest
            used_detected.add(detected_index)

            self._compare_linear_value(issues, "slot_length_mismatch", expected.get("length"), detected.get("length_mm_estimate"), expected, detected)
            self._compare_linear_value(issues, "slot_width_mismatch", expected.get("width"), detected.get("width_mm_estimate"), expected, detected)

            if distance is not None:
                self._append_tolerance_issue(
                    issues, "slot_position_mismatch", "position", distance,
                    3.0, 8.0, expected.get("position"), detected.get("center_mm"), expected, detected
                )

            if expected.get("orientation") and detected.get("orientation") and expected.get("orientation") != detected.get("orientation"):
                issues.append({
                    "type": "slot_orientation_mismatch",
                    "severity": "warning",
                    "expected": expected.get("orientation"),
                    "detected": detected.get("orientation"),
                })

            matches.append({
                "type": "slot_match",
                "expected": expected,
                "detected": detected,
                "position_distance_mm": round(distance, 3) if distance is not None else None,
            })

    def _compare_hole_patterns(self, expected_patterns, detected_patterns, matches, issues):
        if not expected_patterns and not detected_patterns:
            return

        if expected_patterns and not detected_patterns:
            issues.append({
                "type": "missing_detected_hole_pattern",
                "severity": "warning",
                "expected_patterns": expected_patterns,
            })
            return

        for expected in expected_patterns:
            best_detected = None
            best_score = None

            for detected in detected_patterns:
                score = self._hole_pattern_match_score(expected, detected)
                if best_score is None or score < best_score:
                    best_score = score
                    best_detected = detected

            if best_detected is None:
                issues.append({
                    "type": "missing_detected_hole_pattern",
                    "severity": "warning",
                    "expected": expected,
                })
                continue

            if expected.get("rows") != best_detected.get("rows"):
                issues.append({
                    "type": "hole_pattern_rows_mismatch",
                    "severity": "warning",
                    "expected": expected.get("rows"),
                    "detected": best_detected.get("rows"),
                })

            if expected.get("columns") != best_detected.get("columns"):
                issues.append({
                    "type": "hole_pattern_columns_mismatch",
                    "severity": "warning",
                    "expected": expected.get("columns"),
                    "detected": best_detected.get("columns"),
                })

            self._compare_linear_value(issues, "hole_pattern_spacing_x_mismatch", expected.get("spacing_x"), best_detected.get("spacing_x_mm_estimate"), expected, best_detected)
            self._compare_linear_value(issues, "hole_pattern_spacing_y_mismatch", expected.get("spacing_y"), best_detected.get("spacing_y_mm_estimate"), expected, best_detected)

            expected_diameter = self._calib_number(expected.get("diameter"))
            detected_diameter = self._calib_number(best_detected.get("average_diameter_mm_estimate"))

            if expected_diameter is not None and detected_diameter is not None:
                self._append_tolerance_issue(
                    issues, "hole_pattern_diameter_mismatch", "diameter",
                    abs(expected_diameter - detected_diameter),
                    1.5, 4.0, expected_diameter, detected_diameter, expected, best_detected
                )

            matches.append({
                "type": "hole_pattern_match",
                "expected": expected,
                "detected": best_detected,
                "match_score": round(best_score, 3) if best_score is not None else None,
            })

    def _find_nearest_detected_shape(self, expected, detected_shapes, used_detected):
        expected_position = expected.get("position")

        if not self._is_valid_position(expected_position):
            return None

        best = None
        best_distance = None

        for index, detected in enumerate(detected_shapes):
            if index in used_detected:
                continue

            detected_position = detected.get("center_mm")
            if not self._is_valid_position(detected_position):
                continue

            distance = self._distance_2d_mm(expected_position, detected_position)

            if distance is None:
                continue

            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = (index, detected, distance)

        return best

    def _compare_linear_value(self, issues, issue_type, expected_value, detected_value, expected_object, detected_object):
        expected_value = self._calib_number(expected_value)
        detected_value = self._calib_number(detected_value)

        if expected_value is None or detected_value is None:
            return

        delta = abs(expected_value - detected_value)

        self._append_tolerance_issue(
            issues=issues,
            issue_type=issue_type,
            value_name="linear_dimension",
            delta=delta,
            pass_tolerance=3.0,
            warning_tolerance=8.0,
            expected=expected_value,
            detected=detected_value,
            expected_object=expected_object,
            detected_object=detected_object,
        )

    def _append_tolerance_issue(
        self,
        issues,
        issue_type,
        value_name,
        delta,
        pass_tolerance,
        warning_tolerance,
        expected,
        detected,
        expected_object,
        detected_object,
    ):
        if delta <= pass_tolerance:
            return

        severity = "warning" if delta <= warning_tolerance else "conflict"

        issues.append({
            "type": issue_type,
            "severity": severity,
            "value": value_name,
            "delta_mm": round(delta, 3),
            "expected": expected,
            "detected": detected,
            "expected_object": expected_object,
            "detected_object": detected_object,
        })

    def _hole_pattern_match_score(self, expected, detected):
        score = 0.0

        for key in ("rows", "columns"):
            if expected.get(key) != detected.get(key):
                score += 10

        comparisons = [
            ("spacing_x", "spacing_x_mm_estimate"),
            ("spacing_y", "spacing_y_mm_estimate"),
            ("diameter", "average_diameter_mm_estimate"),
        ]

        for expected_key, detected_key in comparisons:
            ev = self._calib_number(expected.get(expected_key))
            dv = self._calib_number(detected.get(detected_key))
            if ev is not None and dv is not None:
                score += abs(ev - dv)

        return score

    def _geometry_confidence_decision(self, issues):
        conflicts = [issue for issue in issues if issue.get("severity") == "conflict"]
        warnings = [issue for issue in issues if issue.get("severity") == "warning"]

        if conflicts:
            return {
                "status": "failed",
                "severity": "conflict",
                "message": "Detected geometry conflicts with the structured CAD evidence.",
            }

        if warnings:
            return {
                "status": "warning",
                "severity": "warning",
                "message": "Detected geometry mostly matches, but some differences need review.",
            }

        return {
            "status": "passed",
            "severity": "info",
            "message": "Detected geometry matches the structured CAD evidence within tolerance.",
        }

    # ------------------------------------------------------------------
    # Reasoning instruction
    # ------------------------------------------------------------------

    def _build_reasoning_instruction(self, canonical):
        geometry_checks = canonical.get("geometry_checks", []) or []
        latest_geometry_check = geometry_checks[-1] if geometry_checks else {}
        geometry_status = latest_geometry_check.get("status", "not_available")

        canonical["reasoning_instruction"] = {
            "primary_source": "excel_structured_data",
            "secondary_source": "user_prompt",
            "supporting_sources": [
                "ocr_text_and_dimensions",
                "calibrated_geometry_estimates",
            ],
            "source_priority": [
                "Excel structured values",
                "Explicit user prompt values",
                "OCR extracted dimensions",
                "Geometry pixel estimates",
            ],
            "geometry_status": geometry_status,
            "rules": [
                "Use canonical operation names only.",
                "Use cad_plan_hint['steps'] as the main CAD hint structure.",
                "Use operation, not type or action.",
                "Do not output aliases such as hole, boss, mirror, fillet, chamfer, radial_pattern.",
                "Do not convert circular/radial patterns into row/column hole patterns.",
                "Keep nested features inside create_linear_pattern, create_circular_pattern, and mirror_feature.",
                "Use Excel structured dimensions as the main source of truth when available.",
                "Use the user prompt to fill missing context or intent.",
                "Use OCR as supporting evidence for text and dimensions found on the plan.",
                "Use calibrated geometry to verify counts, positions, and approximate dimensions.",
                "Do not replace exact Excel or prompt values with geometry estimates unless exact values are missing.",
            ],
        }

        if geometry_status == "passed":
            canonical["reasoning_instruction"]["geometry_guidance"] = (
                "The uploaded drawing visually matches the structured input. Proceed with normal CAD generation."
            )
        elif geometry_status == "warning":
            canonical["reasoning_instruction"]["geometry_guidance"] = (
                "The uploaded drawing mostly matches the structured input but contains differences. "
                "Use exact structured values as source of truth and preserve geometry warnings."
            )
        elif geometry_status == "failed":
            canonical["reasoning_instruction"]["geometry_guidance"] = (
                "The uploaded drawing conflicts with the structured input. Do not infer final dimensions from geometry."
            )
        else:
            canonical["reasoning_instruction"]["geometry_guidance"] = (
                "Geometry verification was unavailable. Generate CAD from Excel, prompt, and OCR evidence."
            )

    # ------------------------------------------------------------------
    # Missing info and conflicts
    # ------------------------------------------------------------------

    def _detect_missing_information(self, canonical):
        base_objects = canonical["geometry"]["base_objects"]

        if not base_objects:
            canonical["missing_information"].append("base object dimensions: length, width, height")
        else:
            base = base_objects[0]
            for field in ["length", "width", "height"]:
                if base.get(field) is None:
                    canonical["missing_information"].append(f"base object missing {field}")

        for index, feature in enumerate(canonical["geometry"]["features"]):
            self._detect_missing_for_feature(canonical, feature, index)

    def _detect_missing_for_feature(self, canonical, feature, index, prefix="feature"):
        if not isinstance(feature, dict):
            return

        operation = feature.get("operation")

        required_by_operation = {
            "create_hole": ["diameter", "depth", "position"],
            "create_threaded_hole": ["diameter", "depth", "position"],
            "create_counterbore_hole": ["position", "hole_diameter", "depth", "counterbore_diameter", "counterbore_depth"],
            "create_countersink_hole": ["position", "hole_diameter", "depth", "countersink_diameter"],
            "create_slot": ["length", "width", "depth", "position"],
            "create_rectangular_cutout": ["length", "width", "depth", "position"],
            "create_rectangular_pocket": ["length", "width", "depth", "position"],
            "create_circular_pocket": ["diameter", "depth", "position"],
            "create_rectangular_boss": ["length", "width", "height", "position"],
            "create_cylindrical_boss": ["height", "position"],
            "create_edge_notch": ["length", "width", "depth", "position"],
            "create_hole_pattern": ["rows", "columns", "diameter", "depth", "first_position", "spacing_x", "spacing_y"],
            "create_linear_pattern": ["count", "spacing", "feature"],
            "create_circular_pattern": ["count", "center", "total_angle", "feature"],
            "mirror_feature": ["mirror_plane", "plane_origin", "feature"],
            "create_fillet": ["radius"],
            "create_chamfer": ["distance"],
        }

        required = required_by_operation.get(operation, [])

        for field in required:
            if feature.get(field) is None:
                canonical["missing_information"].append(
                    f"{prefix} {index} ({operation}) missing {field}"
                )

        if operation == "create_cylindrical_boss":
            if feature.get("diameter") is None and feature.get("radius") is None:
                canonical["missing_information"].append(
                    f"{prefix} {index} ({operation}) missing diameter or radius"
                )

        if operation in {"create_linear_pattern", "create_circular_pattern", "mirror_feature"}:
            nested = feature.get("feature")
            if isinstance(nested, dict):
                self._detect_missing_for_feature(canonical, nested, index, prefix=f"{prefix}.{operation}.feature")

    def _detect_basic_conflicts(self, canonical):
        base_objects = canonical["geometry"]["base_objects"]

        if not base_objects:
            return

        base = base_objects[0]
        base_length = base.get("length")
        base_width = base.get("width")
        base_height = base.get("height")

        for index, feature in enumerate(canonical["geometry"]["features"]):
            self._check_feature_conflict(canonical, index, feature, base_length, base_width, base_height)

    def _check_feature_conflict(self, canonical, index, feature, base_length, base_width, base_height):
        if not isinstance(feature, dict):
            return

        operation = feature.get("operation")

        if operation in {"create_hole", "create_threaded_hole", "create_circular_pocket"}:
            self._check_circular_feature_inside_base(canonical, index, feature, base_length, base_width, "diameter")

        elif operation in {"create_counterbore_hole", "create_countersink_hole"}:
            diameter_key = "counterbore_diameter" if operation == "create_counterbore_hole" else "countersink_diameter"
            self._check_circular_feature_inside_base(canonical, index, feature, base_length, base_width, diameter_key)

        elif operation in {"create_rectangular_cutout", "create_rectangular_pocket", "create_rectangular_boss", "create_slot"}:
            self._check_rectangular_feature_inside_base(canonical, index, feature, base_length, base_width)

        elif operation == "create_hole_pattern":
            self._check_hole_pattern_inside_base(canonical, index, feature, base_length, base_width)

        elif operation in {"create_linear_pattern", "create_circular_pattern", "mirror_feature"}:
            nested = feature.get("feature")
            if isinstance(nested, dict):
                # Avoid being too strict for pattern transformations here.
                self._check_feature_conflict(canonical, index, nested, base_length, base_width, base_height)

        depth = feature.get("depth")
        if (
            isinstance(depth, (int, float))
            and isinstance(base_height, (int, float))
            and depth > base_height * 1.5
        ):
            canonical["conflicts"].append({
                "type": "feature_depth_much_larger_than_base_height",
                "feature_index": index,
                "operation": operation,
                "feature_depth": depth,
                "base_height": base_height,
            })

    def _check_circular_feature_inside_base(self, canonical, index, feature, base_length, base_width, diameter_key):
        position = feature.get("position")
        diameter = feature.get(diameter_key)

        if not (
            self._is_valid_position(position)
            and isinstance(diameter, (int, float))
            and isinstance(base_length, (int, float))
            and isinstance(base_width, (int, float))
        ):
            return

        x, y, _ = position
        radius = diameter / 2

        if x - radius < 0 or x + radius > base_length or y - radius < 0 or y + radius > base_width:
            canonical["conflicts"].append({
                "type": "circular_feature_outside_base",
                "feature_index": index,
                "operation": feature.get("operation"),
                "position": position,
                "diameter": diameter,
                "base_length": base_length,
                "base_width": base_width,
            })

    def _check_rectangular_feature_inside_base(self, canonical, index, feature, base_length, base_width):
        # Edge notches intentionally touch/cross the boundary, so they are not checked here.
        if feature.get("operation") == "create_edge_notch":
            return

        position = feature.get("position")
        length = feature.get("length")
        width = feature.get("width")

        if not (
            self._is_valid_position(position)
            and isinstance(length, (int, float))
            and isinstance(width, (int, float))
            and isinstance(base_length, (int, float))
            and isinstance(base_width, (int, float))
        ):
            return

        x, y, _ = position

        if x - length / 2 < 0 or x + length / 2 > base_length or y - width / 2 < 0 or y + width / 2 > base_width:
            canonical["conflicts"].append({
                "type": "rectangular_feature_outside_base",
                "feature_index": index,
                "operation": feature.get("operation"),
                "position": position,
                "feature_length": length,
                "feature_width": width,
                "base_length": base_length,
                "base_width": base_width,
            })

    def _check_hole_pattern_inside_base(self, canonical, index, feature, base_length, base_width):
        rows = feature.get("rows")
        columns = feature.get("columns")
        diameter = feature.get("diameter")
        first_position = feature.get("first_position")
        spacing_x = feature.get("spacing_x")
        spacing_y = feature.get("spacing_y")

        if not (
            isinstance(rows, int)
            and isinstance(columns, int)
            and isinstance(diameter, (int, float))
            and self._is_valid_position(first_position)
            and isinstance(spacing_x, (int, float))
            and isinstance(spacing_y, (int, float))
            and isinstance(base_length, (int, float))
            and isinstance(base_width, (int, float))
        ):
            return

        radius = diameter / 2
        first_x, first_y, first_z = first_position

        for row in range(rows):
            for column in range(columns):
                x = first_x + column * spacing_x
                y = first_y + row * spacing_y

                if x - radius < 0 or x + radius > base_length or y - radius < 0 or y + radius > base_width:
                    canonical["conflicts"].append({
                        "type": "hole_pattern_hole_outside_base",
                        "feature_index": index,
                        "row": row,
                        "column": column,
                        "position": [x, y, first_z],
                        "base_length": base_length,
                        "base_width": base_width,
                    })

    # ------------------------------------------------------------------
    # Dedupe helpers
    # ------------------------------------------------------------------

    def _dedupe_base_objects(self, canonical):
        seen = set()
        result = []

        for base in canonical["geometry"]["base_objects"]:
            if not isinstance(base, dict):
                continue
            key = (
                base.get("operation"),
                base.get("name"),
                base.get("length"),
                base.get("width"),
                base.get("height"),
                tuple(base.get("position", [])) if isinstance(base.get("position"), list) else None,
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(base)

        canonical["geometry"]["base_objects"] = result

    def _dedupe_features(self, canonical):
        seen = set()
        result = []

        for feature in canonical["geometry"]["features"]:
            if not isinstance(feature, dict):
                continue

            key = self._feature_signature(feature)
            if key in seen:
                continue
            seen.add(key)
            result.append(feature)

        canonical["geometry"]["features"] = result

    def _feature_signature(self, feature):
        position = feature.get("position")
        first_position = feature.get("first_position")
        center = feature.get("center")

        return (
            feature.get("operation"),
            feature.get("target"),
            tuple(position) if isinstance(position, list) else None,
            tuple(first_position) if isinstance(first_position, list) else None,
            tuple(center) if isinstance(center, list) else None,
            feature.get("length"),
            feature.get("width"),
            feature.get("height"),
            feature.get("depth"),
            feature.get("diameter"),
            feature.get("rows"),
            feature.get("columns"),
            feature.get("spacing_x"),
            feature.get("spacing_y"),
            feature.get("count"),
        )

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _choose_units(self, excel_result, ocr_result):
        if isinstance(excel_result, dict):
            units = excel_result.get("units") or excel_result.get("unit")
            if units:
                return units

            constraints = excel_result.get("constraints", {})
            if isinstance(constraints, dict):
                units = constraints.get("units") or constraints.get("unit")
                if units:
                    return units

        if isinstance(ocr_result, dict):
            units = ocr_result.get("units") or ocr_result.get("unit")
            if units:
                return units

        return "mm"

    def _normalize_text(self, text):
        return " ".join(str(text).lower().replace("×", "x").split())

    def _first_regex_number(self, text, patterns):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return self._to_number(match.group("value"))
        return None

    def _first_regex_int(self, text, patterns):
        value = self._first_regex_number(text, patterns)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_center_position_near(self, text, keyword=None):
        patterns = [
            r"center\s+is\s+x\s*=\s*(?P<x>-?\d+(?:\.\d+)?)\s*mm?,?\s*y\s*=\s*(?P<y>-?\d+(?:\.\d+)?)\s*mm?,?\s*z\s*=\s*(?P<z>-?\d+(?:\.\d+)?)",
            r"centre\s+is\s+x\s*=\s*(?P<x>-?\d+(?:\.\d+)?)\s*mm?,?\s*y\s*=\s*(?P<y>-?\d+(?:\.\d+)?)\s*mm?,?\s*z\s*=\s*(?P<z>-?\d+(?:\.\d+)?)",
            r"center\s*(?:at|=)?\s*\[\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*,\s*(?P<z>-?\d+(?:\.\d+)?)\s*\]",
            r"position\s*(?:at|=)?\s*\[\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*,\s*(?P<z>-?\d+(?:\.\d+)?)\s*\]",
            r"x\s*=\s*(?P<x>-?\d+(?:\.\d+)?)\s*mm?,?\s*y\s*=\s*(?P<y>-?\d+(?:\.\d+)?)\s*mm?,?\s*z\s*=\s*(?P<z>-?\d+(?:\.\d+)?)",
        ]

        search_text = text

        if keyword and keyword in text:
            index = text.find(keyword)
            search_text = text[index:index + 500]

        for pattern in patterns:
            match = re.search(pattern, search_text, re.IGNORECASE | re.DOTALL)
            if match:
                return [
                    self._to_number(match.group("x")),
                    self._to_number(match.group("y")),
                    self._to_number(match.group("z")),
                ]

        return None

    def _parse_first_hole_position(self, text):
        patterns = [
            r"first\s+hole\s+center\s+is\s+x\s*=\s*(?P<x>-?\d+(?:\.\d+)?)\s*mm?,?\s*y\s*=\s*(?P<y>-?\d+(?:\.\d+)?)\s*mm?,?\s*z\s*=\s*(?P<z>-?\d+(?:\.\d+)?)",
            r"first\s+hole\s+position\s*(?:=|is)?\s*\[\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*,\s*(?P<z>-?\d+(?:\.\d+)?)\s*\]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return [
                    self._to_number(match.group("x")),
                    self._to_number(match.group("y")),
                    self._to_number(match.group("z")),
                ]

        return None

    def _parse_plane_origin(self, text):
        patterns = [
            r"plane\s+origin\s*(?:=|is)?\s*\[\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*,\s*(?P<z>-?\d+(?:\.\d+)?)\s*\]",
            r"mirror.*?origin\s*(?:=|is)?\s*\[\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*,\s*(?P<z>-?\d+(?:\.\d+)?)\s*\]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return [
                    self._to_number(match.group("x")),
                    self._to_number(match.group("y")),
                    self._to_number(match.group("z")),
                ]

        return None

    def _parse_scope(self, text, default):
        if "top outer edges" in text or "top edges" in text:
            return "base_top_outer_edges"
        if "bottom outer edges" in text or "bottom edges" in text:
            return "base_bottom_outer_edges"
        if "outer vertical edges" in text or "vertical outer edges" in text or "vertical edges" in text:
            return "base_outer_vertical_edges"
        if "all outer edges" in text:
            return "base_all_outer_edges"
        return default

    def _normalize_position(self, value, default=None):
        if value is None:
            return default

        if isinstance(value, dict):
            x = value.get("x", value.get("X", value.get("center_x", value.get("cx"))))
            y = value.get("y", value.get("Y", value.get("center_y", value.get("cy"))))
            z = value.get("z", value.get("Z", value.get("center_z", value.get("cz", 0))))

            x = self._number_or_none(x)
            y = self._number_or_none(y)
            z = self._number_or_none(z)

            if x is not None and y is not None:
                return [x, y, z if z is not None else 0]
            return default

        if isinstance(value, (list, tuple)):
            if len(value) >= 2:
                x = self._number_or_none(value[0])
                y = self._number_or_none(value[1])
                z = self._number_or_none(value[2]) if len(value) >= 3 else 0

                if x is not None and y is not None:
                    return [x, y, z if z is not None else 0]
            return default

        if isinstance(value, str):
            numbers = re.findall(r"[-+]?\d*\.?\d+", value)
            if len(numbers) >= 2:
                x = self._number_or_none(numbers[0])
                y = self._number_or_none(numbers[1])
                z = self._number_or_none(numbers[2]) if len(numbers) >= 3 else 0

                if x is not None and y is not None:
                    return [x, y, z if z is not None else 0]

        return default

    def _first_constraint_number(self, constraints, keys):
        for key in keys:
            if key in constraints:
                value = self._number_or_none(constraints.get(key))
                if value is not None:
                    return value
        return None

    def _base_height(self, base):
        if isinstance(base, dict):
            return self._number_or_none(base.get("height"))
        return None

    def _base_center(self, base):
        if not isinstance(base, dict):
            return None

        length = self._number_or_none(base.get("length"))
        width = self._number_or_none(base.get("width"))

        if length is None or width is None:
            return None

        return [length / 2, width / 2, 0]

    def _to_number(self, value):
        return self._number_or_none(value)

    def _number_or_none(self, value):
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return value

        if isinstance(value, str):
            stripped = value.strip().replace("−", "-")
            if stripped == "":
                return None

            match = re.search(r"[-+]?\d*\.?\d+", stripped)
            if not match:
                return None

            try:
                number = float(match.group(0))
            except ValueError:
                return None

            if number.is_integer():
                return int(number)
            return number

        return None

    def _calib_number(self, value):
        return self._number_or_none(value)

    def _calib_int(self, value):
        value = self._number_or_none(value)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _distance_2d_mm(self, a, b):
        if not self._is_valid_position(a) or not self._is_valid_position(b):
            return None

        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def _is_valid_position(self, value):
        return (
            isinstance(value, list)
            and len(value) == 3
            and all(isinstance(component, (int, float)) and not isinstance(component, bool) for component in value)
        )

    def _as_list(self, value):
        if isinstance(value, list):
            return value
        return [value]

    def _drop_none_values(self, data, keep_none_for=None):
        if keep_none_for is None:
            keep_none_for = set()

        if not isinstance(data, dict):
            return data

        result = {}

        for key, value in data.items():
            if value is None and key not in keep_none_for:
                continue
            result[key] = value

        return result