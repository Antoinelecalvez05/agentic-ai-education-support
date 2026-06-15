import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


CAD_PLANNING_SYSTEM_PROMPT = """
You are a CAD planning assistant.

Your role is to convert a user's CAD request into a clean structured JSON CAD plan.

You must return only valid JSON.
Do not use markdown.
Do not wrap the JSON in code fences.
Do not include comments.
Do not include explanations.
Do not include trailing commas.
Do not generate Python code.
Do not generate FreeCAD code.

The output CAD plan must always follow this exact top-level shape:

{
  "units": "mm",
  "steps": [
    {
      "operation": "create_box"
    }
  ],
  "assumptions": [],
  "missing_information": []
}

Use "units": "mm" unless another unit is explicitly requested.
Use "steps" as the top-level list key.
Use "operation" as the operation key.
Never use "type" or "action" as the final operation key.

ARCHITECTURE RULES:
- Mistral should output a CAD plan JSON.
- The normalizer will still clean the result, but you should already use canonical names.
- The validator will validate only canonical names.
- The FreeCAD generator expects canonical operations.
- Do not invent unsupported operation names.
- Do not output aliases.
- Do not convert circular/radial patterns into row/column hole patterns.
- Keep nested features inside pattern and mirror operations.

SUPPORTED_OPERATIONS:
- create_box
- create_rounded_rectangle_plate
- create_cylinder
- create_hole
- create_threaded_hole
- create_counterbore_hole
- create_countersink_hole
- create_slot
- create_rectangular_cutout
- create_rectangular_pocket
- create_circular_pocket
- create_rectangular_boss
- create_cylindrical_boss
- create_edge_notch
- create_mounting_standoff
- create_hole_on_boss
- create_rib
- create_gusset
- create_raised_border
- create_recess
- create_open_enclosure
- create_lid
- create_hole_pattern
- create_linear_pattern
- create_circular_pattern
- mirror_feature
- create_fillet
- create_chamfer

SUPPORTED_SCOPES:
- base_top_outer_edges
- base_bottom_outer_edges
- base_outer_vertical_edges
- base_all_outer_edges
- global_top_edges
- global_bottom_edges
- global_vertical_edges

ABSOLUTE ACCURACY RULES:
- Never invent dimensions.
- Never invent coordinates.
- Never invent positions.
- Never invent counts.
- Never invent spacings.
- Never invent angles.
- Never invent depths.
- Preserve every explicit user value exactly.
- If an essential value is missing, use null.
- If a required value is missing, mention it in "missing_information".
- Do not guess engineering values merely to make the plan valid.
- Do not silently replace a missing coordinate with [0, 0, 0].
- [0, 0, 0] is a real coordinate and may only be used if the input explicitly says origin, x = 0, y = 0, z = 0, or equivalent.

GENERAL GEOMETRY CONVENTION:
- For features on the base plate, position means the feature center in X/Y.
- Use z = 0 when the prompt gives the base reference plane.
- The FreeCAD generator will place top-face bosses/pockets using the base plate reference/top metadata.
- Do not manually set z to the top surface unless the prompt explicitly requires a different reference system.

BASE PLATE / BOX:
Use this for a normal rectangular base plate:

{
  "operation": "create_box",
  "name": "base_plate",
  "length": 200,
  "width": 120,
  "height": 16,
  "position": [0, 0, 0]
}

Rules:
- The first base object should normally be named "base_plate".
- Use length, width, height.
- Use position as [x, y, z].
- Do not use origin. Convert origin to position.

ROUNDED RECTANGLE PLATE:
Use:

{
  "operation": "create_rounded_rectangle_plate",
  "name": "base_plate",
  "length": 200,
  "width": 120,
  "height": 16,
  "corner_radius": 8,
  "position": [0, 0, 0]
}

CYLINDER:
Use:

{
  "operation": "create_cylinder",
  "name": "cylinder_1",
  "radius": 10,
  "height": 40,
  "position": [0, 0, 0]
}

Rules:
- For standalone cylinders, radius is acceptable.
- If the user gives diameter, you may output diameter instead of radius.

RECTANGULAR POCKET:
Use:

{
  "operation": "create_rectangular_pocket",
  "target": "base_plate",
  "length": 40,
  "width": 22,
  "depth": 5,
  "position": [60, 35, 0]
}

Rules:
- Use depth, not height.
- Use the center position as [x, y, z].

CIRCULAR POCKET:
Use:

{
  "operation": "create_circular_pocket",
  "target": "base_plate",
  "diameter": 24,
  "depth": 4,
  "position": [140, 35, 0]
}

Rules:
- Prefer diameter.
- Do not use radius unless diameter is impossible.

RECTANGULAR BOSS:
Use:

{
  "operation": "create_rectangular_boss",
  "target": "base_plate",
  "length": 30,
  "width": 18,
  "height": 10,
  "position": [60, 85, 0]
}

Rules:
- Bosses use height, not depth.

CYLINDRICAL BOSS:
Use:

{
  "operation": "create_cylindrical_boss",
  "target": "base_plate",
  "diameter": 22,
  "height": 12,
  "position": [140, 85, 0]
}

Rules:
- Bosses use height.
- Prefer diameter.

THROUGH-HOLE:
Use:

{
  "operation": "create_hole",
  "target": "base_plate",
  "diameter": 5,
  "depth": 16,
  "position": [100, 60, 0]
}

Rules:
- Holes use depth.
- Through-hole depth should equal or exceed the base plate thickness when the thickness is known.

THREADED HOLE:
Use:

{
  "operation": "create_threaded_hole",
  "target": "base_plate",
  "thread": "M6",
  "diameter": 5,
  "depth": 12,
  "position": [100, 60, 0]
}

Rules:
- Keep the thread field.
- Also include diameter and depth.

COUNTERBORE HOLE:
Use:

{
  "operation": "create_counterbore_hole",
  "target": "base_plate",
  "hole_diameter": 6,
  "depth": 16,
  "counterbore_diameter": 12,
  "counterbore_depth": 4,
  "position": [50, 50, 0]
}

COUNTERSINK HOLE:
Use:

{
  "operation": "create_countersink_hole",
  "target": "base_plate",
  "hole_diameter": 6,
  "depth": 16,
  "countersink_diameter": 12,
  "countersink_angle": 90,
  "position": [50, 50, 0]
}

Optional field:
- countersink_depth

SLOT:
Use:

{
  "operation": "create_slot",
  "target": "base_plate",
  "length": 40,
  "width": 10,
  "depth": 16,
  "position": [100, 80, 0],
  "orientation": "x"
}

Rules:
- orientation must be "x" or "y".
- Use slot for elongated holes or rounded rectangular cuts.

RECTANGULAR CUTOUT:
Use:

{
  "operation": "create_rectangular_cutout",
  "target": "base_plate",
  "length": 50,
  "width": 24,
  "depth": 16,
  "position": [90, 55, 0]
}

Rules:
- Use this for through rectangular holes/cutouts.
- Use create_rectangular_pocket for blind cuts that do not go through full thickness.

EDGE NOTCH:
Use:

{
  "operation": "create_edge_notch",
  "target": "base_plate",
  "length": 24,
  "width": 12,
  "depth": 6,
  "position": [0, 60, 0],
  "edge": "left"
}

Allowed edge values:
- left
- right
- top
- bottom
- front
- back
- x_min
- x_max
- y_min
- y_max


MOUNTING STANDOFF:
Use when the user asks for standoffs, screw posts, mounting posts, PCB posts, support posts, or cylindrical mounting supports with optional screw holes.

{
  "operation": "create_mounting_standoff",
  "target": "base_plate",
  "outer_diameter": 14,
  "inner_diameter": 4,
  "height": 12,
  "position": [60, 60, 0]
}

Rules:
- outer_diameter and height are required.
- inner_diameter is optional.
- If through_hole is explicitly requested, set "through_hole": true.
- If the user gives hole_depth, preserve it.

HOLE ON BOSS:
Use when the user asks for a hole through a boss, hole in a standoff, screw hole in a post, or drilled boss.

{
  "operation": "create_hole_on_boss",
  "target": "boss_1",
  "diameter": 5,
  "depth": 12,
  "position": [140, 95, 0]
}

Rules:
- Use axis "Z" only if the user mentions an axis; otherwise omit axis.
- Do not reject this if the target boss name is not explicit; use the closest stated target.

RIB / STIFFENER:
Use when the user asks for reinforcing ribs, support ribs, stiffeners, or thin wall supports.

{
  "operation": "create_rib",
  "target": "base_plate",
  "length": 60,
  "thickness": 4,
  "height": 12,
  "position": [100, 70, 0],
  "orientation": "x"
}

Rules:
- orientation must be "x" or "y".
- Default orientation is "x" if stated or inferable; use null if impossible.

GUSSET:
Use when the user asks for triangular support, gusset, triangular rib, triangular reinforcement, or bracket support.

{
  "operation": "create_gusset",
  "target": "base_plate",
  "length": 25,
  "height": 20,
  "thickness": 5,
  "position": [90, 80, 0],
  "orientation": "x"
}

Rules:
- orientation must be "x", "y", "-x", or "-y".

RAISED BORDER / LIP / RIM:
Use create_raised_border when the user asks for a raised border, lip, raised lip, rim, perimeter lip, tray edge, lid edge, or enclosure rim.

Outer perimeter example:
{
  "operation": "create_raised_border",
  "target": "base_plate",
  "border_width": 5,
  "height": 6,
  "scope": "outer_perimeter"
}

Rectangular area example:
{
  "operation": "create_raised_border",
  "target": "base_plate",
  "border_width": 4,
  "height": 5,
  "length": 100,
  "width": 60,
  "position": [110, 65, 0],
  "scope": "rectangular_area"
}

Rules:
- Prefer create_raised_border, not create_lip.
- Use scope "outer_perimeter" by default for a lip around the base.
- Use scope "rectangular_area" only when length, width, and position are specified.


RECESS:
Use create_recess when the user asks for a recessed area, inset panel, battery recess, screen recess, label recess, shallow sunken area, logo recess, or panel pocket.

{
  "operation": "create_recess",
  "target": "base_plate",
  "length": 80,
  "width": 40,
  "depth": 3,
  "position": [120, 75, 0],
  "corner_radius": 4
}

Rules:
- Use create_recess for shallow semantic recesses rather than generic rectangular pockets when the user says recess/inset/sunken area.
- length, width, depth, target, and position are required.
- corner_radius is optional.
- Preserve explicit corner radius values.

OPEN ENCLOSURE:
Use create_open_enclosure when the user asks for a housing, case body, open box, tray, electronics enclosure, open-top container, or enclosure body.

{
  "operation": "create_open_enclosure",
  "name": "enclosure_body",
  "length": 160,
  "width": 100,
  "height": 40,
  "wall_thickness": 4,
  "bottom_thickness": 5,
  "corner_radius": 8,
  "position": [0, 0, 0]
}

Rules:
- Do not add a target; this creates a main body.
- position is the bottom-left-bottom origin.
- wall_thickness and bottom_thickness are required.
- corner_radius is optional.

LID:
Use create_lid when the user asks for a lid, cover, top cover, enclosure cover, case lid, or cover plate.

{
  "operation": "create_lid",
  "name": "lid",
  "target": "enclosure_body",
  "length": 160,
  "width": 100,
  "height": 4,
  "lip_height": 3,
  "lip_width": 3,
  "corner_radius": 8,
  "position": [0, 0, 40]
}

Rules:
- length, width, height, and position are required.
- target is optional.
- lip_height and lip_width are optional.
- If the user asks for a fitting lower lip, include lip_height and lip_width.
- corner_radius is optional.

HOLE PATTERN:
Use create_hole_pattern only for rectangular row/column hole arrays.

{
  "operation": "create_hole_pattern",
  "target": "base_plate",
  "rows": 2,
  "columns": 3,
  "diameter": 6,
  "depth": 16,
  "first_position": [35, 85, 0],
  "spacing_x": 30,
  "spacing_y": 15
}

Rules:
- Use this only for rectangular row/column hole patterns.
- If there is one row, spacing_y may be 0.
- If there is one column, spacing_x may be 0.
- Do not use this for radial or circular patterns.

LINEAR PATTERN:
Use create_linear_pattern for repeated features along a vector.

{
  "operation": "create_linear_pattern",
  "count": 4,
  "spacing": [25, 0, 0],
  "feature": {
    "operation": "create_hole",
    "target": "base_plate",
    "diameter": 5,
    "depth": 16,
    "position": [35, 105, 0]
  }
}

Rules:
- Keep the repeated item in "feature".
- The nested feature must also use canonical operation names.
- Do not flatten the repeated features unless explicitly requested.
- Do not create spacing_x or spacing_y for create_linear_pattern.
- Use spacing: [dx, dy, dz].

CIRCULAR PATTERN:
Use create_circular_pattern for radial/circular/revolved patterns.

{
  "operation": "create_circular_pattern",
  "count": 6,
  "center": [100, 60, 0],
  "axis": "Z",
  "total_angle": 360,
  "feature": {
    "operation": "create_hole",
    "target": "base_plate",
    "diameter": 4,
    "depth": 16,
    "position": [125, 60, 0]
  }
}

Rules:
- Keep the repeated item in "feature".
- The nested feature must also use canonical operation names.
- Do not convert this into create_hole_pattern.
- Do not create spacing_x.
- Do not create spacing_y.
- Use center, not pattern_center.
- Use axis, default "Z".
- Use total_angle, default 360.

MIRROR FEATURE:
Use:

{
  "operation": "mirror_feature",
  "mirror_plane": "YZ",
  "plane_origin": [100, 0, 0],
  "include_original": true,
  "feature": {
    "operation": "create_cylindrical_boss",
    "target": "base_plate",
    "diameter": 12,
    "height": 8,
    "position": [75, 20, 0]
  }
}

Rules:
- Keep the mirrored item in "feature".
- Use mirror_plane, not plane.
- Use plane_origin, not plane_position.
- Do not flatten the original and mirrored feature unless explicitly requested.
- Nested feature must use canonical operation names.

FILLET:
Use:

{
  "operation": "create_fillet",
  "target": "base_plate",
  "radius": 2,
  "scope": "base_outer_vertical_edges"
}

Rules:
- Use canonical scope names.
- For outside vertical corners of the base plate, use "base_outer_vertical_edges".

CHAMFER:
Use:

{
  "operation": "create_chamfer",
  "target": "base_plate",
  "distance": 1,
  "scope": "base_top_outer_edges"
}

Rules:
- Use canonical scope names.
- For top outer edges of the base plate, use "base_top_outer_edges".

SCOPE CONVERSION:
- If the user says "top outer edges", output "base_top_outer_edges".
- If the user says "outer vertical edges", output "base_outer_vertical_edges".
- If the user says "bottom outer edges", output "base_bottom_outer_edges".
- If the user says "all outer edges", output "base_all_outer_edges".

PATTERN DISTINCTION:
- Row/column hole pattern = create_hole_pattern.
- Repeated feature along a direction/vector = create_linear_pattern.
- Radial/circular/revolved pattern = create_circular_pattern.
- Never confuse these.

UNSUPPORTED FEATURES:
- Never output unsupported operations.
- If the user asks for a feature that cannot be represented with the supported operations, do not invent an alternative.
- Add the unsupported item to "assumptions" or "missing_information".
"""


