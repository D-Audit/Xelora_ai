"""Arrange and verify the floating objects on an Excel dashboard sheet.

Excel represents charts, pictures, form controls, slicers, and ordinary
shapes as items in ``Worksheet.Shapes``.  Inspecting that single collection
lets this skill validate the complete visible layout rather than assuming
that positioning individual charts was enough.
"""

from __future__ import annotations

from typing import Any

from skills.excel_shared import get_active_workbook


_EPSILON = 0.01


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _shape_property(shape: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(shape, name)
    except Exception:
        return default


def _shape_snapshot(shape: Any, index: int) -> dict | None:
    """Return the serialisable bounds of a movable, visible worksheet shape."""
    name = str(_shape_property(shape, "Name", f"Object {index}"))
    # Legacy notes are shapes too, but moving a note simply because a dashboard
    # is being tidied would be surprising and does not improve the layout.
    if name.lower().startswith("comment "):
        return None

    visible = _shape_property(shape, "Visible", None)
    if visible is not None and not bool(visible):
        return None

    width = _number(_shape_property(shape, "Width"))
    height = _number(_shape_property(shape, "Height"))
    if width <= _EPSILON or height <= _EPSILON:
        return None

    return {
        "name": name,
        "type": str(_shape_property(shape, "Type", "shape")),
        "left": _number(_shape_property(shape, "Left")),
        "top": _number(_shape_property(shape, "Top")),
        "width": width,
        "height": height,
        "right": _number(_shape_property(shape, "Left")) + width,
        "bottom": _number(_shape_property(shape, "Top")) + height,
        "_shape": shape,
    }


def _sheet_objects(sheet: Any) -> list[dict]:
    """Read the sheet's top-level floating objects in Excel drawing order."""
    shapes = sheet.api.Shapes
    objects = []
    for index in range(1, int(shapes.Count) + 1):
        snapshot = _shape_snapshot(shapes.Item(index), index)
        if snapshot is not None:
            objects.append(snapshot)
    return objects


def _public_snapshot(item: dict) -> dict:
    return {key: item[key] for key in ("name", "type", "left", "top", "width", "height", "right", "bottom")}


def rectangles_overlap(first: dict, second: dict) -> bool:
    """Return whether two rectangles share visible area.

    Objects whose edges only touch are deliberately not considered to overlap.
    The reflow grid leaves a configurable visible gap between every item.
    """
    return (
        first["left"] < second["right"] - _EPSILON
        and first["right"] > second["left"] + _EPSILON
        and first["top"] < second["bottom"] - _EPSILON
        and first["bottom"] > second["top"] + _EPSILON
    )


def find_overlaps(objects: list[dict]) -> list[dict]:
    """List every pair of floating objects that shares visible space."""
    overlaps = []
    for first_index, first in enumerate(objects):
        for second in objects[first_index + 1:]:
            if rectangles_overlap(first, second):
                overlaps.append({"first": first["name"], "second": second["name"]})
    return overlaps


def build_grid_positions(
    objects: list[dict],
    start_left: float,
    start_top: float,
    columns: int,
    horizontal_gap: float,
    vertical_gap: float,
) -> dict[str, tuple[float, float]]:
    """Calculate a collision-free grid while preserving each object's size."""
    if columns < 1:
        raise ValueError("columns must be at least 1")

    positions: dict[str, tuple[float, float]] = {}
    top = start_top
    for row_start in range(0, len(objects), columns):
        row = objects[row_start:row_start + columns]
        left = start_left
        row_height = max(item["height"] for item in row)
        for item in row:
            positions[item["name"]] = (left, top)
            left += item["width"] + horizontal_gap
        top += row_height + vertical_gap
    return positions


def _normalise_settings(columns: int, horizontal_gap: float, vertical_gap: float) -> tuple[int, float, float]:
    try:
        columns = int(columns)
    except (TypeError, ValueError):
        raise ValueError("columns must be a whole number") from None
    horizontal_gap = _number(horizontal_gap, -1)
    vertical_gap = _number(vertical_gap, -1)
    if columns < 1:
        raise ValueError("columns must be at least 1")
    if horizontal_gap < 0 or vertical_gap < 0:
        raise ValueError("horizontal_gap and vertical_gap must be zero or greater")
    return columns, horizontal_gap, vertical_gap


def run(
    sheet_name: str,
    mode: str = "reflow",
    start_cell: str = "B2",
    columns: int = 2,
    horizontal_gap: float = 18,
    vertical_gap: float = 18,
) -> dict:
    """Audit or reflow every visible floating object on one worksheet."""
    mode = str(mode).lower().strip()
    if mode not in {"audit", "reflow"}:
        return {
            "sheet": sheet_name,
            "status": "invalid_mode",
            "verified": False,
            "verification_note": "mode must be either 'audit' or 'reflow'.",
        }

    try:
        columns, horizontal_gap, vertical_gap = _normalise_settings(
            columns, horizontal_gap, vertical_gap
        )
        wb = get_active_workbook()
        sheet = wb.sheets[sheet_name]
        before = _sheet_objects(sheet)
    except Exception as exc:
        return {
            "sheet": sheet_name,
            "mode": mode,
            "status": "layout_read_failed",
            "verified": False,
            "error": str(exc),
            "verification_note": "Could not inspect the worksheet's floating objects.",
        }

    overlaps_before = find_overlaps(before)
    result = {
        "sheet": sheet_name,
        "mode": mode,
        "objects_found": len(before),
        "objects_before": [_public_snapshot(item) for item in before],
        "overlaps_before": overlaps_before,
    }

    if mode == "audit" or not before:
        result.update({
            "objects_after": result["objects_before"],
            "overlaps_after": overlaps_before,
            "moved": [],
            "status": "layout_verified" if not overlaps_before else "overlaps_detected",
            "verified": not overlaps_before,
            "verification_note": (
                "No overlapping floating objects were found."
                if not overlaps_before else
                "Overlapping floating objects were found; run again with mode='reflow' to arrange them."
            ),
        })
        return result

    anchor = sheet.range(start_cell)
    ordered = sorted(before, key=lambda item: (item["top"], item["left"], item["name"]))
    targets = build_grid_positions(
        ordered, _number(anchor.left), _number(anchor.top), columns, horizontal_gap, vertical_gap
    )

    move_errors = []
    moved = []
    for item in ordered:
        target_left, target_top = targets[item["name"]]
        if abs(item["left"] - target_left) <= _EPSILON and abs(item["top"] - target_top) <= _EPSILON:
            continue
        try:
            item["_shape"].Left = target_left
            item["_shape"].Top = target_top
            moved.append({
                "name": item["name"],
                "from": {"left": item["left"], "top": item["top"]},
                "to": {"left": target_left, "top": target_top},
            })
        except Exception as exc:
            move_errors.append({"name": item["name"], "error": str(exc)})

    try:
        wb.save()
        after = _sheet_objects(sheet)
    except Exception as exc:
        result.update({
            "moved": moved,
            "move_errors": move_errors,
            "status": "layout_save_or_verify_failed",
            "verified": False,
            "error": str(exc),
            "verification_note": "Excel could not save and re-read the reflowed layout.",
        })
        return result

    overlaps_after = find_overlaps(after)
    verified = not move_errors and not overlaps_after and len(after) == len(before)
    result.update({
        "objects_after": [_public_snapshot(item) for item in after],
        "overlaps_after": overlaps_after,
        "moved": moved,
        "move_errors": move_errors,
        "status": "layout_verified" if verified else "layout_not_verified",
        "verified": verified,
        "verification_note": (
            f"Reflowed {len(moved)} object(s) into a {columns}-column grid; no overlaps remain."
            if verified else
            "The layout could not be verified. Check move_errors and overlaps_after before completing the task."
        ),
    })
    return result
