"""Professional default styling for data written by write_table."""
from __future__ import annotations

import unittest
from datetime import datetime

from skills.table_style import (
    DATE_FORMAT, DATETIME_FORMAT, DECIMAL_FORMAT, INTEGER_FORMAT, MONEY_FORMAT,
    PERCENT_FORMAT, PLAIN_NUMBER_FORMAT, infer_number_format, style_data_block,
)


class NumberFormatInferenceTests(unittest.TestCase):
    def test_column_kinds(self):
        cases = [
            ("UnitPrice", [12.5, 3], MONEY_FORMAT),
            ("Revenue (KES)", [1200, 3400], MONEY_FORMAT),
            ("Quantity", [3, 12], INTEGER_FORMAT),
            ("Total Units", [3, 12], INTEGER_FORMAT),
            ("Visitors", [1200, 980], INTEGER_FORMAT),
            ("Score", [1.25, 3.5], DECIMAL_FORMAT),
            ("Margin", [0.12, 0.4], PERCENT_FORMAT),
            ("Growth Rate", [12.5, 40.0], DECIMAL_FORMAT),  # already in percent units
            ("OrderID", [1001, 1002], PLAIN_NUMBER_FORMAT),
            ("Year", [2024, 2025], PLAIN_NUMBER_FORMAT),
            ("OrderDate", [datetime(2025, 1, 2)], DATE_FORMAT),
            ("OrderDate", ["2025-01-02", None], DATE_FORMAT),
            ("Created", [datetime(2025, 1, 2, 9, 30)], DATETIME_FORMAT),
        ]
        for header, values, expected in cases:
            with self.subTest(header=header, values=values):
                self.assertEqual(expected, infer_number_format(header, values))

    def test_text_and_empty_columns_are_left_alone(self):
        self.assertIsNone(infer_number_format("Region", ["East", "West"]))
        self.assertIsNone(infer_number_format("Price", ["n/a", 3]))
        self.assertIsNone(infer_number_format("Price", [None, ""]))
        self.assertIsNone(infer_number_format("Active", [True, False]))


class _Font:
    bold = False
    color = None


class _Api:
    def __getattr__(self, name):
        return self

    def __call__(self, *args):
        return self


class _Range:
    def __init__(self, log, row=1, col=1, rows=1, cols=1):
        self.log, self.row, self.col, self.rows, self.cols = log, row, col, rows, cols
        self.font, self.api, self.row_height, self.column_width = _Font(), _Api(), 15, 12

    def resize(self, rows, cols):
        return _Range(self.log, self.row, self.col, rows, cols)

    def offset(self, rows, cols):
        return _Range(self.log, self.row + rows, self.col + cols, self.rows, self.cols)

    @property
    def columns(self):
        return _Columns(self)

    def __setattr__(self, name, value):
        if name == "number_format":
            self.log.append((self.col, self.rows, value))
        object.__setattr__(self, name, value)


class _Columns(list):
    def __init__(self, rng):
        super().__init__(_Range(rng.log, rng.row, rng.col + i, rng.rows, 1) for i in range(rng.cols))

    def autofit(self):
        pass


class StyleBlockTests(unittest.TestCase):
    def test_formats_each_column_and_reports_it(self):
        log = []
        result = style_data_block(
            sheet=None, start=_Range(log), headers=["Region", "Units", "Price"],
            rows=[["East", 3, 9.5], ["West", 4, 10.0]], row_count=2, is_table=False,
        )
        self.assertEqual({"Units": INTEGER_FORMAT, "Price": MONEY_FORMAT}, result["number_formats"])
        self.assertEqual([(2, 2, INTEGER_FORMAT), (3, 2, MONEY_FORMAT)], log)
        self.assertIn("header_style", result["applied"])
        self.assertIn("column_widths", result["applied"])
        # The fake sheet has no Excel window: freezing fails quietly, not loudly.
        self.assertNotIn("frozen_header", result["applied"])


if __name__ == "__main__":
    unittest.main()