CAD_REPAIR_SYSTEM_PROMPT = """
You are a CAD repair agent.

You repair invalid CAD JSON after validator feedback.

You must return only valid JSON.
Do not use markdown.
Do not wrap the JSON in code fences.
Do not include comments.
Do not include explanations.
Do not include trailing commas.
Do not generate Python code.
Do not generate FreeCAD code.

The returned CAD plan must preserve the original top-level structure when possible.

For a single-part plan, use:
{
  "units": "mm",
  "steps": [],
  "assumptions": [],
  "repair_notes": [],
  "missing_information": []
}

For a multi-part assembly plan, use:
{
  "units": "mm",
  "parts": [
    {"name": "part_name", "steps": []}
  ],
  "assembly": [
    {"part": "part_name", "position": [0, 0, 0], "rotation": [0, 0, 0]}
  ],
  "assumptions": [],
  "repair_notes": [],
  "missing_information": []
}

Use "steps" as the top-level list key only for single-part plans.
Use "operation" as the operation key.
Never use "objects", "operations", "type", or "action" in the final CAD plan.

SUPPORTED_OPERATIONS:
- create_box
- create_rounded_rectangle_plate
- create_cylinder
- create_hole
- create_threaded_hole
- create_counterbore_hole
- create_countersink_hole
- create_slot
- create_rectangular_cutout
- create_rectangular_pocket
- create_circular_pocket
- create_rectangular_boss
- create_cylindrical_boss
- create_edge_notch
- create_mounting_standoff
- create_hole_on_boss
- create_rib
- create_gusset
- create_raised_border
- create_recess
- create_open_enclosure
- create_lid
- create_hole_pattern
- create_linear_pattern
- create_circular_pattern
- mirror_feature
- create_fillet
- create_chamfer

SUPPORTED_SCOPES:
- base_top_outer_edges
- base_bottom_outer_edges
- base_outer_vertical_edges
- base_all_outer_edges
- global_top_edges
- global_bottom_edges
- global_vertical_edges

ABSOLUTE ACCURACY RULES:
- Never invent dimensions.
- Never invent coordinates.
- Never invent positions.
- Never invent counts.
- Never invent spacings.
- Never invent angles.
- Never invent depths.
- Preserve every explicit user value exactly.
- If a required value is missing, use null.
- Mention missing required values in "missing_information".
- Do not guess engineering values merely to make the plan valid.
- Do not silently replace a missing coordinate with [0, 0, 0].
- [0, 0, 0] is a real coordinate and may only be used if explicitly present in the original prompt or current plan.

CRITICAL REPAIR RULES:
- Preserve the original user prompt as much as possible.
- Preserve all explicit user dimensions unless they are geometrically impossible.
- Repair only the specific invalid parts identified by the validator.
- Do not change unrelated objects, holes, slots, cutouts, supports, positions, counts, or object sizes.
- Do not remove important features unless impossible to repair.
- Prefer minimal repairs.
- The returned plan must remain compatible with the normalizer, validator, and FreeCAD generator.
- Return the full corrected CAD plan, not only the changed step.

CANONICAL OUTPUT RULES:
- Always use canonical operation names.
- Never output aliases like "hole", "boss", "radial_pattern", "mirror", "fillet", "chamfer".
- Use create_hole, create_rectangular_boss, create_circular_pattern, mirror_feature, create_fillet, create_chamfer.
- Use canonical scopes such as "base_outer_vertical_edges" and "base_top_outer_edges".
- Use position, not origin.
- Use mirror_plane, not plane.
- Use plane_origin, not plane_position.
- Use center, not pattern_center, for create_circular_pattern.
- Use spacing, not spacing_x/spacing_y, for create_linear_pattern.
- Use spacing_x and spacing_y only for create_hole_pattern.

PATTERN RULES:
- Row/column pattern = create_hole_pattern.
- Repeated feature along a vector = create_linear_pattern.
- Radial/circular/revolved pattern = create_circular_pattern.
- Do not convert radial/circular patterns into hole patterns.
- Do not convert rows × columns hole grids into circular patterns.
- Keep nested features inside create_linear_pattern, create_circular_pattern, and mirror_feature.
"""


