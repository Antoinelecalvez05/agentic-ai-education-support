from pathlib import Path
import json
import os
import subprocess
import math
from dotenv import load_dotenv


load_dotenv()


class FreeCADGenerator:
    """
    Generates and executes a FreeCAD Python script from a validated CAD plan.

    Important:
    - Uses absolute paths for generated files.
    - Verifies that the FCStd file is really created.
    - STEP export is treated as optional: if STEP export fails, the FCStd file can still be valid.

    Main fixes:
    - Stores original base plate metadata.
    - Uses reference top/bottom Z instead of changing global ZMax/ZMin.
    - Prevents cylindrical bosses from floating above the plate after another boss has already been added.
    - Makes chamfer/fillet edge selection more reliable.
    - Keeps chamfer/fillet failures non-blocking so FCStd export still happens.
    - Applies removeSplitter() after booleans to improve shape robustness.
    """

    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.freecad_cmd_path = os.getenv(
            "FREECAD_CMD_PATH",
            "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
        )

        self.timeout_seconds = int(os.getenv("FREECAD_TIMEOUT_SECONDS", "300"))

    def generate(self, cad_plan, filename="generated_model"):
        script_path = (self.output_dir / f"{filename}.py").resolve()
        json_path = (self.output_dir / f"{filename}_cad_plan.json").resolve()
        fcstd_path = (self.output_dir / f"{filename}.FCStd").resolve()
        step_path = (self.output_dir / f"{filename}.step").resolve()

        for path in [script_path, json_path, fcstd_path, step_path]:
            if path.exists():
                path.unlink()

        try:
            script_content = self._build_freecad_script(
                cad_plan=cad_plan,
                filename=filename,
                fcstd_path=fcstd_path,
                step_path=step_path,
            )
        except Exception as error:
            return {
                "status": "freecad_script_build_failed",
                "script_path": None,
                "json_path": None,
                "fcstd_path": None,
                "step_path": None,
                "freecad_cmd_path": self.freecad_cmd_path,
                "file_check": {
                    "expected_fcstd_path": str(fcstd_path),
                    "expected_step_path": str(step_path),
                    "fcstd_exists": fcstd_path.exists(),
                    "step_exists": step_path.exists(),
                    "output_dir": str(self.output_dir),
                },
                "execution": {
                    "success": False,
                    "error": "Failed to build FreeCAD script.",
                    "details": str(error),
                    "stdout": "",
                    "stderr": "",
                },
            }

        with open(script_path, "w", encoding="utf-8") as file:
            file.write(script_content)

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(cad_plan, file, indent=4)

        execution_result = self._run_freecad_script(script_path)

        fcstd_exists = fcstd_path.exists()
        step_exists = step_path.exists()

        if execution_result["success"] and not fcstd_exists:
            status = "freecad_file_missing"
        elif execution_result["success"]:
            status = "generated"
        else:
            status = "freecad_execution_failed"

        return {
            "status": status,
            "script_path": str(script_path),
            "json_path": str(json_path),
            "fcstd_path": str(fcstd_path) if fcstd_exists else None,
            "step_path": str(step_path) if step_exists else None,
            "freecad_cmd_path": self.freecad_cmd_path,
            "file_check": {
                "expected_fcstd_path": str(fcstd_path),
                "expected_step_path": str(step_path),
                "fcstd_exists": fcstd_exists,
                "step_exists": step_exists,
                "output_dir": str(self.output_dir),
            },
            "execution": execution_result,
        }

    def _run_freecad_script(self, script_path):
        if not Path(self.freecad_cmd_path).exists():
            return {
                "success": False,
                "error": "FreeCAD command-line executable was not found.",
                "details": f"Checked path: {self.freecad_cmd_path}",
                "stdout": "",
                "stderr": "",
            }

        try:
            completed_process = subprocess.run(
                [self.freecad_cmd_path, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            return {
                "success": completed_process.returncode == 0,
                "returncode": completed_process.returncode,
                "stdout": completed_process.stdout,
                "stderr": completed_process.stderr,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "FreeCAD execution timed out.",
                "details": (
                    f"The FreeCAD script took more than "
                    f"{self.timeout_seconds} seconds to run."
                ),
                "stdout": "",
                "stderr": "",
            }

        except Exception as error:
            return {
                "success": False,
                "error": "Unexpected error while running FreeCAD.",
                "details": str(error),
                "stdout": "",
                "stderr": "",
            }

    def _normalize_operation_name(self, operation):
        aliases = {
            "box": "create_box",
            "cylinder": "create_cylinder",
            "hole": "create_hole",
            "slot": "create_slot",
            "rectangular_cutout": "create_rectangular_cutout",
            "hole_pattern": "create_hole_pattern",
            "fillet": "create_fillet",
            "chamfer": "create_chamfer",
            "counterbore_hole": "create_counterbore_hole",
            "countersink_hole": "create_countersink_hole",
            "edge_notch": "create_edge_notch",
            "rectangular_pocket": "create_rectangular_pocket",
            "circular_pocket": "create_circular_pocket",
            "rectangular_boss": "create_rectangular_boss",
            "cylindrical_boss": "create_cylindrical_boss",
            "threaded_hole": "create_threaded_hole",
            "linear_pattern": "create_linear_pattern",
            "circular_pattern": "create_circular_pattern",
            "mirror": "mirror_feature",
        }

        return aliases.get(operation, operation)

    def _build_freecad_script(self, cad_plan, filename, fcstd_path, step_path):
        units = cad_plan.get("units", "mm")
        steps = cad_plan.get("steps", [])

        lines = []

        lines.append("import FreeCAD as App")
        lines.append("import Part")
        lines.append("import os")
        lines.append("import math")
        lines.append("")
        lines.append("doc = App.newDocument('AI_Generated_CAD_Model')")
        lines.append("objects = {}")
        lines.append("object_meta = {}")
        lines.append("")
        lines.append("SCOPE_ALIASES = {")
        lines.append("    'top_outer_edges': 'base_top_outer_edges',")
        lines.append("    'bottom_outer_edges': 'base_bottom_outer_edges',")
        lines.append("    'outer_vertical_edges': 'base_outer_vertical_edges',")
        lines.append("    'all_outer_edges': 'base_all_outer_edges',")
        lines.append("}")
        lines.append("")
        lines.append("def normalize_scope(scope):")
        lines.append("    if scope is None:")
        lines.append("        return None")
        lines.append("    return SCOPE_ALIASES.get(scope, scope)")
        lines.append("")
        lines.append("def is_close(a, b, tolerance=0.001):")
        lines.append("    return abs(a - b) <= tolerance")
        lines.append("")
        lines.append("def edge_vertices(edge):")
        lines.append("    return [vertex.Point for vertex in edge.Vertexes]")
        lines.append("")
        lines.append("def is_vertical_edge(edge):")
        lines.append("    points = edge_vertices(edge)")
        lines.append("    if len(points) < 2:")
        lines.append("        return False")
        lines.append("    p1, p2 = points[0], points[-1]")
        lines.append(
            "    return is_close(p1.x, p2.x) and is_close(p1.y, p2.y) "
            "and not is_close(p1.z, p2.z)"
        )
        lines.append("")
        lines.append("def is_horizontal_edge(edge):")
        lines.append("    points = edge_vertices(edge)")
        lines.append("    if len(points) < 2:")
        lines.append("        return False")
        lines.append("    p1, p2 = points[0], points[-1]")
        lines.append("    return is_close(p1.z, p2.z)")
        lines.append("")
        lines.append("def get_reference_bbox_values(shape, meta=None):")
        lines.append("    bbox = shape.BoundBox")
        lines.append("    if meta is None:")
        lines.append("        meta = {}")
        lines.append("    return {")
        lines.append("        'x_min': meta.get('x_min', bbox.XMin),")
        lines.append("        'x_max': meta.get('x_max', bbox.XMax),")
        lines.append("        'y_min': meta.get('y_min', bbox.YMin),")
        lines.append("        'y_max': meta.get('y_max', bbox.YMax),")
        lines.append("        'z_min': meta.get('base_bottom_z', bbox.ZMin),")
        lines.append("        'z_max': meta.get('base_top_z', bbox.ZMax),")
        lines.append("    }")
        lines.append("")
        lines.append("def edge_on_reference_outer(edge, ref):")
        lines.append("    points = edge_vertices(edge)")
        lines.append("    if len(points) < 2:")
        lines.append("        return False")
        lines.append("")
        lines.append("    on_x_min = all(is_close(p.x, ref['x_min']) for p in points)")
        lines.append("    on_x_max = all(is_close(p.x, ref['x_max']) for p in points)")
        lines.append("    on_y_min = all(is_close(p.y, ref['y_min']) for p in points)")
        lines.append("    on_y_max = all(is_close(p.y, ref['y_max']) for p in points)")
        lines.append("")
        lines.append("    return on_x_min or on_x_max or on_y_min or on_y_max")
        lines.append("")
        lines.append("def select_edges_by_scope(shape, scope, meta=None):")
        lines.append("    scope = normalize_scope(scope)")
        lines.append("    ref = get_reference_bbox_values(shape, meta)")
        lines.append("    selected_edges = []")
        lines.append("")
        lines.append("    for edge in shape.Edges:")
        lines.append("        points = edge_vertices(edge)")
        lines.append("        if len(points) < 2:")
        lines.append("            continue")
        lines.append("")
        lines.append("        if scope in [")
        lines.append("            'base_top_outer_edges',")
        lines.append("            'base_bottom_outer_edges',")
        lines.append("            'base_outer_vertical_edges',")
        lines.append("            'base_all_outer_edges',")
        lines.append("        ]:")
        lines.append("            if not edge_on_reference_outer(edge, ref):")
        lines.append("                continue")
        lines.append("")
        lines.append("        if scope == 'base_outer_vertical_edges':")
        lines.append("            if is_vertical_edge(edge):")
        lines.append("                selected_edges.append(edge)")
        lines.append("")
        lines.append("        elif scope == 'base_top_outer_edges':")
        lines.append("            if is_horizontal_edge(edge) and all(is_close(p.z, ref['z_max']) for p in points):")
        lines.append("                selected_edges.append(edge)")
        lines.append("")
        lines.append("        elif scope == 'base_bottom_outer_edges':")
        lines.append("            if is_horizontal_edge(edge) and all(is_close(p.z, ref['z_min']) for p in points):")
        lines.append("                selected_edges.append(edge)")
        lines.append("")
        lines.append("        elif scope == 'base_all_outer_edges':")
        lines.append("            selected_edges.append(edge)")
        lines.append("")
        lines.append("        elif scope == 'global_top_edges':")
        lines.append("            bbox = shape.BoundBox")
        lines.append("            if is_horizontal_edge(edge) and all(is_close(p.z, bbox.ZMax) for p in points):")
        lines.append("                selected_edges.append(edge)")
        lines.append("")
        lines.append("        elif scope == 'global_bottom_edges':")
        lines.append("            bbox = shape.BoundBox")
        lines.append("            if is_horizontal_edge(edge) and all(is_close(p.z, bbox.ZMin) for p in points):")
        lines.append("                selected_edges.append(edge)")
        lines.append("")
        lines.append("        elif scope == 'global_vertical_edges':")
        lines.append("            if is_vertical_edge(edge):")
        lines.append("                selected_edges.append(edge)")
        lines.append("")
        lines.append("        else:")
        lines.append("            print('WARNING: Unsupported edge scope:', scope)")
        lines.append("            return []")
        lines.append("")
        lines.append("    return selected_edges")
        lines.append("")
        lines.append("def get_top_z(shape):")
        lines.append("    return shape.BoundBox.ZMax")
        lines.append("")
        lines.append("def get_bottom_z(shape):")
        lines.append("    return shape.BoundBox.ZMin")
        lines.append("")
        lines.append("def get_reference_top_z(target_name, shape):")
        lines.append("    meta = object_meta.get(target_name)")
        lines.append("    if meta and 'base_top_z' in meta:")
        lines.append("        return meta['base_top_z']")
        lines.append("    return shape.BoundBox.ZMax")
        lines.append("")
        lines.append("def get_reference_bottom_z(target_name, shape):")
        lines.append("    meta = object_meta.get(target_name)")
        lines.append("    if meta and 'base_bottom_z' in meta:")
        lines.append("        return meta['base_bottom_z']")
        lines.append("    return shape.BoundBox.ZMin")
        lines.append("")
        lines.append("def get_reference_height(target_name, shape):")
        lines.append("    meta = object_meta.get(target_name)")
        lines.append("    if meta and 'height' in meta:")
        lines.append("        return meta['height']")
        lines.append("    bbox = shape.BoundBox")
        lines.append("    return bbox.ZMax - bbox.ZMin")
        lines.append("")
        lines.append("def clean_shape(shape):")
        lines.append("    try:")
        lines.append("        return shape.removeSplitter()")
        lines.append("    except Exception:")
        lines.append("        return shape")
        lines.append("")
        lines.append("def register_box_meta(name, x, y, z, length, width, height):")
        lines.append("    object_meta[name] = {")
        lines.append("        'type': 'box_like',")
        lines.append("        'x_min': x,")
        lines.append("        'x_max': x + length,")
        lines.append("        'y_min': y,")
        lines.append("        'y_max': y + width,")
        lines.append("        'base_bottom_z': z,")
        lines.append("        'base_top_z': z + height,")
        lines.append("        'length': length,")
        lines.append("        'width': width,")
        lines.append("        'height': height,")
        lines.append("    }")
        lines.append("")
        lines.append(f"# Units: {units}")
        lines.append("")

        for step in steps:
            operation = step.get("operation") or step.get("action") or step.get("type")
            operation = self._normalize_operation_name(operation)

            if operation == "create_box":
                lines.extend(self._create_box_code(step))

            elif operation == "create_rounded_rectangle_plate":
                lines.extend(self._create_rounded_rectangle_plate_code(step))

            elif operation == "create_cylinder":
                lines.extend(self._create_cylinder_code(step))

            elif operation == "create_hole":
                lines.extend(self._create_hole_code(step))

            elif operation == "create_slot":
                lines.extend(self._create_slot_code(step))

            elif operation == "create_rectangular_cutout":
                lines.extend(self._create_rectangular_cutout_code(step))

            elif operation == "create_hole_pattern":
                lines.extend(self._create_hole_pattern_code(step))

            elif operation == "create_fillet":
                lines.extend(self._create_fillet_code(step))

            elif operation == "create_chamfer":
                lines.extend(self._create_chamfer_code(step))

            elif operation == "create_counterbore_hole":
                lines.extend(self._create_counterbore_hole_code(step))

            elif operation == "create_countersink_hole":
                lines.extend(self._create_countersink_hole_code(step))

            elif operation == "create_edge_notch":
                lines.extend(self._create_edge_notch_code(step))

            elif operation == "create_rectangular_pocket":
                lines.extend(self._create_rectangular_pocket_code(step))

            elif operation == "create_circular_pocket":
                lines.extend(self._create_circular_pocket_code(step))

            elif operation == "create_rectangular_boss":
                lines.extend(self._create_rectangular_boss_code(step))

            elif operation == "create_cylindrical_boss":
                lines.extend(self._create_cylindrical_boss_code(step))

            elif operation == "create_threaded_hole":
                lines.extend(self._create_threaded_hole_code(step))

            elif operation == "create_linear_pattern":
                lines.extend(self._create_linear_pattern_code(step))

            elif operation == "create_circular_pattern":
                lines.extend(self._create_circular_pattern_code(step))

            elif operation == "mirror_feature":
                lines.extend(self._create_mirror_feature_code(step))

            else:
                raise ValueError(
                    f"Unsupported operation reached FreeCAD generator: {operation}"
                )

        lines.append("")
        lines.append("doc.recompute()")
        lines.append("")
        lines.append(f"fcstd_path = r'{str(fcstd_path)}'")
        lines.append(f"step_path = r'{str(step_path)}'")
        lines.append("")
        lines.append("visible_objects = [")
        lines.append("    obj for obj in doc.Objects")
        lines.append("    if hasattr(obj, 'Shape') and not obj.Shape.isNull()")
        lines.append("]")
        lines.append("")
        lines.append("if not visible_objects:")
        lines.append("    raise ValueError('No valid visible shape was generated.')")
        lines.append("")
        lines.append("for obj in visible_objects:")
        lines.append("    if not obj.Shape.isValid():")
        lines.append("        raise ValueError(f'Generated shape is invalid: {obj.Name}')")
        lines.append("")
        lines.append("output_folder = os.path.dirname(fcstd_path)")
        lines.append("if output_folder and not os.path.exists(output_folder):")
        lines.append("    os.makedirs(output_folder, exist_ok=True)")
        lines.append("")
        lines.append("print('Saving FCStd to:', fcstd_path)")
        lines.append("doc.saveAs(fcstd_path)")
        lines.append("doc.recompute()")
        lines.append("")
        lines.append("if not os.path.exists(fcstd_path):")
        lines.append(
            "    raise RuntimeError("
            "f'FCStd file was not created at expected path: {fcstd_path}'"
            ")"
        )
        lines.append("")
        lines.append("print('Generated FCStd:', fcstd_path)")
        lines.append("print('FCStd exists:', os.path.exists(fcstd_path))")
        lines.append("")
        lines.append("try:")
        lines.append("    print('Exporting STEP to:', step_path)")
        lines.append("    Part.export(visible_objects, step_path)")
        lines.append("    print('Generated STEP:', step_path)")
        lines.append("    print('STEP exists:', os.path.exists(step_path))")
        lines.append("except Exception as export_error:")
        lines.append(
            "    print('STEP export failed, but FCStd was created:', export_error)"
        )

        return "\n".join(lines)

    def _safe_name(self, name):
        if not name:
            return "unnamed_object"

        safe = "".join(char if char.isalnum() or char == "_" else "_" for char in name)

        if safe[0].isdigit():
            safe = "_" + safe

        return safe

    def _create_box_code(self, step):
        name = step.get("name", "box")
        safe_name = self._safe_name(name)

        length = step.get("length")
        width = step.get("width")
        height = step.get("height")
        position = step.get("position", [0, 0, 0])

        x, y, z = position

        return [
            f"# Create box: {name}",
            f"{safe_name}_shape = Part.makeBox({length}, {width}, {height})",
            f"{safe_name}_shape.translate(App.Vector({x}, {y}, {z}))",
            f"{safe_name}_obj = doc.addObject('Part::Feature', '{name}')",
            f"{safe_name}_obj.Shape = {safe_name}_shape",
            f"objects['{name}'] = {safe_name}_obj",
            f"register_box_meta('{name}', {x}, {y}, {z}, {length}, {width}, {height})",
            "doc.recompute()",
            "",
        ]

    def _create_rounded_rectangle_plate_code(self, step):
        name = step.get("name", "base_plate")
        safe_name = self._safe_name(name)

        length = step.get("length")
        width = step.get("width")
        height = step.get("height")
        corner_radius = step.get("corner_radius")
        position = step.get("position", [0, 0, 0])

        x, y, z = position

        return [
            f"# Create rounded rectangular plate: {name}",
            f"{safe_name}_shape = Part.makeBox({length}, {width}, {height})",
            f"{safe_name}_shape.translate(App.Vector({x}, {y}, {z}))",
            f"register_box_meta('{name}', {x}, {y}, {z}, {length}, {width}, {height})",
            f"rounded_edges = select_edges_by_scope({safe_name}_shape, 'base_outer_vertical_edges', object_meta.get('{name}'))",
            f"if not rounded_edges:",
            f"    raise ValueError('No vertical edges found for rounded rectangle plate.')",
            f"{safe_name}_shape = clean_shape({safe_name}_shape.makeFillet({corner_radius}, rounded_edges))",
            f"{safe_name}_obj = doc.addObject('Part::Feature', '{name}')",
            f"{safe_name}_obj.Shape = {safe_name}_shape",
            f"objects['{name}'] = {safe_name}_obj",
            "doc.recompute()",
            "",
        ]

    def _create_cylinder_code(self, step):
        name = step.get("name", "cylinder")
        safe_name = self._safe_name(name)

        radius = step.get("radius")
        diameter = step.get("diameter")
        height = step.get("height")
        position = step.get("position", [0, 0, 0])

        if radius is None and diameter is not None:
            radius = diameter / 2

        x, y, z = position

        return [
            f"# Create cylinder: {name}",
            f"{safe_name}_shape = Part.makeCylinder({radius}, {height})",
            f"{safe_name}_shape.translate(App.Vector({x}, {y}, {z}))",
            f"{safe_name}_obj = doc.addObject('Part::Feature', '{name}')",
            f"{safe_name}_obj.Shape = {safe_name}_shape",
            f"objects['{name}'] = {safe_name}_obj",
            "doc.recompute()",
            "",
        ]

    def _create_hole_code(self, step):
        target = step.get("target", "base_plate")
        diameter = step.get("diameter")
        depth = step.get("depth")
        position = step.get("position", [0, 0, 0])

        x, y, z = position
        radius = diameter / 2

        return [
            f"# Create circular through-hole in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
            f"    cut_depth = {depth} + 2",
            f"    hole_shape = Part.makeCylinder({radius}, cut_depth)",
            f"    hole_shape.translate(App.Vector({x}, {y}, bottom_z - 1))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(hole_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for hole: {target}')",
            "",
        ]

    def _create_slot_code(self, step):
        target = step.get("target", "base_plate")
        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        position = step.get("position", [0, 0, 0])
        orientation = step.get("orientation", "x")

        x, y, z = position

        radius = width / 2
        center_distance = length - width

        if orientation == "x":
            left_x = x - center_distance / 2
            right_x = x + center_distance / 2

            return [
                f"# Create horizontal rounded slot in: {target}",
                f"if '{target}' in objects:",
                f"    target_obj = objects['{target}']",
                f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
                f"    slot_rect = Part.makeBox({center_distance}, {width}, {depth + 2})",
                f"    slot_rect.translate(App.Vector({left_x}, {y - radius}, bottom_z - 1))",
                f"    left_circle = Part.makeCylinder({radius}, {depth + 2})",
                f"    left_circle.translate(App.Vector({left_x}, {y}, bottom_z - 1))",
                f"    right_circle = Part.makeCylinder({radius}, {depth + 2})",
                f"    right_circle.translate(App.Vector({right_x}, {y}, bottom_z - 1))",
                f"    slot_shape = clean_shape(slot_rect.fuse(left_circle).fuse(right_circle))",
                f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(slot_shape))",
                f"    doc.recompute()",
                f"else:",
                f"    raise ValueError('Target object not found for slot: {target}')",
                "",
            ]

        if orientation == "y":
            bottom_y = y - center_distance / 2
            top_y = y + center_distance / 2

            return [
                f"# Create vertical rounded slot in: {target}",
                f"if '{target}' in objects:",
                f"    target_obj = objects['{target}']",
                f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
                f"    slot_rect = Part.makeBox({width}, {center_distance}, {depth + 2})",
                f"    slot_rect.translate(App.Vector({x - radius}, {bottom_y}, bottom_z - 1))",
                f"    bottom_circle = Part.makeCylinder({radius}, {depth + 2})",
                f"    bottom_circle.translate(App.Vector({x}, {bottom_y}, bottom_z - 1))",
                f"    top_circle = Part.makeCylinder({radius}, {depth + 2})",
                f"    top_circle.translate(App.Vector({x}, {top_y}, bottom_z - 1))",
                f"    slot_shape = clean_shape(slot_rect.fuse(bottom_circle).fuse(top_circle))",
                f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(slot_shape))",
                f"    doc.recompute()",
                f"else:",
                f"    raise ValueError('Target object not found for slot: {target}')",
                "",
            ]

        raise ValueError(f"Invalid slot orientation: {orientation}")

    def _create_rectangular_cutout_code(self, step):
        target = step.get("target", "base_plate")
        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        position = step.get("position", [0, 0, 0])

        x, y, z = position

        return [
            f"# Create rectangular through-cutout in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
            f"    cutout_shape = Part.makeBox({length}, {width}, {depth + 2})",
            f"    cutout_shape.translate(App.Vector({x - length / 2}, {y - width / 2}, bottom_z - 1))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(cutout_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for rectangular cutout: {target}')",
            "",
        ]

    def _create_hole_pattern_code(self, step):
        target = step.get("target", "base_plate")
        rows = step.get("rows")
        columns = step.get("columns")
        diameter = step.get("diameter")
        depth = step.get("depth")
        first_position = step.get("first_position")
        spacing_x = step.get("spacing_x")
        spacing_y = step.get("spacing_y")

        if first_position is None:
            raise ValueError("create_hole_pattern requires first_position.")

        first_x, first_y, first_z = first_position
        radius = diameter / 2

        return [
            f"# Create circular hole pattern in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
            f"    pattern_cutters = []",
            f"    for row in range({rows}):",
            f"        for column in range({columns}):",
            f"            hole_x = {first_x} + column * {spacing_x}",
            f"            hole_y = {first_y} + row * {spacing_y}",
            f"            hole_shape = Part.makeCylinder({radius}, {depth + 2})",
            f"            hole_shape.translate(App.Vector(hole_x, hole_y, bottom_z - 1))",
            f"            pattern_cutters.append(hole_shape)",
            f"    if not pattern_cutters:",
            f"        raise ValueError('No cutters were created for hole pattern.')",
            f"    pattern_tool = pattern_cutters[0]",
            f"    for cutter in pattern_cutters[1:]:",
            f"        pattern_tool = pattern_tool.fuse(cutter)",
            f"    pattern_tool = clean_shape(pattern_tool)",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(pattern_tool))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for hole pattern: {target}')",
            "",
        ]

    def _create_counterbore_hole_code(self, step):
        target = step.get("target", "base_plate")
        position = step.get("position", [0, 0, 0])
        hole_diameter = step.get("hole_diameter")
        depth = step.get("depth")
        counterbore_diameter = step.get("counterbore_diameter")
        counterbore_depth = step.get("counterbore_depth")

        x, y, z = position
        hole_radius = hole_diameter / 2
        counterbore_radius = counterbore_diameter / 2

        return [
            f"# Create counterbore hole in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
            f"    through_hole = Part.makeCylinder({hole_radius}, {depth + 2})",
            f"    through_hole.translate(App.Vector({x}, {y}, bottom_z - 1))",
            f"    counterbore = Part.makeCylinder({counterbore_radius}, {counterbore_depth + 1})",
            f"    counterbore.translate(App.Vector({x}, {y}, top_z - {counterbore_depth}))",
            f"    cut_shape = clean_shape(through_hole.fuse(counterbore))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(cut_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for counterbore hole: {target}')",
            "",
        ]

    def _create_countersink_hole_code(self, step):
        target = step.get("target", "base_plate")
        position = step.get("position", [0, 0, 0])
        hole_diameter = step.get("hole_diameter")
        depth = step.get("depth")
        countersink_diameter = step.get("countersink_diameter")
        countersink_depth = step.get("countersink_depth")
        countersink_angle = step.get("countersink_angle", 90)

        x, y, z = position
        hole_radius = hole_diameter / 2
        countersink_radius = countersink_diameter / 2

        if countersink_depth is None:
            angle_rad = f"math.radians({countersink_angle})"
            depth_expr = (
                f"(({countersink_radius} - {hole_radius}) / "
                f"math.tan({angle_rad} / 2))"
            )
        else:
            depth_expr = str(countersink_depth)

        return [
            f"# Create countersink hole in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    bottom_z = get_reference_bottom_z('{target}', target_obj.Shape)",
            f"    countersink_depth_value = {depth_expr}",
            f"    through_hole = Part.makeCylinder({hole_radius}, {depth + 2})",
            f"    through_hole.translate(App.Vector({x}, {y}, bottom_z - 1))",
            f"    countersink_cone = Part.makeCone({hole_radius}, {countersink_radius}, countersink_depth_value + 0.5)",
            f"    countersink_cone.translate(App.Vector({x}, {y}, top_z - countersink_depth_value))",
            f"    cut_shape = clean_shape(through_hole.fuse(countersink_cone))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(cut_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for countersink hole: {target}')",
            "",
        ]

    def _feature_to_code(self, feature):
        operation = feature.get("operation") or feature.get("action") or feature.get("type")
        operation = self._normalize_operation_name(operation)

        if operation == "create_hole":
            return self._create_hole_code(feature)
        if operation == "create_slot":
            return self._create_slot_code(feature)
        if operation == "create_rectangular_cutout":
            return self._create_rectangular_cutout_code(feature)
        if operation == "create_hole_pattern":
            return self._create_hole_pattern_code(feature)
        if operation == "create_counterbore_hole":
            return self._create_counterbore_hole_code(feature)
        if operation == "create_countersink_hole":
            return self._create_countersink_hole_code(feature)
        if operation == "create_edge_notch":
            return self._create_edge_notch_code(feature)
        if operation == "create_rectangular_pocket":
            return self._create_rectangular_pocket_code(feature)
        if operation == "create_circular_pocket":
            return self._create_circular_pocket_code(feature)
        if operation == "create_rectangular_boss":
            return self._create_rectangular_boss_code(feature)
        if operation == "create_cylindrical_boss":
            return self._create_cylindrical_boss_code(feature)
        if operation == "create_threaded_hole":
            return self._create_threaded_hole_code(feature)

        raise ValueError(f"Unsupported nested feature for pattern/mirror: {operation}")

    def _copy_feature_with_position(self, feature, position):
        copied = dict(feature)
        copied["position"] = position
        return copied

    def _rotate_position_xy(self, position, center, angle_degrees):
        x, y, z = position
        center_x, center_y, center_z = center
        angle_radians = math.radians(angle_degrees)
        dx = x - center_x
        dy = y - center_y

        rotated_x = center_x + dx * math.cos(angle_radians) - dy * math.sin(angle_radians)
        rotated_y = center_y + dx * math.sin(angle_radians) + dy * math.cos(angle_radians)

        return [rotated_x, rotated_y, z]

    def _mirror_position(self, position, mirror_plane, plane_origin):
        x, y, z = position
        origin_x, origin_y, origin_z = plane_origin
        plane = str(mirror_plane).upper()

        if plane in ["YZ", "X"]:
            return [2 * origin_x - x, y, z]
        if plane in ["XZ", "Y"]:
            return [x, 2 * origin_y - y, z]
        if plane in ["XY", "Z"]:
            return [x, y, 2 * origin_z - z]

        raise ValueError(f"Unsupported mirror plane: {mirror_plane}")

    def _create_rectangular_pocket_code(self, step):
        target = step.get("target", "base_plate")
        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        position = step.get("position", [0, 0, 0])

        x, y, z = position

        return [
            f"# Create rectangular pocket in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    pocket_shape = Part.makeBox({length}, {width}, {depth + 0.5})",
            f"    pocket_shape.translate(App.Vector({x - length / 2}, {y - width / 2}, top_z - {depth}))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(pocket_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for rectangular pocket: {target}')",
            "",
        ]

    def _create_circular_pocket_code(self, step):
        target = step.get("target", "base_plate")
        diameter = step.get("diameter")
        depth = step.get("depth")
        position = step.get("position", [0, 0, 0])

        x, y, z = position
        radius = diameter / 2

        return [
            f"# Create circular pocket in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    pocket_shape = Part.makeCylinder({radius}, {depth + 0.5})",
            f"    pocket_shape.translate(App.Vector({x}, {y}, top_z - {depth}))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(pocket_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for circular pocket: {target}')",
            "",
        ]

    def _create_edge_notch_code(self, step):
        target = step.get("target", "base_plate")
        length = step.get("length")
        width = step.get("width")
        depth = step.get("depth")
        position = step.get("position", [0, 0, 0])
        edge = step.get("edge", step.get("side", "left"))

        x, y, z = position

        return [
            f"# Create edge notch in: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    meta = object_meta.get('{target}', {{}})",
            f"    bbox = target_obj.Shape.BoundBox",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    x_min = meta.get('x_min', bbox.XMin)",
            f"    x_max = meta.get('x_max', bbox.XMax)",
            f"    y_min = meta.get('y_min', bbox.YMin)",
            f"    y_max = meta.get('y_max', bbox.YMax)",
            f"    edge_name = '{edge}'",
            f"    if edge_name in ['left', 'x_min']:",
            f"        notch_shape = Part.makeBox({width + 1}, {length}, {depth + 0.5})",
            f"        notch_shape.translate(App.Vector(x_min - 0.5, {y - length / 2}, top_z - {depth}))",
            f"    elif edge_name in ['right', 'x_max']:",
            f"        notch_shape = Part.makeBox({width + 1}, {length}, {depth + 0.5})",
            f"        notch_shape.translate(App.Vector(x_max - {width}, {y - length / 2}, top_z - {depth}))",
            f"    elif edge_name in ['bottom', 'front', 'y_min']:",
            f"        notch_shape = Part.makeBox({length}, {width + 1}, {depth + 0.5})",
            f"        notch_shape.translate(App.Vector({x - length / 2}, y_min - 0.5, top_z - {depth}))",
            f"    elif edge_name in ['top', 'back', 'y_max']:",
            f"        notch_shape = Part.makeBox({length}, {width + 1}, {depth + 0.5})",
            f"        notch_shape.translate(App.Vector({x - length / 2}, y_max - {width}, top_z - {depth}))",
            f"    else:",
            f"        raise ValueError('Unsupported edge for notch: {edge}')",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.cut(notch_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for edge notch: {target}')",
            "",
        ]

    def _create_rectangular_boss_code(self, step):
        target = step.get("target", "base_plate")
        length = step.get("length")
        width = step.get("width")
        height = step.get("height")
        position = step.get("position", [0, 0, 0])

        x, y, z = position

        return [
            f"# Create rectangular boss on: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    boss_shape = Part.makeBox({length}, {width}, {height})",
            f"    boss_shape.translate(App.Vector({x - length / 2}, {y - width / 2}, top_z))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.fuse(boss_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for rectangular boss: {target}')",
            "",
        ]

    def _create_cylindrical_boss_code(self, step):
        target = step.get("target", "base_plate")
        diameter = step.get("diameter")
        radius = step.get("radius")
        height = step.get("height")
        position = step.get("position", [0, 0, 0])

        if diameter is not None:
            radius_value = diameter / 2
        else:
            radius_value = radius

        x, y, z = position

        return [
            f"# Create cylindrical boss on: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    top_z = get_reference_top_z('{target}', target_obj.Shape)",
            f"    boss_shape = Part.makeCylinder({radius_value}, {height})",
            f"    boss_shape.translate(App.Vector({x}, {y}, top_z))",
            f"    target_obj.Shape = clean_shape(target_obj.Shape.fuse(boss_shape))",
            f"    doc.recompute()",
            f"else:",
            f"    raise ValueError('Target object not found for cylindrical boss: {target}')",
            "",
        ]

    def _create_threaded_hole_code(self, step):
        target = step.get("target", "base_plate")
        thread = step.get("thread", "unspecified")
        hole_step = dict(step)
        hole_step["operation"] = "create_hole"

        return [
            f"# Create threaded hole in: {target}; thread callout: {thread}",
            "# Thread is represented as a drilled hole plus a thread callout.",
            "# Full helical thread geometry is intentionally not generated at this stage.",
        ] + self._create_hole_code(hole_step)

    def _create_linear_pattern_code(self, step):
        feature = step.get("feature")
        count = step.get("count")
        spacing = step.get("spacing", [0, 0, 0])

        if not isinstance(feature, dict):
            raise ValueError("create_linear_pattern requires a nested feature dictionary.")

        base_position = feature.get("position")
        if base_position is None:
            raise ValueError("Nested feature in create_linear_pattern requires position.")

        lines = ["# Create linear pattern"]

        for index in range(count):
            patterned_position = [
                base_position[0] + index * spacing[0],
                base_position[1] + index * spacing[1],
                base_position[2] + index * spacing[2],
            ]

            copied_feature = self._copy_feature_with_position(
                feature,
                patterned_position,
            )
            lines.extend(self._feature_to_code(copied_feature))

        return lines

    def _create_circular_pattern_code(self, step):
        feature = step.get("feature")
        count = step.get("count")
        center = step.get("center")
        total_angle = step.get("total_angle", 360)
        angle_step = step.get("angle_step")

        if not isinstance(feature, dict):
            raise ValueError("create_circular_pattern requires a nested feature dictionary.")

        if center is None:
            raise ValueError("create_circular_pattern requires center.")

        if angle_step is None:
            if total_angle == 360:
                angle_step = 360 / count
            else:
                angle_step = total_angle / max(count - 1, 1)

        base_position = feature.get("position")
        if base_position is None:
            raise ValueError("Nested feature in create_circular_pattern requires position.")

        lines = ["# Create circular pattern"]

        for index in range(count):
            angle = index * angle_step
            patterned_position = self._rotate_position_xy(
                base_position,
                center,
                angle,
            )

            copied_feature = self._copy_feature_with_position(
                feature,
                patterned_position,
            )
            lines.extend(self._feature_to_code(copied_feature))

        return lines

    def _create_mirror_feature_code(self, step):
        feature = step.get("feature")
        mirror_plane = step.get("mirror_plane", step.get("plane", "YZ"))
        plane_origin = (
            step.get("plane_origin")
            or step.get("plane_position")
            or [0, 0, 0]
        )
        include_original = step.get("include_original", True)

        if isinstance(plane_origin, (int, float)):
            if str(mirror_plane).upper() in ["YZ", "X"]:
                plane_origin = [plane_origin, 0, 0]
            elif str(mirror_plane).upper() in ["XZ", "Y"]:
                plane_origin = [0, plane_origin, 0]
            elif str(mirror_plane).upper() in ["XY", "Z"]:
                plane_origin = [0, 0, plane_origin]

        if not isinstance(feature, dict):
            raise ValueError("mirror_feature requires a nested feature dictionary.")

        base_position = feature.get("position")
        if base_position is None:
            raise ValueError("Nested feature in mirror_feature requires position.")

        mirrored_position = self._mirror_position(
            base_position,
            mirror_plane,
            plane_origin,
        )
        mirrored_feature = self._copy_feature_with_position(
            feature,
            mirrored_position,
        )

        lines = ["# Create mirrored feature"]

        if include_original:
            lines.extend(self._feature_to_code(feature))

        lines.extend(self._feature_to_code(mirrored_feature))

        return lines

    def _create_fillet_code(self, step):
        target = step.get("target", "base_plate")
        radius = step.get("radius")
        scope = step.get("scope", "outer_vertical_edges")

        return [
            f"# Create controlled fillet on: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    target_meta = object_meta.get('{target}')",
            f"    selected_edges = select_edges_by_scope(target_obj.Shape, '{scope}', target_meta)",
            f"    if not selected_edges:",
            f"        print('WARNING: No edges found for fillet scope: {scope}. Skipping fillet.')",
            f"    else:",
            f"        try:",
            f"            target_obj.Shape = clean_shape(target_obj.Shape.makeFillet({radius}, selected_edges))",
            f"            doc.recompute()",
            f"        except Exception as fillet_error:",
            f"            print('WARNING: Fillet failed and was skipped:', fillet_error)",
            f"else:",
            f"    raise ValueError('Target object not found for fillet: {target}')",
            "",
        ]

    def _create_chamfer_code(self, step):
        target = step.get("target", "base_plate")
        distance = step.get("distance")
        scope = step.get("scope", "top_outer_edges")

        return [
            f"# Create controlled chamfer on: {target}",
            f"if '{target}' in objects:",
            f"    target_obj = objects['{target}']",
            f"    target_meta = object_meta.get('{target}')",
            f"    selected_edges = select_edges_by_scope(target_obj.Shape, '{scope}', target_meta)",
            f"    if not selected_edges:",
            f"        print('WARNING: No edges found for chamfer scope: {scope}. Skipping chamfer.')",
            f"    else:",
            f"        try:",
            f"            target_obj.Shape = clean_shape(target_obj.Shape.makeChamfer({distance}, selected_edges))",
            f"            doc.recompute()",
            f"        except Exception as chamfer_error:",
            f"            print('WARNING: Chamfer failed and was skipped:', chamfer_error)",
            f"else:",
            f"    raise ValueError('Target object not found for chamfer: {target}')",
            "",
        ]