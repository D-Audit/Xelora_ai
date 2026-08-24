"""Fast regression tests for Excel-agent routing and verification safeguards.

These tests intentionally do not start Excel or alter a workbook.  They cover
the bugs that can be reproduced without COM: context loss across skill worker
threads, unverified codegen results, path expansion, and Gemini tool history.
"""

import os
import io
import unittest
from unittest.mock import patch

from agent import core, providers
from agent.prompts import _format_excel_version_block
from codegen.executor import run_generated_code
from skills.base import SKILL_REGISTRY
from skills import excel_shared
from skills.library.insert_formula.impl import _check_complexity
from skills.library.create_pivot_table.impl import _pivot_name
from skills.library.write_table.impl import _table_values_match, run as write_table
from vision import ui_control


BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))


class _Object:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)


class AutomationReliabilityTests(unittest.TestCase):
    def test_excel_2016_capability_message_requires_legacy_formulas(self):
        message = _format_excel_version_block({
            "verified": True,
            "label": "Excel version 16 without dynamic-array support",
            "raw_version": "16.0",
            "build": "4266",
            "supports_dynamic_arrays": False,
            "approved_functions": ["VLOOKUP", "INDEX/MATCH", "SUMIFS", "COUNTIFS"],
            "blocked_functions": ["XLOOKUP", "LET", "UNIQUE", "SORT", "FILTER", "SEQUENCE"],
        })

        self.assertIn("CAPABILITY DECISION: LEGACY", message)
        self.assertIn("Approved: VLOOKUP, INDEX/MATCH, SUMIFS, COUNTIFS", message)
        self.assertIn("Do not use: XLOOKUP, LET, UNIQUE, SORT, FILTER, SEQUENCE", message)

    def test_modern_capability_message_allows_dynamic_functions(self):
        message = _format_excel_version_block({
            "verified": True,
            "label": "Excel with confirmed modern dynamic-array support",
            "raw_version": "16.0",
            "build": "19328",
            "supports_dynamic_arrays": True,
            "approved_functions": ["VLOOKUP", "SUMIFS", "XLOOKUP", "UNIQUE", "SORT", "FILTER", "SEQUENCE", "LET"],
        })

        self.assertIn("CAPABILITY DECISION: MODERN", message)
        self.assertIn("XLOOKUP, UNIQUE, SORT, FILTER, SEQUENCE, LET", message)
        self.assertNotIn("Do not use:", message)

    def test_skill_worker_inherits_selected_workbook(self):
        excel_shared.bind_workbook_context("OnlyThisWorkbook.xlsx")

        def fake_skill(_tool_name, **_tool_input):
            return {"workbook_name": excel_shared._CURRENT_WORKBOOK_NAME.get(), "verified": True}

        with patch("agent.core.run_skill", side_effect=fake_skill):
            result = core._run_skill_with_timeout("fake", {})

        self.assertEqual("OnlyThisWorkbook.xlsx", result["workbook_name"])

    def test_codegen_requires_explicit_verified_result(self):
        success = run_generated_code(
            "result = {'verified': True, 'checked_workbook': WORKBOOK_NAME, "
            "'verification_note': 'Read back the target workbook name.'}",
            BACKEND_ROOT,
            workbook_name="Pinned.xlsx",
        )
        missing = run_generated_code("value = 1", BACKEND_ROOT, workbook_name="Pinned.xlsx")
        invalid_shape = run_generated_code("result = ['not', 'a', 'mapping']", BACKEND_ROOT)
        no_evidence = run_generated_code("result = {'verified': True}", BACKEND_ROOT)

        self.assertTrue(success["verified"])
        self.assertEqual("Pinned.xlsx", success["checked_workbook"])
        self.assertFalse(missing["verified"])
        self.assertEqual("no_result", missing["status"])
        self.assertFalse(invalid_shape["verified"])
        self.assertEqual("invalid_result_shape", invalid_shape["status"])
        self.assertFalse(no_evidence["verified"])
        self.assertEqual("verification_evidence_missing", no_evidence["status"])

    def test_codegen_allows_safe_random_data_generation(self):
        result = run_generated_code(
            "import random\n"
            "result = {'verified': True, 'sample': random.Random(7).randint(1, 9), "
            "'verification_note': 'Created a deterministic sample value for a new workbook.'}",
            BACKEND_ROOT,
        )

        self.assertTrue(result["verified"])
        self.assertEqual(6, result["sample"])

    def test_codegen_dispatch_forwards_the_task_workbook_identity(self):
        expected = {"verified": True, "verification_note": "Verified the pinned workbook."}

        with patch("agent.core.run_generated_code", return_value=expected) as generated:
            result, layer, code = core.dispatch_action(
                "run_excel_code", {"code": "result = {}"}, workbook_name="Pinned.xlsx"
            )

        self.assertEqual(expected, result)
        self.assertEqual("codegen", layer)
        self.assertEqual("result = {}", code)
        self.assertEqual("Pinned.xlsx", generated.call_args.kwargs["workbook_name"])

    def test_operational_skill_failure_is_scheduled_for_codegen(self):
        with patch("agent.core.config.ENABLE_CODEGEN_LAYER", True), patch(
            "agent.core.has_skill", return_value=True
        ):
            self.assertTrue(core._should_schedule_codegen_fallback(
                "write_table",
                {"verified": False, "error": "Excel returned 0x800A03EC"},
                "error",
            ))

    def test_preflight_and_formula_skill_failures_do_not_use_codegen(self):
        with patch("agent.core.config.ENABLE_CODEGEN_LAYER", True), patch(
            "agent.core.has_skill", return_value=True
        ):
            self.assertFalse(core._should_schedule_codegen_fallback(
                "write_table",
                {"verified": False, "status": "invalid_row_shape"},
                "skill",
            ))
            self.assertFalse(core._should_schedule_codegen_fallback(
                "insert_formula",
                {"verified": False, "status": "write_failed"},
                "skill",
            ))

    def test_write_table_rejects_formula_values_before_excel_is_called(self):
        result, layer, _ = core.dispatch_action("write_table", {
            "sheet_name": "Sales Data",
            "start_cell": "A1",
            "headers": ["Revenue"],
            "rows": [["=B2*C2"]],
        })

        self.assertEqual("input_guard", layer)
        self.assertFalse(result["verified"])
        self.assertEqual("formula_values_require_insert_formula", result["status"])

    def test_successful_codegen_recovery_resolves_only_its_failed_skill(self):
        task = core.AgentTask("Create a report")
        failed_input = {"sheet_name": "Sales Data", "start_cell": "A1"}
        task.structured_steps.append({
            "type": "action", "tool_name": "write_table", "input": failed_input,
            "result": {"verified": False}, "status": "fallback_pending",
        })
        task.pending_codegen_fallback = {
            "tool_name": "write_table", "tool_input": failed_input,
        }

        core._mark_codegen_fallback_recovered(task, task.pending_codegen_fallback)

        self.assertEqual("recovered", task.structured_steps[0]["status"])
        self.assertFalse(core._is_unresolved_workbook_action(task.structured_steps[0]))

    def test_insert_formula_exposes_verified_fill_down(self):
        properties = SKILL_REGISTRY["insert_formula"]["input_schema"]["properties"]

        self.assertIn("fill_to", properties)
        self.assertEqual("string", properties["fill_to"]["type"])

    def test_non_mutating_or_preflight_failures_do_not_invalidate_verified_work(self):
        task = core.AgentTask("create a report")
        task.structured_steps = [
            {
                "type": "action", "tool_name": "get_excel_version", "status": "failed",
                "result": {"verified": False, "status": "timeout_recovered"},
            },
            {
                "type": "action", "tool_name": "run_excel_code", "status": "failed",
                "result": {"verified": False, "status": "rejected_by_sandbox"},
            },
            {
                "type": "action", "tool_name": "create_sheet", "status": "success",
                "result": {"verified": True, "status": "sheet_created"},
            },
        ]

        final = core._build_final_response_reality_check(task, "Workbook change verified.")

        self.assertEqual("Workbook change verified.", final)

    def test_progress_log_does_not_crash_on_a_legacy_windows_console(self):
        task = core.AgentTask("create a report")
        output = io.BytesIO()
        legacy_console = io.TextIOWrapper(output, encoding="cp1252", errors="strict")

        with patch("sys.stdout", legacy_console):
            task.log_step("🤖 Excel task started")
            legacy_console.flush()

        self.assertEqual(["🤖 Excel task started"], task.progress_log)
        self.assertIn(b"\\U0001f916", output.getvalue())

    def test_each_pivot_uses_a_distinct_excel_name(self):
        self.assertEqual("Pivot_Month_Revenue", _pivot_name("Month", "Revenue"))
        self.assertEqual("Pivot_Category_Revenue", _pivot_name("Category", "Revenue"))
        self.assertNotEqual(
            _pivot_name("Month", "Revenue"),
            _pivot_name("Category", "Revenue"),
        )

    def test_verified_formula_recovery_resolves_the_earlier_failed_attempt(self):
        task = core.AgentTask("create a report")
        original_input = {
            "sheet_name": "RawData", "cell": "M2", "fill_to": "M501",
            "formula": "=[@UnitPrice]*[@Quantity]",
        }
        task.structured_steps.append({
            "type": "action", "tool_name": "insert_formula", "input": original_input,
            "result": {"verified": False}, "status": "retried",
        })

        core._mark_prior_action_recovered(task, "insert_formula", {
            **original_input, "formula": "=J2*K2",
        })

        self.assertEqual("recovered", task.structured_steps[0]["status"])
        self.assertFalse(core._is_unresolved_workbook_action(task.structured_steps[0]))

    def test_tilde_desktop_path_is_never_sent_to_excel_as_a_relative_folder(self):
        resolved = excel_shared.normalize_workbook_path("~/Desktop/agent-test.xlsx")
        self.assertTrue(os.path.isabs(resolved))
        self.assertNotIn(f"{os.sep}backend{os.sep}~{os.sep}", resolved)
        self.assertTrue(resolved.lower().endswith("agent-test.xlsx"))

    def test_two_heavy_functions_are_allowed_but_three_are_blocked(self):
        self.assertTrue(_check_complexity("=SUMIFS(A:A,B:B,1)+SUMIFS(C:C,D:D,2)")[0])
        self.assertFalse(_check_complexity("=SUMIFS(A:A,B:B,1)+SUMIFS(C:C,D:D,2)+SUMIFS(E:E,F:F,3)")[0])

    def test_table_validation_returns_before_touching_excel(self):
        result = write_table("Data", "A1", ["Name", ""], [["Ada", 1]])
        self.assertFalse(result["verified"])
        self.assertEqual("invalid_headers", result["status"])

    def test_gemini_tool_call_is_preserved_as_native_history(self):
        task = core.AgentTask("create a report")
        function_call = _Object(name="write_table", args={"sheet_name": "Data", "start_cell": "A1"})
        response = _Object(candidates=[_Object(content=_Object(parts=[_Object(
            function_call=function_call, thought_signature=b"signed",
        )]))])

        calls, text, stop_reason = providers._parse_gemini_response(task, response)

        self.assertEqual([function_call], calls)
        self.assertEqual([], text)
        self.assertEqual("tool_use", stop_reason)
        self.assertEqual("assistant", task.messages[-1]["role"])
        self.assertEqual(
            [{
                "function_call": {
                    "name": "write_table", "args": {"sheet_name": "Data", "start_cell": "A1"},
                },
                "thought_signature": "c2lnbmVk",
            }],
            task.messages[-1]["content"][providers._GEMINI_MODEL_PARTS_KEY],
        )

        providers.submit_gemini_tool_result(task, function_call, {"verified": True})
        history = providers._convert_history_for_gemini(task.messages)

        self.assertEqual("write_table", history[-2].parts[0].function_call.name)
        self.assertEqual(b"signed", history[-2].parts[0].thought_signature)
        self.assertEqual("write_table", history[-1].parts[0].function_response.name)
        self.assertTrue(history[-1].parts[0].function_response.response["verified"])
        self.assertEqual(1, len(history[-1].parts))

    def test_gemini_execution_starts_with_a_required_tool_call(self):
        task = core.AgentTask("Format the active worksheet in Excel.")

        config = providers._gemini_tool_config(task)

        self.assertEqual("ANY", config["function_calling_config"]["mode"])
        self.assertEqual(["inspect_workbook"], config["function_calling_config"]["allowed_function_names"])

    def test_new_dashboard_creates_its_sheet_before_writing_a_table(self):
        task = core.AgentTask("Create a sales dashboard with generated dummy data.")

        config = providers._gemini_tool_config(task)
        self.assertEqual(["create_sheet"], config["function_calling_config"]["allowed_function_names"])

        task.structured_steps.append({
            "type": "action", "tool_name": "create_sheet", "status": "success",
            "result": {"verified": True},
        })
        config = providers._gemini_tool_config(task)
        self.assertIn("write_table", config["function_calling_config"]["allowed_function_names"])
        self.assertIn("run_excel_code", config["function_calling_config"]["allowed_function_names"])

    def test_forced_gemini_schema_contains_only_allowed_tools(self):
        tools = providers.build_gemini_tools(["inspect_workbook"])
        names = [declaration["name"] for declaration in tools[0]["function_declarations"]]

        self.assertEqual(["inspect_workbook"], names)

    def test_gemini_requires_a_workbook_change_after_inspection(self):
        task = core.AgentTask("Format the active worksheet in Excel.")
        task.structured_steps = [{
            "type": "action", "tool_name": "inspect_workbook", "status": "success",
            "result": {"verified": True},
        }]

        config = providers._gemini_tool_config(task)

        self.assertEqual("ANY", config["function_calling_config"]["mode"])
        self.assertIn("create_sheet", config["function_calling_config"]["allowed_function_names"])
        self.assertIn("write_table", config["function_calling_config"]["allowed_function_names"])

    def test_gemini_forces_codegen_when_core_schedules_skill_recovery(self):
        task = core.AgentTask("Create a sales dashboard in Excel.")
        task.pending_codegen_fallback = {
            "tool_name": "write_table", "tool_input": {"sheet_name": "Sales Data"},
        }

        config = providers._gemini_tool_config(task)

        self.assertEqual(
            ["run_excel_code"],
            config["function_calling_config"]["allowed_function_names"],
        )

    def test_gemini_initial_mutation_options_include_codegen_when_enabled(self):
        task = core.AgentTask("Format the active worksheet in Excel.")
        task.structured_steps = [{
            "type": "action", "tool_name": "inspect_workbook", "status": "success",
            "result": {"verified": True},
        }]

        with patch("agent.providers.config.ENABLE_CODEGEN_LAYER", True):
            config = providers._gemini_tool_config(task)

        self.assertIn("run_excel_code", config["function_calling_config"]["allowed_function_names"])

    def test_gemini_final_verification_requires_inspection_once(self):
        task = core.AgentTask("Create a sales dashboard in Excel.")
        task.structured_steps = [{
            "type": "action", "tool_name": "create_sheet", "status": "success",
            "result": {"verified": True},
        }]
        task.final_verification_requested = True

        config = providers._gemini_tool_config(task)

        self.assertEqual(["inspect_workbook"], config["function_calling_config"]["allowed_function_names"])

        task.structured_steps.append({
            "type": "action", "tool_name": "inspect_workbook", "status": "success",
            "result": {"verified": True},
        })
        self.assertIsNone(providers._gemini_tool_config(task))

    def test_text_only_execution_cannot_claim_a_workbook_was_completed(self):
        task = core.AgentTask("Create a sales dashboard in Excel.")

        final = core._build_final_response_reality_check(task, "Dashboard created and verified.")

        self.assertTrue(final.startswith("INCOMPLETE:"))
        self.assertIn("text-only response", final)

    def test_explicit_approval_requirement_blocks_excel_until_confirmed(self):
        task = core.AgentTask(
            "Create a sales dashboard, but do not modify Excel immediately. "
            "Plan first and wait for my explicit approval."
        )

        self.assertTrue(task.awaiting_approval)
        self.assertTrue(task.defer_excel_until_approval)
        self.assertFalse(task.started_in_execution_mode)
        self.assertFalse(core._is_direct_action_instruction(task.instruction))

    def test_blank_excel_window_is_not_given_a_second_new_workbook(self):
        typed = []

        class FakeWindow:
            def is_minimized(self):
                return False

            def window_text(self):
                return "Book1 - Excel"

            def type_keys(self, keys, **_kwargs):
                typed.append(keys)

        with patch("vision.ui_control._activate_excel_window", return_value=True):
            ui_control._start_on_fresh_blank_workbook(FakeWindow())

        self.assertEqual([], typed)

    def test_excel_startup_workbook_is_reused_instead_of_creating_book2(self):
        class FakeBooks:
            def __init__(self):
                self.active = object()
                self.add_called = False

            def __len__(self):
                return 1

            def add(self):
                self.add_called = True
                return object()

        books = FakeBooks()
        app = _Object(books=books)

        workbook = excel_shared._active_or_new_workbook(app)

        self.assertIs(workbook, books.active)
        self.assertFalse(books.add_called)


if __name__ == "__main__":
    unittest.main()