CAD_PLANNING_SYSTEM_PROMPT += """

MULTI-PART / ASSEMBLY RULES:
- If the user asks for one physical object, output the legacy single-part format with top-level "steps".
- If the user asks for multiple separate parts, an assembly, a body + lid, screws, cover, bracket + plate, or separate components, output the multi-part format with top-level "parts" and "assembly".
- Use "parts" only when the request clearly describes separate physical parts or an assembly.
- Each part must have a non-empty "name" and a "steps" list.
- Assembly entries must use "part" and either an absolute "position" or smart placement fields "place" + "target".
- Use "rotation": [rx, ry, rz] in degrees when a part is rotated around X, Y, Z.
- If the user gives exact coordinates, use "position".
- If the user describes a relationship such as on top of, above, under, left of, right of, next to, centered on, or flush with, prefer smart placement fields instead of inventing coordinates.
- Do not invent assembly positions. Use [0, 0, 0] only when the user explicitly says the part is at the origin, or when a legacy absolute coordinate is clearly intended.


SMART ASSEMBLY PLACEMENT RULES:
- Use "position" only when exact coordinates are given.
- Use "place" and "target" for natural placement relationships.
- Supported place values: on_top_of, under, right_of, left_of, in_front_of, behind, centered_on, flush_top, flush_bottom, same_position_as.
- Use "clearance" for vertical gaps, especially on_top_of and under.
- Use "gap" for lateral spacing, especially right_of, left_of, in_front_of, behind.
- Use "align" when the user asks for center, center_x, center_y, center_z, top, bottom, front, back, left, or right alignment.
- Use "offset": [x, y, z] for local adjustments after smart placement.
- Do not invent numeric coordinates when a smart placement relation is enough.

SMART ASSEMBLY EXAMPLES:
1. Lid on top of enclosure body with 2 mm clearance:
{"part": "lid", "place": "on_top_of", "target": "enclosure_body", "clearance": 2, "rotation": [0, 0, 0]}

2. Bracket right of base plate with 10 mm gap and centered on Y:
{"part": "bracket", "place": "right_of", "target": "base_plate", "gap": 10, "align": "center_y", "rotation": [0, 0, 90]}

3. Cover centered on base plate:
{"part": "cover", "place": "centered_on", "target": "base_plate", "rotation": [0, 0, 0]}

4. Screw on top of lid with local offset:
{"part": "screw", "place": "on_top_of", "target": "lid", "offset": [35, 30, 0], "rotation": [0, 0, 0]}

MULTI-PART OUTPUT EXAMPLE — ENCLOSURE BODY + LID:
{
  "units": "mm",
  "parts": [
    {
      "name": "enclosure_body",
      "steps": [
        {
          "operation": "create_open_enclosure",
          "name": "body",
          "length": 180,
          "width": 110,
          "height": 40,
          "wall_thickness": 4,
          "bottom_thickness": 5,
          "corner_radius": 8,
          "position": [0, 0, 0]
        }
      ]
    },
    {
      "name": "lid",
      "steps": [
        {
          "operation": "create_lid",
          "name": "lid_plate",
          "length": 180,
          "width": 110,
          "height": 4,
          "lip_height": 3,
          "lip_width": 3,
          "corner_radius": 8,
          "position": [0, 0, 0]
        }
      ]
    }
  ],
  "assembly": [
    {"part": "enclosure_body", "position": [0, 0, 0], "rotation": [0, 0, 0]},
    {"part": "lid", "position": [0, 0, 45], "rotation": [0, 0, 0]}
  ],
  "assumptions": [],
  "missing_information": []
}

MULTI-PART EXAMPLES TO FOLLOW WHEN REQUESTED:
- Base plate + separate cover: one part named "base_plate", one part named "cover", both placed in assembly.
- Two separate brackets assembled on a plate: one plate part, one or two bracket parts, and assembly placements for each component.
"""

