"""Code-generation sandbox: static policy and real subprocess execution.

Execution tests run generated code in the real isolated subprocess without
touching Excel (data-only code). Workbook behaviour needs Windows + Excel.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from codegen.executor import CodeRejected, _check_ast, run_generated_code

ROOT = str(Path(__file__).resolve().parent)


class SandboxPolicyTests(unittest.TestCase):
    def assertRejected(self, code, fragment=""):
        with self.assertRaises(CodeRejected) as caught:
            _check_ast(code)
        self.assertIn(fragment, str(caught.exception))

    def test_classic_escapes_are_rejected(self):
        self.assertRejected("x = ().__class__.__bases__[0].__subclasses__()", "is not allowed")
        self.assertRejected("b = __builtins__", "__builtins__")
        self.assertRejected("import os")
        self.assertRejected("from subprocess import run")
        self.assertRejected("f = open('secret.txt')")
        self.assertRejected("g = getattr(wb, 'api')")

    def test_excel_com_program_execution_is_rejected_case_insensitively(self):
        self.assertRejected("wb.api.Application.ExecuteExcel4Macro('EXEC(\"calc.exe\")')", "ExecuteExcel4Macro")
        self.assertRejected("wb.api.application.executeexcel4macro('x')", "executeexcel4macro")
        self.assertRejected("wb.app.api.Run('Macro1')", "Run")
        self.assertRejected("wb.app.api.Workbooks.Open('C:/x.xlsx')", "Workbooks")
        self.assertRejected("wb.api.SaveAs('C:/x.xlsx')", "SaveAs")
        self.assertRejected("import xlwings as xw\nb = xw.Book('C:/other.xlsx')", "Book")

    def test_pandas_numpy_io_is_rejected(self):
        for code in (
            "import pandas as pd\ndf = pd.read_csv('C:/data.csv')",
            "import pandas as pd\ndf = pd.read_pickle('x')",
            "import pandas as pd\npd.DataFrame().to_csv('x.csv')",
            "import numpy as np\nnp.load('x.npy', allow_pickle=True)",
            "import pandas as pd\npd.DataFrame().query('a > 1')",
            "import pandas as pd\npd.eval('1+1')",
        ):
            with self.subTest(code=code):
                self.assertRejected(code)

    def test_legitimate_analysis_code_is_accepted(self):
        _check_ast(
            "import pandas as pd\nimport numpy as np\nimport json\n"
            "wb = get_task_workbook()\nwb.app.screen_updating = False\n"
            "df = wb.sheets['Data'].range('A1').expand().options(pd.DataFrame, header=1, index=False).value\n"
            "summary = df.groupby('Store', as_index=False)['Revenue'].sum()\n"
            "wb.sheets['Summary'].range('A1').options(index=False).value = summary\n"
            "back = wb.sheets['Summary'].range('A1').expand().value\n"
            "result = {'verified': len(back) == len(summary) + 1, 'verification_note': json.dumps(len(back))}\n"
        )

    def test_one_source_and_one_target_sheet_but_not_a_workbook_build(self):
        _check_ast("wb = get_task_workbook()\na = wb.sheets['Data']\nb = wb.sheets['Summary']")
        self.assertRejected("wb = get_task_workbook()\na = wb.sheets['A']\nb = wb.sheets['B']\nc = wb.sheets['C']", "3 sheets")

    def test_existing_formula_and_save_rules_still_hold(self):
        self.assertRejected("wb = get_task_workbook()\nwb.sheets['S'].range('A1').formula = '=1+1'", "insert_formula")
        self.assertRejected("wb = get_task_workbook()\nwb.sheets['S'].range('A1').value = '=SUM(B:B)'", "insert_formula")
        self.assertRejected("wb = get_task_workbook()\nwb.save()", "must not save")


class SandboxExecutionTests(unittest.TestCase):
    def test_pandas_code_runs_in_isolated_subprocess(self):
        code = (
            "import pandas as pd\n"
            "df = pd.DataFrame({'store': ['A', 'B', 'A'], 'revenue': [10, 20, 5]})\n"
            "totals = df.groupby('store')['revenue'].sum().to_dict()\n"
            "result = {'verified': totals == {'A': 15, 'B': 20}, 'totals': totals,\n"
            "          'verification_note': 'Recomputed totals in memory.'}\n"
        )
        result = run_generated_code(code, ROOT, timeout_seconds=60)
        self.assertTrue(result["verified"], result)
        self.assertEqual({"A": 15, "B": 20}, result["totals"])

    def test_secrets_are_not_visible_to_generated_code(self):
        code = (
            "import json\n"
            "result = {'verified': True, 'verification_note': 'probe', 'probe': 'ran'}\n"
        )
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-should-not-leak"}):
            from codegen.executor import _subprocess_env
            env = _subprocess_env(ROOT)
            result = run_generated_code(code, ROOT, timeout_seconds=60)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertIn(ROOT, env["PYTHONPATH"])
        self.assertEqual("ran", result["probe"])

    def test_unverified_or_evidence_free_results_are_not_success(self):
        missing_note = run_generated_code("result = {'verified': True}", ROOT, timeout_seconds=60)
        self.assertFalse(missing_note["verified"])
        self.assertEqual("verification_evidence_missing", missing_note["status"])
        crash = run_generated_code("x = 1 / 0", ROOT, timeout_seconds=60)
        self.assertEqual("exception", crash["status"])
        self.assertIn("ZeroDivisionError", crash["error"])

    def test_timeout_is_enforced(self):
        result = run_generated_code("while True:\n    pass", ROOT, timeout_seconds=3)
        self.assertEqual("timeout", result["status"])


if __name__ == "__main__":
    unittest.main()
