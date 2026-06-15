import os

from extractors.ocr_extractor import OCRExtractor
from extractors.geometry_extractor import GeometryExtractor
from extractors.excel_parser import ExcelParser
from core.aggregator import Aggregator
from core.validator import Validator
from core.normalizer import Normalizer
from ai.mistral_agent import MistralAgent
from cad.freecad_generator import FreeCADGenerator

try:
    from cad.cadquery_generator import CadQueryGenerator
except Exception as e:
    CadQueryGenerator = None
    CADQUERY_IMPORT_ERROR = str(e)
else:
    CADQUERY_IMPORT_ERROR = None


class CADPipeline:
    """
    Main pipeline controller.

    Flow:
    OCR / geometry / Excel / prompt
    → aggregator
    → canonical validation
    → Mistral initial CAD plan
    → normalizer
    → CAD plan validation
    → if invalid: Mistral repair loop
    → final CAD plan validation
    → model summary
    → selected CAD backend generation.

    Supported backends:
    - freecad
    - cadquery
    """

    def __init__(self, backend="freecad"):
        self.ocr = OCRExtractor()
        self.geometry = GeometryExtractor()
        self.excel = ExcelParser()
        self.aggregator = Aggregator()
        self.validator = Validator()
        self.normalizer = Normalizer()
        self.mistral = MistralAgent()

        self.backend = self._normalize_backend(backend)

        self.max_repair_attempts = self._get_int_env(
            "MAX_REPAIR_ATTEMPTS",
            default=0,
        )

    def _get_int_env(self, name, default):
        value = os.getenv(name)

        if value is None or value == "":
            return default

        try:
            parsed = int(value)
        except ValueError:
            return default

        if parsed < 0:
            return default

        return parsed

    # ------------------------------------------------------------------
    # Backend selection helpers
    # ------------------------------------------------------------------

    def _normalize_backend(self, backend):
        """
        Normalize backend aliases.

        Accepted values:
        - "freecad", "fcstd", "fc" -> "freecad"
        - "cadquery", "cq", "step" -> "cadquery"

        Unknown values fall back to "freecad".
        """
        if backend is None:
            return "freecad"

        backend = str(backend).strip().lower()

        aliases = {
            "freecad": "freecad",
            "fcstd": "freecad",
            "fc": "freecad",

            "cadquery": "cadquery",
            "cq": "cadquery",
            "step": "cadquery",
        }

        return aliases.get(backend, "freecad")

    def _get_backend_warning(self, backend):
        """
        Return a readable warning if the backend value is unknown.
        """
        if backend is None:
            return None

        backend_value = str(backend).strip().lower()

        valid_values = {
            "freecad",
            "fcstd",
            "fc",
            "cadquery",
            "cq",
            "step",
        }

        if backend_value not in valid_values:
            return (
                f"Unknown backend '{backend}' was provided. "
                "Falling back to 'freecad'."
            )

        return None

    def _get_generator_for_backend(self, backend):
        """
        Create only the selected generator.

        This avoids running both FreeCAD and CadQuery.
        It also avoids crashing the whole pipeline if CadQuery is not installed.
        """
        selected_backend = self._normalize_backend(backend)

        if selected_backend == "freecad":
            return FreeCADGenerator()

        if selected_backend == "cadquery":
            if CadQueryGenerator is None:
                raise RuntimeError(
                    "CadQuery backend is not available. "
                    f"Import error: {CADQUERY_IMPORT_ERROR}"
                )

            return CadQueryGenerator()

        return FreeCADGenerator()

    def _generate_cad_model(self, normalized_cad_plan, backend):
        """
        Generate CAD model using the selected backend only.

        FreeCAD:
        - filename: generated_model
        - expected outputs: .py, .FCStd, .step

        CadQuery:
        - filename: generated_model_cq
        - expected outputs: .py, .step, _cad_plan.json
        """
        selected_backend = self._normalize_backend(backend)

        if selected_backend == "cadquery":
            filename = "generated_model_cq"
        else:
            filename = "generated_model"

        try:
            generator = self._get_generator_for_backend(selected_backend)

            generation_result = generator.generate(
                cad_plan=normalized_cad_plan,
                filename=filename,
            )

            if generation_result is None:
                generation_result = {}

            generation_result["backend"] = selected_backend
            generation_result["filename"] = filename

            # Do not force success=True.
            # Some generators may return status="generated", others may return success.
            if "success" not in generation_result:
                generation_result["success"] = (
                    generation_result.get("status") == "generated"
                )

            return generation_result

        except Exception as e:
            return {
                "success": False,
                "backend": selected_backend,
                "filename": filename,
                "error": str(e),
                "message": (
                    f"CAD generation failed using backend '{selected_backend}'."
                ),
            }

    # ------------------------------------------------------------------
    # Model summary
    # ------------------------------------------------------------------

    def build_model_summary(self, normalized_cad_plan):
        """
        Build a human-readable and structured summary of the normalized CAD plan.

        This method is intentionally independent from the CAD backend. It does not
        call Mistral, FreeCAD, CadQuery, OCR, geometry extraction, or Streamlit.
        """

        if isinstance(normalized_cad_plan.get("parts"), list):
            units = normalized_cad_plan.get("units", "mm")
            parts = normalized_cad_plan.get("parts", [])
            assembly = normalized_cad_plan.get("assembly", [])

            summary = {
                "units": units,
                "is_assembly": True,
                "parts": [],
                "assembly": assembly if isinstance(assembly, list) else [],
                "counts": {
                    "parts": len(parts),
                    "assembly_items": len(assembly) if isinstance(assembly, list) else 0,
                    "total_steps": 0,
                    "total_features": 0,
                },
                "readable_summary": [],
            }

            summary["readable_summary"].append(
                f"Assembly with {len(parts)} part(s) and "
                f"{summary['counts']['assembly_items']} placement(s)."
            )

            for part in parts:
                if not isinstance(part, dict):
                    continue

                name = part.get("name", "unnamed_part")
                steps = part.get("steps", []) if isinstance(part.get("steps"), list) else []
                operations = []

                for step in steps:
                    if isinstance(step, dict):
                        operation = step.get("operation") or step.get("action") or step.get("type")
                        if operation:
                            operations.append(operation)
                            key = f"operation:{operation}"
                            summary["counts"][key] = summary["counts"].get(key, 0) + 1

                part_summary = {
                    "name": name,
                    "steps_count": len(steps),
                    "operations": operations,
                    "steps": steps,
                }

                summary["parts"].append(part_summary)
                summary["counts"]["total_steps"] += len(steps)

                included = ", ".join(dict.fromkeys(operations)) if operations else "no operations"
                summary["readable_summary"].append(
                    f"Part '{name}': {len(steps)} step(s), includes {included}."
                )

            summary["counts"]["total_features"] = summary["counts"]["total_steps"]

            for item in summary["assembly"]:
                if not isinstance(item, dict):
                    continue

                if item.get("position") is not None:
                    summary["readable_summary"].append(
                        f"Assembly placement: part '{item.get('part')}' at "
                        f"{item.get('position', [0, 0, 0])}, rotation "
                        f"{item.get('rotation', [0, 0, 0])}."
                    )
                else:
                    details = (
                        f"Assembly smart placement: part '{item.get('part')}' "
                        f"placed {item.get('place')} '{item.get('target')}'"
                    )

                    if item.get("gap") is not None:
                        details += f" with gap {item.get('gap')}"

                    if item.get("clearance") is not None:
                        details += f" with clearance {item.get('clearance')}"

                    if item.get("align") is not None:
                        details += f" and align {item.get('align')}"

                    if item.get("offset") is not None:
                        details += f", offset {item.get('offset')}"

                    details += f", rotation {item.get('rotation', [0, 0, 0])}."

                    summary["readable_summary"].append(details)

            return summary

        def op(step):
            return step.get("operation") or step.get("action") or step.get("type")

        def clean_position(value):
            if isinstance(value, list):
                return value

            if isinstance(value, tuple):
                return list(value)

            return value

        def feature_operation(feature):
            if not isinstance(feature, dict):
                return None

            return op(feature)

        def nested_position(feature):
            if not isinstance(feature, dict):
                return None

            if feature.get("position") is not None:
                return feature.get("position")

            if feature.get("first_position") is not None:
                return feature.get("first_position")

            return None

        def as_int(value, default=0):
            try:
                if value is None:
                    return default
                return int(value)
            except Exception:
                return default

        def add_count(counts, key, amount=1):
            counts[key] = counts.get(key, 0) + amount

        def hole_pattern_total(step):
            rows = as_int(step.get("rows"), 0)
            columns = as_int(step.get("columns"), 0)

            if rows <= 0 or columns <= 0:
                return 0

            return rows * columns

        def estimate_holes_in_feature(feature):
            if not isinstance(feature, dict):
                return 0

            operation = feature_operation(feature)

            if operation in {
                "create_hole",
                "create_threaded_hole",
                "create_counterbore_hole",
                "create_countersink_hole",
                "create_hole_on_boss",
            }:
                return 1

            if operation == "create_hole_pattern":
                return hole_pattern_total(feature)

            if operation == "create_mounting_standoff":
                if feature.get("inner_diameter") is not None:
                    return 1
                return 0

            if operation == "create_linear_pattern":
                count = as_int(feature.get("count"), 0)
                nested = feature.get("feature", {})
                return max(count, 0) * estimate_holes_in_feature(nested)

            if operation == "create_circular_pattern":
                count = as_int(feature.get("count"), 0)
                nested = feature.get("feature", {})
                return max(count, 0) * estimate_holes_in_feature(nested)

            if operation == "mirror_feature":
                nested = feature.get("feature", {})
                multiplier = 2 if feature.get("include_original", True) else 1
                return multiplier * estimate_holes_in_feature(nested)

            return 0

        units = normalized_cad_plan.get("units", "mm")
        steps = normalized_cad_plan.get("steps", [])

        summary = {
            "units": units,
            "base_objects": [],
            "open_enclosures": [],
            "lids": [],
            "recesses": [],
            "holes": [],
            "threaded_holes": [],
            "counterbores": [],
            "countersinks": [],
            "slots": [],
            "rectangular_cutouts": [],
            "pockets": [],
            "edge_notches": [],
            "bosses": [],
            "standoffs": [],
            "boss_holes": [],
            "ribs": [],
            "gussets": [],
            "raised_borders": [],
            "hole_patterns": [],
            "linear_patterns": [],
            "circular_patterns": [],
            "mirrors": [],
            "fillets": [],
            "chamfers": [],

            # Backward-compatible / useful extra categories
            "cylinders": [],

            "counts": {
                "total_steps": len(steps),
                "total_features": 0,
                "estimated_holes_total": 0,

                "base_objects": 0,
                "open_enclosures": 0,
                "lids": 0,
                "recesses": 0,
                "holes": 0,
                "threaded_holes": 0,
                "counterbores": 0,
                "countersinks": 0,
                "slots": 0,
                "rectangular_cutouts": 0,
                "pockets": 0,
                "edge_notches": 0,
                "bosses": 0,
                "standoffs": 0,
                "boss_holes": 0,
                "ribs": 0,
                "gussets": 0,
                "raised_borders": 0,
                "hole_patterns": 0,
                "pattern_holes_total": 0,
                "linear_patterns": 0,
                "circular_patterns": 0,
                "mirrors": 0,
                "fillets": 0,
                "chamfers": 0,
                "cylinders": 0,
                "unsupported_or_unknown": 0,
            },
            "readable_summary": [],
        }

        for step in steps:
            operation = op(step)

            if operation == "create_box":
                item = {
                    "operation": operation,
                    "name": step.get("name", "base_plate"),
                    "length": step.get("length"),
                    "width": step.get("width"),
                    "height": step.get("height"),
                    "position": clean_position(step.get("position", [0, 0, 0])),
                }

                summary["base_objects"].append(item)
                add_count(summary["counts"], "base_objects")

                summary["readable_summary"].append(
                    f"Base object '{item['name']}': "
                    f"{item['length']} × {item['width']} × {item['height']} {units}, "
                    f"position {item['position']}"
                )

            elif operation == "create_rounded_rectangle_plate":
                item = {
                    "operation": operation,
                    "name": step.get("name", "base_plate"),
                    "length": step.get("length"),
                    "width": step.get("width"),
                    "height": step.get("height"),
                    "corner_radius": step.get("corner_radius"),
                    "position": clean_position(step.get("position", [0, 0, 0])),
                }

                summary["base_objects"].append(item)
                add_count(summary["counts"], "base_objects")

                summary["readable_summary"].append(
                    f"Rounded base plate '{item['name']}': "
                    f"{item['length']} × {item['width']} × {item['height']} {units}, "
                    f"corner radius {item['corner_radius']} {units}, "
                    f"position {item['position']}"
                )

            elif operation == "create_cylinder":
                diameter = step.get("diameter")
                radius = step.get("radius")

                item = {
                    "operation": operation,
                    "name": step.get("name", "cylinder"),
                    "diameter": diameter,
                    "radius": radius,
                    "height": step.get("height"),
                    "position": clean_position(step.get("position", [0, 0, 0])),
                }

                summary["cylinders"].append(item)
                add_count(summary["counts"], "cylinders")

                if diameter is not None:
                    size_text = f"diameter {diameter} {units}"
                else:
                    size_text = f"radius {radius} {units}"

                summary["readable_summary"].append(
                    f"Cylinder '{item['name']}': {size_text}, "
                    f"height {item['height']} {units}, "
                    f"position {item['position']}"
                )

            elif operation == "create_open_enclosure":
                item = {
                    "operation": operation,
                    "name": step.get("name", "enclosure_body"),
                    "length": step.get("length"),
                    "width": step.get("width"),
                    "height": step.get("height"),
                    "wall_thickness": step.get("wall_thickness"),
                    "bottom_thickness": step.get("bottom_thickness"),
                    "corner_radius": step.get("corner_radius"),
                    "position": clean_position(step.get("position", [0, 0, 0])),
                }

                summary["open_enclosures"].append(item)
                add_count(summary["counts"], "open_enclosures")

                summary["readable_summary"].append(
                    f"Open enclosure '{item['name']}': "
                    f"{item['length']} × {item['width']} × {item['height']} {units}, "
                    f"wall thickness {item['wall_thickness']} {units}, "
                    f"bottom thickness {item['bottom_thickness']} {units}, "
                    f"corner radius {item['corner_radius']} {units}"
                )

            elif operation == "create_lid":
                item = {
                    "operation": operation,
                    "name": step.get("name", "lid"),
                    "target": step.get("target"),
                    "length": step.get("length"),
                    "width": step.get("width"),
                    "height": step.get("height"),
                    "lip_height": step.get("lip_height"),
                    "lip_width": step.get("lip_width"),
                    "corner_radius": step.get("corner_radius"),
                    "position": clean_position(step.get("position", [0, 0, 0])),
                }

                summary["lids"].append(item)
                add_count(summary["counts"], "lids")

                summary["readable_summary"].append(
                    f"Lid '{item['name']}': "
                    f"{item['length']} × {item['width']} × {item['height']} {units}, "
                    f"lower lip {item['lip_height']} {units} high and "
                    f"{item['lip_width']} {units} wide"
                )

            elif operation == "create_recess":
                item = dict(step)
                summary["recesses"].append(item)
                add_count(summary["counts"], "recesses")

                summary["readable_summary"].append(
                    f"Recess in '{item.get('target')}': "
                    f"{item.get('length')} × {item.get('width')} × "
                    f"{item.get('depth')} {units}, "
                    f"corner radius {item.get('corner_radius')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_hole":
                item = dict(step)
                summary["holes"].append(item)
                add_count(summary["counts"], "holes")

                summary["readable_summary"].append(
                    f"Hole in '{item.get('target')}': "
                    f"diameter {item.get('diameter')} {units}, "
                    f"depth {item.get('depth')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_threaded_hole":
                item = dict(step)
                summary["threaded_holes"].append(item)
                add_count(summary["counts"], "threaded_holes")

                summary["readable_summary"].append(
                    f"Threaded hole in '{item.get('target')}': "
                    f"thread {item.get('thread')}, "
                    f"diameter {item.get('diameter')} {units}, "
                    f"depth {item.get('depth')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_counterbore_hole":
                item = dict(step)
                summary["counterbores"].append(item)
                add_count(summary["counts"], "counterbores")

                summary["readable_summary"].append(
                    f"Counterbore hole in '{item.get('target')}': "
                    f"through diameter {item.get('hole_diameter')} {units}, "
                    f"depth {item.get('depth')} {units}, "
                    f"counterbore diameter {item.get('counterbore_diameter')} {units}, "
                    f"counterbore depth {item.get('counterbore_depth')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_countersink_hole":
                item = dict(step)
                summary["countersinks"].append(item)
                add_count(summary["counts"], "countersinks")

                summary["readable_summary"].append(
                    f"Countersink hole in '{item.get('target')}': "
                    f"through diameter {item.get('hole_diameter')} {units}, "
                    f"depth {item.get('depth')} {units}, "
                    f"countersink diameter {item.get('countersink_diameter')} {units}, "
                    f"angle {item.get('countersink_angle')} degrees, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_slot":
                item = dict(step)
                summary["slots"].append(item)
                add_count(summary["counts"], "slots")

                summary["readable_summary"].append(
                    f"Slot in '{item.get('target')}': "
                    f"{item.get('length')} × {item.get('width')} × "
                    f"{item.get('depth')} {units}, "
                    f"orientation {item.get('orientation')}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_rectangular_cutout":
                item = dict(step)
                summary["rectangular_cutouts"].append(item)
                add_count(summary["counts"], "rectangular_cutouts")

                summary["readable_summary"].append(
                    f"Rectangular cutout in '{item.get('target')}': "
                    f"{item.get('length')} × {item.get('width')} × "
                    f"{item.get('depth')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation in {"create_rectangular_pocket", "create_circular_pocket"}:
                item = dict(step)
                summary["pockets"].append(item)
                add_count(summary["counts"], "pockets")

                if operation == "create_rectangular_pocket":
                    summary["readable_summary"].append(
                        f"Rectangular pocket in '{item.get('target')}': "
                        f"{item.get('length')} × {item.get('width')} × "
                        f"{item.get('depth')} {units}, "
                        f"center {item.get('position')}"
                    )
                else:
                    summary["readable_summary"].append(
                        f"Circular pocket in '{item.get('target')}': "
                        f"diameter {item.get('diameter')} {units}, "
                        f"depth {item.get('depth')} {units}, "
                        f"center {item.get('position')}"
                    )

            elif operation == "create_edge_notch":
                item = dict(step)
                summary["edge_notches"].append(item)
                add_count(summary["counts"], "edge_notches")

                summary["readable_summary"].append(
                    f"Edge notch on '{item.get('target')}': "
                    f"edge {item.get('edge')}, "
                    f"{item.get('length')} × {item.get('width')} × "
                    f"{item.get('depth')} {units}, "
                    f"position {item.get('position')}"
                )

            elif operation in {"create_rectangular_boss", "create_cylindrical_boss"}:
                item = dict(step)
                summary["bosses"].append(item)
                add_count(summary["counts"], "bosses")

                if operation == "create_rectangular_boss":
                    summary["readable_summary"].append(
                        f"Rectangular boss on '{item.get('target')}': "
                        f"{item.get('length')} × {item.get('width')} × "
                        f"{item.get('height')} {units}, "
                        f"center {item.get('position')}"
                    )
                else:
                    summary["readable_summary"].append(
                        f"Cylindrical boss on '{item.get('target')}': "
                        f"diameter {item.get('diameter')} {units}, "
                        f"height {item.get('height')} {units}, "
                        f"center {item.get('position')}"
                    )

            elif operation == "create_mounting_standoff":
                item = dict(step)
                summary["standoffs"].append(item)
                add_count(summary["counts"], "standoffs")

                summary["readable_summary"].append(
                    f"Mounting standoff on '{item.get('target')}': "
                    f"outer diameter {item.get('outer_diameter')} {units}, "
                    f"inner diameter {item.get('inner_diameter')} {units}, "
                    f"height {item.get('height')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_hole_on_boss":
                item = dict(step)
                summary["boss_holes"].append(item)
                add_count(summary["counts"], "boss_holes")

                summary["readable_summary"].append(
                    f"Hole on boss '{item.get('target')}': "
                    f"diameter {item.get('diameter')} {units}, "
                    f"depth {item.get('depth')} {units}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_rib":
                item = dict(step)
                summary["ribs"].append(item)
                add_count(summary["counts"], "ribs")

                summary["readable_summary"].append(
                    f"Rib on '{item.get('target')}': "
                    f"length {item.get('length')} {units}, "
                    f"thickness {item.get('thickness')} {units}, "
                    f"height {item.get('height')} {units}, "
                    f"orientation {item.get('orientation')}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_gusset":
                item = dict(step)
                summary["gussets"].append(item)
                add_count(summary["counts"], "gussets")

                summary["readable_summary"].append(
                    f"Gusset on '{item.get('target')}': "
                    f"length {item.get('length')} {units}, "
                    f"height {item.get('height')} {units}, "
                    f"thickness {item.get('thickness')} {units}, "
                    f"orientation {item.get('orientation')}, "
                    f"center {item.get('position')}"
                )

            elif operation == "create_raised_border":
                item = dict(step)
                summary["raised_borders"].append(item)
                add_count(summary["counts"], "raised_borders")

                summary["readable_summary"].append(
                    f"Raised border on '{item.get('target')}': "
                    f"border width {item.get('border_width')} {units}, "
                    f"height {item.get('height')} {units}, "
                    f"scope {item.get('scope')}"
                )

            elif operation == "create_hole_pattern":
                item = dict(step)
                total_holes = hole_pattern_total(step)
                item["total_holes"] = total_holes

                summary["hole_patterns"].append(item)
                add_count(summary["counts"], "hole_patterns")
                add_count(summary["counts"], "pattern_holes_total", total_holes)

                summary["readable_summary"].append(
                    f"Hole pattern in '{item.get('target')}': "
                    f"{item.get('rows')} row(s) × {item.get('columns')} column(s), "
                    f"{total_holes} hole(s), "
                    f"diameter {item.get('diameter')} {units}, "
                    f"first position {item.get('first_position')}, "
                    f"spacing X {item.get('spacing_x')} {units}, "
                    f"spacing Y {item.get('spacing_y')} {units}"
                )

            elif operation == "create_linear_pattern":
                item = dict(step)
                nested = item.get("feature", {})
                nested_op = feature_operation(nested)
                nested_pos = nested_position(nested)

                summary["linear_patterns"].append(item)
                add_count(summary["counts"], "linear_patterns")

                summary["readable_summary"].append(
                    f"Linear pattern: count {item.get('count')}, "
                    f"spacing {item.get('spacing')}, "
                    f"nested feature {nested_op}, "
                    f"nested feature position {nested_pos}"
                )

            elif operation == "create_circular_pattern":
                item = dict(step)
                nested = item.get("feature", {})
                nested_op = feature_operation(nested)

                summary["circular_patterns"].append(item)
                add_count(summary["counts"], "circular_patterns")

                summary["readable_summary"].append(
                    f"Circular pattern: count {item.get('count')}, "
                    f"center {item.get('center')}, "
                    f"axis {item.get('axis', 'Z')}, "
                    f"total angle {item.get('total_angle', 360)}, "
                    f"nested feature {nested_op}"
                )

            elif operation == "mirror_feature":
                item = dict(step)
                nested = item.get("feature", {})
                nested_op = feature_operation(nested)

                summary["mirrors"].append(item)
                add_count(summary["counts"], "mirrors")

                summary["readable_summary"].append(
                    f"Mirror feature across {item.get('mirror_plane')} plane "
                    f"at origin {item.get('plane_origin')}, "
                    f"include original {item.get('include_original', True)}, "
                    f"feature {nested_op}"
                )

            elif operation == "create_fillet":
                item = dict(step)
                summary["fillets"].append(item)
                add_count(summary["counts"], "fillets")

                summary["readable_summary"].append(
                    f"Fillet on '{item.get('target')}': "
                    f"radius {item.get('radius')} {units}, "
                    f"scope {item.get('scope')}"
                )

            elif operation == "create_chamfer":
                item = dict(step)
                summary["chamfers"].append(item)
                add_count(summary["counts"], "chamfers")

                summary["readable_summary"].append(
                    f"Chamfer on '{item.get('target')}': "
                    f"distance {item.get('distance')} {units}, "
                    f"scope {item.get('scope')}"
                )

            else:
                add_count(summary["counts"], "unsupported_or_unknown")

                summary["readable_summary"].append(
                    f"Unsupported or unknown operation skipped in summary: {operation}"
                )

            if operation is not None:
                add_count(summary["counts"], f"operation:{operation}")

            summary["counts"]["estimated_holes_total"] += estimate_holes_in_feature(step)

        summary["counts"]["total_features"] = (
            summary["counts"]["total_steps"]
            - summary["counts"].get("unsupported_or_unknown", 0)
        )

        return summary

    # ------------------------------------------------------------------
    # Repair loop
    # ------------------------------------------------------------------

    def _repair_cad_plan_if_needed(
        self,
        prompt,
        canonical_input,
        cad_plan,
        normalized_cad_plan,
        cad_validation,
    ):
        repair_attempts = 0
        repair_history = []

        while (
            not cad_validation.get("valid", False)
            and repair_attempts < self.max_repair_attempts
        ):
            repair_attempts += 1

            validation_errors = cad_validation.get("errors", [])

            repair_history.append(
                {
                    "attempt": repair_attempts,
                    "errors_before_repair": validation_errors,
                }
            )

            repaired_cad_plan = self.mistral.repair_cad_plan(
                original_prompt=prompt,
                canonical_input=canonical_input,
                current_cad_plan=cad_plan,
                normalized_cad_plan=normalized_cad_plan,
                validation_errors=validation_errors,
            )

            cad_plan = repaired_cad_plan
            normalized_cad_plan = self.normalizer.normalize_cad_plan(cad_plan)

            cad_validation = self.validator.validate_cad_plan(
                cad_plan=normalized_cad_plan,
                canonical_input=canonical_input,
            )

            repair_history[-1]["valid_after_repair"] = cad_validation.get(
                "valid", False
            )
            repair_history[-1]["errors_after_repair"] = cad_validation.get(
                "errors", []
            )

        return cad_plan, normalized_cad_plan, cad_validation, repair_history

    # ------------------------------------------------------------------
    # Main run method
    # ------------------------------------------------------------------

    def run(self, prompt, plan_file=None, excel_file=None, backend=None):
        requested_backend = backend if backend is not None else self.backend
        selected_backend = self._normalize_backend(requested_backend)
        backend_warning = self._get_backend_warning(requested_backend)

        if backend_warning:
            selected_backend = "freecad"

        if plan_file:
            ocr_result = self.ocr.extract(plan_file)
        else:
            ocr_result = {
                "tool": "ocr_extractor",
                "status": "skipped",
                "reason": "No 2D plan uploaded. Using text prompt only.",
                "detected_dimensions": [],
                "detected_text": "",
            }

        if plan_file:
            geometry_result = self.geometry.extract(plan_file)
        else:
            geometry_result = {
                "tool": "geometry_extractor",
                "status": "skipped",
                "reason": "No 2D plan uploaded. Using text prompt only.",
                "detected_shapes": [],
                "detected_geometry": {},
            }

        if excel_file:
            excel_result = self.excel.parse(excel_file)
        else:
            excel_result = {
                "tool": "excel_parser",
                "status": "skipped",
                "reason": "No Excel file uploaded. Using text prompt only.",
                "constraints": {},
            }

        canonical_input = self.aggregator.build(
            prompt=prompt,
            ocr_result=ocr_result,
            geometry_result=geometry_result,
            excel_result=excel_result,
        )

        canonical_input["ready_for_reasoning"] = True
        canonical_input["missing_information"] = []

        canonical_validation = self.validator.validate_canonical_input(
            canonical_input
        )

        if not canonical_validation["valid"]:
            return {
                "status": "canonical_input_invalid",
                "backend_requested": requested_backend,
                "backend": selected_backend,
                "backend_warning": backend_warning,
                "ocr_result": ocr_result,
                "geometry_result": geometry_result,
                "excel_result": excel_result,
                "canonical_input": canonical_input,
                "cad_plan": {},
                "normalized_cad_plan": {},
                "model_summary": {},
                "validation": canonical_validation,
                "repair_history": [],
                "generation": {},
                "generation_message": (
                    "CAD generation was skipped because the canonical input "
                    "did not pass validation."
                ),
            }

        cad_plan = self.mistral.create_cad_plan(canonical_input)
        normalized_cad_plan = self.normalizer.normalize_cad_plan(cad_plan)

        cad_validation = self.validator.validate_cad_plan(
            cad_plan=normalized_cad_plan,
            canonical_input=canonical_input,
        )

        cad_plan, normalized_cad_plan, cad_validation, repair_history = (
            self._repair_cad_plan_if_needed(
                prompt=prompt,
                canonical_input=canonical_input,
                cad_plan=cad_plan,
                normalized_cad_plan=normalized_cad_plan,
                cad_validation=cad_validation,
            )
        )

        model_summary = self.build_model_summary(normalized_cad_plan)

        if cad_validation["valid"]:
            generation_result = self._generate_cad_model(
                normalized_cad_plan=normalized_cad_plan,
                backend=selected_backend,
            )
        else:
            generation_result = {
                "success": False,
                "backend": selected_backend,
                "message": (
                    "CAD generation was skipped because the normalized CAD plan "
                    "did not pass validation."
                ),
                "error": "cad_plan_invalid",
            }

        return {
            "status": "success" if cad_validation["valid"] else "cad_plan_invalid",
            "backend_requested": requested_backend,
            "backend": selected_backend,
            "backend_warning": backend_warning,
            "ocr_result": ocr_result,
            "geometry_result": geometry_result,
            "excel_result": excel_result,
            "canonical_input": canonical_input,
            "cad_plan": cad_plan,
            "normalized_cad_plan": normalized_cad_plan,
            "model_summary": model_summary,
            "validation": cad_validation,
            "repair_history": repair_history,
            "generation": generation_result,
        }