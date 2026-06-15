# cad/cadquery_generator.py

import json
import os
import subprocess
import sys


SUPPORTED_OPERATIONS = {
    "create_box",
    "create_rounded_rectangle_plate",
    "create_cylinder",
    "create_hole",
    "create_slot",
    "create_rectangular_cutout",
    "create_rectangular_pocket",
    "create_circular_pocket",
    "create_rectangular_boss",
    "create_cylindrical_boss",
    "create_hole_pattern",
    "create_linear_pattern",
    "create_circular_pattern",
    "mirror_feature",
    "create_fillet",
    "create_chamfer",
    "create_counterbore_hole",
    "create_countersink_hole",
    "create_threaded_hole",
    "create_edge_notch",
    "create_mounting_standoff",
    "create_hole_on_boss",
    "create_rib",
    "create_gusset",
    "create_raised_border",
    "create_recess",
    "create_open_enclosure",
    "create_lid",
}

SKIPPED_OPERATIONS = set()


class CadQueryGenerator:
    """
    CadQuery backend generator.

    Public interface:

        generator = CadQueryGenerator()
        result = generator.generate(cad_plan, filename="generated_model_cq")

    This generator:
    - writes outputs/generated_model_cq.py
    - writes outputs/generated_model_cq_cad_plan.json
    - compiles the generated Python script before execution
    - executes the generated CadQuery script
    - exports outputs/generated_model_cq.step
    - returns structured generation results
    """

    def __init__(self, output_dir="outputs"):
        self.output_dir = output_dir

    def generate(self, cad_plan, filename="generated_model_cq"):
        os.makedirs(self.output_dir, exist_ok=True)

        script_path = os.path.join(self.output_dir, f"{filename}.py")
        step_path = os.path.join(self.output_dir, f"{filename}.step")
        json_path = os.path.join(self.output_dir, f"{filename}_cad_plan.json")

        try:
            with open(json_path, "w", encoding="utf-8") as file:
                json.dump(cad_plan, file, indent=2)

            script = self._build_script(
                cad_plan=cad_plan,
                step_path=step_path,
            )

            with open(script_path, "w", encoding="utf-8") as file:
                file.write(script)

            try:
                compile(script, script_path, "exec")
            except Exception as e:
                return {
                    "status": "script_compile_failed",
                    "success": False,
                    "backend": "cadquery",
                    "filename": filename,
                    "script_path": script_path,
                    "step_path": None,
                    "json_path": json_path,
                    "stdout": "",
                    "stderr": "",
                    "returncode": None,
                    "error": str(e),
                }

            process = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                check=False,
            )

            success = process.returncode == 0 and os.path.exists(step_path)
            part_step_paths = self._collect_part_step_paths(cad_plan, filename)

            return {
                "status": "generated" if success else "failed",
                "success": success,
                "backend": "cadquery",
                "filename": filename,
                "script_path": script_path,
                "step_path": step_path if os.path.exists(step_path) else None,
                "json_path": json_path,
                "part_step_paths": part_step_paths,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "returncode": process.returncode,
            }

        except Exception as e:
            return {
                "status": "failed",
                "success": False,
                "backend": "cadquery",
                "filename": filename,
                "script_path": script_path,
                "step_path": None,
                "json_path": json_path,
                "part_step_paths": {},
                "stdout": "",
                "stderr": "",
                "returncode": None,
                "error": str(e),
            }

    def _safe_file_component(self, value):
        text = str(value or "part").strip()
        safe = []

        for char in text:
            if char.isalnum() or char in {"_", "-"}:
                safe.append(char)
            else:
                safe.append("_")

        result = "".join(safe).strip("_")
        return result or "part"

    def _collect_part_step_paths(self, cad_plan, filename):
        if not isinstance(cad_plan, dict):
            return {}

        parts = cad_plan.get("parts")

        if not isinstance(parts, list):
            return {}

        part_step_paths = {}

        for index, part in enumerate(parts):
            if not isinstance(part, dict):
                continue

            part_name = (
                part.get("name")
                or part.get("part_name")
                or part.get("id")
                or part.get("label")
                or f"part_{index + 1}"
            )

            safe_part_name = self._safe_file_component(part_name)
            path = os.path.join(self.output_dir, f"{filename}_{safe_part_name}.step")

            if os.path.exists(path):
                part_step_paths[str(part_name)] = path

        return part_step_paths

    def _build_script(self, cad_plan, step_path):
        cad_plan_json = json.dumps(cad_plan, indent=2)
        step_path_json = json.dumps(step_path)
        supported_json = repr(sorted(SUPPORTED_OPERATIONS))
        skipped_json = repr(sorted(SKIPPED_OPERATIONS))

        script = """
import json
import math
import os
import traceback

import cadquery as cq
from cadquery import exporters


CAD_PLAN = json.loads(r'''__CAD_PLAN_JSON__''')
STEP_PATH = __STEP_PATH_JSON__

SUPPORTED_OPERATIONS = __SUPPORTED_OPERATIONS__
SKIPPED_OPERATIONS = __SKIPPED_OPERATIONS__

EPSILON = 0.2

model = None
base_meta = None
feature_meta = {}


# ---------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------

def warn(message):
    print("WARNING:", message)


def info(message):
    print(message)


def number(value, default=None):
    try:
        if value is None:
            return default

        if isinstance(value, bool):
            return default

        return float(value)
    except Exception:
        return default


def integer(value, default=None):
    try:
        if value is None:
            return default

        if isinstance(value, bool):
            return default

        return int(value)
    except Exception:
        return default


def boolean(value, default=False):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        lowered = value.strip().lower()

        if lowered in ["true", "yes", "1", "y"]:
            return True

        if lowered in ["false", "no", "0", "n"]:
            return False

    if isinstance(value, (int, float)):
        return bool(value)

    return default


def as_position(value, default=None):
    if default is None:
        default = [0.0, 0.0, 0.0]

    if not isinstance(value, (list, tuple)):
        return default

    if len(value) < 2:
        return default

    x = number(value[0], default[0])
    y = number(value[1], default[1])

    if len(value) >= 3:
        z = number(value[2], default[2])
    else:
        z = default[2]

    return [x, y, z]


def as_rotation(value, default=None):
    if default is None:
        default = [0.0, 0.0, 0.0]

    if not isinstance(value, (list, tuple)):
        return default

    if len(value) != 3:
        return default

    rx = number(value[0], default[0])
    ry = number(value[1], default[1])
    rz = number(value[2], default[2])

    return [rx, ry, rz]


def ensure_model():
    global model

    if model is None:
        raise RuntimeError("No model exists yet. Create a base object or cylinder first.")


def ensure_base_meta():
    global base_meta

    if base_meta is None:
        raise RuntimeError("No base metadata exists yet. create_box or create_rounded_rectangle_plate must run first.")


def base_bottom_z():
    ensure_base_meta()
    return base_meta["bottom_z"]


def base_top_z():
    ensure_base_meta()
    return base_meta["top_z"]


def base_height():
    ensure_base_meta()
    return base_meta["height"]


def base_origin():
    ensure_base_meta()
    return base_meta["origin"]


def base_x_min():
    ensure_base_meta()
    return base_meta["origin"][0]


def base_y_min():
    ensure_base_meta()
    return base_meta["origin"][1]


def base_x_max():
    ensure_base_meta()
    return base_meta["origin"][0] + base_meta["length"]


def base_y_max():
    ensure_base_meta()
    return base_meta["origin"][1] + base_meta["width"]


def make_box_solid(length, width, height, center):
    return (
        cq.Workplane("XY")
        .box(length, width, height, centered=(True, True, True))
        .translate((center[0], center[1], center[2]))
    )


def make_cylinder_solid(diameter, height, center):
    radius = diameter / 2.0

    return (
        cq.Workplane("XY")
        .circle(radius)
        .extrude(height, both=True)
        .translate((center[0], center[1], center[2]))
    )


def cut_solid_from_model(cutter):
    global model
    ensure_model()
    model = model.cut(cutter)


def union_solid_to_model(solid):
    global model
    ensure_model()
    model = model.union(solid)


def rotate_position_xy(position, center, angle_degrees):
    angle = math.radians(angle_degrees)

    px, py, pz = as_position(position)
    cx, cy, cz = as_position(center)

    dx = px - cx
    dy = py - cy

    rx = cx + dx * math.cos(angle) - dy * math.sin(angle)
    ry = cy + dx * math.sin(angle) + dy * math.cos(angle)

    return [rx, ry, pz]


def shifted_feature(feature, offset):
    copied = dict(feature)
    position = as_position(copied.get("position"), [0.0, 0.0, 0.0])
    offset = as_position(offset, [0.0, 0.0, 0.0])

    copied["position"] = [
        position[0] + offset[0],
        position[1] + offset[1],
        position[2] + offset[2],
    ]

    return copied


def circular_shifted_feature(feature, center, angle_degrees):
    copied = dict(feature)
    position = as_position(copied.get("position"), [0.0, 0.0, 0.0])
    copied["position"] = rotate_position_xy(position, center, angle_degrees)
    return copied


def mirror_position(position, mirror_plane, plane_origin):
    position = as_position(position)
    plane_origin = as_position(plane_origin)

    x, y, z = position
    px, py, pz = plane_origin

    mirror_plane = str(mirror_plane).strip().upper()

    if mirror_plane in ["YZ", "X"]:
        return [2 * px - x, y, z]

    if mirror_plane in ["XZ", "Y"]:
        return [x, 2 * py - y, z]

    if mirror_plane in ["XY", "Z"]:
        return [x, y, 2 * pz - z]

    warn(f"Unsupported mirror plane: {mirror_plane}. Returning original position.")
    return position


def mirrored_feature(feature, mirror_plane, plane_origin):
    copied = dict(feature)

    if copied.get("operation") == "mirror_feature":
        warn("Nested mirror_feature inside mirror_feature is not supported.")
        return None

    operation = copied.get("operation") or copied.get("action")

    if operation == "create_circular_pattern":
        warn("Mirroring create_circular_pattern is not supported in this CadQuery backend yet.")
        return None

    if "position" in copied:
        copied["position"] = mirror_position(copied["position"], mirror_plane, plane_origin)

    elif "first_position" in copied:
        copied["first_position"] = mirror_position(copied["first_position"], mirror_plane, plane_origin)

    elif operation == "create_linear_pattern" and isinstance(copied.get("feature"), dict):
        nested = dict(copied["feature"])

        if "position" in nested:
            nested["position"] = mirror_position(nested["position"], mirror_plane, plane_origin)
            copied["feature"] = nested
        elif "first_position" in nested:
            nested["first_position"] = mirror_position(nested["first_position"], mirror_plane, plane_origin)
            copied["feature"] = nested
        else:
            warn("Mirrored linear pattern nested feature has no position or first_position.")

    else:
        warn("Mirrored feature has no position or first_position.")

    return copied


def remember_feature(name, data):
    if name:
        feature_meta[name] = data


def find_feature_meta(target):
    if not target:
        return None

    return feature_meta.get(target)


def set_base_meta(name, position, length, width, height):
    global base_meta

    x0, y0, z0 = position

    base_meta = {
        "name": name,
        "origin": [x0, y0, z0],
        "length": length,
        "width": width,
        "height": height,
        "bottom_z": z0,
        "top_z": z0 + height,
    }

    remember_feature(name, {
        "type": "base",
        "position": position,
        "length": length,
        "width": width,
        "height": height,
        "bottom_z": z0,
        "top_z": z0 + height,
    })


# ---------------------------------------------------------------------
# Base / standalone creation
# ---------------------------------------------------------------------

def create_box(step):
    global model

    name = step.get("name", "base_plate")
    length = number(step.get("length"))
    width = number(step.get("width"))
    height = number(step.get("height"))
    position = as_position(step.get("position"), [0.0, 0.0, 0.0])

    if not length or not width or not height:
        warn(f"Invalid create_box dimensions: {step}")
        return

    x0, y0, z0 = position

    center = [
        x0 + length / 2.0,
        y0 + width / 2.0,
        z0 + height / 2.0,
    ]

    print("Creating base box:", name, "length", length, "width", width, "height", height)

    solid = make_box_solid(length, width, height, center)

    if model is None:
        model = solid
    else:
        union_solid_to_model(solid)

    set_base_meta(name, position, length, width, height)


def create_rounded_rectangle_plate(step):
    global model

    name = step.get("name", "base_plate")
    length = number(step.get("length"))
    width = number(step.get("width"))
    height = number(step.get("height"))
    corner_radius = number(step.get("corner_radius"), 0)
    position = as_position(step.get("position"), [0.0, 0.0, 0.0])

    if not length or not width or not height:
        warn(f"Invalid create_rounded_rectangle_plate dimensions: {step}")
        return

    max_radius = min(length, width) / 2.0 - EPSILON

    if corner_radius is None or corner_radius <= 0:
        warn(f"Invalid corner_radius for rounded rectangle plate, using normal box: {step}")
        corner_radius = 0

    if corner_radius > max_radius:
        warn(f"corner_radius too large. Reducing from {corner_radius} to {max_radius}.")
        corner_radius = max_radius

    x0, y0, z0 = position

    center = [
        x0 + length / 2.0,
        y0 + width / 2.0,
        z0 + height / 2.0,
    ]

    print(
        "Creating rounded rectangle plate:",
        name,
        "length",
        length,
        "width",
        width,
        "height",
        height,
        "corner_radius",
        corner_radius,
    )

    solid = make_box_solid(length, width, height, center)

    if corner_radius > 0:
        try:
            solid = solid.edges("|Z").fillet(corner_radius)
        except Exception as e:
            warn(f"Rounded plate vertical edge fillet failed, keeping rectangular plate: {e}")

    if model is None:
        model = solid
    else:
        union_solid_to_model(solid)

    set_base_meta(name, position, length, width, height)


def create_cylinder(step):
    global model

    name = step.get("name", "cylinder")
    diameter = number(step.get("diameter"))
    radius = number(step.get("radius"))
    height = number(step.get("height"))
    position = as_position(step.get("position"), [0.0, 0.0, 0.0])

    if not diameter and radius:
        diameter = radius * 2.0

    if not diameter or not height:
        warn(f"Invalid create_cylinder dimensions: {step}")
        return

    x, y, z = position
    center_z = z + height / 2.0

    print("Creating cylinder:", name, "diameter", diameter, "height", height, "position", position)

    cylinder = make_cylinder_solid(
        diameter=diameter,
        height=height,
        center=[x, y, center_z],
    )

    if model is None:
        model = cylinder
    else:
        union_solid_to_model(cylinder)

    remember_feature(name, {
        "type": "cylinder",
        "position": position,
        "diameter": diameter,
        "height": height,
        "bottom_z": z,
        "top_z": z + height,
    })



def create_open_enclosure(step):
    global model

    name = step.get("name", "enclosure_body")
    length = number(step.get("length"))
    width = number(step.get("width"))
    height = number(step.get("height"))
    wall_thickness = number(step.get("wall_thickness") or step.get("wall_width") or step.get("wall_thick"))
    bottom_thickness = number(step.get("bottom_thickness") or step.get("base_thickness") or step.get("floor_thickness") or step.get("bottom_height"))
    corner_radius = number(step.get("corner_radius"), 0)
    position = as_position(step.get("position"), [0.0, 0.0, 0.0])

    if not length or not width or not height or not wall_thickness or not bottom_thickness:
        warn(f"Invalid open enclosure dimensions: {step}")
        return

    if wall_thickness >= min(length, width) / 2.0:
        warn(f"wall_thickness too large for open enclosure: {step}")
        return

    if bottom_thickness >= height:
        warn(f"bottom_thickness must be smaller than enclosure height: {step}")
        return

    x0, y0, z0 = position
    center = [x0 + length / 2.0, y0 + width / 2.0, z0 + height / 2.0]

    print("Creating open enclosure:", name, "length", length, "width", width, "height", height)

    enclosure = make_box_solid(length, width, height, center)

    max_radius = min(length, width) / 2.0 - EPSILON
    if corner_radius and corner_radius > 0:
        if corner_radius > max_radius:
            warn(f"corner_radius too large. Reducing from {corner_radius} to {max_radius}.")
            corner_radius = max_radius

        try:
            enclosure = enclosure.edges("|Z").fillet(corner_radius)
        except Exception as e:
            warn(f"Open enclosure outer fillet failed, keeping rectangular enclosure: {e}")

    inner_length = length - 2.0 * wall_thickness
    inner_width = width - 2.0 * wall_thickness
    inner_depth = height - bottom_thickness

    inner_center = [
        x0 + length / 2.0,
        y0 + width / 2.0,
        z0 + bottom_thickness + inner_depth / 2.0 + EPSILON,
    ]

    inner_cutter = make_box_solid(
        length=inner_length,
        width=inner_width,
        height=inner_depth + 2.0 * EPSILON,
        center=inner_center,
    )

    try:
        enclosure = enclosure.cut(inner_cutter)
    except Exception as e:
        warn(f"Failed to cut enclosure cavity: {e}")

    if model is None:
        model = enclosure
    else:
        union_solid_to_model(enclosure)

    set_base_meta(name, position, length, width, height)


def create_lid(step):
    global model

    name = step.get("name", "lid")
    length = number(step.get("length"))
    width = number(step.get("width"))
    height = number(step.get("height"))
    lip_height = number(step.get("lip_height") or step.get("lip_depth") or step.get("inner_lip_height"))
    lip_width = number(step.get("lip_width") or step.get("lip_thickness") or step.get("inner_lip_width"))
    corner_radius = number(step.get("corner_radius"), 0)
    position = as_position(step.get("position"), [0.0, 0.0, 0.0])

    if not length or not width or not height:
        warn(f"Invalid lid dimensions: {step}")
        return

    x0, y0, z0 = position
    center = [x0 + length / 2.0, y0 + width / 2.0, z0 + height / 2.0]

    print("Creating lid:", name, "length", length, "width", width, "height", height)

    lid = make_box_solid(length, width, height, center)

    max_radius = min(length, width) / 2.0 - EPSILON
    if corner_radius and corner_radius > 0:
        if corner_radius > max_radius:
            warn(f"corner_radius too large. Reducing from {corner_radius} to {max_radius}.")
            corner_radius = max_radius

        try:
            lid = lid.edges("|Z").fillet(corner_radius)
        except Exception as e:
            warn(f"Lid outer fillet failed, keeping rectangular lid: {e}")

    if lip_height and lip_width:
        lip_length = length - 2.0 * lip_width
        lip_width_y = width - 2.0 * lip_width

        if lip_length > 0 and lip_width_y > 0 and lip_height > 0:
            lip_center = [
                x0 + length / 2.0,
                y0 + width / 2.0,
                z0 - lip_height / 2.0,
            ]

            print("Creating lid lower lip")

            lip = make_box_solid(
                length=lip_length,
                width=lip_width_y,
                height=lip_height,
                center=lip_center,
            )

            try:
                lid = lid.union(lip)
            except Exception as e:
                warn(f"Failed to create lid lower lip, continuing without lip: {e}")
        else:
            warn(f"Invalid lid lip dimensions, creating lid without lip: {step}")

    if model is None:
        model = lid
    else:
        union_solid_to_model(lid)

    remember_feature(name, {
        "type": "lid",
        "position": position,
        "length": length,
        "width": width,
        "height": height,
        "bottom_z": z0,
        "top_z": z0 + height,
    })


# ---------------------------------------------------------------------
# Cut operations
# ---------------------------------------------------------------------

def create_hole(step):
    ensure_base_meta()

    diameter = number(step.get("diameter") or step.get("hole_diameter"))
    depth = number(step.get("depth"), base_height() + 2 * EPSILON)
    position = as_position(step.get("position"))

    if not diameter or not depth:
        warn(f"Invalid create_hole dimensions: {step}")
        return

    x, y, _ = position
    cut_depth = depth + 2 * EPSILON
    center_z = base_top_z() - depth / 2.0

    print("Creating hole at", position, "diameter", diameter, "depth", depth)

    cutter = make_cylinder_solid(
        diameter=diameter,
        height=cut_depth,
        center=[x, y, center_z],
    )

    cut_solid_from_model(cutter)


def create_slot(step):
    ensure_base_meta()

    length = number(step.get("length"))
    width = number(step.get("width"))
    depth = number(step.get("depth"), base_height())
    position = as_position(step.get("position"))
    orientation = str(step.get("orientation", "x")).lower()

    if not length or not width or not depth:
        warn(f"Invalid create_slot dimensions: {step}")
        return

    if length < width:
        warn(f"Slot length is smaller than width, using circular cut fallback: {step}")
        length = width

    x, y, _ = position
    cut_depth = depth + 2 * EPSILON
    center_z = base_top_z() - depth / 2.0
    straight_length = max(length - width, 0.0)

    print("Creating slot at", position, "length", length, "width", width, "orientation", orientation)

    try:
        if orientation == "y":
            rect_length_x = width
            rect_length_y = max(straight_length, width)

            rect = make_box_solid(
                length=rect_length_x,
                width=rect_length_y,
                height=cut_depth,
                center=[x, y, center_z],
            )

            end_offset = straight_length / 2.0

            cyl1 = make_cylinder_solid(
                diameter=width,
                height=cut_depth,
                center=[x, y - end_offset, center_z],
            )

            cyl2 = make_cylinder_solid(
                diameter=width,
                height=cut_depth,
                center=[x, y + end_offset, center_z],
            )

        else:
            rect_length_x = max(straight_length, width)
            rect_length_y = width

            rect = make_box_solid(
                length=rect_length_x,
                width=rect_length_y,
                height=cut_depth,
                center=[x, y, center_z],
            )

            end_offset = straight_length / 2.0

            cyl1 = make_cylinder_solid(
                diameter=width,
                height=cut_depth,
                center=[x - end_offset, y, center_z],
            )

            cyl2 = make_cylinder_solid(
                diameter=width,
                height=cut_depth,
                center=[x + end_offset, y, center_z],
            )

        cutter = rect.union(cyl1).union(cyl2)
        cut_solid_from_model(cutter)

    except Exception as e:
        warn(f"Failed to create slot {step}: {e}")


def create_rectangular_cutout(step):
    ensure_base_meta()

    length = number(step.get("length"))
    width = number(step.get("width"))
    depth = number(step.get("depth"), base_height())
    position = as_position(step.get("position"))

    if not length or not width or not depth:
        warn(f"Invalid rectangular cutout dimensions: {step}")
        return

    x, y, _ = position
    cut_depth = depth + 2 * EPSILON
    center_z = base_top_z() - depth / 2.0

    print("Creating rectangular cutout at", position)

    cutter = make_box_solid(
        length=length,
        width=width,
        height=cut_depth,
        center=[x, y, center_z],
    )

    cut_solid_from_model(cutter)


def create_rectangular_pocket(step):
    ensure_base_meta()

    length = number(step.get("length"))
    width = number(step.get("width"))
    depth = number(step.get("depth"))
    position = as_position(step.get("position"))

    if not length or not width or not depth:
        warn(f"Invalid rectangular pocket dimensions: {step}")
        return

    x, y, _ = position
    cut_depth = depth + EPSILON
    center_z = base_top_z() - depth / 2.0

    print("Creating rectangular pocket at", position)

    cutter = make_box_solid(
        length=length,
        width=width,
        height=cut_depth,
        center=[x, y, center_z],
    )

    cut_solid_from_model(cutter)



def create_recess(step):
    ensure_base_meta()

    length = number(step.get("length"))
    width = number(step.get("width"))
    depth = number(step.get("depth"))
    corner_radius = number(step.get("corner_radius"), 0)
    position = as_position(step.get("position"))

    if not length or not width or not depth:
        warn(f"Invalid recess dimensions: {step}")
        return

    x, y, _ = position
    cut_depth = depth + EPSILON
    center_z = base_top_z() - depth / 2.0

    print("Creating recess at", position, "length", length, "width", width, "depth", depth)

    cutter = make_box_solid(
        length=length,
        width=width,
        height=cut_depth,
        center=[x, y, center_z],
    )

    if corner_radius and corner_radius > 0:
        max_radius = min(length, width) / 2.0 - EPSILON

        if corner_radius > max_radius:
            warn(f"corner_radius too large for recess. Reducing from {corner_radius} to {max_radius}.")
            corner_radius = max_radius

        try:
            cutter = cutter.edges("|Z").fillet(corner_radius)
        except Exception as e:
            warn(f"Rounded recess cutter failed, using rectangular recess fallback: {e}")

    try:
        cut_solid_from_model(cutter)
    except Exception as e:
        warn(f"Failed to create recess {step}: {e}")


def create_circular_pocket(step):
    ensure_base_meta()

    diameter = number(step.get("diameter"))
    depth = number(step.get("depth"))
    position = as_position(step.get("position"))

    if not diameter or not depth:
        warn(f"Invalid circular pocket dimensions: {step}")
        return

    x, y, _ = position
    cut_depth = depth + EPSILON
    center_z = base_top_z() - depth / 2.0

    print("Creating circular pocket at", position)

    cutter = make_cylinder_solid(
        diameter=diameter,
        height=cut_depth,
        center=[x, y, center_z],
    )

    cut_solid_from_model(cutter)


def create_counterbore_hole(step):
    ensure_base_meta()

    hole_diameter = number(step.get("hole_diameter") or step.get("diameter"))
    depth = number(step.get("depth"), base_height())
    counterbore_diameter = number(step.get("counterbore_diameter"))
    counterbore_depth = number(step.get("counterbore_depth"))
    position = as_position(step.get("position"))

    if not hole_diameter or not depth or not counterbore_diameter or not counterbore_depth:
        warn(f"Invalid counterbore dimensions: {step}")
        return

    x, y, _ = position

    print("Creating counterbore hole at", position)

    main_cutter = make_cylinder_solid(
        diameter=hole_diameter,
        height=depth + 2 * EPSILON,
        center=[x, y, base_top_z() - depth / 2.0],
    )

    counterbore_cutter = make_cylinder_solid(
        diameter=counterbore_diameter,
        height=counterbore_depth + EPSILON,
        center=[x, y, base_top_z() - counterbore_depth / 2.0],
    )

    try:
        cut_solid_from_model(main_cutter)
        cut_solid_from_model(counterbore_cutter)
    except Exception as e:
        warn(f"Failed to create counterbore {step}: {e}")


def create_countersink_hole(step):
    ensure_base_meta()

    hole_diameter = number(step.get("hole_diameter") or step.get("diameter"))
    depth = number(step.get("depth"), base_height())
    countersink_diameter = number(step.get("countersink_diameter"))
    countersink_angle = number(step.get("countersink_angle"), 90.0)
    countersink_depth = number(step.get("countersink_depth"))
    position = as_position(step.get("position"))

    if not hole_diameter or not depth or not countersink_diameter:
        warn(f"Invalid countersink dimensions: {step}")
        return

    x, y, _ = position

    hole_radius = hole_diameter / 2.0
    countersink_radius = countersink_diameter / 2.0

    if countersink_depth is None:
        half_angle_rad = math.radians(countersink_angle / 2.0)

        if math.tan(half_angle_rad) == 0:
            countersink_depth = 2.0
        else:
            countersink_depth = (countersink_radius - hole_radius) / math.tan(half_angle_rad)

    if countersink_depth <= 0:
        warn(f"Invalid derived countersink depth: {step}")
        countersink_depth = 2.0

    print("Creating countersink hole at", position)

    main_cutter = make_cylinder_solid(
        diameter=hole_diameter,
        height=depth + 2 * EPSILON,
        center=[x, y, base_top_z() - depth / 2.0],
    )

    try:
        cut_solid_from_model(main_cutter)
    except Exception as e:
        warn(f"Failed to create main countersink hole {step}: {e}")
        return

    try:
        bottom_z = base_top_z() - countersink_depth

        cone = cq.Solid.makeCone(
            hole_radius,
            countersink_radius,
            countersink_depth + EPSILON,
            pnt=cq.Vector(x, y, bottom_z - EPSILON / 2.0),
            dir=cq.Vector(0, 0, 1),
        )

        cone_cutter = cq.Workplane("XY").add(cone)
        cut_solid_from_model(cone_cutter)

    except Exception as e:
        warn(
            "Failed to create true conical countersink. "
            f"Using shallow cylindrical visual fallback. Error: {e}"
        )

        fallback = make_cylinder_solid(
            diameter=countersink_diameter,
            height=countersink_depth + EPSILON,
            center=[x, y, base_top_z() - countersink_depth / 2.0],
        )

        try:
            cut_solid_from_model(fallback)
        except Exception as fallback_error:
            warn(f"Failed countersink fallback {step}: {fallback_error}")


def create_threaded_hole(step):
    thread = step.get("thread", "unspecified")
    diameter = number(step.get("diameter") or step.get("hole_diameter"))
    depth = number(step.get("depth"), base_height())
    position = as_position(step.get("position"))

    if not diameter or not depth:
        warn(f"Invalid threaded hole dimensions: {step}")
        return

    print(f"Thread {thread} represented as simplified drilled hole.")
    print("Creating threaded hole at", position)

    create_hole(
        {
            "operation": "create_hole",
            "target": step.get("target"),
            "diameter": diameter,
            "depth": depth,
            "position": position,
        }
    )


def create_hole_on_boss(step):
    ensure_base_meta()

    diameter = number(step.get("diameter") or step.get("hole_diameter"))
    depth = number(step.get("depth"), base_height())
    position = as_position(step.get("position"))
    target = step.get("target", "boss")

    if not diameter or not depth:
        warn(f"Invalid hole-on-boss dimensions: {step}")
        return

    x, y, _ = position

    meta = find_feature_meta(target)
    if meta and "top_z" in meta and "bottom_z" in meta:
        top_z = meta["top_z"]
        center_z = top_z - depth / 2.0
    else:
        center_z = base_top_z()

    print("Creating hole on boss at", position, "target", target)

    cutter = make_cylinder_solid(
        diameter=diameter,
        height=depth + 2 * EPSILON,
        center=[x, y, center_z],
    )

    try:
        cut_solid_from_model(cutter)
    except Exception as e:
        warn(f"Failed to create hole on boss {step}: {e}")


def create_edge_notch(step):
    ensure_base_meta()

    length = number(step.get("length"))
    width = number(step.get("width"))
    depth = number(step.get("depth"))
    position = as_position(step.get("position"))
    edge = str(step.get("edge", "left")).lower()

    if not length or not width or not depth:
        warn(f"Invalid edge notch dimensions: {step}")
        return

    overlap = max(1.0, EPSILON * 5)
    x, y, _ = position
    center_z = base_top_z() - depth / 2.0
    cut_depth = depth + EPSILON

    print("Creating edge notch at", position, "edge", edge)

    if edge in ["left", "x_min"]:
        size_x = width + overlap
        size_y = length
        center_x = base_x_min() - overlap + size_x / 2.0
        center_y = y

    elif edge in ["right", "x_max"]:
        size_x = width + overlap
        size_y = length
        center_x = base_x_max() + overlap - size_x / 2.0
        center_y = y

    elif edge in ["bottom", "front", "y_min"]:
        size_x = length
        size_y = width + overlap
        center_x = x
        center_y = base_y_min() - overlap + size_y / 2.0

    elif edge in ["top", "back", "y_max"]:
        size_x = length
        size_y = width + overlap
        center_x = x
        center_y = base_y_max() + overlap - size_y / 2.0

    else:
        warn(f"Unsupported edge value for notch: {edge}")
        return

    try:
        cutter = make_box_solid(
            length=size_x,
            width=size_y,
            height=cut_depth,
            center=[center_x, center_y, center_z],
        )

        cut_solid_from_model(cutter)

    except Exception as e:
        warn(f"Failed to create edge notch {step}: {e}")


# ---------------------------------------------------------------------
# Boss and raised feature operations
# ---------------------------------------------------------------------

def create_rectangular_boss(step):
    ensure_base_meta()

    length = number(step.get("length"))
    width = number(step.get("width"))
    height = number(step.get("height"))
    position = as_position(step.get("position"))
    name = step.get("name")

    if not length or not width or not height:
        warn(f"Invalid rectangular boss dimensions: {step}")
        return

    x, y, _ = position
    center_z = base_top_z() + height / 2.0

    print("Creating rectangular boss at", position)

    boss = make_box_solid(
        length=length,
        width=width,
        height=height,
        center=[x, y, center_z],
    )

    union_solid_to_model(boss)

    remember_feature(name, {
        "type": "rectangular_boss",
        "position": position,
        "length": length,
        "width": width,
        "height": height,
        "bottom_z": base_top_z(),
        "top_z": base_top_z() + height,
    })


def create_cylindrical_boss(step):
    ensure_base_meta()

    diameter = number(step.get("diameter"))
    height = number(step.get("height"))
    position = as_position(step.get("position"))
    name = step.get("name")

    if not diameter or not height:
        warn(f"Invalid cylindrical boss dimensions: {step}")
        return

    x, y, _ = position
    center_z = base_top_z() + height / 2.0

    print("Creating cylindrical boss at", position)

    boss = make_cylinder_solid(
        diameter=diameter,
        height=height,
        center=[x, y, center_z],
    )

    union_solid_to_model(boss)

    remember_feature(name, {
        "type": "cylindrical_boss",
        "position": position,
        "diameter": diameter,
        "height": height,
        "bottom_z": base_top_z(),
        "top_z": base_top_z() + height,
    })


def create_mounting_standoff(step):
    ensure_base_meta()

    outer_diameter = number(step.get("outer_diameter") or step.get("diameter"))
    inner_diameter = number(
        step.get("inner_diameter")
        or step.get("hole_diameter")
        or step.get("inner_hole_diameter")
        or step.get("central_hole_diameter")
    )
    height = number(step.get("height"))
    hole_depth = number(step.get("hole_depth"))
    through_hole = boolean(step.get("through_hole"), False)
    position = as_position(step.get("position"))
    name = step.get("name")

    if not outer_diameter or not height:
        warn(f"Invalid mounting standoff dimensions: {step}")
        return

    x, y, _ = position
    center_z = base_top_z() + height / 2.0

    print("Creating mounting standoff at", position)

    standoff = make_cylinder_solid(
        diameter=outer_diameter,
        height=height,
        center=[x, y, center_z],
    )

    try:
        union_solid_to_model(standoff)
    except Exception as e:
        warn(f"Failed to union mounting standoff {step}: {e}")
        return

    remember_feature(name or "standoff", {
        "type": "mounting_standoff",
        "position": position,
        "diameter": outer_diameter,
        "height": height,
        "bottom_z": base_top_z(),
        "top_z": base_top_z() + height,
    })

    if inner_diameter and inner_diameter > 0:
        if inner_diameter >= outer_diameter:
            warn(f"inner_diameter must be smaller than outer_diameter: {step}")
            return

        if through_hole:
            cut_depth = height + base_height() + 2 * EPSILON
            cut_center_z = base_bottom_z() + cut_depth / 2.0
        else:
            if hole_depth is None:
                hole_depth = height
            cut_depth = hole_depth + 2 * EPSILON
            cut_center_z = base_top_z() + height - hole_depth / 2.0

        print("Creating standoff central hole at", position)

        cutter = make_cylinder_solid(
            diameter=inner_diameter,
            height=cut_depth,
            center=[x, y, cut_center_z],
        )

        try:
            cut_solid_from_model(cutter)
        except Exception as e:
            warn(f"Failed to cut standoff central hole {step}: {e}")


def create_rib(step):
    ensure_base_meta()

    length = number(step.get("length"))
    thickness = number(step.get("thickness") or step.get("width"))
    height = number(step.get("height"))
    position = as_position(step.get("position"))
    orientation = str(step.get("orientation", "x")).lower()
    name = step.get("name")

    if not length or not thickness or not height:
        warn(f"Invalid rib dimensions: {step}")
        return

    x, y, _ = position

    if orientation == "y":
        size_x = thickness
        size_y = length
    else:
        size_x = length
        size_y = thickness

    center_z = base_top_z() + height / 2.0

    print("Creating rib at", position, "orientation", orientation)

    rib = make_box_solid(
        length=size_x,
        width=size_y,
        height=height,
        center=[x, y, center_z],
    )

    try:
        union_solid_to_model(rib)
    except Exception as e:
        warn(f"Failed to create rib {step}: {e}")
        return

    remember_feature(name, {
        "type": "rib",
        "position": position,
        "length": length,
        "thickness": thickness,
        "height": height,
        "orientation": orientation,
        "bottom_z": base_top_z(),
        "top_z": base_top_z() + height,
    })


def create_gusset(step):
    ensure_base_meta()

    length = number(step.get("length"))
    height = number(step.get("height"))
    thickness = number(step.get("thickness") or step.get("width"))
    position = as_position(step.get("position"))
    orientation = str(step.get("orientation", "x")).lower()
    name = step.get("name")

    if not length or not height or not thickness:
        warn(f"Invalid gusset dimensions: {step}")
        return

    x, y, _ = position
    z = base_top_z()

    print("Creating gusset at", position, "orientation", orientation)

    try:
        if orientation in ["x", "-x"]:
            direction = 1 if orientation == "x" else -1

            points = [
                (x, z),
                (x + direction * length, z),
                (x, z + height),
            ]

            gusset = (
                cq.Workplane("XZ")
                .polyline(points)
                .close()
                .extrude(thickness, both=True)
                .translate((0, y, 0))
            )

        elif orientation in ["y", "-y"]:
            direction = 1 if orientation == "y" else -1

            points = [
                (y, z),
                (y + direction * length, z),
                (y, z + height),
            ]

            gusset = (
                cq.Workplane("YZ")
                .polyline(points)
                .close()
                .extrude(thickness, both=True)
                .translate((x, 0, 0))
            )

        else:
            warn(f"Unsupported gusset orientation: {orientation}")
            return

        union_solid_to_model(gusset)

        remember_feature(name, {
            "type": "gusset",
            "position": position,
            "length": length,
            "height": height,
            "thickness": thickness,
            "orientation": orientation,
            "bottom_z": base_top_z(),
            "top_z": base_top_z() + height,
        })

    except Exception as e:
        warn(f"Failed to create gusset {step}: {e}")


def create_raised_border(step):
    ensure_base_meta()

    border_width = number(
        step.get("border_width")
        or step.get("lip_width")
        or step.get("rim_width")
        or step.get("border_thickness")
        or step.get("thickness")
    )
    height = number(step.get("height") or step.get("lip_height") or step.get("rim_height"))
    scope = str(step.get("scope", "outer_perimeter")).lower()

    if not border_width or not height:
        warn(f"Invalid raised border dimensions: {step}")
        return

    print("Creating raised border scope", scope)

    try:
        if scope == "rectangular_area":
            length = number(step.get("length"))
            width = number(step.get("width"))
            position = as_position(step.get("position"))

            if not length or not width:
                warn(f"Rectangular raised border requires length and width: {step}")
                return

            x, y, _ = position
            x_min = x - length / 2.0
            x_max = x + length / 2.0
            y_min = y - width / 2.0
            y_max = y + width / 2.0

        else:
            x_min = base_x_min()
            x_max = base_x_max()
            y_min = base_y_min()
            y_max = base_y_max()
            length = x_max - x_min
            width = y_max - y_min

        center_z = base_top_z() + height / 2.0

        top_strip = make_box_solid(
            length=length,
            width=border_width,
            height=height,
            center=[(x_min + x_max) / 2.0, y_max - border_width / 2.0, center_z],
        )

        bottom_strip = make_box_solid(
            length=length,
            width=border_width,
            height=height,
            center=[(x_min + x_max) / 2.0, y_min + border_width / 2.0, center_z],
        )

        left_strip = make_box_solid(
            length=border_width,
            width=max(width - 2 * border_width, border_width),
            height=height,
            center=[x_min + border_width / 2.0, (y_min + y_max) / 2.0, center_z],
        )

        right_strip = make_box_solid(
            length=border_width,
            width=max(width - 2 * border_width, border_width),
            height=height,
            center=[x_max - border_width / 2.0, (y_min + y_max) / 2.0, center_z],
        )

        border = top_strip.union(bottom_strip).union(left_strip).union(right_strip)
        union_solid_to_model(border)

    except Exception as e:
        warn(f"Failed to create raised border {step}: {e}")


# ---------------------------------------------------------------------
# Pattern / mirror operations
# ---------------------------------------------------------------------

def create_hole_pattern(step):
    rows = integer(step.get("rows"))
    columns = integer(step.get("columns"))
    diameter = number(step.get("diameter"))
    depth = number(step.get("depth"), base_height())
    first_position = as_position(step.get("first_position") or step.get("position"))
    spacing_x = number(step.get("spacing_x"), 0)
    spacing_y = number(step.get("spacing_y"), 0)

    if not rows or not columns or not diameter:
        warn(f"Invalid hole pattern: {step}")
        return

    print("Creating hole pattern:", rows, "rows", columns, "columns")

    for row in range(rows):
        for column in range(columns):
            position = [
                first_position[0] + column * spacing_x,
                first_position[1] + row * spacing_y,
                first_position[2],
            ]

            create_hole(
                {
                    "operation": "create_hole",
                    "target": step.get("target"),
                    "diameter": diameter,
                    "depth": depth,
                    "position": position,
                }
            )


def create_linear_pattern(step):
    count = integer(step.get("count"))
    spacing = as_position(step.get("spacing"), [0.0, 0.0, 0.0])
    feature = step.get("feature")

    if not count or not isinstance(feature, dict):
        warn(f"Invalid linear pattern: {step}")
        return

    print("Creating linear pattern count", count, "spacing", spacing)

    for index in range(count):
        offset = [
            spacing[0] * index,
            spacing[1] * index,
            spacing[2] * index,
        ]

        nested_feature = shifted_feature(feature, offset)
        apply_feature(nested_feature, nested=True)


def create_circular_pattern(step):
    count = integer(step.get("count"))
    center = as_position(step.get("center"), [0.0, 0.0, 0.0])
    total_angle = number(step.get("total_angle"), 360.0)
    feature = step.get("feature")

    if not count or not isinstance(feature, dict):
        warn(f"Invalid circular pattern: {step}")
        return

    if count <= 0:
        warn(f"Invalid circular pattern count: {step}")
        return

    print("Creating circular pattern count", count, "center", center)

    if count == 1:
        apply_feature(feature, nested=True)
        return

    angle_step = total_angle / count

    for index in range(count):
        angle = angle_step * index
        nested_feature = circular_shifted_feature(feature, center, angle)
        apply_feature(nested_feature, nested=True)


def create_mirror_feature(step):
    feature = step.get("feature")
    mirror_plane = step.get("mirror_plane")
    plane_origin = as_position(step.get("plane_origin"), [0.0, 0.0, 0.0])
    include_original = boolean(step.get("include_original"), True)

    if not isinstance(feature, dict):
        warn(f"Invalid mirror_feature: missing nested feature: {step}")
        return

    if feature.get("operation") == "mirror_feature":
        warn("Nested mirror_feature inside mirror_feature is not supported.")
        return

    if not mirror_plane:
        warn(f"Invalid mirror_feature: missing mirror_plane: {step}")
        return

    print("Creating mirror feature across", mirror_plane, "at", plane_origin)

    if include_original:
        apply_feature(feature, nested=True)

    mirrored_copy = mirrored_feature(feature, mirror_plane, plane_origin)

    if not isinstance(mirrored_copy, dict):
        warn("Mirror feature could not create a mirrored copy.")
        return

    print("Mirrored feature:", mirrored_copy.get("operation"))
    apply_feature(mirrored_copy, nested=True)


# ---------------------------------------------------------------------
# Fillet / chamfer
# ---------------------------------------------------------------------

def create_chamfer(step):
    global model
    ensure_model()
    ensure_base_meta()

    distance = number(step.get("distance"))
    scope = step.get("scope", "base_top_outer_edges")

    if not distance:
        warn(f"Invalid chamfer distance: {step}")
        return

    print("Creating chamfer scope", scope, "distance", distance)

    try:
        if scope == "base_top_outer_edges":
            z = base_top_z()
            x_min = base_x_min()
            x_max = base_x_max()
            y_min = base_y_min()
            y_max = base_y_max()

            model = (
                model
                .edges(cq.selectors.BoxSelector(
                    (x_min - EPSILON, y_min - EPSILON, z - EPSILON),
                    (x_max + EPSILON, y_max + EPSILON, z + EPSILON),
                ))
                .chamfer(distance)
            )

        else:
            model = model.edges().chamfer(distance)

    except Exception as e:
        warn(f"Chamfer failed for {step}: {e}")


def create_fillet(step):
    global model
    ensure_model()
    ensure_base_meta()

    radius = number(step.get("radius"))
    scope = step.get("scope", "base_outer_vertical_edges")

    if not radius:
        warn(f"Invalid fillet radius: {step}")
        return

    print("Creating fillet scope", scope, "radius", radius)

    try:
        if scope == "base_outer_vertical_edges":
            x_min = base_x_min()
            x_max = base_x_max()
            y_min = base_y_min()
            y_max = base_y_max()
            z_min = base_bottom_z()
            z_max = base_top_z()

            model = (
                model
                .edges(cq.selectors.BoxSelector(
                    (x_min - EPSILON, y_min - EPSILON, z_min - EPSILON),
                    (x_max + EPSILON, y_max + EPSILON, z_max + EPSILON),
                ))
                .fillet(radius)
            )

        else:
            model = model.edges().fillet(radius)

    except Exception as e:
        warn(f"Fillet failed for {step}: {e}")


# ---------------------------------------------------------------------
# Feature dispatcher
# ---------------------------------------------------------------------

def apply_feature(step, nested=False):
    operation = step.get("operation") or step.get("action")

    if operation == "create_lip":
        operation = "create_raised_border"
        step = dict(step)
        step["operation"] = operation

    if not operation:
        warn(f"Step without operation: {step}")
        return

    if operation in SKIPPED_OPERATIONS:
        warn(f"Skipping unsupported operation for now: {operation}")
        return

    if operation not in SUPPORTED_OPERATIONS:
        warn(f"Unsupported operation: {operation}")
        return

    try:
        if operation == "create_box":
            if nested:
                warn("create_box inside pattern or mirror is not supported.")
                return
            create_box(step)

        elif operation == "create_rounded_rectangle_plate":
            if nested:
                warn("create_rounded_rectangle_plate inside pattern or mirror is not supported.")
                return
            create_rounded_rectangle_plate(step)

        elif operation == "create_cylinder":
            create_cylinder(step)

        elif operation == "create_open_enclosure":
            if nested:
                warn("create_open_enclosure inside pattern or mirror is not supported.")
                return
            create_open_enclosure(step)

        elif operation == "create_lid":
            create_lid(step)

        elif operation == "create_hole":
            create_hole(step)

        elif operation == "create_slot":
            create_slot(step)

        elif operation == "create_rectangular_cutout":
            create_rectangular_cutout(step)

        elif operation == "create_rectangular_pocket":
            create_rectangular_pocket(step)

        elif operation == "create_recess":
            create_recess(step)

        elif operation == "create_circular_pocket":
            create_circular_pocket(step)

        elif operation == "create_counterbore_hole":
            create_counterbore_hole(step)

        elif operation == "create_countersink_hole":
            create_countersink_hole(step)

        elif operation == "create_threaded_hole":
            create_threaded_hole(step)

        elif operation == "create_hole_on_boss":
            create_hole_on_boss(step)

        elif operation == "create_edge_notch":
            create_edge_notch(step)

        elif operation == "create_rectangular_boss":
            create_rectangular_boss(step)

        elif operation == "create_cylindrical_boss":
            create_cylindrical_boss(step)

        elif operation == "create_mounting_standoff":
            create_mounting_standoff(step)

        elif operation == "create_rib":
            create_rib(step)

        elif operation == "create_gusset":
            create_gusset(step)

        elif operation == "create_raised_border":
            create_raised_border(step)

        elif operation == "create_hole_pattern":
            create_hole_pattern(step)

        elif operation == "create_linear_pattern":
            create_linear_pattern(step)

        elif operation == "create_circular_pattern":
            create_circular_pattern(step)

        elif operation == "mirror_feature":
            create_mirror_feature(step)

        elif operation == "create_chamfer":
            create_chamfer(step)

        elif operation == "create_fillet":
            create_fillet(step)

        else:
            warn(f"No handler implemented for operation: {operation}")

    except Exception as e:
        warn(f"Operation failed but generation will continue: {operation}")
        warn(str(e))
        traceback.print_exc()


# ---------------------------------------------------------------------
# Main script execution
# ---------------------------------------------------------------------

def reset_part_state():
    global model, base_meta, feature_meta
    model = None
    base_meta = None
    feature_meta = {}


def get_model_bbox(model_to_measure):
    # Return a simple numeric bounding box dictionary for a CadQuery object.
    if model_to_measure is None:
        raise RuntimeError("Cannot compute bounding box for None model.")

    bbox = model_to_measure.val().BoundingBox()

    x_min = float(bbox.xmin)
    x_max = float(bbox.xmax)
    y_min = float(bbox.ymin)
    y_max = float(bbox.ymax)
    z_min = float(bbox.zmin)
    z_max = float(bbox.zmax)

    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "z_min": z_min,
        "z_max": z_max,
        "x_center": (x_min + x_max) / 2.0,
        "y_center": (y_min + y_max) / 2.0,
        "z_center": (z_min + z_max) / 2.0,
        "length": x_max - x_min,
        "width": y_max - y_min,
        "height": z_max - z_min,
    }


def offset_bbox(bbox, offset):
    offset = as_position(offset, [0.0, 0.0, 0.0])
    dx, dy, dz = offset

    return {
        "x_min": bbox["x_min"] + dx,
        "x_max": bbox["x_max"] + dx,
        "y_min": bbox["y_min"] + dy,
        "y_max": bbox["y_max"] + dy,
        "z_min": bbox["z_min"] + dz,
        "z_max": bbox["z_max"] + dz,
        "x_center": bbox["x_center"] + dx,
        "y_center": bbox["y_center"] + dy,
        "z_center": bbox["z_center"] + dz,
        "length": bbox["length"],
        "width": bbox["width"],
        "height": bbox["height"],
    }


def build_model_from_steps(steps, part_name=None):
    global model

    reset_part_state()

    if not isinstance(steps, list) or not steps:
        raise RuntimeError(f"Part {part_name or '<single>'} has no steps.")

    print("Building part:", part_name or "single_part")
    print("Number of CAD steps:", len(steps))

    base_created = False

    for step in steps:
        operation = step.get("operation") or step.get("action")

        if operation in ["create_box", "create_rounded_rectangle_plate", "create_open_enclosure"]:
            apply_feature(step)
            base_created = True
            break

    if not base_created:
        for step in steps:
            operation = step.get("operation") or step.get("action")

            if operation in ["create_cylinder", "create_lid"]:
                apply_feature(step)
                break

    ensure_model()

    early_operations = {"create_chamfer", "create_fillet"}

    if base_meta is not None:
        for step in steps:
            operation = step.get("operation") or step.get("action")
            scope = step.get("scope")

            if operation in early_operations and scope in [
                "base_top_outer_edges",
                "base_outer_vertical_edges",
            ]:
                apply_feature(step)

    for step in steps:
        operation = step.get("operation") or step.get("action")
        scope = step.get("scope")

        if operation in ["create_box", "create_rounded_rectangle_plate", "create_open_enclosure"]:
            continue

        if base_created and operation in early_operations and scope in [
            "base_top_outer_edges",
            "base_outer_vertical_edges",
        ]:
            continue

        if operation in ["create_cylinder", "create_lid"] and not base_created:
            continue

        apply_feature(step)

    ensure_model()
    return model


def build_parts(parts):
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("CAD plan has 'parts' but the parts list is empty or invalid.")

    part_models = {}
    part_bboxes = {}

    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            warn(f"Invalid part at index {index}; skipped.")
            continue

        name = part.get("name") or part.get("part_name") or part.get("id") or part.get("label")

        if not name:
            name = f"part_{index + 1}"
            warn(f"Part at index {index} has no name. Using generated name: {name}")

        steps = part.get("steps", [])
        part_model = build_model_from_steps(steps, part_name=name)
        part_models[name] = part_model
        part_bboxes[name] = get_model_bbox(part_model)
        print("Part bbox", name, part_bboxes[name])

    if not part_models:
        raise RuntimeError("No valid part models were generated.")

    return part_models, part_bboxes


def rotation_is_zero(rotation):
    rotation = as_rotation(rotation, [0.0, 0.0, 0.0])
    return all(abs(value) < 1e-9 for value in rotation)


def safe_file_component(value):
    text = str(value or "part").strip()
    safe = []

    for char in text:
        if char.isalnum() or char in ["_", "-"]:
            safe.append(char)
        else:
            safe.append("_")

    result = "".join(safe).strip("_")
    return result or "part"


def default_assembly_for_parts(part_models):
    return [
        {
            "part": part_name,
            "position": [0, 0, 0],
            "rotation": [0, 0, 0],
        }
        for part_name in part_models.keys()
    ]


def normalized_assembly_items(part_models, assembly):
    if not isinstance(assembly, list) or not assembly:
        warn("No assembly list provided. Placing every part at [0, 0, 0].")
        assembly = default_assembly_for_parts(part_models)

    normalized = []

    for index, item in enumerate(assembly):
        if not isinstance(item, dict):
            warn(f"Invalid assembly item at index {index}; skipped.")
            continue

        part_name = item.get("part") or item.get("part_name") or item.get("target_part") or item.get("component") or item.get("name")

        if part_name not in part_models:
            warn(f"Assembly item references unknown part '{part_name}'; skipped.")
            continue

        has_position = "position" in item and item.get("position") is not None
        position = as_position(item.get("position"), [0.0, 0.0, 0.0]) if has_position else None
        rotation = as_rotation(item.get("rotation"), [0.0, 0.0, 0.0])

        normalized.append(
            {
                "index": index,
                "part_name": part_name,
                "position": position,
                "has_position": has_position,
                "rotation": rotation,
                "place": item.get("place") or item.get("placement") or item.get("relation"),
                "target": item.get("target") or item.get("target_part") or item.get("relative_to") or item.get("reference"),
                "target_instance": item.get("target_instance"),
                "gap": number(item.get("gap"), number(item.get("spacing"), 0.0)),
                "clearance": number(item.get("clearance"), number(item.get("clearance_z"), 0.0)),
                "align": item.get("align"),
                "offset": as_position(item.get("offset") or item.get("additional_offset"), [0.0, 0.0, 0.0]),
            }
        )

    if not normalized:
        raise RuntimeError("Assembly did not contain any valid part placement.")

    return normalized


def export_individual_part_steps(part_models):
    output_dir = os.path.dirname(STEP_PATH)
    base_name = os.path.splitext(os.path.basename(STEP_PATH))[0]

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    for part_name, part_model in part_models.items():
        safe_part_name = safe_file_component(part_name)
        part_step_path = os.path.join(output_dir, f"{base_name}_{safe_part_name}.step")

        try:
            print("Exporting individual part STEP:", part_name, "->", part_step_path)
            exporters.export(part_model, part_step_path)
        except Exception as e:
            warn(f"Failed to export individual STEP for part '{part_name}': {e}")


def rotate_part_model(part_model, rotation):
    rotation = as_rotation(rotation, [0.0, 0.0, 0.0])
    placed_model = part_model

    rx, ry, rz = rotation

    if abs(rx) > 1e-9:
        placed_model = placed_model.rotate((0, 0, 0), (1, 0, 0), rx)

    if abs(ry) > 1e-9:
        placed_model = placed_model.rotate((0, 0, 0), (0, 1, 0), ry)

    if abs(rz) > 1e-9:
        placed_model = placed_model.rotate((0, 0, 0), (0, 0, 1), rz)

    return placed_model


def translate_part_model(part_model, position):
    position = as_position(position, [0.0, 0.0, 0.0])
    return part_model.translate((position[0], position[1], position[2]))


def transform_part_for_assembly(part_model, position, rotation):
    rotated_model = rotate_part_model(part_model, rotation)
    return translate_part_model(rotated_model, position)


def make_location(position, rotation):
    # Rotation and translation are applied directly to the placed model for robustness.
    # The assembly Location remains at origin to avoid double-transforming.
    return cq.Location(cq.Vector(0, 0, 0))


def find_target_instance_bbox(target, target_instance, placed_instances):
    if target_instance and target_instance in placed_instances:
        return placed_instances[target_instance]["bbox"], target_instance

    if target and target in placed_instances:
        return placed_instances[target]["bbox"], target

    if target:
        for instance_name, data in placed_instances.items():
            if data.get("part") == target:
                return data.get("bbox"), instance_name

    return None, None


def set_axis_center(position, axis, target_bbox, part_bbox):
    if axis == "x":
        position[0] = target_bbox["x_center"] - part_bbox["x_center"]
    elif axis == "y":
        position[1] = target_bbox["y_center"] - part_bbox["y_center"]
    elif axis == "z":
        position[2] = target_bbox["z_center"] - part_bbox["z_center"]


def set_axis_min(position, axis, target_bbox, part_bbox):
    if axis == "x":
        position[0] = target_bbox["x_min"] - part_bbox["x_min"]
    elif axis == "y":
        position[1] = target_bbox["y_min"] - part_bbox["y_min"]
    elif axis == "z":
        position[2] = target_bbox["z_min"] - part_bbox["z_min"]


def set_axis_max(position, axis, target_bbox, part_bbox):
    if axis == "x":
        position[0] = target_bbox["x_max"] - part_bbox["x_max"]
    elif axis == "y":
        position[1] = target_bbox["y_max"] - part_bbox["y_max"]
    elif axis == "z":
        position[2] = target_bbox["z_max"] - part_bbox["z_max"]


def apply_align_rule(position, align, target_bbox, part_bbox, protected_axes=None):
    if protected_axes is None:
        protected_axes = set()

    if not align:
        return position

    align = str(align).strip().lower()

    if align == "center":
        if "x" not in protected_axes:
            set_axis_center(position, "x", target_bbox, part_bbox)
        if "y" not in protected_axes:
            set_axis_center(position, "y", target_bbox, part_bbox)
        if "z" not in protected_axes:
            set_axis_center(position, "z", target_bbox, part_bbox)

    elif align == "center_x" and "x" not in protected_axes:
        set_axis_center(position, "x", target_bbox, part_bbox)

    elif align == "center_y" and "y" not in protected_axes:
        set_axis_center(position, "y", target_bbox, part_bbox)

    elif align == "center_z" and "z" not in protected_axes:
        set_axis_center(position, "z", target_bbox, part_bbox)

    elif align == "top" and "z" not in protected_axes:
        set_axis_max(position, "z", target_bbox, part_bbox)

    elif align == "bottom" and "z" not in protected_axes:
        set_axis_min(position, "z", target_bbox, part_bbox)

    elif align == "front" and "y" not in protected_axes:
        set_axis_min(position, "y", target_bbox, part_bbox)

    elif align == "back" and "y" not in protected_axes:
        set_axis_max(position, "y", target_bbox, part_bbox)

    elif align == "left" and "x" not in protected_axes:
        set_axis_min(position, "x", target_bbox, part_bbox)

    elif align == "right" and "x" not in protected_axes:
        set_axis_max(position, "x", target_bbox, part_bbox)

    else:
        warn(f"Unsupported or context-protected align rule ignored: {align}")

    return position


def compute_smart_position(item, part_name, rotated_part_bbox, placed_instances):
    if item.get("has_position"):
        return as_position(item.get("position"), [0.0, 0.0, 0.0]), "absolute", None

    place = item.get("place")
    target = item.get("target")

    if not place or not target:
        warn(f"Assembly item for part '{part_name}' has no position and no place/target rule. Falling back to [0, 0, 0].")
        return [0.0, 0.0, 0.0], "fallback_origin", None

    place = str(place).strip().lower()
    align = item.get("align")
    gap = number(item.get("gap"), 0.0) or 0.0
    clearance = number(item.get("clearance"), 0.0) or 0.0
    offset = as_position(item.get("offset"), [0.0, 0.0, 0.0])

    target_bbox, target_label = find_target_instance_bbox(
        target=target,
        target_instance=item.get("target_instance"),
        placed_instances=placed_instances,
    )

    if target_bbox is None:
        warn(f"Smart placement target '{target}' not found for part '{part_name}'. Falling back to [0, 0, 0].")
        return offset, f"smart_target_missing:{place}", None

    part_bbox = rotated_part_bbox
    position = [0.0, 0.0, 0.0]
    protected_axes = set()

    if place == "on_top_of":
        set_axis_center(position, "x", target_bbox, part_bbox)
        set_axis_center(position, "y", target_bbox, part_bbox)
        position[2] = target_bbox["z_max"] - part_bbox["z_min"] + clearance
        protected_axes.add("z")
        if align is None:
            align = "center_x"  # x/y already centered above; this is harmless and explicit.

    elif place == "under":
        set_axis_center(position, "x", target_bbox, part_bbox)
        set_axis_center(position, "y", target_bbox, part_bbox)
        position[2] = target_bbox["z_min"] - part_bbox["z_max"] - clearance
        protected_axes.add("z")

    elif place == "right_of":
        position[0] = target_bbox["x_max"] - part_bbox["x_min"] + gap
        set_axis_center(position, "y", target_bbox, part_bbox)
        set_axis_min(position, "z", target_bbox, part_bbox)
        protected_axes.add("x")
        if align is None:
            align = "center_y"

    elif place == "left_of":
        position[0] = target_bbox["x_min"] - part_bbox["x_max"] - gap
        set_axis_center(position, "y", target_bbox, part_bbox)
        set_axis_min(position, "z", target_bbox, part_bbox)
        protected_axes.add("x")
        if align is None:
            align = "center_y"

    elif place == "in_front_of":
        position[1] = target_bbox["y_min"] - part_bbox["y_max"] - gap
        set_axis_center(position, "x", target_bbox, part_bbox)
        set_axis_min(position, "z", target_bbox, part_bbox)
        protected_axes.add("y")
        if align is None:
            align = "center_x"

    elif place == "behind":
        position[1] = target_bbox["y_max"] - part_bbox["y_min"] + gap
        set_axis_center(position, "x", target_bbox, part_bbox)
        set_axis_min(position, "z", target_bbox, part_bbox)
        protected_axes.add("y")
        if align is None:
            align = "center_x"

    elif place == "centered_on":
        set_axis_center(position, "x", target_bbox, part_bbox)
        set_axis_center(position, "y", target_bbox, part_bbox)
        position[2] = 0.0
        if align is None:
            align = "center_x"

    elif place == "flush_top":
        set_axis_min(position, "x", target_bbox, part_bbox)
        set_axis_min(position, "y", target_bbox, part_bbox)
        set_axis_max(position, "z", target_bbox, part_bbox)
        protected_axes.add("z")

    elif place == "flush_bottom":
        set_axis_min(position, "x", target_bbox, part_bbox)
        set_axis_min(position, "y", target_bbox, part_bbox)
        set_axis_min(position, "z", target_bbox, part_bbox)
        protected_axes.add("z")

    elif place == "same_position_as":
        set_axis_min(position, "x", target_bbox, part_bbox)
        set_axis_min(position, "y", target_bbox, part_bbox)
        set_axis_min(position, "z", target_bbox, part_bbox)

    else:
        warn(f"Unsupported smart placement rule '{place}' for part '{part_name}'. Falling back to [0, 0, 0].")
        position = [0.0, 0.0, 0.0]

    # Apply explicit alignment after the placement rule, without overriding the relation axis.
    if align:
        apply_align_rule(position, align, target_bbox, part_bbox, protected_axes=protected_axes)

    position = [
        position[0] + offset[0],
        position[1] + offset[1],
        position[2] + offset[2],
    ]

    return position, f"smart:{place}", target_label


def create_placed_assembly_models(part_models, part_bboxes, assembly):
    records = []
    used_names = set()
    placed_instances = {}

    for instance_index, item in enumerate(normalized_assembly_items(part_models, assembly)):
        part_name = item["part_name"]
        rotation = item["rotation"]
        safe_part_name = safe_file_component(part_name)
        instance_name = f"{safe_part_name}_{instance_index + 1}"

        while instance_name in used_names:
            instance_name = f"{safe_part_name}_{instance_index + 1}_{len(used_names) + 1}"

        used_names.add(instance_name)

        rotated_model = rotate_part_model(part_models[part_name], rotation)
        rotated_bbox = get_model_bbox(rotated_model)
        position, placement_mode, target_label = compute_smart_position(
            item=item,
            part_name=part_name,
            rotated_part_bbox=rotated_bbox,
            placed_instances=placed_instances,
        )
        placed_model = translate_part_model(rotated_model, position)
        placed_bbox = get_model_bbox(placed_model)

        if placement_mode == "absolute":
            print(
                "Adding assembly part",
                instance_name,
                "using absolute placement final position",
                position,
                "rotation",
                rotation,
            )
        else:
            print(
                "Adding assembly part",
                instance_name,
                "using",
                placement_mode,
                "target",
                target_label or item.get("target"),
                "final position",
                position,
                "rotation",
                rotation,
            )

        record = {
            "part_name": part_name,
            "instance_name": instance_name,
            "position": position,
            "rotation": rotation,
            "placed_model": placed_model,
            "bbox": placed_bbox,
            "placement_mode": placement_mode,
            "target": target_label,
        }

        records.append(record)
        placed_instances[instance_name] = {
            "part": part_name,
            "bbox": placed_bbox,
            "position": position,
            "rotation": rotation,
        }

        # First instance of a part can be referenced by the raw part name.
        if part_name not in placed_instances:
            placed_instances[part_name] = placed_instances[instance_name]

    if not records:
        raise RuntimeError("Assembly did not produce any valid placed models.")

    return records


def build_cadquery_assembly(part_models, part_bboxes, assembly):
    cad_assembly = cq.Assembly()
    records = create_placed_assembly_models(part_models, part_bboxes, assembly)

    for record in records:
        cad_assembly.add(
            record["placed_model"],
            name=record["instance_name"],
            loc=make_location(record["position"], record["rotation"]),
        )

    return cad_assembly


def build_union_assembly(part_models, part_bboxes, assembly):
    records = create_placed_assembly_models(part_models, part_bboxes, assembly)
    final_model = None

    for record in records:
        placed = record["placed_model"]

        if final_model is None:
            final_model = placed
        else:
            final_model = final_model.union(placed)

    if final_model is None:
        raise RuntimeError("Fallback union assembly did not produce any final model.")

    return final_model


def main():
    global model

    print("CadQuery generation started.")

    if isinstance(CAD_PLAN.get("parts"), list):
        parts = CAD_PLAN.get("parts", [])
        assembly = CAD_PLAN.get("assembly", [])

        print("Multi-part assembly mode enabled.")
        print("Number of parts:", len(parts))
        print("Number of assembly placements:", len(assembly) if isinstance(assembly, list) else 0)

        part_models, part_bboxes = build_parts(parts)
        export_individual_part_steps(part_models)

        output_dir = os.path.dirname(STEP_PATH)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            cad_assembly = build_cadquery_assembly(part_models, part_bboxes, assembly)
            print("Exporting named CadQuery Assembly STEP to:", STEP_PATH)
            exporters.export(cad_assembly, STEP_PATH)
            print("CadQuery named assembly export completed successfully.")

        except Exception as e:
            warn(f"CadQuery Assembly export failed. Falling back to union STEP export: {e}")
            traceback.print_exc()
            model = build_union_assembly(part_models, part_bboxes, assembly)
            print("Exporting fallback union STEP to:", STEP_PATH)
            exporters.export(model, STEP_PATH)
            print("CadQuery fallback union export completed successfully.")

    else:
        steps = CAD_PLAN.get("steps", [])

        if not steps:
            raise RuntimeError("CAD plan has no steps.")

        print("Single-part mode enabled.")
        model = build_model_from_steps(steps)

        output_dir = os.path.dirname(STEP_PATH)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        print("Exporting STEP to:", STEP_PATH)
        exporters.export(model, STEP_PATH)

    print("CadQuery generation completed successfully.")


if __name__ == "__main__":
    main()
"""

        script = script.replace("__CAD_PLAN_JSON__", cad_plan_json)
        script = script.replace("__STEP_PATH_JSON__", step_path_json)
        script = script.replace("__SUPPORTED_OPERATIONS__", supported_json)
        script = script.replace("__SKIPPED_OPERATIONS__", skipped_json)

        return script.strip() + "\n"