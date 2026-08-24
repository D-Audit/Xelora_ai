"""Unit tests for the dashboard floating-object layout guard.

These tests use small fake COM objects. They cover the layout maths and the
read-back verification path without opening or changing a real Excel workbook.
"""

import unittest
from unittest.mock import patch

from skills.library.arrange_dashboard_layout import impl


def _box(name, left, top, width, height):
    return {
        "name": name,
        "left": float(left),
        "top": float(top),
        "width": float(width),
        "height": float(height),
        "right": float(left + width),
        "bottom": float(top + height),
    }


class _FakeShape:
    def __init__(self, name, left, top, width, height, visible=True):
        self.Name = name
        self.Left = left
        self.Top = top
        self.Width = width
        self.Height = height
        self.Visible = visible
        self.Type = "test-shape"


class _FakeShapes:
    def __init__(self, shapes):
        self._shapes = shapes
        self.Count = len(shapes)

    def Item(self, index):
        return self._shapes[index - 1]


class _FakeRange:
    def __init__(self, left, top):
        self.left = left
        self.top = top


class _FakeSheet:
    def __init__(self, shapes):
        self.api = type("Api", (), {"Shapes": _FakeShapes(shapes)})()

    def range(self, _cell):
        return _FakeRange(12, 24)


class _FakeWorkbook:
    def __init__(self, sheet):
        self.sheets = {"Dashboard": sheet}
        self.saved = False

    def save(self):
        self.saved = True


class DashboardLayoutTests(unittest.TestCase):
    def test_touching_edges_are_not_an_overlap(self):
        self.assertFalse(impl.rectangles_overlap(
            _box("First", 0, 0, 100, 80), _box("Second", 100, 0, 100, 80)
        ))

    def test_overlap_scan_reports_only_intersecting_pairs(self):
        overlaps = impl.find_overlaps([
            _box("Chart", 0, 0, 150, 100),
            _box("Logo", 100, 60, 50, 30),
            _box("Control", 300, 0, 100, 30),
        ])

        self.assertEqual([{"first": "Chart", "second": "Logo"}], overlaps)

    def test_grid_positions_preserve_object_sizes_and_spacing(self):
        objects = [
            _box("Wide", 0, 0, 200, 80),
            _box("Small", 0, 0, 100, 40),
            _box("Tall", 0, 0, 90, 160),
        ]
        positions = impl.build_grid_positions(objects, 10, 20, 2, 18, 12)

        self.assertEqual((10, 20), positions["Wide"])
        self.assertEqual((228, 20), positions["Small"])
        self.assertEqual((10, 112), positions["Tall"])

    def test_reflow_moves_overlapping_shapes_and_verifies_read_back(self):
        shapes = [
            _FakeShape("Chart 1", 0, 0, 200, 100),
            _FakeShape("Chart 2", 30, 20, 150, 80),
            _FakeShape("Logo", 40, 30, 60, 30),
        ]
        workbook = _FakeWorkbook(_FakeSheet(shapes))

        with patch.object(impl, "get_active_workbook", return_value=workbook):
            result = impl.run("Dashboard", columns=2, horizontal_gap=18, vertical_gap=12)

        self.assertTrue(result["verified"])
        self.assertTrue(workbook.saved)
        self.assertEqual([], result["overlaps_after"])
        self.assertEqual(3, len(result["moved"]))
        self.assertEqual(12, shapes[0].Left)
        self.assertEqual(24, shapes[0].Top)
        self.assertEqual(230, shapes[1].Left)
        self.assertEqual(24, shapes[1].Top)
        self.assertEqual(12, shapes[2].Left)
        self.assertEqual(136, shapes[2].Top)

    def test_audit_does_not_change_positions_and_fails_on_overlap(self):
        shapes = [
            _FakeShape("Chart 1", 0, 0, 200, 100),
            _FakeShape("Chart 2", 30, 20, 150, 80),
        ]
        workbook = _FakeWorkbook(_FakeSheet(shapes))

        with patch.object(impl, "get_active_workbook", return_value=workbook):
            result = impl.run("Dashboard", mode="audit")

        self.assertFalse(result["verified"])
        self.assertEqual("overlaps_detected", result["status"])
        self.assertFalse(workbook.saved)
        self.assertEqual(0, shapes[0].Left)
        self.assertEqual(30, shapes[1].Left)


if __name__ == "__main__":
    unittest.main()
