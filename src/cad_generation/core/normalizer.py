# core/normalizer.py

import copy
import re
from typing import Any, Dict, List, Optional, Union


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

    "create_mounting_standoff",
    "create_hole_on_boss",
    "create_rib",
    "create_gusset",
    "create_raised_border",
    "create_recess",
    "create_open_enclosure",
    "create_lid",

    "create_hole_pattern",
    "create_linear_pattern",
    "create_circular_pattern",

    "mirror_feature",

    "create_fillet",
    "create_chamfer",
}


OPERATION_ALIASES = {
    # Basic solids
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

    # Holes
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
    "create_counterbore": "create_counterbore_hole",
    "create_counterbore_hole": "create_counterbore_hole",

    "countersink": "create_countersink_hole",
    "countersink_hole": "create_countersink_hole",
    "create_countersink": "create_countersink_hole",
    "create_countersink_hole": "create_countersink_hole",

    # Cuts / pockets / slots
    "slot": "create_slot",
    "rounded_slot": "create_slot",
    "through_slot": "create_slot",
    "create_slot": "create_slot",

    "rectangular_cutout": "create_rectangular_cutout",
    "rectangle_cutout": "create_rectangular_cutout",
    "rectangular_hole": "create_rectangular_cutout",
    "cutout": "create_rectangular_cutout",
    "through_cutout": "create_rectangular_cutout",
    "through_rectangular_cutout": "create_rectangular_cutout",
    "create_rectangular_cutout": "create_rectangular_cutout",

    "rectangular_pocket": "create_rectangular_pocket",
    "rectangle_pocket": "create_rectangular_pocket",
    "pocket": "create_rectangular_pocket",
    "create_rectangular_pocket": "create_rectangular_pocket",

    "circular_pocket": "create_circular_pocket",
    "round_pocket": "create_circular_pocket",
    "create_circular_pocket": "create_circular_pocket",

    # Bosses
    "rectangular_boss": "create_rectangular_boss",
    "box_boss": "create_rectangular_boss",
    "cube_boss": "create_rectangular_boss",
    "create_rectangular_boss": "create_rectangular_boss",

    "cylindrical_boss": "create_cylindrical_boss",
    "round_boss": "create_cylindrical_boss",
    "cylinder_boss": "create_cylindrical_boss",
    "create_cylindrical_boss": "create_cylindrical_boss",

    # Edge feature
    "edge_notch": "create_edge_notch",
    "notch": "create_edge_notch",
    "side_notch": "create_edge_notch",
    "create_edge_notch": "create_edge_notch",

    # Professional mechanical features
    "mounting_standoff": "create_mounting_standoff",
    "standoff": "create_mounting_standoff",
    "screw_post": "create_mounting_standoff",
    "mounting_post": "create_mounting_standoff",
    "boss_with_hole": "create_mounting_standoff",
    "create_mounting_standoff": "create_mounting_standoff",

    "hole_on_boss": "create_hole_on_boss",
    "boss_hole": "create_hole_on_boss",
    "hole_in_boss": "create_hole_on_boss",
    "drill_boss": "create_hole_on_boss",
    "create_hole_on_boss": "create_hole_on_boss",

    "rib": "create_rib",
    "reinforcing_rib": "create_rib",
    "support_rib": "create_rib",
    "stiffener": "create_rib",
    "create_rib": "create_rib",

    "gusset": "create_gusset",
    "triangular_support": "create_gusset",
    "triangular_rib": "create_gusset",
    "support_gusset": "create_gusset",
    "create_gusset": "create_gusset",

    "raised_border": "create_raised_border",
    "border": "create_raised_border",
    "lip": "create_raised_border",
    "raised_lip": "create_raised_border",
    "rim": "create_raised_border",
    "perimeter_lip": "create_raised_border",
    "create_raised_border": "create_raised_border",
    "create_lip": "create_raised_border",

    "recess": "create_recess",
    "inset": "create_recess",
    "inset_area": "create_recess",
    "sunken_area": "create_recess",
    "recessed_area": "create_recess",
    "panel_recess": "create_recess",
    "screen_recess": "create_recess",
    "battery_recess": "create_recess",
    "label_recess": "create_recess",
    "create_recess": "create_recess",

    "open_enclosure": "create_open_enclosure",
    "enclosure": "create_open_enclosure",
    "enclosure_body": "create_open_enclosure",
    "housing": "create_open_enclosure",
    "open_box": "create_open_enclosure",
    "tray": "create_open_enclosure",
    "case_body": "create_open_enclosure",
    "electronics_enclosure": "create_open_enclosure",
    "create_open_enclosure": "create_open_enclosure",

    "lid": "create_lid",
    "cover": "create_lid",
    "enclosure_lid": "create_lid",
    "top_cover": "create_lid",
    "cover_plate": "create_lid",
    "case_lid": "create_lid",
    "create_lid": "create_lid",

    # Patterns
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

    # Mirror
    "mirror": "mirror_feature",
    "mirror_feature": "mirror_feature",
    "mirrored_feature": "mirror_feature",

    # Finishing
    "fillet": "create_fillet",
    "add_fillet": "create_fillet",
    "round_edges": "create_fillet",
    "create_fillet": "create_fillet",

    "chamfer": "create_chamfer",
    "add_chamfer": "create_chamfer",
    "bevel": "create_chamfer",
    "create_chamfer": "create_chamfer",
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


TARGET_OPERATIONS = {
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

    "create_mounting_standoff",
    "create_hole_on_boss",
    "create_rib",
    "create_gusset",
    "create_raised_border",
    "create_recess",
    "create_open_enclosure",
    "create_lid",

    "create_hole_pattern",
    "create_linear_pattern",
    "create_circular_pattern",
    "mirror_feature",

    "create_fillet",
    "create_chamfer",
}


BOSS_OPERATIONS = {
    "create_rectangular_boss",
    "create_cylindrical_boss",
    "create_mounting_standoff",
    "create_rib",
    "create_gusset",
    "create_raised_border",
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
    "create_hole_on_boss",
    "create_recess",
    "create_hole_pattern",
}


DIAMETER_OPERATIONS = {
    "create_hole",
    "create_threaded_hole",
    "create_circular_pocket",
    "create_cylindrical_boss",
    "create_hole_on_boss",
}


NUMERIC_FIELDS = {
    "length",
    "width",
    "height",
    "depth",
    "radius",
    "diameter",
    "corner_radius",

    "x",
    "y",
    "z",
    "center_x",
    "center_y",
    "center_z",

    "spacing_x",
    "spacing_y",
    "spacing_z",

    "count",
    "quantity",
    "number",
    "rows",
    "columns",

    "total_angle",
    "angle",
    "start_angle",
    "end_angle",

    "hole_diameter",
    "tap_drill_diameter",
    "major_diameter",
    "minor_diameter",
    "thread_pitch",

    "counterbore_diameter",
    "counterbore_depth",
    "head_diameter",
    "head_depth",

    "countersink_diameter",
    "countersink_angle",

    "notch_depth",
    "notch_width",

    "outer_diameter",
    "inner_diameter",
    "hole_depth",
    "inner_hole_diameter",
    "central_hole_diameter",

    "thickness",
    "border_width",
    "lip_width",
    "rim_width",
    "border_thickness",
    "lip_height",
    "rim_height",

    "wall_thickness",
    "wall_width",
    "wall_thick",
    "bottom_thickness",
    "base_thickness",
    "floor_thickness",
    "bottom_height",

    "cover_height",
    "lid_height",
    "lip_depth",
    "inner_lip_height",
    "lip_thickness",
    "inner_lip_width",
}


FIELD_ALIASES = {
    # Operation-like keys are handled separately.
    "id": "name",
    "label": "name",

    "pos": "position",
    "location": "position",
    "origin": "origin",
    "center": "center",
    "centre": "center",

    "center_position": "center",
    "centre_position": "center",
    "pattern_center": "pattern_center",

    "first_hole_position": "first_position",
    "first_hole_center": "first_position",
    "start": "first_position",
    "start_position": "first_position",

    "qty": "count",
    "quantity": "count",
    "number": "count",
    "instances": "count",

    "cols": "columns",
    "columns_count": "columns",
    "rows_count": "rows",

    "pitch_x": "spacing_x",
    "pitch_y": "spacing_y",
    "pitch_z": "spacing_z",

    "distance_x": "spacing_x",
    "distance_y": "spacing_y",
    "distance_z": "spacing_z",

    "hole_dia": "hole_diameter",
    "hole_diameter": "hole_diameter",
    "tap_diameter": "tap_drill_diameter",

    "cbore_diameter": "counterbore_diameter",
    "cbore_depth": "counterbore_depth",

    "csink_diameter": "countersink_diameter",
    "csink_angle": "countersink_angle",

    "plane": "mirror_plane",
    "mirror_plane": "mirror_plane",
    "plane_position": "plane_origin",
    "mirror_origin": "plane_origin",
    "mirror_plane_origin": "plane_origin",

    "hole_diameter": "hole_diameter",
    "inner_hole_diameter": "inner_diameter",
    "central_hole_diameter": "inner_diameter",
    "inner_dia": "inner_diameter",
    "outer_dia": "outer_diameter",

    "lip_width": "border_width",
    "rim_width": "border_width",
    "border_thickness": "border_width",

    "lip_height": "height",
    "rim_height": "height",

    "wall_width": "wall_thickness",
    "wall_thick": "wall_thickness",
    "base_thickness": "bottom_thickness",
    "floor_thickness": "bottom_thickness",
    "bottom_height": "bottom_thickness",

    "cover_height": "height",
    "lid_height": "height",
    "lip_depth": "lip_height",
    "inner_lip_height": "lip_height",
    "lip_thickness": "lip_width",
    "inner_lip_width": "lip_width",

    "fillet_radius": "corner_radius",
    "corner_rounding": "corner_radius",

    "rotation_axis": "axis",
}


class Normalizer:
    """
    Central CAD normalization layer.

    Converts messy AI / OCR / Excel / geometry output into a stable CAD plan:

    {
        "units": "mm",
        "steps": [...]
    }

    The validator remains responsible for strict correctness.
    This class is intentionally defensive and should avoid crashing on partial input.
    """

    def normalize(self, cad_plan: dict) -> dict:
        """
        Public method expected by the pipeline.

        Supports both:
        - legacy single-part plans with top-level "steps"
        - V1 multi-part assembly plans with top-level "parts" + optional "assembly"
        """

        if not isinstance(cad_plan, dict):
            return {
                "units": "mm",
                "steps": [],
                "assumptions": ["Invalid CAD plan format. Expected a dictionary."],
                "repair_notes": [],
                "raw_input_plan": cad_plan,
            }

        raw_plan = copy.deepcopy(cad_plan)
        units = cad_plan.get("units") or cad_plan.get("unit") or "mm"

        raw_parts = self._extract_parts(cad_plan)

        # Backward compatibility: if a top-level steps list exists, keep the old
        # single-part shape. Do not convert old plans into parts.
        if raw_parts is not None and not isinstance(cad_plan.get("steps"), list):
            normalized_parts = []

            for index, raw_part in enumerate(raw_parts):
                normalized_part = self._normalize_part(raw_part, index=index)

                if normalized_part is not None:
                    normalized_parts.append(normalized_part)

            normalized_assembly = self._normalize_assembly(cad_plan)

            return {
                "units": units,
                "parts": normalized_parts,
                "assembly": normalized_assembly,
                "assumptions": cad_plan.get("assumptions", []),
                "repair_notes": cad_plan.get("repair_notes", []),
                "missing_information": cad_plan.get("missing_information", []),
                "raw_input_plan": raw_plan,
            }

        raw_steps = self._extract_steps(cad_plan)

        normalized_steps = []
        first_box_seen = False

        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                continue

            normalized = self._normalize_step(raw_step)

            if not isinstance(normalized, dict):
                continue

            if normalized.get("operation") == "create_box":
                if not first_box_seen and not normalized.get("name"):
                    normalized["name"] = "base_plate"
                first_box_seen = True

            normalized_steps.append(normalized)

        normalized_steps = self._derive_missing_depths_from_targets(normalized_steps)

        return {
            "units": units,
            "steps": normalized_steps,
            "assumptions": cad_plan.get("assumptions", []),
            "repair_notes": cad_plan.get("repair_notes", []),
            "raw_input_plan": raw_plan,
        }

    def normalize_cad_plan(self, cad_plan: dict) -> dict:
        """
        Backward-compatible alias for older orchestrator.py versions.
        """

        return self.normalize(cad_plan)


    def _extract_parts(self, cad_plan: dict):
        """
        Accepts top-level multi-part aliases:
        - parts
        - components
        - bodies
        """

        if isinstance(cad_plan.get("parts"), list):
            return cad_plan["parts"]

        if isinstance(cad_plan.get("components"), list):
            return cad_plan["components"]

        if isinstance(cad_plan.get("bodies"), list):
            return cad_plan["bodies"]

        return None

    def _normalize_part(self, part: dict, index: int = 0):
        if not isinstance(part, dict):
            return None

        name = (
            part.get("name")
            or part.get("part_name")
            or part.get("id")
            or part.get("label")
            or f"part_{index + 1}"
        )

        raw_steps = self._extract_part_steps(part)
        normalized_steps = []
        first_box_seen = False

        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                continue

            normalized = self._normalize_step(raw_step)

            if not isinstance(normalized, dict):
                continue

            if normalized.get("operation") == "create_box":
                if not first_box_seen and not normalized.get("name"):
                    normalized["name"] = "base_plate"
                first_box_seen = True

            normalized_steps.append(normalized)

        normalized_steps = self._derive_missing_depths_from_targets(normalized_steps)

        return {
            "name": str(name),
            "steps": normalized_steps,
        }

    def _extract_part_steps(self, part: dict) -> List[dict]:
        if isinstance(part.get("steps"), list):
            return part["steps"]

        if isinstance(part.get("operations"), list):
            return part["operations"]

        if isinstance(part.get("features"), list):
            return part["features"]

        return []

    def _normalize_assembly(self, cad_plan: dict) -> List[dict]:
        raw_assembly = (
            cad_plan.get("assembly")
            or cad_plan.get("placements")
            or cad_plan.get("instances")
            or []
        )

        if not isinstance(raw_assembly, list):
            return []

        normalized = []

        for item in raw_assembly:
            normalized_item = self._normalize_assembly_item(item)

            if normalized_item is not None:
                normalized.append(normalized_item)

        return normalized

    def _normalize_assembly_item(self, item: dict):
        if not isinstance(item, dict):
            return None

        part_name = (
            item.get("part")
            or item.get("part_name")
            or item.get("target_part")
            or item.get("component")
            or item.get("name")
        )

        position_source = (
            item.get("position")
            or item.get("pos")
            or item.get("location")
            or item.get("translation")
        )

        rotation_source = (
            item.get("rotation")
            or item.get("rot")
            or item.get("orientation")
            or item.get("rotation_euler")
        )

        normalized = {
            "part": str(part_name) if part_name is not None else None,
            "rotation": self._normalize_position(rotation_source, default=[0, 0, 0]) or [0, 0, 0],
        }

        # Absolute placement remains backward-compatible and has priority in the generator.
        if position_source is not None:
            normalized["position"] = self._normalize_position(position_source, default=[0, 0, 0]) or [0, 0, 0]

        # Smart assembly placement aliases. These apply only to assembly items;
        # feature-level pattern spacing is intentionally untouched.
        place = item.get("place") or item.get("placement") or item.get("relation")
        if place is not None:
            normalized["place"] = str(place).strip().lower()

        target = (
            item.get("target")
            or item.get("relative_to")
            or item.get("reference")
            or item.get("target_part")
        )
        if target is not None:
            normalized["target"] = str(target)

        if item.get("target_instance") is not None:
            normalized["target_instance"] = str(item.get("target_instance"))

        gap = item.get("gap")
        if gap is None and item.get("spacing") is not None:
            gap = item.get("spacing")
        if gap is not None:
            normalized["gap"] = self._to_number(gap)

        clearance = item.get("clearance")
        if clearance is None and item.get("clearance_z") is not None:
            clearance = item.get("clearance_z")
        if clearance is not None:
            normalized["clearance"] = self._to_number(clearance)

        if item.get("align") is not None:
            normalized["align"] = str(item.get("align")).strip().lower()

        offset_source = item.get("offset")
        if offset_source is None and item.get("additional_offset") is not None:
            offset_source = item.get("additional_offset")
        if offset_source is not None:
            normalized["offset"] = self._normalize_position(offset_source, default=[0, 0, 0]) or [0, 0, 0]

        # Preserve old default behavior: if no smart placement was provided and no
        # absolute position exists, place at the origin.
        if "position" not in normalized and "place" not in normalized:
            normalized["position"] = [0, 0, 0]

        return normalized

    def _extract_steps(self, cad_plan: dict) -> List[dict]:
        """
        Accepts:
        - steps
        - operations
        - features
        - objects + operations style plans
        """

        if isinstance(cad_plan.get("steps"), list):
            return cad_plan["steps"]

        if isinstance(cad_plan.get("operations"), list):
            return cad_plan["operations"]

        if isinstance(cad_plan.get("features"), list):
            return cad_plan["features"]

        steps = []

        objects = cad_plan.get("objects")
        if isinstance(objects, list):
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                steps.append(obj)

        operations = cad_plan.get("operations")
        if isinstance(operations, list):
            for op in operations:
                if isinstance(op, dict):
                    steps.append(op)

        return steps

    def _normalize_step(self, step: dict, default_target: str = "base_plate") -> dict:
        """
        Normalize one CAD operation.
        """

        if not isinstance(step, dict):
            return {}

        normalized = self._normalize_field_names(step)

        operation = self._normalize_operation(
            normalized.get("operation")
            or normalized.get("type")
            or normalized.get("action")
            or normalized.get("feature_type")
            or normalized.get("object_type")
        )

        normalized["operation"] = operation

        # Remove ambiguous duplicate operation keys after canonical operation is chosen.
        normalized.pop("type", None)
        normalized.pop("action", None)
        normalized.pop("feature_type", None)
        normalized.pop("object_type", None)

        normalized = self._normalize_dimensions(normalized, operation=operation)

        # Position normalization.
        if operation in {"create_box", "create_rounded_rectangle_plate", "create_cylinder", "create_open_enclosure", "create_lid"}:
            if "position" not in normalized:
                position = self._normalize_position(
                    normalized.get("position")
                    or normalized.get("origin")
                    or normalized.get("center")
                )
                normalized["position"] = position if position is not None else [0, 0, 0]
            else:
                normalized["position"] = self._normalize_position(
                    normalized.get("position"),
                    default=[0, 0, 0],
                )
        else:
            position_source = (
                normalized.get("position")
                or normalized.get("center")
                or normalized.get("origin")
            )

            position = self._normalize_position(position_source)

            if position is None:
                position = self._position_from_xyz_fields(normalized)

            if position is not None:
                normalized["position"] = position

        # Target defaults for operations that modify an existing object.
        if operation in TARGET_OPERATIONS and not normalized.get("target"):
            normalized["target"] = default_target

        # Defaults and operation-specific cleanup.
        if operation == "create_slot" and not normalized.get("orientation"):
            normalized["orientation"] = "x"

        if operation == "create_rib" and not normalized.get("orientation"):
            normalized["orientation"] = "x"

        if operation == "create_gusset" and not normalized.get("orientation"):
            normalized["orientation"] = "x"

        if operation == "create_raised_border":
            if not normalized.get("scope"):
                normalized["scope"] = "outer_perimeter"

        if operation == "create_fillet":
            normalized["scope"] = self._normalize_scope(
                normalized.get("scope"),
                default="base_outer_vertical_edges",
            )

        if operation == "create_chamfer":
            normalized["scope"] = self._normalize_scope(
                normalized.get("scope"),
                default="base_top_outer_edges",
            )

        if operation in {
            "create_hole_pattern",
            "create_linear_pattern",
            "create_circular_pattern",
        }:
            normalized = self._normalize_pattern(normalized, operation, default_target)

        if operation == "mirror_feature":
            normalized = self._normalize_mirror(normalized, default_target)

        # Normalize nested feature if it exists even outside known pattern/mirror ops.
        if isinstance(normalized.get("feature"), dict):
            normalized["feature"] = self._normalize_nested_feature(
                normalized["feature"],
                default_target=normalized.get("target", default_target),
            )

        # Give a safe default name to the base box.
        if operation == "create_box" and not normalized.get("name"):
            normalized["name"] = "base_plate"

        return normalized

    def _normalize_operation(self, operation: Any) -> str:
        """
        Normalize operation aliases to canonical names.
        """

        if operation is None:
            return "unknown_operation"

        if not isinstance(operation, str):
            operation = str(operation)

        key = operation.strip().lower()
        key = key.replace(" ", "_").replace("-", "_")

        canonical = OPERATION_ALIASES.get(key, key)

        if canonical in SUPPORTED_OPERATIONS:
            return canonical

        return canonical

    def _normalize_scope(self, scope: Any, default: Optional[str] = None) -> Optional[str]:
        """
        Normalize fillet/chamfer scope names.
        """

        if scope is None:
            return default

        if not isinstance(scope, str):
            scope = str(scope)

        key = scope.strip().lower()
        key = key.replace(" ", "_").replace("-", "_")

        canonical = SCOPE_ALIASES.get(key, key)

        if canonical in SUPPORTED_SCOPES:
            return canonical

        return canonical or default

    def _normalize_position(
        self,
        value: Any,
        default: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        """
        Normalize position-like values into [x, y, z].

        Accepts:
        - [x, y, z]
        - [x, y]
        - {"x": 10, "y": 20, "z": 0}
        - {"X": "10 mm", "Y": "20 mm", "Z": "0"}
        - {"center_x": 10, "center_y": 20}
        - "10, 20, 0"
        """

        if value is None:
            return default

        if isinstance(value, dict):
            x = (
                value.get("x")
                if value.get("x") is not None
                else value.get("X")
                if value.get("X") is not None
                else value.get("center_x")
                if value.get("center_x") is not None
                else value.get("cx")
            )

            y = (
                value.get("y")
                if value.get("y") is not None
                else value.get("Y")
                if value.get("Y") is not None
                else value.get("center_y")
                if value.get("center_y") is not None
                else value.get("cy")
            )

            z = (
                value.get("z")
                if value.get("z") is not None
                else value.get("Z")
                if value.get("Z") is not None
                else value.get("center_z")
                if value.get("center_z") is not None
                else value.get("cz")
                if value.get("cz") is not None
                else 0
            )

            x = self._to_number(x)
            y = self._to_number(y)
            z = self._to_number(z)

            if x is not None and y is not None:
                return [x, y, z if z is not None else 0]

            return default

        if isinstance(value, (list, tuple)):
            if len(value) >= 2:
                x = self._to_number(value[0])
                y = self._to_number(value[1])
                z = self._to_number(value[2]) if len(value) >= 3 else 0

                if x is not None and y is not None:
                    return [x, y, z if z is not None else 0]

            return default

        if isinstance(value, str):
            numbers = re.findall(r"[-+]?\d*\.?\d+", value)

            if len(numbers) >= 2:
                x = self._to_number(numbers[0])
                y = self._to_number(numbers[1])
                z = self._to_number(numbers[2]) if len(numbers) >= 3 else 0

                if x is not None and y is not None:
                    return [x, y, z if z is not None else 0]

        return default

    def _position_from_xyz_fields(self, data: dict) -> Optional[List[float]]:
        """
        Build a position from x/y/z or center_x/center_y/center_z fields.
        """

        if not isinstance(data, dict):
            return None

        x = data.get("x")
        y = data.get("y")
        z = data.get("z", 0)

        if x is None:
            x = data.get("center_x")

        if y is None:
            y = data.get("center_y")

        if z is None:
            z = data.get("center_z", 0)

        x = self._to_number(x)
        y = self._to_number(y)
        z = self._to_number(z)

        if x is not None and y is not None:
            return [x, y, z if z is not None else 0]

        return None

    def _to_number(self, value: Any) -> Optional[Union[int, float]]:
        """
        Convert numeric-like values into numbers.

        Accepts:
        - 12
        - 12.5
        - "12"
        - "12 mm"
        - "diameter 12 mm"
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return value

        if isinstance(value, str):
            stripped = value.strip()

            if stripped == "":
                return None

            # Convert common unicode minus.
            stripped = stripped.replace("−", "-")

            match = re.search(r"[-+]?\d*\.?\d+", stripped)

            if not match:
                return value

            number_text = match.group(0)

            try:
                number = float(number_text)
            except ValueError:
                return value

            if number.is_integer():
                return int(number)

            return number

        return value

    def _normalize_dimensions(self, step: dict, operation: Optional[str] = None) -> dict:
        """
        Normalize numeric fields and diameter/radius/depth/height conventions.
        """

        if not isinstance(step, dict):
            return step

        normalized = {}

        for key, value in step.items():
            if isinstance(value, dict):
                normalized[key] = value
            elif isinstance(value, list):
                normalized[key] = [
                    self._to_number(item) if not isinstance(item, dict) else item
                    for item in value
                ]
            elif key in NUMERIC_FIELDS:
                normalized[key] = self._to_number(value)
            else:
                # Try number conversion only for obvious numeric strings.
                if isinstance(value, str):
                    converted = self._to_number(value)
                    normalized[key] = converted
                else:
                    normalized[key] = value

        # Diameter/radius handling.
        if operation in DIAMETER_OPERATIONS:
            if normalized.get("diameter") is None and normalized.get("radius") is not None:
                radius = self._to_number(normalized.get("radius"))
                if isinstance(radius, (int, float)) and radius > 0:
                    normalized["diameter"] = radius * 2

        if operation == "create_cylinder":
            if normalized.get("radius") is None and normalized.get("diameter") is not None:
                diameter = self._to_number(normalized.get("diameter"))
                if isinstance(diameter, (int, float)) and diameter > 0:
                    normalized["radius"] = diameter / 2

        # Bosses use height.
        if operation in BOSS_OPERATIONS:
            if normalized.get("height") is None and normalized.get("depth") is not None:
                normalized["height"] = normalized.get("depth")

        # Pockets / holes / cuts use depth.
        if operation in DEPTH_OPERATIONS:
            if normalized.get("depth") is None and normalized.get("height") is not None:
                normalized["depth"] = normalized.get("height")

        # Threaded hole aliases.
        if operation == "create_threaded_hole":
            if normalized.get("diameter") is None:
                diameter = (
                    normalized.get("tap_drill_diameter")
                    or normalized.get("major_diameter")
                    or normalized.get("hole_diameter")
                )
                if diameter is not None:
                    normalized["diameter"] = self._to_number(diameter)

            if normalized.get("thread") is None and normalized.get("thread_size") is not None:
                normalized["thread"] = normalized.get("thread_size")

        # Counterbore aliases.
        if operation == "create_counterbore_hole":
            if normalized.get("hole_diameter") is None and normalized.get("diameter") is not None:
                normalized["hole_diameter"] = normalized.get("diameter")

            if normalized.get("counterbore_diameter") is None:
                head_diameter = normalized.get("head_diameter")
                if head_diameter is not None:
                    normalized["counterbore_diameter"] = self._to_number(head_diameter)

            if normalized.get("counterbore_depth") is None:
                head_depth = normalized.get("head_depth")
                if head_depth is not None:
                    normalized["counterbore_depth"] = self._to_number(head_depth)

        # Countersink aliases.
        if operation == "create_countersink_hole":
            if normalized.get("hole_diameter") is None and normalized.get("diameter") is not None:
                normalized["hole_diameter"] = normalized.get("diameter")

            if normalized.get("countersink_diameter") is None:
                head_diameter = normalized.get("head_diameter")
                if head_diameter is not None:
                    normalized["countersink_diameter"] = self._to_number(head_diameter)

            if normalized.get("countersink_angle") is None:
                normalized["countersink_angle"] = 90


        # Mounting standoff aliases.
        if operation == "create_mounting_standoff":
            if normalized.get("outer_diameter") is None and normalized.get("diameter") is not None:
                normalized["outer_diameter"] = normalized.get("diameter")

            if normalized.get("inner_diameter") is None:
                inner = (
                    normalized.get("hole_diameter")
                    or normalized.get("inner_hole_diameter")
                    or normalized.get("central_hole_diameter")
                )
                if inner is not None:
                    normalized["inner_diameter"] = self._to_number(inner)

            if normalized.get("hole_depth") is None and normalized.get("depth") is not None:
                normalized["hole_depth"] = normalized.get("depth")

        # Hole on boss aliases.
        if operation == "create_hole_on_boss":
            if normalized.get("diameter") is None and normalized.get("hole_diameter") is not None:
                normalized["diameter"] = normalized.get("hole_diameter")

        # Rib uses thickness rather than width.
        if operation == "create_rib":
            if normalized.get("thickness") is None and normalized.get("width") is not None:
                normalized["thickness"] = normalized.get("width")

        # Gusset uses thickness; width can be used as an alias.
        if operation == "create_gusset":
            if normalized.get("thickness") is None and normalized.get("width") is not None:
                normalized["thickness"] = normalized.get("width")

        # Raised border / lip aliases.
        if operation == "create_raised_border":
            if normalized.get("border_width") is None:
                border_width = (
                    normalized.get("lip_width")
                    or normalized.get("rim_width")
                    or normalized.get("border_thickness")
                    or normalized.get("thickness")
                )
                if border_width is not None:
                    normalized["border_width"] = self._to_number(border_width)

            if normalized.get("height") is None:
                border_height = normalized.get("lip_height") or normalized.get("rim_height")
                if border_height is not None:
                    normalized["height"] = self._to_number(border_height)

            if not normalized.get("scope"):
                normalized["scope"] = "outer_perimeter"


        # Recess aliases.
        if operation == "create_recess":
            if normalized.get("corner_radius") is None:
                corner_radius = (
                    normalized.get("radius")
                    or normalized.get("fillet_radius")
                    or normalized.get("corner_rounding")
                )
                if corner_radius is not None:
                    normalized["corner_radius"] = self._to_number(corner_radius)

        # Open enclosure aliases.
        if operation == "create_open_enclosure":
            if normalized.get("wall_thickness") is None:
                wall_thickness = (
                    normalized.get("wall_width")
                    or normalized.get("wall_thick")
                    or normalized.get("thickness")
                )
                if wall_thickness is not None:
                    normalized["wall_thickness"] = self._to_number(wall_thickness)

            if normalized.get("bottom_thickness") is None:
                bottom_thickness = (
                    normalized.get("base_thickness")
                    or normalized.get("floor_thickness")
                    or normalized.get("bottom_height")
                )
                if bottom_thickness is not None:
                    normalized["bottom_thickness"] = self._to_number(bottom_thickness)

            if normalized.get("corner_radius") is None:
                corner_radius = (
                    normalized.get("radius")
                    or normalized.get("fillet_radius")
                    or normalized.get("corner_rounding")
                )
                if corner_radius is not None:
                    normalized["corner_radius"] = self._to_number(corner_radius)

        # Lid aliases.
        if operation == "create_lid":
            if normalized.get("height") is None:
                lid_height = normalized.get("cover_height") or normalized.get("lid_height")
                if lid_height is not None:
                    normalized["height"] = self._to_number(lid_height)

            if normalized.get("lip_height") is None:
                lip_height = (
                    normalized.get("lip_depth")
                    or normalized.get("inner_lip_height")
                )
                if lip_height is not None:
                    normalized["lip_height"] = self._to_number(lip_height)

            if normalized.get("lip_width") is None:
                lip_width = (
                    normalized.get("lip_thickness")
                    or normalized.get("inner_lip_width")
                )
                if lip_width is not None:
                    normalized["lip_width"] = self._to_number(lip_width)

            if normalized.get("corner_radius") is None:
                corner_radius = (
                    normalized.get("radius")
                    or normalized.get("fillet_radius")
                    or normalized.get("corner_rounding")
                )
                if corner_radius is not None:
                    normalized["corner_radius"] = self._to_number(corner_radius)

        return normalized

    def _normalize_pattern(
        self,
        step: dict,
        operation: str,
        default_target: str = "base_plate",
    ) -> dict:
        """
        Normalize hole, linear, and circular patterns.

        Important:
        - circular pattern remains create_circular_pattern
        - it is not converted into create_hole_pattern
        """

        if not isinstance(step, dict):
            return step

        normalized = step

        # Count aliases.
        if normalized.get("count") is None:
            for key in ("quantity", "number", "instances"):
                if normalized.get(key) is not None:
                    normalized["count"] = self._to_number(normalized.get(key))
                    break

        if operation == "create_hole_pattern":
            normalized = self._normalize_hole_pattern(normalized)

        elif operation == "create_linear_pattern":
            normalized = self._normalize_linear_pattern(normalized, default_target)

        elif operation == "create_circular_pattern":
            normalized = self._normalize_circular_pattern(normalized, default_target)

        return normalized

    def _normalize_hole_pattern(self, step: dict) -> dict:
        """
        Normalize create_hole_pattern while preserving its operation type.
        """

        normalized = step

        # Normalize rows/columns.
        if normalized.get("rows") is not None:
            normalized["rows"] = self._to_number(normalized.get("rows"))

        if normalized.get("columns") is not None:
            normalized["columns"] = self._to_number(normalized.get("columns"))

        if normalized.get("spacing_x") is not None:
            normalized["spacing_x"] = self._to_number(normalized.get("spacing_x"))

        if normalized.get("spacing_y") is not None:
            normalized["spacing_y"] = self._to_number(normalized.get("spacing_y"))

        if normalized.get("spacing_z") is not None:
            normalized["spacing_z"] = self._to_number(normalized.get("spacing_z"))

        # Single row/column safe defaults.
        if normalized.get("rows") == 1 and normalized.get("spacing_y") is None:
            normalized["spacing_y"] = 0

        if normalized.get("columns") == 1 and normalized.get("spacing_x") is None:
            normalized["spacing_x"] = 0

        first_position = (
            normalized.get("first_position")
            or normalized.get("start_position")
            or normalized.get("first_hole_position")
            or normalized.get("first_hole_center")
        )

        if first_position is not None:
            parsed = self._normalize_position(first_position)
            if parsed is not None:
                normalized["first_position"] = parsed

        pattern_center = (
            normalized.get("pattern_center")
            or normalized.get("center")
            or normalized.get("center_position")
        )

        parsed_center = self._normalize_position(pattern_center)

        if parsed_center is not None:
            normalized["pattern_center"] = parsed_center

        # Derive first_position from pattern_center if possible.
        rows = normalized.get("rows")
        columns = normalized.get("columns")
        spacing_x = normalized.get("spacing_x")
        spacing_y = normalized.get("spacing_y")

        if (
            normalized.get("first_position") is None
            and parsed_center is not None
            and isinstance(rows, int)
            and isinstance(columns, int)
            and isinstance(spacing_x, (int, float))
            and isinstance(spacing_y, (int, float))
        ):
            center_x, center_y, center_z = parsed_center
            first_x = center_x - ((columns - 1) * spacing_x) / 2
            first_y = center_y - ((rows - 1) * spacing_y) / 2
            normalized["first_position"] = [first_x, first_y, center_z]

        return normalized

    def _normalize_linear_pattern(
        self,
        step: dict,
        default_target: str = "base_plate",
    ) -> dict:
        """
        Normalize create_linear_pattern.

        Required output shape:
        {
            "operation": "create_linear_pattern",
            "feature": {...},
            "count": ...,
            "spacing": [x, y, z]
        }
        """

        normalized = step

        if normalized.get("feature") is not None:
            normalized["feature"] = self._normalize_nested_feature(
                normalized.get("feature"),
                default_target=normalized.get("target", default_target),
            )

        # Count aliases already handled above, but keep defensive fallback.
        if normalized.get("count") is None:
            for key in ("quantity", "number", "instances"):
                if normalized.get(key) is not None:
                    normalized["count"] = self._to_number(normalized.get(key))
                    break

        spacing = normalized.get("spacing")

        if isinstance(spacing, (list, tuple)):
            parsed_spacing = self._normalize_position(spacing)
            if parsed_spacing is not None:
                normalized["spacing"] = parsed_spacing

        elif isinstance(spacing, dict):
            parsed_spacing = self._normalize_position(spacing)
            if parsed_spacing is not None:
                normalized["spacing"] = parsed_spacing

        elif spacing is not None and normalized.get("direction") is not None:
            direction = str(normalized.get("direction")).lower()
            spacing_value = self._to_number(spacing)

            if direction == "x":
                normalized["spacing"] = [spacing_value, 0, 0]
            elif direction == "y":
                normalized["spacing"] = [0, spacing_value, 0]
            elif direction == "z":
                normalized["spacing"] = [0, 0, spacing_value]

        if normalized.get("spacing") is None:
            spacing_x = self._to_number(normalized.get("spacing_x"))
            spacing_y = self._to_number(normalized.get("spacing_y"))
            spacing_z = self._to_number(normalized.get("spacing_z"))

            if spacing_x is not None or spacing_y is not None or spacing_z is not None:
                normalized["spacing"] = [
                    spacing_x if spacing_x is not None else 0,
                    spacing_y if spacing_y is not None else 0,
                    spacing_z if spacing_z is not None else 0,
                ]

        return normalized

    def _normalize_circular_pattern(
        self,
        step: dict,
        default_target: str = "base_plate",
    ) -> dict:
        """
        Normalize create_circular_pattern.

        Required output shape:
        {
            "operation": "create_circular_pattern",
            "feature": {...},
            "center": [x, y, z],
            "count": ...,
            "total_angle": 360,
            "axis": "Z"
        }
        """

        normalized = step

        if normalized.get("feature") is not None:
            normalized["feature"] = self._normalize_nested_feature(
                normalized.get("feature"),
                default_target=normalized.get("target", default_target),
            )

        center_source = (
            normalized.get("center")
            or normalized.get("pattern_center")
            or normalized.get("center_position")
            or normalized.get("origin")
        )

        center = self._normalize_position(center_source)

        if center is not None:
            normalized["center"] = center

        if normalized.get("count") is None:
            for key in ("quantity", "number", "instances"):
                if normalized.get(key) is not None:
                    normalized["count"] = self._to_number(normalized.get(key))
                    break

        if normalized.get("total_angle") is None:
            normalized["total_angle"] = self._to_number(normalized.get("angle")) or 360
        else:
            normalized["total_angle"] = self._to_number(normalized.get("total_angle"))

        if normalized.get("axis") is None:
            normalized["axis"] = normalized.get("rotation_axis") or "Z"

        if isinstance(normalized.get("axis"), str):
            normalized["axis"] = normalized["axis"].upper()

        return normalized

    def _normalize_mirror(
        self,
        step: dict,
        default_target: str = "base_plate",
    ) -> dict:
        """
        Normalize mirror_feature.

        Required output shape:
        {
            "operation": "mirror_feature",
            "feature": {...},
            "mirror_plane": "...",
            "plane_origin": [x, y, z],
            "include_original": True
        }
        """

        normalized = step

        if normalized.get("feature") is not None:
            normalized["feature"] = self._normalize_nested_feature(
                normalized.get("feature"),
                default_target=normalized.get("target", default_target),
            )

        mirror_plane = (
            normalized.get("mirror_plane")
            or normalized.get("plane")
            or normalized.get("symmetry_plane")
        )

        if mirror_plane is not None:
            normalized["mirror_plane"] = mirror_plane

        plane_origin_source = (
            normalized.get("plane_origin")
            or normalized.get("plane_position")
            or normalized.get("mirror_origin")
            or normalized.get("mirror_plane_origin")
            or normalized.get("origin")
        )

        plane_origin = self._normalize_position(plane_origin_source, default=[0, 0, 0])
        normalized["plane_origin"] = plane_origin

        if normalized.get("include_original") is None:
            normalized["include_original"] = True

        # Remove duplicate aliases after canonical output is produced.
        normalized.pop("plane", None)
        normalized.pop("plane_position", None)
        normalized.pop("mirror_origin", None)
        normalized.pop("mirror_plane_origin", None)

        return normalized

    def _normalize_nested_feature(
        self,
        feature: Any,
        default_target: str = "base_plate",
    ) -> Any:
        """
        Recursively normalize a nested feature inside:
        - create_linear_pattern
        - create_circular_pattern
        - mirror_feature
        """

        if not isinstance(feature, dict):
            return feature

        return self._normalize_step(feature, default_target=default_target)

    def _normalize_field_names(self, step: dict) -> dict:
        """
        Normalize messy field aliases while avoiding destructive overwrites.
        """

        normalized = {}

        for key, value in step.items():
            if not isinstance(key, str):
                normalized[key] = value
                continue

            clean_key = key.strip()
            clean_key = clean_key.replace(" ", "_").replace("-", "_")
            clean_key = clean_key.lower()

            canonical_key = FIELD_ALIASES.get(clean_key, clean_key)

            # Avoid overwriting existing stronger fields.
            if canonical_key in normalized and normalized[canonical_key] is not None:
                continue

            normalized[canonical_key] = value

        return normalized

    def _derive_missing_depths_from_targets(self, steps: List[dict]) -> List[dict]:
        """
        Optional helper:
        If a through-cut / hole has no depth, infer target thickness from base object height.
        The validator can still reject if this assumption is not acceptable.
        """

        if not isinstance(steps, list):
            return steps

        target_heights = {}

        for step in steps:
            if not isinstance(step, dict):
                continue

            operation = step.get("operation")
            name = step.get("name")

            if operation in {"create_box", "create_rounded_rectangle_plate"}:
                height = self._to_number(step.get("height"))

                if name and isinstance(height, (int, float)) and height > 0:
                    target_heights[name] = height

        if "base_plate" not in target_heights:
            for step in steps:
                if not isinstance(step, dict):
                    continue

                if step.get("operation") in {"create_box", "create_rounded_rectangle_plate"}:
                    height = self._to_number(step.get("height"))

                    if isinstance(height, (int, float)) and height > 0:
                        target_heights["base_plate"] = height
                        break

        def apply_depth(step: dict) -> None:
            if not isinstance(step, dict):
                return

            operation = step.get("operation")

            if operation in DEPTH_OPERATIONS and step.get("depth") is None:
                target = step.get("target", "base_plate")
                target_height = target_heights.get(target)

                if isinstance(target_height, (int, float)) and target_height > 0:
                    step["depth"] = target_height

            if operation in {
                "create_linear_pattern",
                "create_circular_pattern",
                "mirror_feature",
            }:
                feature = step.get("feature")

                if isinstance(feature, dict):
                    apply_depth(feature)

        for step in steps:
            apply_depth(step)

        return steps