"""Focused unit coverage for the bounded spreadsheet metadata extractors.

Run from ``backend`` with:
    python -m unittest test_file_processing
"""
import os
import tempfile
import unittest

from openpyxl import Workbook

from files import _extract_metadata


class FileMetadataExtractionTests(unittest.TestCase):
    def test_csv_summary_includes_headers_and_sample_rows(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="") as handle:
            handle.write("name,amount\nAda,12\nLin,24\n")
            path = handle.name
        try:
            metadata = _extract_metadata(path, "csv")
        finally:
            os.remove(path)

        self.assertEqual(metadata["status"], "completed")
        self.assertEqual(metadata["row_count"], 2)
        self.assertEqual(metadata["column_count"], 2)
        sheet = metadata["sheet_summary"]["sheets"][0]
        self.assertEqual(sheet["headers"], ["name", "amount"])
        self.assertEqual(sheet["sampleRows"], [["Ada", "12"], ["Lin", "24"]])

    def test_xlsx_summary_captures_each_sheet(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
            path = handle.name
        workbook = Workbook()
        main = workbook.active
        main.title = "Sales"
        main.append(["month", "revenue"])
        main.append(["January", 100])
        archive = workbook.create_sheet("Archive")
        archive.append(["id"])
        archive.append(["A-1"])
        workbook.save(path)
        workbook.close()
        try:
            metadata = _extract_metadata(path, "xlsx")
        finally:
            os.remove(path)

        self.assertEqual(metadata["status"], "completed")
        self.assertEqual(metadata["row_count"], 2)
        self.assertEqual(metadata["column_count"], 2)
        self.assertEqual([sheet["name"] for sheet in metadata["sheet_summary"]["sheets"]], ["Sales", "Archive"])

    def test_legacy_format_is_retained_but_marked_for_review(self):
        metadata = _extract_metadata("unused.xls", "xls")

        self.assertEqual(metadata["status"], "needs_review")
        self.assertIn(".xls", metadata["error"])


if __name__ == "__main__":
    unittest.main()