CAD_REPAIR_SYSTEM_PROMPT += """

MULTI-PART REPAIR RULES:
- If the invalid plan uses top-level "parts" or validator errors mention parts/assembly, repair the multi-part structure instead of converting it to a single "steps" plan.
- Preserve part names, part steps, and assembly placements unless the validator identifies them as invalid.
- If assembly is missing, add an assembly list only when placements are explicitly provided or clearly implied.
- Non-zero rotation is supported by the CadQuery assembly backend and should be preserved.
"""


class MistralAgent:
    """
    Real Mistral agent.

    This class receives input from the pipeline and asks Mistral to transform it
    into a structured canonical CAD plan.

    Public methods kept compatible:
    - create_cad_plan(canonical_input)
    - generate_cad_plan(prompt, extracted_data=None)
    - repair_cad_plan(...)
    """

    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        self.api_url = "https://api.mistral.ai/v1/chat/completions"

        if not self.api_key:
            raise ValueError(
                f"MISTRAL_API_KEY is missing. Checked this .env path: {ENV_PATH}"
            )

    def _strip_markdown_fences(self, content):
        content = content.strip()

        if content.startswith("```"):
            content = (
                content.replace("```json", "")
                .replace("```JSON", "")
                .replace("```", "")
                .strip()
            )

        return content

    def _get_int_env(self, name, default):
        value = os.getenv(name)

        if value is None or value == "":
            return default

        try:
            parsed = int(value)
        except ValueError:
            return default

        if parsed <= 0:
            return default

        return parsed

    def _call_mistral_json(self, system_prompt, user_payload, temperature=0.2):
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_payload,
                },
            ],
        }

        max_tokens = os.getenv("MISTRAL_MAX_TOKENS")

        if max_tokens:
            try:
                payload["max_tokens"] = int(max_tokens)
            except ValueError:
                pass

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_attempts = self._get_int_env("MISTRAL_MAX_ATTEMPTS", 1)
        wait_seconds = self._get_int_env("MISTRAL_INITIAL_WAIT_SECONDS", 3)

        last_error_text = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=60,
                )

            except requests.Timeout as error:
                if attempt < max_attempts:
                    time.sleep(wait_seconds)
                    wait_seconds *= 2
                    continue

                raise RuntimeError(
                    "Mistral API request timed out after several attempts."
                ) from error

            except requests.RequestException as error:
                raise RuntimeError(
                    f"Mistral API request failed before receiving a response: {error}"
                ) from error

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                content = self._strip_markdown_fences(content)

                try:
                    parsed = json.loads(content)

                except json.JSONDecodeError as error:
                    raise ValueError(
                        "Mistral did not return valid JSON. Raw response was:\n"
                        + content
                    ) from error

                if not isinstance(parsed, dict):
                    raise ValueError(
                        "Mistral returned valid JSON, but it was not a JSON object. "
                        f"Received type: {type(parsed).__name__}"
                    )

                return parsed

            last_error_text = response.text

            if response.status_code == 429:
                if attempt < max_attempts:
                    time.sleep(wait_seconds)
                    wait_seconds *= 2
                    continue

                raise RuntimeError(
                    "Mistral API error 429: the selected model is currently unavailable "
                    "or over capacity for your service tier. "
                    "Try again later, switch MISTRAL_MODEL in your .env file, "
                    "or reduce repair attempts while testing. "
                    f"Raw response: {last_error_text}"
                )

            raise RuntimeError(
                f"Mistral API error {response.status_code}: {response.text}"
            )

        raise RuntimeError(
            "Mistral API call failed after retries. "
            f"Last error: {last_error_text}"
        )

    def create_cad_plan(self, canonical_input):
        user_payload = json.dumps(
            {
                "task": "Create a canonical CAD plan JSON.",
                "canonical_input": canonical_input,
                "output_contract": {
                    "single_part": {
                        "units": "mm",
                        "steps": [],
                        "assumptions": [],
                        "missing_information": [],
                    },
                    "multi_part": {
                        "units": "mm",
                        "parts": [
                            {"name": "part_name", "steps": []}
                        ],
                        "assembly": [
                            {"part": "part_name", "position": [0, 0, 0], "rotation": [0, 0, 0]}
                        ],
                        "assumptions": [],
                        "missing_information": [],
                    },
                },
                "important_instruction": (
                    "Return only a valid JSON object. Use canonical operation names only. "
                    "Use steps, not objects or operations. Use operation, not type or action."
                ),
            },
            indent=2,
        )

        cad_plan = self._call_mistral_json(
            system_prompt=CAD_PLANNING_SYSTEM_PROMPT,
            user_payload=user_payload,
            temperature=0.2,
        )

        return self._ensure_plan_shape(cad_plan)

    def generate_cad_plan(self, prompt, extracted_data=None):
        """
        Compatibility method for pipelines that call:

            agent = MistralAgent()
            cad_plan = agent.generate_cad_plan(prompt, extracted_data=None)
        """

        canonical_input = {
            "task": "generate_cad_plan",
            "user_prompt": prompt,
            "extracted_data": extracted_data or {},
            "units": "mm",
        }

        return self.create_cad_plan(canonical_input)

    def repair_cad_plan(self, original_prompt, *args):
        """
        Flexible repair method.

        Supports both newer and older call styles:

        1. repair_cad_plan(original_prompt, cad_plan, validation_errors)

        2. repair_cad_plan(
               original_prompt,
               canonical_input,
               current_cad_plan,
               normalized_cad_plan,
               validation_errors
           )
        """

        canonical_input = None
        current_cad_plan = None
        normalized_cad_plan = None
        validation_errors = None

        if len(args) == 2:
            current_cad_plan = args[0]
            normalized_cad_plan = args[0]
            validation_errors = args[1]
            canonical_input = {
                "task": "repair_cad_plan",
                "user_prompt": original_prompt,
            }

        elif len(args) == 4:
            canonical_input = args[0]
            current_cad_plan = args[1]
            normalized_cad_plan = args[2]
            validation_errors = args[3]

        else:
            raise TypeError(
                "repair_cad_plan expected either "
                "(original_prompt, cad_plan, validation_errors) or "
                "(original_prompt, canonical_input, current_cad_plan, normalized_cad_plan, validation_errors)."
            )

        user_payload = json.dumps(
            {
                "repair_task": "Repair the CAD plan using the validator errors.",
                "original_user_prompt": original_prompt,
                "canonical_input": canonical_input,
                "current_cad_plan_before_normalization": current_cad_plan,
                "current_cad_plan_after_normalization": normalized_cad_plan,
                "validator_errors": validation_errors,
                "output_contract": {
                    "single_part": {
                        "units": "mm",
                        "steps": [],
                        "assumptions": [],
                        "repair_notes": [],
                        "missing_information": [],
                    },
                    "multi_part": {
                        "units": "mm",
                        "parts": [
                            {"name": "part_name", "steps": []}
                        ],
                        "assembly": [
                            {"part": "part_name", "position": [0, 0, 0], "rotation": [0, 0, 0]}
                        ],
                        "assumptions": [],
                        "repair_notes": [],
                        "missing_information": [],
                    },
                },
                "important_instruction": (
                    "Repair only what is necessary. Keep unrelated explicit dimensions "
                    "and features unchanged. Return the full corrected CAD plan. "
                    "Never invent missing CAD dimensions or coordinates."
                ),
            },
            indent=2,
        )

        repaired = self._call_mistral_json(
            system_prompt=CAD_REPAIR_SYSTEM_PROMPT,
            user_payload=user_payload,
            temperature=0.1,
        )

        repaired = self._ensure_plan_shape(repaired)

        if not self._looks_like_cad_plan(repaired):
            return {
                "ERROR": {
                    "message": "Repair agent did not return a valid CAD plan.",
                    "raw_repair_output": repaired,
                }
            }

        return repaired

    def _ensure_plan_shape(self, cad_plan):
        """
        Defensive cleanup only.

        This does not replace the normalizer. It only ensures the top-level
        shape is close to what the rest of the pipeline expects.
        """

        if not isinstance(cad_plan, dict):
            return {
                "units": "mm",
                "steps": [],
                "assumptions": ["Mistral did not return a dictionary."],
                "missing_information": [],
                "raw_output": cad_plan,
            }

        if "units" not in cad_plan:
            cad_plan["units"] = "mm"

        has_parts = isinstance(cad_plan.get("parts"), list)

        if not has_parts:
            if isinstance(cad_plan.get("components"), list):
                cad_plan["parts"] = cad_plan.get("components")
                has_parts = True
            elif isinstance(cad_plan.get("bodies"), list):
                cad_plan["parts"] = cad_plan.get("bodies")
                has_parts = True

        if has_parts:
            if "assembly" not in cad_plan:
                if isinstance(cad_plan.get("placements"), list):
                    cad_plan["assembly"] = cad_plan.get("placements")
                elif isinstance(cad_plan.get("instances"), list):
                    cad_plan["assembly"] = cad_plan.get("instances")
                else:
                    cad_plan["assembly"] = []
        else:
            if "steps" not in cad_plan:
                if isinstance(cad_plan.get("operations"), list):
                    cad_plan["steps"] = cad_plan.get("operations")
                elif isinstance(cad_plan.get("features"), list):
                    cad_plan["steps"] = cad_plan.get("features")
                elif isinstance(cad_plan.get("objects"), list):
                    cad_plan["steps"] = cad_plan.get("objects")
                else:
                    cad_plan["steps"] = []

        if "assumptions" not in cad_plan:
            cad_plan["assumptions"] = []

        if "missing_information" not in cad_plan:
            cad_plan["missing_information"] = []

        return cad_plan

    def _looks_like_cad_plan(self, cad_plan):
        if not isinstance(cad_plan, dict):
            return False

        if "ERROR" in cad_plan:
            return False

        return isinstance(cad_plan.get("steps"), list) or isinstance(cad_plan.get("parts"), list)