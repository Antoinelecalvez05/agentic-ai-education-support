# core/validator.py

import math
from typing import Any, Dict, List, Optional


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

    "create_fillet",
    "create_chamfer",
}


VALID_SLOT_ORIENTATIONS = {"x", "y"}

VALID_EDGE_NAMES = {
    "left",
    "right",
    "top",
    "bottom",
    "front",
    "back",
    "x_min",
    "x_max",
    "y_min",
    "y_max",
}

VALID_MIRROR_PLANES = {"YZ", "XZ", "XY", "X", "Y", "Z"}

VALID_PATTERN_AXES = {"X", "Y", "Z"}

VALID_RIB_ORIENTATIONS = {"x", "y"}
VALID_GUSSET_ORIENTATIONS = {"x", "y", "-x", "-y"}
VALID_BORDER_SCOPES = {"outer_perimeter", "rectangular_area"}


class Validator:
    """
    Combined validation layer.

    This validator does two levels of validation:

    1. Strict schema validation:
       - accepts only canonical operation names
       - checks required fields
       - checks dimensions, positions, targets, scopes, nested features

    2. Engineering geometry validation:
       - checks whether features fit inside the target object
       - checks pattern instances against the target
       - checks mirrored and circular pattern instances where possible

    The normalizer is responsible for aliases and messy input.
    The validator should validate clean normalized CAD plans.
    """

    def __init__(self):
        self.errors = []
        self.warnings = []

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def validate(self, cad_plan: dict) -> dict:
        self.errors = []
        self.warnings = []

        if not isinstance(cad_plan, dict):
            self._add_error(
                error_type="invalid_plan",
                step_index=None,
                field="cad_plan",
                value=cad_plan,
                message="CAD plan must be a dictionary.",
            )
            return self._result()

        units = cad_plan.get("units", "mm")

        if units != "mm":
            self._add_warning(
                warning_type="unsupported_units",
                step_index=None,
                field="units",
                value=units,
                message='Units should be "mm". The FreeCAD generator expects millimeters.',
            )

        if isinstance(cad_plan.get("parts"), list) and not isinstance(cad_plan.get("steps"), list):
            self._validate_parts_plan(cad_plan)
            return self._result()

        steps = cad_plan.get("steps")

        if steps is None:
            self._add_error(
                error_type="missing_steps_or_parts",
                step_index=None,
                field="steps",
                value=None,
                message='CAD plan must contain either a "steps" list or a "parts" list.',
            )
            return self._result()

        if not isinstance(steps, list):
            self._add_error(
                error_type="invalid_steps",
                step_index=None,
                field="steps",
                value=steps,
                message='"steps" must be a list.',
            )
            return self._result()

        if len(steps) == 0:
            self._add_error(
                error_type="empty_steps",
                step_index=None,
                field="steps",
                value=steps,
                message="CAD plan must contain at least one step.",
            )
            return self._result()

        for index, step in enumerate(steps):
            self._validate_step(step, step_index=index)

        # Only run engineering geometry checks if schema-level validation passed.
        # This prevents crashes caused by missing positions/dimensions.
        if len(self.errors) == 0:
            self._validate_engineering_geometry(steps)

        return self._result()


    def _validate_parts_plan(self, cad_plan: dict) -> None:
        parts = cad_plan.get("parts")

        if not isinstance(parts, list):
            self._add_error(
                error_type="invalid_parts",
                step_index=None,
                field="parts",
                value=parts,
                message='"parts" must be a list.',
            )
            return

        if len(parts) == 0:
            self._add_error(
                error_type="empty_parts",
                step_index=None,
                field="parts",
                value=parts,
                message='"parts" must contain at least one part.',
            )
            return

        part_names = set()

        for part_index, part in enumerate(parts):
            field_prefix = f"parts[{part_index}]."

            if not isinstance(part, dict):
                self._add_error(
                    error_type="invalid_part",
                    step_index=None,
                    field=field_prefix.rstrip("."),
                    value=part,
                    message="Each part must be a dictionary.",
                )
                continue

            name = part.get("name")

            if not isinstance(name, str) or not name.strip():
                self._add_error(
                    error_type="invalid_part_name",
                    step_index=None,
                    field=f"{field_prefix}name",
                    value=name,
                    message='Each part must have a non-empty string "name".',
                )
            else:
                part_names.add(name)

            steps = part.get("steps")

            if not isinstance(steps, list):
                self._add_error(
                    error_type="invalid_part_steps",
                    step_index=None,
                    field=f"{field_prefix}steps",
                    value=steps,
                    message='Each part must have a "steps" list.',
                )
                continue

            if len(steps) == 0:
                self._add_error(
                    error_type="empty_part_steps",
                    step_index=None,
                    field=f"{field_prefix}steps",
                    value=steps,
                    message="Each part must contain at least one step.",
                )
                continue

            for step_index, step in enumerate(steps):
                self._validate_step(
                    step,
                    step_index=step_index,
                    field_prefix=f"{field_prefix}steps[{step_index}].",
                )

            if len(self.errors) == 0:
                self._validate_engineering_geometry(steps)

        self._validate_assembly(cad_plan.get("assembly"), part_names)

    def _validate_assembly(self, assembly, part_names) -> None:
        valid_place_rules = {
            "on_top_of",
            "under",
            "right_of",
            "left_of",
            "in_front_of",
            "behind",
            "centered_on",
            "flush_top",
            "flush_bottom",
            "same_position_as",
        }
        valid_align_rules = {
            "center",
            "center_x",
            "center_y",
            "center_z",
            "top",
            "bottom",
            "front",
            "back",
            "left",
            "right",
        }

        if assembly is None:
            self._add_warning(
                warning_type="missing_assembly",
                step_index=None,
                field="assembly",
                value=None,
                message="Assembly list is missing. CadQuery assembly will place every part at [0, 0, 0].",
            )
            return

        if not isinstance(assembly, list):
            self._add_error(
                error_type="invalid_assembly",
                step_index=None,
                field="assembly",
                value=assembly,
                message='"assembly" must be a list when provided.',
            )
            return

        already_placed = set()

        for index, item in enumerate(assembly):
            field_prefix = f"assembly[{index}]."

            if not isinstance(item, dict):
                self._add_error(
                    error_type="invalid_assembly_item",
                    step_index=None,
                    field=field_prefix.rstrip("."),
                    value=item,
                    message="Each assembly item must be a dictionary.",
                )
                continue

            part_name = item.get("part")

            if not part_name:
                self._add_error(
                    error_type="missing_assembly_part",
                    step_index=None,
                    field=f"{field_prefix}part",
                    value=part_name,
                    message='Each assembly item must reference a part using "part".',
                )
            elif part_name not in part_names:
                self._add_error(
                    error_type="unknown_assembly_part",
                    step_index=None,
                    field=f"{field_prefix}part",
                    value=part_name,
                    message=f"Assembly item references unknown part: {part_name}",
                )

            has_position = "position" in item and item.get("position") is not None
            has_smart_rule = item.get("place") is not None or item.get("target") is not None

            if has_position:
                self._validate_position(
                    item.get("position"),
                    "position",
                    step_index=None,
                    field_prefix=field_prefix,
                    required=True,
                )
            elif has_smart_rule:
                place = item.get("place")
                target = item.get("target")

                if not place:
                    self._add_error(
                        error_type="missing_assembly_place",
                        step_index=None,
                        field=f"{field_prefix}place",
                        value=place,
                        message='Smart assembly placement requires "place" when no absolute position is provided.',
                    )
                elif str(place) not in valid_place_rules:
                    self._add_error(
                        error_type="invalid_assembly_place",
                        step_index=None,
                        field=f"{field_prefix}place",
                        value=place,
                        message=f"Unsupported smart placement rule: {place}",
                    )

                if not target:
                    self._add_error(
                        error_type="missing_assembly_target",
                        step_index=None,
                        field=f"{field_prefix}target",
                        value=target,
                        message='Smart assembly placement requires "target" when no absolute position is provided.',
                    )
                elif target not in part_names and target not in already_placed:
                    self._add_warning(
                        warning_type="assembly_target_not_yet_placed",
                        step_index=None,
                        field=f"{field_prefix}target",
                        value=target,
                        message=(
                            f"Smart placement target '{target}' is not known as an already placed instance. "
                            "It should reference a part name or an earlier assembly instance."
                        ),
                    )
            else:
                self._add_error(
                    error_type="missing_assembly_placement",
                    step_index=None,
                    field=field_prefix.rstrip("."),
                    value=item,
                    message='Assembly item requires either "position" or both "place" and "target".',
                )

            if "rotation" in item:
                self._validate_position(
                    item.get("rotation"),
                    "rotation",
                    step_index=None,
                    field_prefix=field_prefix,
                    required=True,
                )

            if "offset" in item:
                self._validate_position(
                    item.get("offset"),
                    "offset",
                    step_index=None,
                    field_prefix=field_prefix,
                    required=True,
                )

            if "gap" in item and not self._is_number(item.get("gap")):
                self._add_error(
                    error_type="invalid_assembly_gap",
                    step_index=None,
                    field=f"{field_prefix}gap",
                    value=item.get("gap"),
                    message="Assembly gap must be numeric when provided.",
                )

            if "clearance" in item and not self._is_number(item.get("clearance")):
                self._add_error(
                    error_type="invalid_assembly_clearance",
                    step_index=None,
                    field=f"{field_prefix}clearance",
                    value=item.get("clearance"),
                    message="Assembly clearance must be numeric when provided.",
                )

            if "align" in item and item.get("align") not in valid_align_rules:
                self._add_error(
                    error_type="invalid_assembly_align",
                    step_index=None,
                    field=f"{field_prefix}align",
                    value=item.get("align"),
                    message=f"Unsupported assembly align rule: {item.get('align')}",
                )

            if part_name:
                already_placed.add(part_name)


    def validate_cad_plan(self, cad_plan: dict, canonical_input: Optional[dict] = None) -> dict:
        """
        Backward-compatible method for older orchestrator.py code.
        """

        return self.validate(cad_plan)

    def validate_canonical_input(self, canonical_input: dict) -> dict:
        """
        Backward-compatible helper for your older pipeline.

        This validates the pre-Mistral / aggregated input if your orchestrator
        still uses this stage.
        """

        errors = []
        warnings = []

        if not isinstance(canonical_input, dict):
            return {
                "valid": False,
                "errors": [
                    {
                        "type": "invalid_canonical_input",
                        "field": "canonical_input",
                        "value": canonical_input,
                        "message": "Canonical input must be a dictionary.",
                    }
                ],
                "warnings": [],
            }

        if not canonical_input.get("task"):
            errors.append(
                {
                    "type": "missing_task",
                    "field": "task",
                    "value": canonical_input.get("task"),
                    "message": "Canonical input is missing a task.",
                }
            )

        if not canonical_input.get("user_prompt"):
            warnings.append(
                {
                    "type": "missing_user_prompt",
                    "field": "user_prompt",
                    "value": canonical_input.get("user_prompt"),
                    "message": "Canonical input is missing the original user prompt.",
                }
            )

        if not canonical_input.get("units"):
            warnings.append(
                {
                    "type": "missing_units",
                    "field": "units",
                    "value": canonical_input.get("units"),
                    "message": 'Canonical input is missing units. "mm" will usually be assumed.',
                }
            )

        if canonical_input.get("ready_for_reasoning") is False:
            errors.append(
                {
                    "type": "not_ready_for_reasoning",
                    "field": "ready_for_reasoning",
                    "value": False,
                    "message": "Canonical input is not ready for reasoning.",
                }
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    # -------------------------------------------------------------------------
    # Core step validation
    # -------------------------------------------------------------------------

    def _validate_step(
        self,
        step: dict,
        step_index: int,
        field_prefix: str = "",
        nested: bool = False,
    ) -> None:
        if not isinstance(step, dict):
            self._add_error(
                error_type="invalid_nested_feature" if nested else "invalid_step",
                step_index=step_index,
                field=field_prefix.rstrip(".") or "step",
                value=step,
                message="Nested feature must be a dictionary." if nested else "Step must be a dictionary.",
            )
            return

        operation = step.get("operation")

        if operation is None:
            self._add_error(
                error_type="missing_operation",
                step_index=step_index,
                field=f"{field_prefix}operation",
                value=None,
                message="Step is missing required field: operation.",
            )
            return

        if operation not in SUPPORTED_OPERATIONS:
            self._add_error(
                error_type="unsupported_operation",
                step_index=step_index,
                field=f"{field_prefix}operation",
                value=operation,
                message=(
                    f"Unsupported operation: {operation}. "
                    "The validator only accepts canonical operation names. "
                    "Aliases must be handled by the normalizer."
                ),
            )
            return

        if operation in TARGET_OPERATIONS:
            self._validate_target(step, step_index, field_prefix)

        if operation == "create_box":
            self._validate_create_box(step, step_index, field_prefix)

        elif operation == "create_rounded_rectangle_plate":
            self._validate_create_rounded_rectangle_plate(step, step_index, field_prefix)

        elif operation == "create_cylinder":
            self._validate_create_cylinder(step, step_index, field_prefix)

        elif operation == "create_hole":
            self._validate_create_hole(step, step_index, field_prefix, nested)

        elif operation == "create_threaded_hole":
            self._validate_create_threaded_hole(step, step_index, field_prefix, nested)

        elif operation == "create_counterbore_hole":
            self._validate_create_counterbore_hole(step, step_index, field_prefix, nested)

        elif operation == "create_countersink_hole":
            self._validate_create_countersink_hole(step, step_index, field_prefix, nested)

        elif operation == "create_slot":
            self._validate_create_slot(step, step_index, field_prefix, nested)

        elif operation == "create_rectangular_cutout":
            self._validate_create_rectangular_cutout(step, step_index, field_prefix, nested)

        elif operation == "create_rectangular_pocket":
            self._validate_create_rectangular_pocket(step, step_index, field_prefix, nested)

        elif operation == "create_circular_pocket":
            self._validate_create_circular_pocket(step, step_index, field_prefix, nested)

        elif operation == "create_rectangular_boss":
            self._validate_create_rectangular_boss(step, step_index, field_prefix, nested)

        elif operation == "create_cylindrical_boss":
            self._validate_create_cylindrical_boss(step, step_index, field_prefix, nested)

        elif operation == "create_edge_notch":
            self._validate_create_edge_notch(step, step_index, field_prefix, nested)

        elif operation == "create_mounting_standoff":
            self._validate_create_mounting_standoff(step, step_index, field_prefix, nested)

        elif operation == "create_hole_on_boss":
            self._validate_create_hole_on_boss(step, step_index, field_prefix, nested)

        elif operation == "create_rib":
            self._validate_create_rib(step, step_index, field_prefix, nested)

        elif operation == "create_gusset":
            self._validate_create_gusset(step, step_index, field_prefix, nested)

        elif operation == "create_raised_border":
            self._validate_create_raised_border(step, step_index, field_prefix, nested)

        elif operation == "create_recess":
            self._validate_create_recess(step, step_index, field_prefix, nested)

        elif operation == "create_open_enclosure":
            self._validate_create_open_enclosure(step, step_index, field_prefix)

        elif operation == "create_lid":
            self._validate_create_lid(step, step_index, field_prefix)

        elif operation == "create_hole_pattern":
            self._validate_create_hole_pattern(step, step_index, field_prefix)

        elif operation == "create_linear_pattern":
            self._validate_linear_pattern(step, step_index, field_prefix)

        elif operation == "create_circular_pattern":
            self._validate_circular_pattern(step, step_index, field_prefix)

        elif operation == "mirror_feature":
            self._validate_mirror_feature(step, step_index, field_prefix)

        elif operation == "create_fillet":
            self._validate_create_fillet(step, step_index, field_prefix)

        elif operation == "create_chamfer":
            self._validate_create_chamfer(step, step_index, field_prefix)

    # -------------------------------------------------------------------------
    # Operation-specific schema validators
    # -------------------------------------------------------------------------

    def _validate_create_box(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix)
        self._validate_positive_number(step, "width", step_index, field_prefix)
        self._validate_positive_number(step, "height", step_index, field_prefix)

        if "position" in step:
            self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True)

    def _validate_create_rounded_rectangle_plate(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix)
        self._validate_positive_number(step, "width", step_index, field_prefix)
        self._validate_positive_number(step, "height", step_index, field_prefix)
        self._validate_positive_number(step, "corner_radius", step_index, field_prefix)

        if "position" in step:
            self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True)

        length = step.get("length")
        width = step.get("width")
        corner_radius = step.get("corner_radius")

        if self._is_number(length) and self._is_number(width) and self._is_number(corner_radius):
            max_radius = min(length, width) / 2

            if corner_radius >= max_radius:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}corner_radius",
                    value=corner_radius,
                    message="corner_radius must be smaller than half of the smaller plate dimension.",
                )

    def _validate_create_cylinder(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "height", step_index, field_prefix)

        radius = step.get("radius")
        diameter = step.get("diameter")

        if not self._is_positive_number(radius) and not self._is_positive_number(diameter):
            self._add_error(
                error_type="invalid_dimension",
                step_index=step_index,
                field=f"{field_prefix}radius",
                value=radius,
                message="create_cylinder requires either radius or diameter to be a positive number.",
            )

        if "position" in step:
            self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True)

    def _validate_create_hole(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

    def _validate_create_threaded_hole(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        if not step.get("thread"):
            self._add_warning(
                warning_type="missing_thread",
                step_index=step_index,
                field=f"{field_prefix}thread",
                value=step.get("thread"),
                message="Threaded hole has no thread specification. Example: M6, M8, M10.",
            )

    def _validate_create_counterbore_hole(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)
        self._validate_positive_number(step, "hole_diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_positive_number(step, "counterbore_diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "counterbore_depth", step_index, field_prefix, nested)

        hole_diameter = step.get("hole_diameter")
        counterbore_diameter = step.get("counterbore_diameter")
        depth = step.get("depth")
        counterbore_depth = step.get("counterbore_depth")

        if self._is_number(hole_diameter) and self._is_number(counterbore_diameter):
            if counterbore_diameter <= hole_diameter:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}counterbore_diameter",
                    value=counterbore_diameter,
                    message="counterbore_diameter must be greater than hole_diameter.",
                )

        if self._is_number(depth) and self._is_number(counterbore_depth):
            if counterbore_depth > depth:
                self._add_warning(
                    warning_type="suspicious_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}counterbore_depth",
                    value=counterbore_depth,
                    message="counterbore_depth is greater than the total hole depth.",
                )

    def _validate_create_countersink_hole(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)
        self._validate_positive_number(step, "hole_diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_positive_number(step, "countersink_diameter", step_index, field_prefix, nested)

        hole_diameter = step.get("hole_diameter")
        countersink_diameter = step.get("countersink_diameter")

        if self._is_number(hole_diameter) and self._is_number(countersink_diameter):
            if countersink_diameter <= hole_diameter:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}countersink_diameter",
                    value=countersink_diameter,
                    message="countersink_diameter must be greater than hole_diameter.",
                )

        if "countersink_depth" in step:
            self._validate_positive_number(step, "countersink_depth", step_index, field_prefix, nested)

        if "countersink_angle" in step:
            angle = step.get("countersink_angle")

            if not self._is_number(angle):
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}countersink_angle",
                    value=angle,
                    message="countersink_angle must be a number.",
                )
            elif angle < 30 or angle > 180:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}countersink_angle",
                    value=angle,
                    message="countersink_angle must be between 30 and 180 degrees.",
                )

    def _validate_create_slot(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        orientation = step.get("orientation", "x")

        if orientation not in VALID_SLOT_ORIENTATIONS:
            self._add_error(
                error_type="invalid_orientation",
                step_index=step_index,
                field=f"{field_prefix}orientation",
                value=orientation,
                message='orientation must be either "x" or "y".',
            )

        length = step.get("length")
        width = step.get("width")

        if self._is_number(length) and self._is_number(width) and length <= width:
            self._add_error(
                error_type="invalid_dimension",
                step_index=step_index,
                field=f"{field_prefix}length",
                value=length,
                message="slot length must be greater than slot width.",
            )

    def _validate_create_rectangular_cutout(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

    def _validate_create_rectangular_pocket(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

    def _validate_create_circular_pocket(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

    def _validate_create_rectangular_boss(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "height", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

    def _validate_create_cylindrical_boss(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "height", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        radius = step.get("radius")
        diameter = step.get("diameter")

        if not self._is_positive_number(radius) and not self._is_positive_number(diameter):
            self._add_error(
                error_type="invalid_dimension",
                step_index=step_index,
                field=f"{field_prefix}diameter",
                value=diameter,
                message="create_cylindrical_boss requires either diameter or radius to be a positive number.",
            )

    def _validate_create_edge_notch(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        edge = step.get("edge", step.get("side"))

        if edge is not None and edge not in VALID_EDGE_NAMES:
            self._add_error(
                error_type="invalid_edge",
                step_index=step_index,
                field=f"{field_prefix}edge",
                value=edge,
                message=f"edge/side must be one of: {sorted(VALID_EDGE_NAMES)}.",
            )


    def _validate_create_mounting_standoff(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "outer_diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "height", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        inner_diameter = step.get("inner_diameter")
        outer_diameter = step.get("outer_diameter")

        if inner_diameter is not None:
            self._validate_positive_number(step, "inner_diameter", step_index, field_prefix, nested)

            if self._is_number(inner_diameter) and self._is_number(outer_diameter):
                if inner_diameter >= outer_diameter:
                    self._add_error(
                        error_type="invalid_dimension",
                        step_index=step_index,
                        field=f"{field_prefix}inner_diameter",
                        value=inner_diameter,
                        message="inner_diameter must be smaller than outer_diameter.",
                    )

        if "hole_depth" in step and step.get("hole_depth") is not None:
            self._validate_positive_number(step, "hole_depth", step_index, field_prefix, nested)

    def _validate_create_hole_on_boss(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "diameter", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        if not step.get("target"):
            self._add_warning(
                warning_type="missing_target",
                step_index=step_index,
                field=f"{field_prefix}target",
                value=step.get("target"),
                message="create_hole_on_boss should include a target boss/standoff name, but target resolution is not required yet.",
            )

    def _validate_create_rib(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "thickness", step_index, field_prefix, nested)
        self._validate_positive_number(step, "height", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        orientation = step.get("orientation", "x")
        if orientation not in VALID_RIB_ORIENTATIONS:
            self._add_error(
                error_type="invalid_orientation",
                step_index=step_index,
                field=f"{field_prefix}orientation",
                value=orientation,
                message='orientation must be either "x" or "y".',
            )

    def _validate_create_gusset(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "height", step_index, field_prefix, nested)
        self._validate_positive_number(step, "thickness", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        orientation = step.get("orientation", "x")
        if orientation not in VALID_GUSSET_ORIENTATIONS:
            self._add_error(
                error_type="invalid_orientation",
                step_index=step_index,
                field=f"{field_prefix}orientation",
                value=orientation,
                message='orientation must be one of "x", "y", "-x", "-y".',
            )

    def _validate_create_raised_border(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "border_width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "height", step_index, field_prefix, nested)

        scope = step.get("scope", "outer_perimeter")
        if scope not in VALID_BORDER_SCOPES:
            self._add_error(
                error_type="invalid_scope",
                step_index=step_index,
                field=f"{field_prefix}scope",
                value=scope,
                message='scope must be either "outer_perimeter" or "rectangular_area".',
            )

        if scope == "rectangular_area":
            self._validate_positive_number(step, "length", step_index, field_prefix, nested)
            self._validate_positive_number(step, "width", step_index, field_prefix, nested)
            self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)


    def _validate_create_recess(self, step: dict, step_index: int, field_prefix: str, nested: bool = False) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix, nested)
        self._validate_positive_number(step, "width", step_index, field_prefix, nested)
        self._validate_positive_number(step, "depth", step_index, field_prefix, nested)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True, nested=nested)

        if "corner_radius" in step and step.get("corner_radius") is not None:
            self._validate_positive_number(step, "corner_radius", step_index, field_prefix, nested)

            length = step.get("length")
            width = step.get("width")
            corner_radius = step.get("corner_radius")

            if self._is_number(length) and self._is_number(width) and self._is_number(corner_radius):
                if corner_radius >= min(length, width) / 2:
                    self._add_error(
                        error_type="invalid_dimension",
                        step_index=step_index,
                        field=f"{field_prefix}corner_radius",
                        value=corner_radius,
                        message="corner_radius must be smaller than half of the smaller recess dimension.",
                    )

    def _validate_create_open_enclosure(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix)
        self._validate_positive_number(step, "width", step_index, field_prefix)
        self._validate_positive_number(step, "height", step_index, field_prefix)
        self._validate_positive_number(step, "wall_thickness", step_index, field_prefix)
        self._validate_positive_number(step, "bottom_thickness", step_index, field_prefix)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True)

        if "corner_radius" in step and step.get("corner_radius") is not None:
            self._validate_positive_number(step, "corner_radius", step_index, field_prefix)

        length = step.get("length")
        width = step.get("width")
        height = step.get("height")
        wall_thickness = step.get("wall_thickness")
        bottom_thickness = step.get("bottom_thickness")
        corner_radius = step.get("corner_radius")

        if self._is_number(length) and self._is_number(width) and self._is_number(wall_thickness):
            if wall_thickness >= min(length, width) / 2:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}wall_thickness",
                    value=wall_thickness,
                    message="wall_thickness must be smaller than half of both enclosure length and width.",
                )

        if self._is_number(height) and self._is_number(bottom_thickness):
            if bottom_thickness >= height:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}bottom_thickness",
                    value=bottom_thickness,
                    message="bottom_thickness must be smaller than enclosure height.",
                )

        if self._is_number(length) and self._is_number(width) and self._is_number(corner_radius):
            if corner_radius >= min(length, width) / 2:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}corner_radius",
                    value=corner_radius,
                    message="corner_radius must be smaller than half of the smaller enclosure dimension.",
                )

    def _validate_create_lid(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "length", step_index, field_prefix)
        self._validate_positive_number(step, "width", step_index, field_prefix)
        self._validate_positive_number(step, "height", step_index, field_prefix)
        self._validate_position(step.get("position"), "position", step_index, field_prefix, required=True)

        if "lip_height" in step and step.get("lip_height") is not None:
            self._validate_positive_number(step, "lip_height", step_index, field_prefix)

        if "lip_width" in step and step.get("lip_width") is not None:
            self._validate_positive_number(step, "lip_width", step_index, field_prefix)

        if "corner_radius" in step and step.get("corner_radius") is not None:
            self._validate_positive_number(step, "corner_radius", step_index, field_prefix)

        length = step.get("length")
        width = step.get("width")
        lip_width = step.get("lip_width")
        corner_radius = step.get("corner_radius")

        if self._is_number(length) and self._is_number(width) and self._is_number(lip_width):
            if lip_width >= min(length, width) / 2:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}lip_width",
                    value=lip_width,
                    message="lip_width must be smaller than half of both lid length and width.",
                )

        if self._is_number(length) and self._is_number(width) and self._is_number(corner_radius):
            if corner_radius >= min(length, width) / 2:
                self._add_error(
                    error_type="invalid_dimension",
                    step_index=step_index,
                    field=f"{field_prefix}corner_radius",
                    value=corner_radius,
                    message="corner_radius must be smaller than half of the smaller lid dimension.",
                )

    def _validate_create_hole_pattern(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_integer(step, "rows", step_index, field_prefix, minimum=1)
        self._validate_integer(step, "columns", step_index, field_prefix, minimum=1)
        self._validate_positive_number(step, "diameter", step_index, field_prefix)
        self._validate_positive_number(step, "depth", step_index, field_prefix)

        self._validate_position(
            step.get("first_position"),
            "first_position",
            step_index,
            field_prefix,
            required=True,
        )

        rows = step.get("rows")
        columns = step.get("columns")
        spacing_x = step.get("spacing_x")
        spacing_y = step.get("spacing_y")

        if self._is_integer(columns) and columns > 1:
            self._validate_positive_number(step, "spacing_x", step_index, field_prefix)
        else:
            self._validate_non_negative_number(step, "spacing_x", step_index, field_prefix)

        if self._is_integer(rows) and rows > 1:
            self._validate_positive_number(step, "spacing_y", step_index, field_prefix)
        else:
            self._validate_non_negative_number(step, "spacing_y", step_index, field_prefix)

        if self._is_number(spacing_x) and self._is_number(spacing_y):
            if spacing_x == 0 and spacing_y == 0 and self._is_integer(rows) and self._is_integer(columns):
                if rows > 1 or columns > 1:
                    self._add_error(
                        error_type="invalid_spacing",
                        step_index=step_index,
                        field=f"{field_prefix}spacing_x",
                        value=spacing_x,
                        message="At least one spacing direction must be positive when hole pattern has multiple instances.",
                    )

        if "pattern_center" in step and step.get("pattern_center") is not None:
            self._validate_position(
                step.get("pattern_center"),
                "pattern_center",
                step_index,
                field_prefix,
                required=True,
            )

    def _validate_linear_pattern(self, step: dict, step_index: int, field_prefix: str) -> None:
        feature = step.get("feature")
        count = step.get("count")
        spacing = step.get("spacing")

        if not isinstance(feature, dict):
            self._add_error(
                error_type="invalid_nested_feature",
                step_index=step_index,
                field=f"{field_prefix}feature",
                value=feature,
                message="create_linear_pattern requires feature to be a nested dictionary.",
            )
        else:
            self._validate_nested_feature(feature, step_index, f"{field_prefix}feature.")

        self._validate_integer(step, "count", step_index, field_prefix, minimum=1)

        self._validate_position(
            spacing,
            "spacing",
            step_index,
            field_prefix,
            required=True,
            allow_zero_vector=True,
        )

        if self._is_integer(count) and count > 1 and self._is_valid_position(spacing):
            if spacing[0] == 0 and spacing[1] == 0 and spacing[2] == 0:
                self._add_error(
                    error_type="invalid_spacing",
                    step_index=step_index,
                    field=f"{field_prefix}spacing",
                    value=spacing,
                    message="At least one spacing component must be non-zero when count is greater than 1.",
                )

    def _validate_circular_pattern(self, step: dict, step_index: int, field_prefix: str) -> None:
        feature = step.get("feature")

        if not isinstance(feature, dict):
            self._add_error(
                error_type="invalid_nested_feature",
                step_index=step_index,
                field=f"{field_prefix}feature",
                value=feature,
                message="create_circular_pattern requires feature to be a nested dictionary.",
            )
        else:
            self._validate_nested_feature(feature, step_index, f"{field_prefix}feature.")

        self._validate_integer(step, "count", step_index, field_prefix, minimum=1)

        self._validate_position(
            step.get("center"),
            "center",
            step_index,
            field_prefix,
            required=True,
        )

        self._validate_positive_number(step, "total_angle", step_index, field_prefix)

        total_angle = step.get("total_angle")

        if self._is_number(total_angle):
            if total_angle <= 0 or total_angle > 360:
                self._add_error(
                    error_type="invalid_angle",
                    step_index=step_index,
                    field=f"{field_prefix}total_angle",
                    value=total_angle,
                    message="total_angle must be greater than 0 and less than or equal to 360.",
                )

        axis = step.get("axis", "Z")

        if axis not in VALID_PATTERN_AXES:
            self._add_error(
                error_type="invalid_axis",
                step_index=step_index,
                field=f"{field_prefix}axis",
                value=axis,
                message='axis must be one of "X", "Y", or "Z".',
            )

        if "angle_step" in step:
            self._validate_positive_number(step, "angle_step", step_index, field_prefix)

    def _validate_mirror_feature(self, step: dict, step_index: int, field_prefix: str) -> None:
        feature = step.get("feature")

        if not isinstance(feature, dict):
            self._add_error(
                error_type="invalid_nested_feature",
                step_index=step_index,
                field=f"{field_prefix}feature",
                value=feature,
                message="mirror_feature requires feature to be a nested dictionary.",
            )
        else:
            self._validate_nested_feature(feature, step_index, f"{field_prefix}feature.")

            if "position" not in feature:
                self._add_error(
                    error_type="invalid_nested_feature",
                    step_index=step_index,
                    field=f"{field_prefix}feature.position",
                    value=None,
                    message="Nested feature inside mirror_feature must have a position.",
                )

        mirror_plane = step.get("mirror_plane")

        if mirror_plane is None:
            self._add_error(
                error_type="missing_required_field",
                step_index=step_index,
                field=f"{field_prefix}mirror_plane",
                value=None,
                message="mirror_feature requires mirror_plane.",
            )
        elif mirror_plane not in VALID_MIRROR_PLANES:
            self._add_error(
                error_type="invalid_mirror_plane",
                step_index=step_index,
                field=f"{field_prefix}mirror_plane",
                value=mirror_plane,
                message=f"mirror_plane must be one of: {sorted(VALID_MIRROR_PLANES)}.",
            )

        if "plane_position" in step:
            self._add_error(
                error_type="unexpected_field",
                step_index=step_index,
                field=f"{field_prefix}plane_position",
                value=step.get("plane_position"),
                message="Do not use plane_position here. The normalizer should convert it to plane_origin.",
            )

        self._validate_position(
            step.get("plane_origin"),
            "plane_origin",
            step_index,
            field_prefix,
            required=True,
        )

        if "include_original" in step and not isinstance(step.get("include_original"), bool):
            self._add_error(
                error_type="invalid_boolean",
                step_index=step_index,
                field=f"{field_prefix}include_original",
                value=step.get("include_original"),
                message="include_original must be a boolean.",
            )

    def _validate_create_fillet(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "radius", step_index, field_prefix)
        self._validate_scope(step, step_index, field_prefix, default="base_outer_vertical_edges")

        radius = step.get("radius")

        if self._is_number(radius) and radius > 20:
            self._add_warning(
                warning_type="large_radius",
                step_index=step_index,
                field=f"{field_prefix}radius",
                value=radius,
                message="Fillet radius looks large. This may fail if the selected edges are too small.",
            )

    def _validate_create_chamfer(self, step: dict, step_index: int, field_prefix: str) -> None:
        self._validate_positive_number(step, "distance", step_index, field_prefix)
        self._validate_scope(step, step_index, field_prefix, default="base_top_outer_edges")

    # -------------------------------------------------------------------------
    # Generic validation helpers
    # -------------------------------------------------------------------------

    def _validate_positive_number(
        self,
        step: dict,
        field: str,
        step_index: int,
        field_prefix: str = "",
        nested: bool = False,
    ) -> None:
        value = step.get(field)

        if not self._is_positive_number(value):
            self._add_error(
                error_type="invalid_nested_feature" if nested else "invalid_dimension",
                step_index=step_index,
                field=f"{field_prefix}{field}",
                value=value,
                message=(
                    f"Nested feature {field} must be a positive number."
                    if nested
                    else f"{field} must be a positive number."
                ),
            )

    def _validate_non_negative_number(
        self,
        step: dict,
        field: str,
        step_index: int,
        field_prefix: str = "",
    ) -> None:
        value = step.get(field)

        if not self._is_non_negative_number(value):
            self._add_error(
                error_type="invalid_dimension",
                step_index=step_index,
                field=f"{field_prefix}{field}",
                value=value,
                message=f"{field} must be a non-negative number.",
            )

    def _validate_integer(
        self,
        step: dict,
        field: str,
        step_index: int,
        field_prefix: str = "",
        minimum: Optional[int] = None,
    ) -> None:
        value = step.get(field)

        if not self._is_integer(value):
            self._add_error(
                error_type="invalid_integer",
                step_index=step_index,
                field=f"{field_prefix}{field}",
                value=value,
                message=f"{field} must be an integer.",
            )
            return

        if minimum is not None and value < minimum:
            self._add_error(
                error_type="invalid_integer",
                step_index=step_index,
                field=f"{field_prefix}{field}",
                value=value,
                message=f"{field} must be greater than or equal to {minimum}.",
            )

    def _validate_position(
        self,
        position: Any,
        field: str,
        step_index: int,
        field_prefix: str = "",
        required: bool = True,
        nested: bool = False,
        allow_zero_vector: bool = True,
    ) -> None:
        if position is None:
            if required:
                self._add_error(
                    error_type="invalid_nested_feature" if nested else "invalid_position",
                    step_index=step_index,
                    field=f"{field_prefix}{field}",
                    value=position,
                    message=(
                        f"Nested feature {field} must be a list of three numbers: [x, y, z]."
                        if nested
                        else f"{field} must be a list of three numbers: [x, y, z]."
                    ),
                )
            return

        if not self._is_valid_position(position):
            self._add_error(
                error_type="invalid_nested_feature" if nested else "invalid_position",
                step_index=step_index,
                field=f"{field_prefix}{field}",
                value=position,
                message=(
                    f"Nested feature {field} must be a list of three numbers: [x, y, z]."
                    if nested
                    else f"{field} must be a list of three numbers: [x, y, z]."
                ),
            )
            return

        if not allow_zero_vector:
            if position[0] == 0 and position[1] == 0 and position[2] == 0:
                self._add_error(
                    error_type="invalid_position",
                    step_index=step_index,
                    field=f"{field_prefix}{field}",
                    value=position,
                    message=f"{field} cannot be the zero vector.",
                )

    def _validate_target(self, step: dict, step_index: int, field_prefix: str = "") -> None:
        target = step.get("target")

        if not target:
            self._add_warning(
                warning_type="missing_target",
                step_index=step_index,
                field=f"{field_prefix}target",
                value=target,
                message='target is missing. It will probably default to "base_plate", but the normalizer should normally set it.',
            )

    def _validate_scope(
        self,
        step: dict,
        step_index: int,
        field_prefix: str = "",
        default: Optional[str] = None,
    ) -> None:
        scope = step.get("scope", default)

        if scope not in SUPPORTED_SCOPES:
            self._add_error(
                error_type="invalid_scope",
                step_index=step_index,
                field=f"{field_prefix}scope",
                value=scope,
                message=f"scope must be one of: {sorted(SUPPORTED_SCOPES)}.",
            )

    def _validate_nested_feature(
        self,
        feature: Any,
        step_index: int,
        field_prefix: str = "feature.",
    ) -> None:
        if not isinstance(feature, dict):
            self._add_error(
                error_type="invalid_nested_feature",
                step_index=step_index,
                field=field_prefix.rstrip("."),
                value=feature,
                message="Nested feature must be a dictionary.",
            )
            return

        self._validate_step(
            feature,
            step_index=step_index,
            field_prefix=field_prefix,
            nested=True,
        )

    # -------------------------------------------------------------------------
    # Engineering geometry validation
    # -------------------------------------------------------------------------

    def _validate_engineering_geometry(self, steps: List[dict]) -> None:
        objects = {}

        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            operation = step.get("operation")

            if operation in {"create_box", "create_rounded_rectangle_plate", "create_open_enclosure"}:
                name = step.get("name") or "base_plate"
                position = step.get("position", [0, 0, 0])

                if not self._is_valid_position(position):
                    continue

                length = step.get("length")
                width = step.get("width")
                height = step.get("height")

                if not (
                    self._is_positive_number(length)
                    and self._is_positive_number(width)
                    and self._is_positive_number(height)
                ):
                    continue

                objects[name] = {
                    "step_index": index,
                    "type": "box",
                    "x_min": position[0],
                    "y_min": position[1],
                    "z_min": position[2],
                    "x_max": position[0] + length,
                    "y_max": position[1] + width,
                    "z_max": position[2] + height,
                    "length": length,
                    "width": width,
                    "height": height,
                    "corner_radius": step.get("corner_radius"),
                }

        for index, step in enumerate(steps):
            if isinstance(step, dict):
                self._validate_step_against_targets(step, index, objects)

    def _validate_step_against_targets(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        operation = step.get("operation")

        if operation == "create_hole":
            self._validate_circular_feature_inside_target(step, step_index, objects, "diameter", "Hole", field_prefix)

        elif operation == "create_threaded_hole":
            self._validate_circular_feature_inside_target(step, step_index, objects, "diameter", "Threaded hole", field_prefix)

        elif operation == "create_slot":
            self._validate_slot_inside_target(step, step_index, objects, field_prefix)

        elif operation == "create_rectangular_cutout":
            self._validate_rectangular_feature_inside_target(step, step_index, objects, "Rectangular cutout", through=True, field_prefix=field_prefix)

        elif operation == "create_rectangular_pocket":
            self._validate_rectangular_feature_inside_target(step, step_index, objects, "Rectangular pocket", through=False, field_prefix=field_prefix)

        elif operation == "create_recess":
            self._validate_rectangular_feature_inside_target(step, step_index, objects, "Recess", through=False, field_prefix=field_prefix)

        elif operation == "create_circular_pocket":
            self._validate_circular_feature_inside_target(step, step_index, objects, "diameter", "Circular pocket", field_prefix)

        elif operation == "create_rectangular_boss":
            self._validate_rectangular_feature_inside_target(step, step_index, objects, "Rectangular boss", through=False, is_boss=True, field_prefix=field_prefix)

        elif operation == "create_cylindrical_boss":
            diameter_field = "diameter" if step.get("diameter") is not None else "radius"
            self._validate_circular_feature_inside_target(
                step,
                step_index,
                objects,
                diameter_field,
                "Cylindrical boss",
                field_prefix,
                radius_field=(diameter_field == "radius"),
            )

        elif operation == "create_counterbore_hole":
            self._validate_circular_feature_inside_target(step, step_index, objects, "counterbore_diameter", "Counterbore hole", field_prefix)

        elif operation == "create_countersink_hole":
            self._validate_circular_feature_inside_target(step, step_index, objects, "countersink_diameter", "Countersink hole", field_prefix)

        elif operation == "create_edge_notch":
            self._validate_edge_notch_against_target(step, step_index, objects, field_prefix)

        elif operation == "create_mounting_standoff":
            self._validate_circular_feature_inside_target(step, step_index, objects, "outer_diameter", "Mounting standoff", field_prefix)

        elif operation == "create_hole_on_boss":
            # Do not require target metadata yet; validate schema only.
            return

        elif operation == "create_rib":
            self._validate_rectangular_feature_inside_target(step, step_index, objects, "Rib", through=False, is_boss=True, field_prefix=field_prefix)

        elif operation == "create_gusset":
            # Simple schema validation is enough for now; exact boss attachment is not resolved yet.
            return

        elif operation == "create_raised_border":
            # Outer perimeter / rectangular lip can intentionally sit on edges; skip strict fit check.
            return

        elif operation == "create_open_enclosure":
            return

        elif operation == "create_lid":
            return

        elif operation == "create_hole_pattern":
            self._validate_hole_pattern_inside_target(step, step_index, objects, field_prefix)

        elif operation == "create_fillet":
            self._validate_fillet_against_target(step, step_index, objects, field_prefix)

        elif operation == "create_chamfer":
            self._validate_chamfer_against_target(step, step_index, objects, field_prefix)

        elif operation == "create_linear_pattern":
            self._validate_linear_pattern_against_target(step, step_index, objects, field_prefix)

        elif operation == "create_circular_pattern":
            self._validate_circular_pattern_against_target(step, step_index, objects, field_prefix)

        elif operation == "mirror_feature":
            self._validate_mirror_feature_against_target(step, step_index, objects, field_prefix)

    def _get_target(self, step: dict, step_index: int, objects: dict, feature_name: str, field_prefix: str = "") -> Optional[dict]:
        target_name = step.get("target") or "base_plate"
        target = objects.get(target_name)

        if not target:
            self._add_error(
                error_type="missing_target_object",
                step_index=step_index,
                field=f"{field_prefix}target",
                value=target_name,
                message=f"{feature_name} target object '{target_name}' does not exist.",
            )
            return None

        return target

    def _validate_circular_feature_inside_target(
        self,
        step: dict,
        step_index: int,
        objects: dict,
        diameter_field: str,
        feature_name: str,
        field_prefix: str = "",
        radius_field: bool = False,
    ) -> None:
        target = self._get_target(step, step_index, objects, feature_name, field_prefix)

        if not target:
            return

        position = step.get("position")
        value = step.get(diameter_field)
        depth = step.get("depth")

        if not self._is_valid_position(position) or not self._is_number(value):
            return

        x, y, z = position
        radius = value if radius_field else value / 2

        if (
            x - radius < target["x_min"]
            or x + radius > target["x_max"]
            or y - radius < target["y_min"]
            or y + radius > target["y_max"]
        ):
            self._add_error(
                error_type=f"{feature_name.lower().replace(' ', '_')}_outside_target",
                step_index=step_index,
                field=f"{field_prefix}position",
                value=position,
                message=f"{feature_name} is not fully inside the target.",
            )

        if self._is_number(depth) and depth > target["height"] * 1.5:
            self._add_warning(
                warning_type=f"{feature_name.lower().replace(' ', '_')}_depth_large",
                step_index=step_index,
                field=f"{field_prefix}depth",
                value=depth,
                message=f"{feature_name} depth is much larger than target height.",
            )

    def _validate_slot_inside_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        target = self._get_target(step, step_index, objects, "Slot", field_prefix)

        if not target:
            return

        position = step.get("position")
        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        orientation = step.get("orientation", "x")

        if not (
            self._is_valid_position(position)
            and self._is_number(length)
            and self._is_number(width)
        ):
            return

        x, y, z = position

        half_length = length / 2
        half_width = width / 2

        if orientation == "x":
            x_min, x_max = x - half_length, x + half_length
            y_min, y_max = y - half_width, y + half_width
        else:
            x_min, x_max = x - half_width, x + half_width
            y_min, y_max = y - half_length, y + half_length

        if (
            x_min < target["x_min"]
            or x_max > target["x_max"]
            or y_min < target["y_min"]
            or y_max > target["y_max"]
        ):
            self._add_error(
                error_type="slot_outside_target",
                step_index=step_index,
                field=f"{field_prefix}position",
                value=position,
                message="Slot is not fully inside the target.",
            )

        if self._is_number(depth) and depth > target["height"] * 1.5:
            self._add_warning(
                warning_type="slot_depth_large",
                step_index=step_index,
                field=f"{field_prefix}depth",
                value=depth,
                message="Slot depth is much larger than target height.",
            )

    def _validate_rectangular_feature_inside_target(
        self,
        step: dict,
        step_index: int,
        objects: dict,
        feature_name: str,
        through: bool = False,
        is_boss: bool = False,
        field_prefix: str = "",
    ) -> None:
        target = self._get_target(step, step_index, objects, feature_name, field_prefix)

        if not target:
            return

        position = step.get("position")
        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        height = step.get("height")

        if not (
            self._is_valid_position(position)
            and self._is_number(length)
            and self._is_number(width)
        ):
            return

        x, y, z = position

        if (
            x - length / 2 < target["x_min"]
            or x + length / 2 > target["x_max"]
            or y - width / 2 < target["y_min"]
            or y + width / 2 > target["y_max"]
        ):
            self._add_error(
                error_type=f"{feature_name.lower().replace(' ', '_')}_outside_target",
                step_index=step_index,
                field=f"{field_prefix}position",
                value=position,
                message=f"{feature_name} is not fully inside the target.",
            )

        if through and self._is_number(depth) and depth > target["height"] * 1.5:
            self._add_warning(
                warning_type=f"{feature_name.lower().replace(' ', '_')}_depth_large",
                step_index=step_index,
                field=f"{field_prefix}depth",
                value=depth,
                message=f"{feature_name} depth is much larger than target height.",
            )

        if not through and not is_boss and self._is_number(depth) and depth >= target["height"]:
            self._add_warning(
                warning_type=f"{feature_name.lower().replace(' ', '_')}_depth_large",
                step_index=step_index,
                field=f"{field_prefix}depth",
                value=depth,
                message=f"{feature_name} depth should usually be smaller than target height.",
            )

        if is_boss and self._is_number(height) and height > target["height"] * 3:
            self._add_warning(
                warning_type=f"{feature_name.lower().replace(' ', '_')}_height_large",
                step_index=step_index,
                field=f"{field_prefix}height",
                value=height,
                message=f"{feature_name} height is unusually large compared with target height.",
            )

    def _validate_edge_notch_against_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        target = self._get_target(step, step_index, objects, "Edge notch", field_prefix)

        if not target:
            return

        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        edge = step.get("edge", step.get("side", "left"))

        if not (self._is_number(length) and self._is_number(width) and self._is_number(depth)):
            return

        if edge in {"left", "right", "x_min", "x_max"} and length > target["width"]:
            self._add_error(
                error_type="edge_notch_too_long",
                step_index=step_index,
                field=f"{field_prefix}length",
                value=length,
                message="Edge notch length is larger than target width.",
            )

        if edge in {"top", "bottom", "front", "back", "y_min", "y_max"} and length > target["length"]:
            self._add_error(
                error_type="edge_notch_too_long",
                step_index=step_index,
                field=f"{field_prefix}length",
                value=length,
                message="Edge notch length is larger than target length.",
            )

        if width >= max(target["length"], target["width"]):
            self._add_error(
                error_type="edge_notch_width_too_large",
                step_index=step_index,
                field=f"{field_prefix}width",
                value=width,
                message="Edge notch width is too large for target.",
            )

        if depth >= target["height"]:
            self._add_warning(
                warning_type="edge_notch_depth_large",
                step_index=step_index,
                field=f"{field_prefix}depth",
                value=depth,
                message="Edge notch depth should usually be smaller than target height.",
            )

    def _validate_hole_pattern_inside_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        target = self._get_target(step, step_index, objects, "Hole pattern", field_prefix)

        if not target:
            return

        rows = step.get("rows")
        columns = step.get("columns")
        diameter = step.get("diameter")
        depth = step.get("depth")
        first_position = step.get("first_position")
        spacing_x = step.get("spacing_x", 0)
        spacing_y = step.get("spacing_y", 0)

        if not (
            self._is_integer(rows)
            and self._is_integer(columns)
            and self._is_number(diameter)
            and self._is_valid_position(first_position)
            and self._is_number(spacing_x)
            and self._is_number(spacing_y)
        ):
            return

        radius = diameter / 2
        first_x, first_y, first_z = first_position

        for row in range(rows):
            for column in range(columns):
                x = first_x + column * spacing_x
                y = first_y + row * spacing_y
                position = [x, y, first_z]

                if (
                    x - radius < target["x_min"]
                    or x + radius > target["x_max"]
                    or y - radius < target["y_min"]
                    or y + radius > target["y_max"]
                ):
                    self._add_error(
                        error_type="hole_pattern_hole_outside_target",
                        step_index=step_index,
                        field=f"{field_prefix}first_position",
                        value=position,
                        message=f"A hole in the pattern is outside the target at row {row}, column {column}.",
                    )

        if self._is_number(depth) and depth > target["height"] * 1.5:
            self._add_warning(
                warning_type="hole_pattern_depth_large",
                step_index=step_index,
                field=f"{field_prefix}depth",
                value=depth,
                message="Hole pattern depth is much larger than target height.",
            )

    def _validate_fillet_against_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        target = self._get_target(step, step_index, objects, "Fillet", field_prefix)

        if not target:
            return

        radius = step.get("radius")

        if not self._is_number(radius):
            return

        smallest_dimension = min(target["length"], target["width"], target["height"])

        if radius >= smallest_dimension / 2:
            self._add_error(
                error_type="fillet_radius_too_large",
                step_index=step_index,
                field=f"{field_prefix}radius",
                value=radius,
                message="Fillet radius is too large for the target.",
            )

    def _validate_chamfer_against_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        target = self._get_target(step, step_index, objects, "Chamfer", field_prefix)

        if not target:
            return

        distance = step.get("distance")

        if not self._is_number(distance):
            return

        smallest_dimension = min(target["length"], target["width"], target["height"])

        if distance >= smallest_dimension / 2:
            self._add_error(
                error_type="chamfer_distance_too_large",
                step_index=step_index,
                field=f"{field_prefix}distance",
                value=distance,
                message="Chamfer distance is too large for the target.",
            )

    def _validate_linear_pattern_against_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        feature = step.get("feature")
        count = step.get("count")
        spacing = step.get("spacing")

        if not (isinstance(feature, dict) and self._is_integer(count) and self._is_valid_position(spacing)):
            return

        base_position = feature.get("position")

        if not self._is_valid_position(base_position):
            return

        for i in range(count):
            copied = dict(feature)

            copied["position"] = [
                base_position[0] + i * spacing[0],
                base_position[1] + i * spacing[1],
                base_position[2] + i * spacing[2],
            ]

            self._validate_step_against_targets(
                copied,
                step_index,
                objects,
                field_prefix=f"{field_prefix}feature.pattern_{i}.",
            )

    def _validate_circular_pattern_against_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        feature = step.get("feature")
        count = step.get("count")
        center = step.get("center")
        total_angle = step.get("total_angle", 360)

        if not (
            isinstance(feature, dict)
            and self._is_integer(count)
            and count > 0
            and self._is_valid_position(center)
            and self._is_number(total_angle)
        ):
            return

        base_position = feature.get("position")

        if not self._is_valid_position(base_position):
            return

        angle_step = step.get("angle_step")

        if not self._is_number(angle_step):
            angle_step = total_angle / count

        for i in range(count):
            copied = dict(feature)
            copied["position"] = self._rotate_point(base_position, center, i * angle_step)

            self._validate_step_against_targets(
                copied,
                step_index,
                objects,
                field_prefix=f"{field_prefix}feature.pattern_{i}.",
            )

    def _validate_mirror_feature_against_target(self, step: dict, step_index: int, objects: dict, field_prefix: str = "") -> None:
        feature = step.get("feature")

        if not isinstance(feature, dict):
            return

        position = feature.get("position")
        plane_origin = step.get("plane_origin")
        mirror_plane = step.get("mirror_plane", "YZ")

        if not (self._is_valid_position(position) and self._is_valid_position(plane_origin)):
            return

        copied = dict(feature)
        copied["position"] = self._mirror_point(position, mirror_plane, plane_origin)

        self._validate_step_against_targets(
            copied,
            step_index,
            objects,
            field_prefix=f"{field_prefix}feature.mirror.",
        )

    # -------------------------------------------------------------------------
    # Geometry math helpers
    # -------------------------------------------------------------------------

    def _rotate_point(self, point: List[float], center: List[float], angle_degrees: float) -> List[float]:
        angle = math.radians(angle_degrees)

        px, py, pz = point
        cx, cy, cz = center

        tx = px - cx
        ty = py - cy

        rx = tx * math.cos(angle) - ty * math.sin(angle)
        ry = tx * math.sin(angle) + ty * math.cos(angle)

        return [cx + rx, cy + ry, pz]

    def _mirror_point(self, point: List[float], plane: str, origin: List[float]) -> List[float]:
        x, y, z = point
        ox, oy, oz = origin

        plane = str(plane).upper()

        if plane in {"YZ", "X"}:
            return [2 * ox - x, y, z]

        if plane in {"XZ", "Y"}:
            return [x, 2 * oy - y, z]

        if plane in {"XY", "Z"}:
            return [x, y, 2 * oz - z]

        return point

    # -------------------------------------------------------------------------
    # Error / warning helpers
    # -------------------------------------------------------------------------

    def _add_error(
        self,
        error_type: str,
        step_index: Optional[int],
        field: str,
        value: Any,
        message: str,
    ) -> None:
        error = {
            "type": error_type,
            "field": field,
            "value": value,
            "message": message,
        }

        if step_index is not None:
            error["step_index"] = step_index

        self.errors.append(error)

    def _add_warning(
        self,
        warning_type: str,
        step_index: Optional[int],
        field: str,
        value: Any,
        message: str,
    ) -> None:
        warning = {
            "type": warning_type,
            "field": field,
            "value": value,
            "message": message,
        }

        if step_index is not None:
            warning["step_index"] = step_index

        self.warnings.append(warning)

    def _result(self) -> dict:
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    # -------------------------------------------------------------------------
    # Type helpers
    # -------------------------------------------------------------------------

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _is_positive_number(self, value: Any) -> bool:
        return self._is_number(value) and value > 0

    def _is_non_negative_number(self, value: Any) -> bool:
        return self._is_number(value) and value >= 0

    def _is_integer(self, value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    def _is_valid_position(self, value: Any) -> bool:
        if not isinstance(value, list):
            return False

        if len(value) != 3:
            return False

        return all(self._is_number(component) for component in value)