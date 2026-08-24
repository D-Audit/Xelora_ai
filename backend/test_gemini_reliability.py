"""Regression tests for Gemini tool-history and Excel-value reliability."""

from datetime import datetime
import unittest

from agent import core, providers
from skills.library.write_table.impl import _table_values_match


class _Object:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)


class GeminiReliabilityTests(unittest.TestCase):
    def test_parallel_function_results_are_submitted_together(self):
        task = core.AgentTask("Create a report")
        first_call = _Object(name="create_sheet", args={"sheet_name": "Data"}, id="call-1")
        second_call = _Object(name="create_sheet", args={"sheet_name": "Dashboard"}, id="call-2")
        response = _Object(candidates=[_Object(content=_Object(parts=[
            _Object(function_call=first_call, text=None, thought=None, thought_signature=b"first-signature"),
            _Object(function_call=second_call, text=None, thought=None, thought_signature=None),
        ]))])

        calls, _, stop_reason = providers._parse_gemini_response(task, response)
        self.assertEqual("tool_use", stop_reason)
        self.assertEqual([first_call, second_call], calls)

        # Core can reorder independent calls to satisfy sheet dependencies;
        # the provider must still return results in Gemini's original order.
        providers.submit_gemini_tool_result(task, second_call, {"verified": True})
        self.assertEqual(2, len(task.messages))
        providers.submit_gemini_tool_result(task, first_call, {"verified": True})

        self.assertEqual(3, len(task.messages))
        responses = task.messages[-1]["content"][providers._GEMINI_FUNCTION_RESPONSES_KEY]
        self.assertEqual(["call-1", "call-2"], [response["id"] for response in responses])
        history = providers._convert_history_for_gemini(task.messages)
        self.assertEqual(b"first-signature", history[-2].parts[0].thought_signature)
        self.assertIsNone(history[-2].parts[1].thought_signature)
        self.assertEqual(2, len(history[-1].parts))
        self.assertEqual("call-1", history[-1].parts[0].function_response.id)
        self.assertEqual("call-2", history[-1].parts[1].function_response.id)

    def test_signature_on_non_function_part_is_preserved_in_history(self):
        task = core.AgentTask("Create a report")
        call = _Object(name="create_sheet", args={"sheet_name": "Data"}, id="call-1")
        response = _Object(candidates=[_Object(content=_Object(parts=[
            _Object(function_call=None, text="", thought=True, thought_signature=b"thought-signature"),
            _Object(function_call=call, text=None, thought=None, thought_signature=None),
        ]))])

        providers._parse_gemini_response(task, response)
        providers.submit_gemini_tool_result(task, call, {"verified": True})
        history = providers._convert_history_for_gemini(task.messages)

        self.assertTrue(history[-2].parts[0].thought)
        self.assertEqual(b"thought-signature", history[-2].parts[0].thought_signature)
        self.assertEqual("create_sheet", history[-2].parts[1].function_call.name)

    def test_table_verification_accepts_excel_date_and_numeric_coercions(self):
        self.assertTrue(_table_values_match(
            [["2025-01-15", "1200", "0.30"]],
            [[datetime(2025, 1, 15), 1200, 0.3]],
        ))

    def test_table_verification_still_rejects_different_values(self):
        self.assertFalse(_table_values_match(
            [["2025-01-15", "1200"]],
            [[datetime(2025, 1, 15), 1201]],
        ))


if __name__ == "__main__":
    unittest.main()
