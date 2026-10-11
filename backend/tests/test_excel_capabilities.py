"""Excel-layer contract tests: argument guards, bulk file import, copy_range,
and the fixed skills.

Excel itself is replaced by test_support/fake_excel.py (values/formulas on a
grid, no calculation, no COM). These tests prove Xelora's own logic; they do
not prove Microsoft Excel behaves identically. COM-only paths (PasteSpecial,
AutoFit widths) need the Windows host.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from agent.excel_guards import excel_argument_error, read_only_sql_error
from agent.permissions import decide_action
from agent.tool_registry import get_tool_spec
from test_support.fake_excel import FakeBook
from tools import filesystem as fs
from tools import workspace_import as wi

LIB = Path(__file__).resolve().parents[1] / "skills" / "library"


def load_skill(name):
    spec = importlib.util.spec_from_file_location(f"skill_{name}", LIB / name / "impl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExcelGuardTests(unittest.TestCase):
    def test_write_table_errors_name_the_bad_row(self):
        error = excel_argument_error("write_table", {"headers": ["A", "B"], "rows": [[1, 2], [3]]})
        self.assertIn("row 2 has 1 values", error)
        self.assertIn("formula", excel_argument_error("write_table", {"headers": ["A"], "rows": [["=SUM(B:B)"]]}))
        self.assertIn("import_workspace_file_to_sheet",
                      excel_argument_error("write_table", {"headers": ["A"] * 10, "rows": [[1] * 10] * 2500}))
        self.assertIsNone(excel_argument_error("write_table", {"headers": ["A", "B"], "rows": []}))

    def test_file_type_and_location_rules(self):
        self.assertIsNone(excel_argument_error("open_workbook", {"file_path": r"C:\Users\ana\Documents\Budget.xlsx"}))
        # Outlook attachments open from AppData; allowed for workbooks.
        self.assertIsNone(excel_argument_error("open_workbook", {"file_path": r"C:\Users\ana\AppData\Local\Temp\q3.xlsx"}))
        for skill, args in (
            ("import_unstructured_document", {"file_path": "/home/ana/.ssh/id_rsa", "sheet_name": "S"}),
            ("import_unstructured_document", {"file_path": "/home/ana/.aws/credentials.txt", "sheet_name": "S"}),
            ("import_unstructured_document", {"file_path": r"C:\Users\ana\AppData\Roaming\x\notes.txt", "sheet_name": "S"}),
            ("open_workbook", {"file_path": r"C:\Users\ana\.config\secrets.xlsx"}),
            ("open_workbook", {"file_path": "/home/ana/backend/.env"}),
            ("export_to_pdf", {"sheet_name": "S", "output_path": r"C:\Windows\System32\report.pdf"}),
            ("insert_picture", {"sheet_name": "S", "image_path": "/tmp/payload.exe"}),
        ):
            with self.subTest(skill=skill, args=args):
                self.assertIsNotNone(excel_argument_error(skill, args))

    def test_database_import_is_read_only(self):
        self.assertIsNone(read_only_sql_error("SELECT id, total FROM orders WHERE total > 10"))
        self.assertIsNone(read_only_sql_error("WITH t AS (SELECT 1 AS x) SELECT * FROM t"))
        for query in ("DELETE FROM orders", "select 1; drop table orders", "UPDATE t SET a=1",
                      "SELECT * FROM t; INSERT INTO t VALUES (1)", "EXEC sp_who"):
            with self.subTest(query=query):
                self.assertIsNotNone(read_only_sql_error(query))
        self.assertIsNone(read_only_sql_error("SELECT 'delete me' AS note FROM t"))  # literal text is data

    def test_guards_are_enforced_by_policy(self):
        spec = get_tool_spec("write_table", visual_tool_names=set())
        decision = decide_action(spec, planning_only=False,
                                 tool_input={"sheet_name": "S", "start_cell": "A1", "headers": ["A"], "rows": [[1, 2]]})
        self.assertEqual("invalid_arguments", decision.status)

    def test_refused_arguments_do_not_count_as_unverified_workbook_changes(self):
        from agent.core import _is_unresolved_workbook_action
        step = {"type": "action", "tool_name": "write_table", "status": "blocked",
                "result": {"verified": False, "status": "invalid_arguments"}}
        self.assertFalse(_is_unresolved_workbook_action(step))


class WorkspaceImportParsingTests(unittest.TestCase):
    def test_cell_coercion_keeps_identifiers_and_blocks_formula_injection(self):
        self.assertEqual(42, wi.coerce_cell("42"))
        self.assertEqual(-3.5, wi.coerce_cell("-3.5"))
        self.assertEqual("'00123", wi.coerce_cell("00123"))
        self.assertEqual("'+250788123456", wi.coerce_cell("+250788123456"))
        self.assertEqual("'4111111111111111111", wi.coerce_cell("4111111111111111111"))
        self.assertEqual(datetime(2024, 3, 5), wi.coerce_cell("2024-03-05"))
        self.assertEqual("'=WEBSERVICE(\"http://x\")", wi.coerce_cell('=WEBSERVICE("http://x")'))
        self.assertEqual("'@SUM(A1)", wi.coerce_cell("@SUM(A1)"))
        self.assertIsNone(wi.coerce_cell("  "))
        self.assertEqual("Kigali", wi.coerce_cell("Kigali"))

    def test_delimiter_sniffing_and_ragged_rows(self):
        rows = wi.rectangular(wi.parse_delimited(b"name;qty\nA;1\nB\n\n", ".csv"))
        self.assertEqual([["name", "qty"], ["A", 1], ["B", None]], rows)
        self.assertEqual([["a", "b"], [1, 2]], wi.parse_delimited(b"a\tb\n1\t2\n", ".tsv"))


class WorkspaceImportExcelTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "7").mkdir()
        lines = ["Date,Store,Units,Code"] + [f"2024-01-{d:02d},S{d % 3},{d * 10},00{d}" for d in range(1, 29)]
        (self.root / "7" / "sales.csv").write_text("\n".join(lines))
        self.book = FakeBook("Sheet1")
        for item in (
            patch.object(fs, "_storage_root", return_value=self.root),
            patch("skills.excel_shared.get_active_workbook", return_value=self.book),
            patch("skills.excel_shared.bind_workbook_context"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_import_creates_sheet_writes_all_rows_and_verifies(self):
        result = wi.import_workspace_file_to_sheet(7, "sales.csv", "Imported")
        self.assertTrue(result["verified"], result)
        self.assertEqual(29, result["rows_written"])
        sheet = self.book.sheets["Imported"]
        self.assertEqual(["Date", "Store", "Units", "Code"], sheet.range("A1:D1").value)
        self.assertEqual(datetime(2024, 1, 28), sheet.range("A29").value)
        self.assertEqual("0028", sheet.range("D29").value)  # leading zeros survived
        self.assertEqual(1, self.book.saves)

    def test_refuses_to_overwrite_and_stays_in_user_storage(self):
        self.book.sheets["Sheet1"].range("B2").value = "keep me"
        refused = wi.import_workspace_file_to_sheet(7, "sales.csv", "Sheet1")
        self.assertEqual("target_not_empty", refused["status"])
        self.assertEqual("keep me", self.book.sheets["Sheet1"].range("B2").value)
        with self.assertRaises(PermissionError):
            wi.import_workspace_file_to_sheet(7, "../8/other.csv", "X")

    def test_dispatch_requires_signed_in_user(self):
        from agent.core import dispatch_action
        denied, _, _ = dispatch_action("import_workspace_file_to_sheet", {"path": "sales.csv", "sheet_name": "X"})
        self.assertEqual("authenticated_file_access_required", denied["status"])
        ok, layer, _ = dispatch_action(
            "import_workspace_file_to_sheet", {"path": "sales.csv", "sheet_name": "X"},
            user_id=7, file_access_authorized=True,
        )
        self.assertEqual("workspace_import", layer)
        self.assertTrue(ok["verified"], ok)


class CopyRangeSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = load_skill("copy_range")
        self.book = FakeBook("Data", "Out")
        data = self.book.sheets["Data"]
        data.range("A1:C3").value = [["Item", "Q1", "Q2"], ["Pens", 10, 12], ["Ink", 4, 6]]
        patcher = patch.object(self.skill, "get_active_workbook", return_value=self.book)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_paste_values_transposed(self):
        result = self.skill.run("Data", "A1:C3", "Out", "B2", mode="values", transpose=True)
        self.assertTrue(result["verified"], result)
        self.assertEqual((3, 3), (result["rows"], result["columns"]))
        self.assertEqual(["Item", "Pens", "Ink"], self.book.sheets["Out"].range("B2:D2").value)
        self.assertEqual(["Q2", 12, 6], self.book.sheets["Out"].range("B4:D4").value)

    def test_overlap_invalid_mode_and_missing_sheet_are_refused(self):
        self.assertEqual("ranges_overlap", self.skill.run("Data", "A1:C3", "Data", "B2", mode="values")["status"])
        self.assertEqual("invalid_mode", self.skill.run("Data", "A1:C3", "Out", "A1", mode="magic")["status"])
        self.assertEqual("sheet_not_found", self.skill.run("Data", "A1:C3", "Nope", "A1")["status"])
        self.assertEqual("invalid_arguments", self.skill.run("Data", "A1:C3", "Out", "A1", mode="values", move=True)["status"])


class FixedSkillTests(unittest.TestCase):
    def test_delete_chart_reports_missing_chart_instead_of_success(self):
        skill = load_skill("delete_chart")

        class Sheet:
            charts = []

        class Book:
            sheets = {"S": Sheet()}

            def save(self):
                pass

        with patch.object(skill, "get_active_workbook", return_value=Book()):
            result = skill.run("S", "Chart 9")
        self.assertFalse(result["verified"])
        self.assertEqual("chart_not_found", result["status"])

    def test_database_import_refuses_writes_before_touching_excel(self):
        skill = load_skill("import_from_database")
        with patch.object(skill, "get_active_workbook", side_effect=AssertionError("Excel must not be touched")):
            result = skill.run("sqlite://", "DROP TABLE users", "S")
        self.assertEqual("query_not_read_only", result["status"])

    def test_database_import_reads_and_caps_rows(self):
        skill = load_skill("import_from_database")
        book = FakeBook("S")
        with tempfile.TemporaryDirectory() as tmp:
            import sqlite3
            path = Path(tmp) / "d.db"
            with sqlite3.connect(path) as conn:
                conn.execute("create table t (id integer, name text)")
                conn.executemany("insert into t values (?, ?)", [(i, f"n{i}") for i in range(5)])
            with patch.object(skill, "get_active_workbook", return_value=book), \
                 patch.object(skill, "_MAX_IMPORT_ROWS", 3):
                result = skill.run(f"sqlite:///{path}", "SELECT id, name FROM t ORDER BY id", "S")
        self.assertTrue(result["verified"], result)
        self.assertEqual(3, result["rows_written"])
        self.assertTrue(result["truncated"])
        self.assertEqual(["id", "name"], book.sheets["S"].range("A1:B1").value)


if __name__ == "__main__":
    unittest.main()
