# extractors/geometry_extractor.py

import math
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class GeometryExtractor:
    """
    Advanced 2D geometry extractor for the CAD pipeline.

    What it does:
    - reads an uploaded 2D plan image
    - detects the outer plate outline
    - detects circles / holes
    - detects rectangular cutouts
    - detects slots / rounded rectangles
    - estimates feature layout patterns
    - returns pixel-based geometry evidence

    Important:
    This extractor does NOT decide final CAD dimensions in millimeters.
    It returns visual evidence. Excel and prompt data should remain the
    source of truth for exact engineering dimensions.
    """

    def extract(self, plan_file):
        try:
            file_path = self._resolve_file_path(plan_file)

            if not file_path:
                return self._error_result("Could not resolve uploaded plan file path.")

            suffix = Path(file_path).suffix.lower()

            if suffix == ".pdf":
                return self._error_result(
                    "PDF geometry extraction is not supported in this version. "
                    "Please upload a PNG, JPG, JPEG, BMP, WEBP, or TIFF image."
                )

            image = self._load_image(file_path)

            if image is None:
                return self._error_result("Could not load image.")

            image_height, image_width = image.shape[:2]

            processed = self._preprocess(image)

            contour_shapes = self._detect_shapes_from_contours(
                processed=processed,
                image_width=image_width,
                image_height=image_height,
            )

            circle_shapes = self._detect_circles(
                gray=processed["gray"],
                image_width=image_width,
                image_height=image_height,
            )

            shapes = self._merge_and_clean_shapes(
                contour_shapes=contour_shapes,
                circle_shapes=circle_shapes,
                image_width=image_width,
                image_height=image_height,
            )

            outer_rectangle = self._find_outer_rectangle(shapes)

            if outer_rectangle:
                shapes = self._mark_shapes_relative_to_outer_rectangle(
                    shapes,
                    outer_rectangle,
                )

            hole_patterns = self._detect_hole_patterns(shapes)
            summary = self._build_geometry_summary(
                shapes=shapes,
                outer_rectangle=outer_rectangle,
                hole_patterns=hole_patterns,
            )

            return {
                "tool": "geometry_extractor",
                "status": "success",
                "source_file": os.path.basename(file_path),
                "image_size_px": {
                    "width": image_width,
                    "height": image_height,
                },
                "detected_shapes": shapes,
                "detected_geometry": summary,
                "warnings": [
                    "Geometry extraction is pixel-based.",
                    "Use this as supporting evidence, not as the final millimeter source of truth.",
                ],
            }

        except Exception as error:
            return self._error_result(str(error))

    # ----------------------------------------------------
    # File handling
    # ----------------------------------------------------

    def _resolve_file_path(self, plan_file):
        if plan_file is None:
            return None

        if isinstance(plan_file, (str, Path)):
            return str(plan_file)

        if hasattr(plan_file, "name") and hasattr(plan_file, "getbuffer"):
            suffix = Path(plan_file.name).suffix

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(plan_file.getbuffer())
                return temp_file.name

        return None

    def _load_image(self, file_path):
        try:
            pil_image = Image.open(file_path).convert("RGB")
            image_np = np.array(pil_image)
            return cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    # ----------------------------------------------------
    # Preprocessing
    # ----------------------------------------------------

    def _preprocess(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Improve contrast while avoiding aggressive distortion.
        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8),
        )
        enhanced = clahe.apply(gray)

        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

        # Binary image useful for technical drawings with filled areas.
        _, binary_otsu = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )

        # Edge image useful for outlines.
        edges = cv2.Canny(
            blurred,
            threshold1=40,
            threshold2=140,
        )

        kernel = np.ones((3, 3), np.uint8)

        closed_edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=1,
        )

        closed_binary = cv2.morphologyEx(
            binary_otsu,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=1,
        )

        return {
            "gray": gray,
            "enhanced": enhanced,
            "blurred": blurred,
            "binary": closed_binary,
            "edges": closed_edges,
        }

    # ----------------------------------------------------
    # Contour detection
    # ----------------------------------------------------

    def _detect_shapes_from_contours(self, processed, image_width, image_height):
        shapes = []

        contour_sources = [
            ("edges", processed["edges"]),
            ("binary", processed["binary"]),
        ]

        image_area = image_width * image_height

        for source_name, source_image in contour_sources:
            contours, hierarchy = cv2.findContours(
                source_image,
                cv2.RETR_TREE,
                cv2.CHAIN_APPROX_SIMPLE,
            )

            for contour_index, contour in enumerate(contours):
                area = cv2.contourArea(contour)

                if area < max(40, image_area * 0.00005):
                    continue

                perimeter = cv2.arcLength(contour, True)

                if perimeter <= 0:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                if w <= 2 or h <= 2:
                    continue

                bbox_area = w * h
                rectangularity = area / bbox_area if bbox_area > 0 else 0
                aspect_ratio = w / h if h > 0 else 0

                approx = cv2.approxPolyDP(
                    contour,
                    0.02 * perimeter,
                    True,
                )

                center_x = x + w / 2
                center_y = y + h / 2

                circularity = self._calculate_circularity(area, perimeter)

                shape_type, confidence = self._classify_contour(
                    area=area,
                    image_area=image_area,
                    approx_vertices=len(approx),
                    rectangularity=rectangularity,
                    aspect_ratio=aspect_ratio,
                    circularity=circularity,
                    width=w,
                    height=h,
                )

                if shape_type == "ignore":
                    continue

                rotation = self._estimate_rotation(contour)

                shape = {
                    "type": shape_type,
                    "source": f"contour_{source_name}",
                    "center_px": [
                        round(center_x, 2),
                        round(center_y, 2),
                    ],
                    "bounding_box_px": {
                        "x": int(x),
                        "y": int(y),
                        "width": int(w),
                        "height": int(h),
                    },
                    "area_px": round(float(area), 2),
                    "perimeter_px": round(float(perimeter), 2),
                    "approx_vertices": int(len(approx)),
                    "rectangularity": round(float(rectangularity), 3),
                    "aspect_ratio": round(float(aspect_ratio), 3),
                    "circularity": round(float(circularity), 3),
                    "rotation_degrees": rotation,
                    "confidence": confidence,
                }

                if shape_type == "slot":
                    shape["orientation"] = "x" if aspect_ratio >= 1 else "y"

                if shape_type == "circle":
                    estimated_radius = (w + h) / 4
                    shape["radius_px"] = round(float(estimated_radius), 2)
                    shape["diameter_px"] = round(float(estimated_radius * 2), 2)

                shapes.append(shape)

        return shapes

    def _classify_contour(
        self,
        area,
        image_area,
        approx_vertices,
        rectangularity,
        aspect_ratio,
        circularity,
        width,
        height,
    ):
        area_ratio = area / image_area if image_area > 0 else 0

        # Large rectangular outline = likely base plate.
        if (
            area_ratio > 0.20
            and approx_vertices in {4, 5}
            and rectangularity > 0.65
        ):
            return "outer_rectangle", 0.95

        # Circle-like inner contour.
        if (
            circularity > 0.70
            and 0.65 <= aspect_ratio <= 1.35
            and area_ratio < 0.05
        ):
            return "circle", 0.82

        # Long rounded rectangle = slot.
        if (
            rectangularity > 0.55
            and area_ratio < 0.20
            and (aspect_ratio > 2.0 or aspect_ratio < 0.50)
            and width > 8
            and height > 8
        ):
            return "slot", 0.82

        # Standard inner rectangle / cutout.
        if (
            approx_vertices in {4, 5}
            and rectangularity > 0.65
            and area_ratio < 0.20
            and width > 8
            and height > 8
        ):
            return "rectangle", 0.84

        return "ignore", 0.0

    def _calculate_circularity(self, area, perimeter):
        if perimeter <= 0:
            return 0

        return 4 * math.pi * area / (perimeter * perimeter)

    def _estimate_rotation(self, contour):
        try:
            rect = cv2.minAreaRect(contour)
            angle = rect[-1]

            if angle < -45:
                angle = 90 + angle

            return round(float(angle), 2)

        except Exception:
            return 0.0

    # ----------------------------------------------------
    # Circle detection
    # ----------------------------------------------------

    def _detect_circles(self, gray, image_width, image_height):
        shapes = []

        image_min = min(image_width, image_height)

        blurred = cv2.medianBlur(gray, 5)

        # Multiple passes help with different drawing styles.
        hough_settings = [
            {
                "dp": 1.2,
                "minDist": max(15, image_min // 25),
                "param1": 80,
                "param2": 18,
                "minRadius": max(3, image_min // 250),
                "maxRadius": max(10, image_min // 8),
            },
            {
                "dp": 1.1,
                "minDist": max(15, image_min // 30),
                "param1": 100,
                "param2": 24,
                "minRadius": max(3, image_min // 300),
                "maxRadius": max(10, image_min // 10),
            },
        ]

        for settings in hough_settings:
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=settings["dp"],
                minDist=settings["minDist"],
                param1=settings["param1"],
                param2=settings["param2"],
                minRadius=settings["minRadius"],
                maxRadius=settings["maxRadius"],
            )

            if circles is None:
                continue

            circles = np.round(circles[0, :]).astype("int")

            for x, y, radius in circles:
                if radius <= 0:
                    continue

                shapes.append(
                    {
                        "type": "circle",
                        "source": "hough_circle",
                        "center_px": [
                            int(x),
                            int(y),
                        ],
                        "radius_px": int(radius),
                        "diameter_px": int(radius * 2),
                        "bounding_box_px": {
                            "x": int(x - radius),
                            "y": int(y - radius),
                            "width": int(radius * 2),
                            "height": int(radius * 2),
                        },
                        "area_px": round(float(math.pi * radius * radius), 2),
                        "confidence": 0.88,
                    }
                )

        return shapes

    # ----------------------------------------------------
    # Shape cleanup / deduplication
    # ----------------------------------------------------

    def _merge_and_clean_shapes(
        self,
        contour_shapes,
        circle_shapes,
        image_width,
        image_height,
    ):
        all_shapes = []

        for shape in contour_shapes + circle_shapes:
            if not self._is_shape_inside_image(shape, image_width, image_height):
                continue

            all_shapes.append(shape)

        # Sort highest confidence first so duplicates keep the best detection.
        all_shapes = sorted(
            all_shapes,
            key=lambda item: item.get("confidence", 0),
            reverse=True,
        )

        cleaned = []

        for shape in all_shapes:
            duplicate = False

            for existing in cleaned:
                if self._are_duplicate_shapes(shape, existing):
                    duplicate = True
                    break

            if not duplicate:
                cleaned.append(shape)

        return self._sort_shapes(cleaned)

    def _is_shape_inside_image(self, shape, image_width, image_height):
        bbox = shape.get("bounding_box_px", {})

        x = bbox.get("x", 0)
        y = bbox.get("y", 0)
        w = bbox.get("width", 0)
        h = bbox.get("height", 0)

        if x + w < 0 or y + h < 0:
            return False

        if x > image_width or y > image_height:
            return False

        return True

    def _are_duplicate_shapes(self, a, b):
        a_type = a.get("type")
        b_type = b.get("type")

        a_center = a.get("center_px", [None, None])
        b_center = b.get("center_px", [None, None])

        if None in a_center or None in b_center:
            return False

        distance = self._distance(a_center, b_center)

        a_bbox = a.get("bounding_box_px", {})
        b_bbox = b.get("bounding_box_px", {})

        a_size = max(a_bbox.get("width", 0), a_bbox.get("height", 0))
        b_size = max(b_bbox.get("width", 0), b_bbox.get("height", 0))

        size_tolerance = max(6, min(a_size, b_size) * 0.25)

        if a_type == b_type and distance <= size_tolerance:
            return True

        # A contour circle and a Hough circle often overlap.
        if {a_type, b_type} == {"circle"} and distance <= size_tolerance:
            return True

        # A slot may sometimes also be seen as a rectangle.
        if {a_type, b_type} == {"slot", "rectangle"}:
            iou = self._bbox_iou(a_bbox, b_bbox)

            if iou > 0.65:
                return True

        return False

    def _bbox_iou(self, a, b):
        ax1 = a.get("x", 0)
        ay1 = a.get("y", 0)
        ax2 = ax1 + a.get("width", 0)
        ay2 = ay1 + a.get("height", 0)

        bx1 = b.get("x", 0)
        by1 = b.get("y", 0)
        bx2 = bx1 + b.get("width", 0)
        by2 = by1 + b.get("height", 0)

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)

        union = area_a + area_b - inter_area

        if union <= 0:
            return 0

        return inter_area / union

    def _sort_shapes(self, shapes):
        type_priority = {
            "outer_rectangle": 0,
            "circle": 1,
            "rectangle": 2,
            "slot": 3,
        }

        return sorted(
            shapes,
            key=lambda shape: (
                type_priority.get(shape.get("type"), 99),
                shape.get("center_px", [0, 0])[1],
                shape.get("center_px", [0, 0])[0],
            ),
        )

    # ----------------------------------------------------
    # Relative geometry
    # ----------------------------------------------------

    def _find_outer_rectangle(self, shapes):
        candidates = [
            shape for shape in shapes if shape.get("type") == "outer_rectangle"
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda shape: shape.get("area_px", 0),
        )

    def _mark_shapes_relative_to_outer_rectangle(self, shapes, outer_rectangle):
        outer_bbox = outer_rectangle.get("bounding_box_px", {})

        ox = outer_bbox.get("x", 0)
        oy = outer_bbox.get("y", 0)
        ow = outer_bbox.get("width", 1)
        oh = outer_bbox.get("height", 1)

        marked = []

        for shape in shapes:
            shape = dict(shape)

            center = shape.get("center_px")

            if (
                shape is outer_rectangle
                or shape.get("type") == "outer_rectangle"
            ):
                shape["inside_outer_rectangle"] = False
                marked.append(shape)
                continue

            if not isinstance(center, list) or len(center) != 2:
                marked.append(shape)
                continue

            cx, cy = center

            inside = (
                ox <= cx <= ox + ow
                and oy <= cy <= oy + oh
            )

            shape["inside_outer_rectangle"] = inside

            if inside:
                shape["relative_center_in_outer_px"] = [
                    round(cx - ox, 2),
                    round(cy - oy, 2),
                ]

                shape["relative_center_normalized"] = [
                    round((cx - ox) / ow, 4),
                    round((cy - oy) / oh, 4),
                ]

            marked.append(shape)

        return marked

    # ----------------------------------------------------
    # Hole pattern detection
    # ----------------------------------------------------

    def _detect_hole_patterns(self, shapes):
        circles = [
            shape for shape in shapes
            if shape.get("type") == "circle"
            and shape.get("inside_outer_rectangle", True)
        ]

        if len(circles) < 2:
            return []

        circles = sorted(
            circles,
            key=lambda item: (
                item.get("center_px", [0, 0])[1],
                item.get("center_px", [0, 0])[0],
            ),
        )

        rows = self._cluster_axis(
            values=[circle["center_px"][1] for circle in circles],
            tolerance=self._estimate_axis_tolerance(circles, axis="y"),
        )

        columns = self._cluster_axis(
            values=[circle["center_px"][0] for circle in circles],
            tolerance=self._estimate_axis_tolerance(circles, axis="x"),
        )

        if len(rows) <= 1 and len(columns) <= 1:
            return []

        row_centers = [cluster["center"] for cluster in rows]
        column_centers = [cluster["center"] for cluster in columns]

        expected_count = len(row_centers) * len(column_centers)
        actual_count = len(circles)

        pattern_confidence = 0.65

        if expected_count == actual_count:
            pattern_confidence = 0.9
        elif abs(expected_count - actual_count) <= 1:
            pattern_confidence = 0.78

        spacing_x = self._average_spacing(column_centers)
        spacing_y = self._average_spacing(row_centers)

        first_x = min(column_centers) if column_centers else circles[0]["center_px"][0]
        first_y = min(row_centers) if row_centers else circles[0]["center_px"][1]

        diameters = [
            circle.get("diameter_px")
            for circle in circles
            if isinstance(circle.get("diameter_px"), (int, float))
        ]

        average_diameter = (
            sum(diameters) / len(diameters)
            if diameters
            else None
        )

        return [
            {
                "type": "circle_pattern",
                "rows": len(row_centers),
                "columns": len(column_centers),
                "actual_circle_count": actual_count,
                "expected_grid_count": expected_count,
                "first_position_px": [
                    round(float(first_x), 2),
                    round(float(first_y), 2),
                ],
                "spacing_x_px": round(float(spacing_x), 2) if spacing_x else None,
                "spacing_y_px": round(float(spacing_y), 2) if spacing_y else None,
                "average_diameter_px": round(float(average_diameter), 2)
                if average_diameter
                else None,
                "confidence": pattern_confidence,
            }
        ]

    def _cluster_axis(self, values, tolerance):
        if not values:
            return []

        values = sorted(values)
        clusters = []

        current = [values[0]]

        for value in values[1:]:
            current_center = sum(current) / len(current)

            if abs(value - current_center) <= tolerance:
                current.append(value)
            else:
                clusters.append(self._cluster_summary(current))
                current = [value]

        clusters.append(self._cluster_summary(current))

        return clusters

    def _cluster_summary(self, values):
        return {
            "center": sum(values) / len(values),
            "count": len(values),
            "min": min(values),
            "max": max(values),
        }

    def _estimate_axis_tolerance(self, circles, axis):
        diameters = [
            circle.get("diameter_px")
            for circle in circles
            if isinstance(circle.get("diameter_px"), (int, float))
        ]

        if diameters:
            return max(8, sum(diameters) / len(diameters) * 0.6)

        return 12

    def _average_spacing(self, centers):
        if len(centers) < 2:
            return None

        centers = sorted(centers)
        spacings = []

        for index in range(len(centers) - 1):
            spacings.append(centers[index + 1] - centers[index])

        return sum(spacings) / len(spacings)

    # ----------------------------------------------------
    # Summary
    # ----------------------------------------------------

    def _build_geometry_summary(self, shapes, outer_rectangle, hole_patterns):
        circles = [shape for shape in shapes if shape.get("type") == "circle"]
        rectangles = [shape for shape in shapes if shape.get("type") == "rectangle"]
        slots = [shape for shape in shapes if shape.get("type") == "slot"]

        inner_shapes = [
            shape for shape in shapes
            if shape.get("type") != "outer_rectangle"
        ]

        return {
            "outer_rectangle": outer_rectangle,
            "feature_counts": {
                "total_shapes": len(shapes),
                "inner_shapes": len(inner_shapes),
                "circles": len(circles),
                "rectangles": len(rectangles),
                "slots": len(slots),
                "hole_patterns": len(hole_patterns),
            },
            "hole_patterns": hole_patterns,
            "likely_features": {
                "base_plate_detected": outer_rectangle is not None,
                "hole_count": len(circles),
                "rectangular_cutout_count": len(rectangles),
                "slot_count": len(slots),
            },
            "confidence": self._overall_confidence(
                outer_rectangle=outer_rectangle,
                circles=circles,
                rectangles=rectangles,
                slots=slots,
                hole_patterns=hole_patterns,
            ),
        }

    def _overall_confidence(
        self,
        outer_rectangle,
        circles,
        rectangles,
        slots,
        hole_patterns,
    ):
        confidence_values = []

        if outer_rectangle:
            confidence_values.append(outer_rectangle.get("confidence", 0))

        for shape in circles + rectangles + slots:
            confidence_values.append(shape.get("confidence", 0))

        for pattern in hole_patterns:
            confidence_values.append(pattern.get("confidence", 0))

        if not confidence_values:
            return 0.0

        return round(sum(confidence_values) / len(confidence_values), 3)

    # ----------------------------------------------------
    # Math helpers
    # ----------------------------------------------------

    def _distance(self, a, b):
        return math.sqrt(
            (a[0] - b[0]) ** 2
            + (a[1] - b[1]) ** 2
        )

    # ----------------------------------------------------
    # Error handling
    # ----------------------------------------------------

    def _error_result(self, message):
        return {
            "tool": "geometry_extractor",
            "status": "failed",
            "error": message,
            "detected_shapes": [],
            "detected_geometry": {},
            "warnings": [
                "Geometry extraction failed. No fake geometry was invented."
            ],
        }