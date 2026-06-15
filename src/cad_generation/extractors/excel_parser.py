# extractors/excel_parser.py

import math
from pathlib import Path

import pandas as pd


class ExcelParser:
    """
    Real Excel parser for the CAD pipeline.

    Supported workbook structure:

    1. Optional sheet: constraints
       Columns:
       parameter | value

       Example:
       parameter        value
       units            mm
       material         aluminium
       export_format    STEP

    2. Optional sheet: base
       Columns:
       name | type | length | width | height | x | y | z | corner_radius

       Example:
       name        type                length  width  height  x  y  z
       base_plate  rectangular_plate   180     110    14      0  0  0

    3. Optional sheet: features
       Columns:
       type | target | length | width | diameter | depth | x | y | z |
       rows | columns | spacing_x | spacing_y | orientation |
       radius | distance | scope |
       counterbore_diameter | counterbore_depth |
       countersink_diameter | countersink_depth | countersink_angle

       Example:
       type                 target      length width diameter depth x   y   z rows columns spacing_x spacing_y orientation
       rectangular_cutout   base_plate  50     24             14    90  55  0
       hole_pattern         base_plate                6        14    35  85  0 2    3       30        15
       slot                 base_plate  40     10             14    130 30  0                         x

    Backward compatibility:
    - If the Excel file only contains a simple parameter/value sheet, it still works.
    - The parser does not invent engineering dimensions.
    - Missing values remain missing and are reported through warnings.
    """

    def parse(self, excel_file):
        if excel_file is None:
            return {
                "tool": "excel_parser",
                "status": "skipped",
                "reason": "No Excel file uploaded.",
                "units": "mm",
                "constraints": {},
                "base_objects": [],
                "features": [],
                "warnings": [],
            }

        try:
            workbook = pd.ExcelFile(excel_file)
            sheet_names = workbook.sheet_names

            constraints = {}
            base_objects = []
            features = []
            warnings = []

            for sheet_name in sheet_names:
                df = pd.read_excel(workbook, sheet_name=sheet_name)
                df = self._clean_dataframe(df)

                if df.empty:
                    continue

                normalized_sheet_name = self._normalize_key(sheet_name)

                if normalized_sheet_name in {
                    "constraints",
                    "constraint",
                    "parameters",
                    "parameter",
                    "params",
                    "settings",
                    "config",
                }:
                    parsed_constraints = self._parse_constraints_sheet(df, warnings)
                    constraints.update(parsed_constraints)

                elif normalized_sheet_name in {
                    "base",
                    "bases",
                    "base_objects",
                    "base_object",
                    "objects",
                    "object",
                    "plate",
                    "plates",
                }:
                    base_objects.extend(self._parse_base_sheet(df, warnings))

                elif normalized_sheet_name in {
                    "features",
                    "feature",
                    "operations",
                    "operation",
                    "holes",
                    "cuts",
                    "cutouts",
                }:
                    features.extend(self._parse_features_sheet(df, warnings))

                else:
                    detected = self._auto_detect_sheet(df, sheet_name, warnings)

                    constraints.update(detected.get("constraints", {}))
                    base_objects.extend(detected.get("base_objects", []))
                    features.extend(detected.get("features", []))

            units = constraints.get("units") or constraints.get("unit") or "mm"

            status = "success"

            if not constraints and not base_objects and not features:
                status = "no_usable_data"
                warnings.append(
                    "Excel file was read, but no constraints, base objects, or features were detected."
                )

            return {
                "tool": "excel_parser",
                "status": status,
                "source_file": self._source_name(excel_file),
                "sheet_names": sheet_names,
                "units": units,
                "constraints": constraints,
                "base_objects": base_objects,
                "features": features,
                "warnings": warnings,
            }

        except Exception as error:
            return {
                "tool": "excel_parser",
                "status": "failed",
                "source_file": self._source_name(excel_file),
                "error": str(error),
                "units": "mm",
                "constraints": {},
                "base_objects": [],
                "features": [],
                "warnings": [
                    "Excel parsing failed. No engineering values were invented."
                ],
            }

    # ----------------------------------------------------
    # Sheet parsers
    # ----------------------------------------------------

    def _parse_constraints_sheet(self, df, warnings):
        constraints = {}

        columns = set(df.columns)

        if {"parameter", "value"}.issubset(columns):
            for _, row in df.iterrows():
                key = self._clean_value(row.get("parameter"))
                value = self._clean_value(row.get("value"))

                if key is None:
                    continue

                constraints[str(key).strip()] = value

            return constraints

        if len(df.columns) >= 2:
            first_col = df.columns[0]
            second_col = df.columns[1]

            warnings.append(
                "Constraints sheet does not use exact columns 'parameter' and 'value'. "
                f"Using '{first_col}' and '{second_col}' as fallback."
            )

            for _, row in df.iterrows():
                key = self._clean_value(row.get(first_col))
                value = self._clean_value(row.get(second_col))

                if key is None:
                    continue

                constraints[str(key).strip()] = value

            return constraints

        warnings.append(
            "Constraints sheet could not be parsed because it needs at least two columns."
        )

        return constraints

    def _parse_base_sheet(self, df, warnings):
        base_objects = []

        for row_index, row in df.iterrows():
            row_dict = self._row_to_dict(row)

            if self._row_is_empty(row_dict):
                continue

            base_type = (
                row_dict.get("type")
                or row_dict.get("object_type")
                or row_dict.get("shape")
                or "rectangular_plate"
            )

            base_type = self._canonical_base_type(base_type)

            name = (
                row_dict.get("name")
                or row_dict.get("id")
                or row_dict.get("object_name")
                or "base_plate"
            )

            length = self._first_number(
                row_dict,
                ["length", "length_mm", "l", "x_length", "size_x"],
            )

            width = self._first_number(
                row_dict,
                ["width", "width_mm", "w", "y_width", "size_y"],
            )

            height = self._first_number(
                row_dict,
                [
                    "height",
                    "height_mm",
                    "thickness",
                    "thickness_mm",
                    "depth",
                    "depth_mm",
                    "z_height",
                    "size_z",
                ],
            )

            x = self._first_number(row_dict, ["x", "x_mm", "origin_x"], default=0)
            y = self._first_number(row_dict, ["y", "y_mm", "origin_y"], default=0)
            z = self._first_number(row_dict, ["z", "z_mm", "origin_z"], default=0)

            base_object = {
                "type": base_type,
                "name": str(name),
                "length": length,
                "width": width,
                "height": height,
                "position": [x, y, z],
                "source": "excel",
                "source_row": int(row_index) + 2,
            }

            corner_radius = self._first_number(
                row_dict,
                ["corner_radius", "corner_radius_mm", "radius", "fillet_radius"],
            )

            if corner_radius is not None:
                base_object["corner_radius"] = corner_radius

            missing = []

            for field in ["length", "width", "height"]:
                if base_object.get(field) is None:
                    missing.append(field)

            if missing:
                warnings.append(
                    f"Base object '{name}' is missing required field(s): {missing}."
                )

            base_objects.append(base_object)

        return base_objects

    def _parse_features_sheet(self, df, warnings):
        features = []

        for row_index, row in df.iterrows():
            row_dict = self._row_to_dict(row)

            if self._row_is_empty(row_dict):
                continue

            raw_type = (
                row_dict.get("type")
                or row_dict.get("operation")
                or row_dict.get("feature")
                or row_dict.get("feature_type")
            )

            if raw_type is None:
                warnings.append(
                    f"Feature row {int(row_index) + 2} ignored because no type/operation was provided."
                )
                continue

            feature_type = self._canonical_feature_type(raw_type)

            target = row_dict.get("target") or row_dict.get("object") or "base_plate"

            x = self._first_number(
                row_dict,
                ["x", "x_mm", "center_x", "center_x_mm", "position_x"],
            )
            y = self._first_number(
                row_dict,
                ["y", "y_mm", "center_y", "center_y_mm", "position_y"],
            )
            z = self._first_number(
                row_dict,
                ["z", "z_mm", "center_z", "center_z_mm", "position_z"],
                default=0,
            )

            feature = {
                "type": feature_type,
                "target": str(target),
                "source": "excel",
                "source_row": int(row_index) + 2,
            }

            if x is not None and y is not None:
                feature["position"] = [x, y, z]

            self._apply_common_feature_fields(feature, row_dict)

            missing = self._missing_required_feature_fields(feature)

            if missing:
                warnings.append(
                    f"Feature row {int(row_index) + 2} ({feature_type}) is missing field(s): {missing}."
                )

            features.append(feature)

        return features

    def _auto_detect_sheet(self, df, sheet_name, warnings):
        columns = set(df.columns)

        result = {
            "constraints": {},
            "base_objects": [],
            "features": [],
        }

        if {"parameter", "value"}.issubset(columns):
            result["constraints"] = self._parse_constraints_sheet(df, warnings)
            return result

        if self._has_any_column(
            columns,
            ["length", "width", "height", "thickness", "length_mm", "width_mm"],
        ) and self._has_any_column(columns, ["name", "type", "object_type", "shape"]):
            result["base_objects"] = self._parse_base_sheet(df, warnings)
            return result

        if self._has_any_column(
            columns,
            ["operation", "feature", "feature_type", "diameter", "rows", "columns"],
        ):
            result["features"] = self._parse_features_sheet(df, warnings)
            return result

        warnings.append(
            f"Sheet '{sheet_name}' was not recognized as constraints, base, or features."
        )

        return result

    # ----------------------------------------------------
    # Feature normalization
    # ----------------------------------------------------

    def _apply_common_feature_fields(self, feature, row_dict):
        feature_type = feature["type"]

        length = self._first_number(row_dict, ["length", "length_mm", "slot_length"])
        width = self._first_number(row_dict, ["width", "width_mm", "slot_width"])
        diameter = self._first_number(
            row_dict,
            ["diameter", "diameter_mm", "hole_diameter", "hole_diameter_mm"],
        )
        depth = self._first_number(
            row_dict,
            ["depth", "depth_mm", "cut_depth", "through_depth"],
        )

        rows = self._first_int(row_dict, ["rows", "row_count", "number_of_rows"])
        columns = self._first_int(
            row_dict,
            ["columns", "cols", "column_count", "number_of_columns"],
        )

        spacing_x = self._first_number(
            row_dict,
            ["spacing_x", "spacing_x_mm", "x_spacing", "pitch_x"],
        )
        spacing_y = self._first_number(
            row_dict,
            ["spacing_y", "spacing_y_mm", "y_spacing", "pitch_y"],
        )

        if feature_type == "create_hole":
            feature["diameter"] = diameter
            feature["depth"] = depth

        elif feature_type == "create_slot":
            feature["length"] = length
            feature["width"] = width
            feature["depth"] = depth
            feature["orientation"] = (
                row_dict.get("orientation")
                or row_dict.get("axis")
                or "x"
            )

        elif feature_type == "create_rectangular_cutout":
            feature["length"] = length
            feature["width"] = width
            feature["depth"] = depth

        elif feature_type == "create_hole_pattern":
            feature["rows"] = rows
            feature["columns"] = columns
            feature["diameter"] = diameter
            feature["depth"] = depth
            feature["spacing_x"] = spacing_x
            feature["spacing_y"] = spacing_y

            if "position" in feature:
                feature["first_position"] = feature["position"]

            pattern_center_x = self._first_number(
                row_dict,
                ["pattern_center_x", "pattern_center_x_mm", "center_x_pattern"],
            )
            pattern_center_y = self._first_number(
                row_dict,
                ["pattern_center_y", "pattern_center_y_mm", "center_y_pattern"],
            )
            pattern_center_z = self._first_number(
                row_dict,
                ["pattern_center_z", "pattern_center_z_mm", "center_z_pattern"],
                default=0,
            )

            if pattern_center_x is not None and pattern_center_y is not None:
                feature["pattern_center"] = [
                    pattern_center_x,
                    pattern_center_y,
                    pattern_center_z,
                ]

        elif feature_type == "create_fillet":
            feature["radius"] = self._first_number(
                row_dict,
                ["radius", "radius_mm", "fillet_radius", "fillet_radius_mm"],
            )
            feature["scope"] = row_dict.get("scope") or "outer_vertical_edges"

        elif feature_type == "create_chamfer":
            feature["distance"] = self._first_number(
                row_dict,
                ["distance", "distance_mm", "chamfer_distance"],
            )
            feature["scope"] = row_dict.get("scope") or "top_outer_edges"

        elif feature_type == "create_counterbore_hole":
            feature["hole_diameter"] = diameter
            feature["depth"] = depth
            feature["counterbore_diameter"] = self._first_number(
                row_dict,
                ["counterbore_diameter", "counterbore_diameter_mm", "head_diameter"],
            )
            feature["counterbore_depth"] = self._first_number(
                row_dict,
                ["counterbore_depth", "counterbore_depth_mm", "head_depth"],
            )

        elif feature_type == "create_countersink_hole":
            feature["hole_diameter"] = diameter
            feature["depth"] = depth
            feature["countersink_diameter"] = self._first_number(
                row_dict,
                ["countersink_diameter", "countersink_diameter_mm", "head_diameter"],
            )
            feature["countersink_depth"] = self._first_number(
                row_dict,
                ["countersink_depth", "countersink_depth_mm"],
            )
            feature["countersink_angle"] = self._first_number(
                row_dict,
                ["countersink_angle", "angle", "angle_degrees"],
                default=90,
            )

    def _missing_required_feature_fields(self, feature):
        feature_type = feature.get("type")

        required_by_type = {
            "create_hole": ["target", "position", "diameter"],
            "create_slot": ["target", "position", "length", "width"],
            "create_rectangular_cutout": ["target", "position", "length", "width"],
            "create_hole_pattern": [
                "target",
                "rows",
                "columns",
                "diameter",
                "spacing_x",
                "spacing_y",
            ],
            "create_fillet": ["target", "radius"],
            "create_chamfer": ["target", "distance"],
            "create_counterbore_hole": [
                "target",
                "position",
                "hole_diameter",
                "counterbore_diameter",
                "counterbore_depth",
            ],
            "create_countersink_hole": [
                "target",
                "position",
                "hole_diameter",
                "countersink_diameter",
            ],
        }

        required = required_by_type.get(feature_type, [])
        missing = []

        for field in required:
            if feature.get(field) is None:
                missing.append(field)

        return missing

    # ----------------------------------------------------
    # Canonical names
    # ----------------------------------------------------

    def _canonical_base_type(self, value):
        value = self._normalize_key(value)

        mapping = {
            "box": "create_box",
            "plate": "create_box",
            "base_plate": "create_box",
            "rectangular_plate": "create_box",
            "rectangle_plate": "create_box",
            "create_box": "create_box",
            "rounded_plate": "create_rounded_rectangle_plate",
            "rounded_rectangle_plate": "create_rounded_rectangle_plate",
            "create_rounded_rectangle_plate": "create_rounded_rectangle_plate",
        }

        return mapping.get(value, "create_box")

    def _canonical_feature_type(self, value):
        value = self._normalize_key(value)

        mapping = {
            "hole": "create_hole",
            "through_hole": "create_hole",
            "circular_hole": "create_hole",
            "create_hole": "create_hole",

            "slot": "create_slot",
            "through_slot": "create_slot",
            "create_slot": "create_slot",

            "rectangular_cutout": "create_rectangular_cutout",
            "rectangle_cutout": "create_rectangular_cutout",
            "through_rectangular_cutout": "create_rectangular_cutout",
            "rectangular_hole": "create_rectangular_cutout",
            "create_rectangular_cutout": "create_rectangular_cutout",

            "hole_pattern": "create_hole_pattern",
            "circular_hole_pattern": "create_hole_pattern",
            "pattern": "create_hole_pattern",
            "create_hole_pattern": "create_hole_pattern",

            "fillet": "create_fillet",
            "add_fillet": "create_fillet",
            "create_fillet": "create_fillet",

            "chamfer": "create_chamfer",
            "add_chamfer": "create_chamfer",
            "create_chamfer": "create_chamfer",

            "counterbore": "create_counterbore_hole",
            "counterbore_hole": "create_counterbore_hole",
            "create_counterbore": "create_counterbore_hole",
            "create_counterbore_hole": "create_counterbore_hole",

            "countersink": "create_countersink_hole",
            "countersink_hole": "create_countersink_hole",
            "create_countersink": "create_countersink_hole",
            "create_countersink_hole": "create_countersink_hole",
        }

        return mapping.get(value, value)

    # ----------------------------------------------------
    # Helpers
    # ----------------------------------------------------

    def _clean_dataframe(self, df):
        df = df.copy()
        df.columns = [self._normalize_key(column) for column in df.columns]
        df = df.dropna(how="all")
        return df

    def _row_to_dict(self, row):
        result = {}

        for key, value in row.items():
            clean_value = self._clean_value(value)

            if clean_value is not None:
                result[self._normalize_key(key)] = clean_value

        return result

    def _row_is_empty(self, row_dict):
        return len(row_dict) == 0

    def _clean_value(self, value):
        if value is None:
            return None

        if isinstance(value, float) and math.isnan(value):
            return None

        if pd.isna(value):
            return None

        if isinstance(value, str):
            stripped = value.strip()

            if not stripped:
                return None

            if stripped.lower() in {"nan", "none", "null", "-"}:
                return None

            number = self._try_number(stripped)

            if number is not None:
                return number

            return stripped

        if isinstance(value, (int, float)):
            return value

        return value

    def _try_number(self, value):
        try:
            if isinstance(value, str):
                normalized = value.replace(",", ".").strip()

                if normalized == "":
                    return None

                number = float(normalized)

                if number.is_integer():
                    return int(number)

                return number

            return None

        except Exception:
            return None

    def _normalize_key(self, value):
        return (
            str(value)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "")
            .replace("(", "")
            .replace(")", "")
        )

    def _first_number(self, row_dict, possible_keys, default=None):
        for key in possible_keys:
            normalized_key = self._normalize_key(key)

            if normalized_key not in row_dict:
                continue

            value = row_dict.get(normalized_key)

            if isinstance(value, (int, float)):
                return value

            parsed = self._try_number(value)

            if parsed is not None:
                return parsed

        return default

    def _first_int(self, row_dict, possible_keys, default=None):
        value = self._first_number(row_dict, possible_keys, default=default)

        if value is None:
            return None

        try:
            return int(value)
        except Exception:
            return default

    def _has_any_column(self, columns, possible_columns):
        normalized_columns = {self._normalize_key(column) for column in columns}

        for column in possible_columns:
            if self._normalize_key(column) in normalized_columns:
                return True

        return False

    def _source_name(self, excel_file):
        if hasattr(excel_file, "name"):
            return excel_file.name

        try:
            return Path(str(excel_file)).name
        except Exception:
            return "uploaded_excel_file"