"""Regression coverage for planning, data observation and native chart contracts.

The Excel objects are simulated: Windows Excel still needs a release smoke test.
"""
import inspect
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.intent_inference import INTENT_PATTERNS, enhance_plan_with_intent, infer_implicit_steps
from skills.excel_shared import normalize
from skills.registry import SKILL_REGISTRY
from skills.library.create_chart import impl as create_chart
from skills.library.modify_chart import impl as modify_chart
from skills.library.inspect_workbook import impl as inspect_workbook
from skills.library.read_range import impl as read_range
from test_support.fake_excel import FakeBook


class PlanningJudgmentTests(unittest.TestCase):
    def test_every_skill_schema_matches_its_callable(self):
        for name, entry in SKILL_REGISTRY.items():
            with self.subTest(skill=name):
                params = inspect.signature(entry['func']).parameters
                schema = entry['input_schema']
                self.assertEqual(set(params), set(schema.get('properties', {})))
                required = {key for key, value in params.items() if value.default is inspect.Parameter.empty}
                self.assertEqual(required, set(schema.get('required', [])))

    def test_inferred_tools_are_real_excel_skills(self):
        for pattern in INTENT_PATTERNS.values():
            for step in pattern['implicit_steps']:
                self.assertIn(step['tool_hint'], SKILL_REGISTRY)

    def test_incidental_substrings_and_generic_changes_do_not_add_work(self):
        for instruction in ('Change B2 to 8', 'Copy the summary', 'Update the impact label'):
            self.assertEqual([], infer_implicit_steps(instruction))

    def test_generic_cleanup_does_not_instruct_row_deletion(self):
        steps = infer_implicit_steps('Clean customer data')
        self.assertTrue(steps)
        self.assertEqual('read_range', steps[0]['tool_hint'])
        self.assertNotIn('remove_duplicates', [step['tool_hint'] for step in steps])

    def test_merging_preserves_dependency_edges_and_original_input(self):
        original = [{'id': 'subtask_1', 'depends_on': []},
                    {'id': 'subtask_2', 'depends_on': ['subtask_1']}]
        before = deepcopy(original)
        result = enhance_plan_with_intent(original, 'Create a dashboard')
        self.assertEqual(before, original)
        self.assertEqual(['subtask_1'], result[-1]['depends_on'])
        seen = set()
        for step in result:
            self.assertNotIn(step['id'], seen)
            self.assertLessEqual(set(step['depends_on']), seen)
            seen.add(step['id'])


class DataObservationTests(unittest.TestCase):
    def test_com_tuple_formulas_are_a_matrix(self):
        self.assertEqual([['=A1', '=B1'], ['=A2', '=B2']],
                         normalize((('=A1', '=B1'), ('=A2', '=B2'))))

    def test_single_column_read_preserves_rows(self):
        book = FakeBook('Data')
        book.sheets['Data'].range('A1:A3').value = [['Sales'], [12], [18]]
        with patch.object(read_range, 'get_active_workbook', return_value=book):
            result = read_range.run('Data', 'A1:A3')
        self.assertEqual([['Sales'], [12], [18]], result['values'])

    def test_read_keeps_excel_errors_visible(self):
        book = MagicMock()
        source = book.sheets.__getitem__.return_value.range.return_value
        source.options.return_value.value = [['#DIV/0!']]
        with patch.object(read_range, 'get_active_workbook', return_value=book):
            result = read_range.run('Data', 'A1')
        source.options.assert_called_once_with(ndim=2, err_to_str=True)
        self.assertEqual([['#DIV/0!']], result['values'])

    def test_audit_reports_cell_addresses_and_total_errors_beyond_preview(self):
        book = FakeBook('Data')
        sheet = book.sheets['Data']
        used = sheet.range('C4:C84')
        used.value = [['#REF!']] * 81
        sheet.used_range = used
        sheet.tables, sheet.charts = [], []
        sheet.api = SimpleNamespace(PivotTables=lambda: [])
        book.names = []
        result = inspect_workbook._inspect_sheet(book, sheet)
        self.assertEqual('$C$4', result['formula_errors'][0]['address'])
        self.assertEqual(81, result['formula_error_count'])
        self.assertEqual(80, len(result['formula_errors']))
        self.assertTrue(result['formula_errors_truncated'])


class ChartJudgmentTests(unittest.TestCase):
    def setUp(self):
        self.chart = MagicMock()
        self.chart.name = 'Revenue'
        self.sheet = MagicMock()
        self.sheet.charts.add.return_value = self.chart
        self.sheet.charts.__getitem__.return_value = self.chart
        self.book = MagicMock()
        self.book.sheets.__getitem__.return_value = self.sheet

    def test_unsupported_chart_never_opens_or_modifies_excel(self):
        with patch.object(create_chart, 'get_active_workbook') as get_book:
            result = create_chart.run('Data', 'A1:B4', chart_type='waterfall')
        self.assertFalse(result['verified'])
        get_book.assert_not_called()

    def test_existing_chart_name_is_not_duplicated(self):
        self.sheet.charts.__iter__.return_value = iter([self.chart])
        with patch.object(create_chart, 'get_active_workbook', return_value=self.book):
            result = create_chart.run('Data', 'A1:B4', chart_name='Revenue')
        self.assertEqual('chart_already_exists', result['status'])
        self.sheet.charts.add.assert_not_called()

    def test_failed_chart_is_removed_before_retry(self):
        self.chart.set_source_data.side_effect = RuntimeError('Invalid source')
        with patch.object(create_chart, 'get_active_workbook', return_value=self.book):
            result = create_chart.run('Data', 'A1:B4')
        self.assertFalse(result['verified'])
        self.chart.delete.assert_called_once()
        self.book.save.assert_not_called()

    def test_requested_chart_type_is_preserved(self):
        self.sheet.charts.__iter__.side_effect = [iter([]), iter([self.chart])]
        with patch.object(create_chart, 'get_active_workbook', return_value=self.book):
            result = create_chart.run('Data', 'A1:B4', chart_name='Revenue', chart_type='line')
        self.assertTrue(result['verified'])
        self.assertEqual('line', self.chart.chart_type)

    def test_dynamic_title_uses_formula_property(self):
        title = SimpleNamespace(Text='Old title', Formula='')
        self.chart.api = SimpleNamespace(HasTitle=True, ChartTitle=title)
        self.sheet.charts.__iter__.return_value = iter([self.chart])
        with patch.object(modify_chart, 'get_active_workbook', return_value=self.book):
            result = modify_chart.run('Data', 'Revenue', title_formula="='Data'!$A$1")
        self.assertTrue(result['verified'])
        self.assertEqual("='Data'!$A$1", title.Formula)
        self.assertEqual('Old title', title.Text)

    def test_modify_rejects_unsupported_type_before_touching_excel(self):
        with patch.object(modify_chart, 'get_active_workbook') as get_book:
            result = modify_chart.run('Data', 'Revenue', chart_type='waterfall')
        self.assertFalse(result['verified'])
        get_book.assert_not_called()

    def test_modify_scatter_keeps_points_without_connecting_lines(self):
        self.sheet.charts.__iter__.return_value = iter([self.chart])
        with patch.object(modify_chart, 'get_active_workbook', return_value=self.book):
            result = modify_chart.run('Data', 'Revenue', chart_type='scatter')
        self.assertTrue(result['verified'])
        self.assertEqual('xy_scatter', self.chart.chart_type)


if __name__ == '__main__':
    unittest.main()
