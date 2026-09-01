"""Fast regression tests for Excel-agent routing and verification safeguards.

These tests intentionally do not start Excel or alter a workbook.  They cover
the bugs that can be reproduced without COM: context loss across skill worker
threads, unverified codegen results, path expansion, and Gemini tool history.
"""

import os
import io
import time
import json
from datetime import datetime
import unittest
from unittest.mock import patch

import config
from PIL import Image

from agent import core, providers
from agent.capabilities import build_execution_capabilities, planning_context
from agent.prompts import _format_excel_version_block, build_system_prompt
from agent.reveal import progress_snapshot
from codegen.executor import run_generated_code
from skills.base import SKILL_REGISTRY
from skills import excel_shared
from skills.library.insert_formula.impl import _check_complexity, _validate_bounded_ranges, _validate_table_qualifiers
from skills.library.insert_formula.impl import _first_excel_error_in_range, _first_blank_formula_result
from skills.library.inspect_workbook import impl as inspect_workbook_impl
from skills.library.create_pivot_table.impl import _pivot_name
from skills.library.write_table.impl import _table_values_match, run as write_table
from vision import ui_control
from vision.excel_shortcuts import resolve_shortcut


BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))


class _Object:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)


class AutomationReliabilityTests(unittest.TestCase):
    def setUp(self):
        """Keep routing tests deterministic regardless of a developer's .env mode."""
        self._mode_patches = [
            patch("agent.core.config.VISUAL_ONLY_MODE", False),
            patch("agent.core.config.OMNIPARSER_ONLY_MODE", False),
            patch("agent.core.config.ENABLE_CODEGEN_LAYER", True),
        ]
        for mode_patch in self._mode_patches:
            mode_patch.start()

    def tearDown(self):
        for mode_patch in reversed(self._mode_patches):
            mode_patch.stop()

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

    def test_local_omniparser_mode_fails_at_startup_validation_when_module_is_missing(self):
        with patch("config.OMNIPARSER_LOCAL_MODE", True), patch(
            "config.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'vision.local_omniparser'"),
        ):
            with self.assertRaisesRegex(RuntimeError, "OMNIPARSER_LOCAL_MODE=true"):
                config.validate_local_omniparser_configuration()

    def test_openrouter_tool_result_serializes_excel_datetime_values(self):
        task = core.AgentTask("Read a workbook range.")

        providers.submit_openrouter_tool_result(
            task,
            "tool-call-1",
            {"verified": True, "values": [[datetime(2024, 1, 31, 0, 0)]]},
        )

        content = json.loads(task.messages[-1]["content"])
        self.assertEqual("2024-01-31 00:00:00", content["values"][0][0])

    def test_blank_formula_result_is_reported_with_exact_cell(self):
        formula_range = _Object(value=[[25], [None]], row=2, column=4)
        sheet = _Object(range=lambda coordinates: _Object(address="$D$3"))

        result = _first_blank_formula_result(sheet, formula_range)

        self.assertEqual({"address": "$D$3", "value": None}, result)

    def test_formula_preflight_rejects_table_name_used_as_worksheet(self):
        table = _Object(Name="SalesData", Parent=_Object(Name="Sales Data"))
        workbook = _Object(sheets=[_Object(api=_Object(ListObjects=[table]))])

        valid, error = _validate_table_qualifiers(
            workbook,
            "=SUM(SalesData!$M:$M)",
        )

        self.assertFalse(valid)
        self.assertIn("Excel Table name", error)
        self.assertIn("SalesData[Revenue]", error)

    def test_formula_preflight_rejects_whole_column_reference(self):
        valid, error = _validate_bounded_ranges("=AVERAGE('Sales Data'!M:M)")

        self.assertFalse(valid)
        self.assertIn("Whole-column reference", error)

    def test_timeout_recovery_rebinds_the_task_to_the_restarted_excel_pid(self):
        task = core.AgentTask("Build a workbook.")
        task.workbook_name = "Book1.xlsx"
        task.excel_app_pid = 111

        with patch("skills.excel_shared.bind_workbook_context") as bind_context:
            core._adopt_recovered_workbook_identity(
                task,
                {
                    "verified": False,
                    "workbook_recovered": True,
                    "workbook_name": "Book1.xlsx",
                    "excel_app_pid": 222,
                },
            )

        self.assertEqual("Book1.xlsx", task.workbook_name)
        self.assertEqual(222, task.excel_app_pid)
        bind_context.assert_called_once_with("Book1.xlsx", 222)

    def test_workbook_audit_reports_displayed_error_when_formula_metadata_fails(self):
        class _UsedRange:
            address = "$A$1:$B$2"
            value = [["Label", "Result"], ["Revenue", "#VALUE!"]]
            rows = [_Object(value=[["Label", "Result"]])]

            @property
            def formula(self):
                raise RuntimeError("Legacy Excel formula metadata unavailable")

            def offset(self, row, column):
                addresses = {(0, 0): "$A$1", (0, 1): "$B$1", (1, 0): "$A$2", (1, 1): "$B$2"}
                return _Object(address=addresses[(row, column)])

        sheet = _Object(
            name="Summary",
            used_range=_UsedRange(),
            tables=[],
            charts=[],
            api=_Object(PivotTables=lambda: []),
        )
        workbook = _Object(sheets=[sheet], names=[])

        report = inspect_workbook_impl._inspect_sheet(workbook, sheet)

        self.assertEqual(1, report["formula_error_count"])
        self.assertEqual("$B$2", report["formula_errors"][0]["address"])
        self.assertEqual("#VALUE!", report["formula_errors"][0]["error"])
        self.assertIn("Could not read formula metadata", report["formula_scan_warning"])

    def test_formula_repair_guard_blocks_another_sheet_until_repair_audit(self):
        task = core.AgentTask("Build a sales workbook.")
        task.pending_formula_repair = {
            "sheet_name": "Monthly Budget",
            "cell": "D2",
            "formula_rewritten": False,
        }

        self.assertTrue(core._pending_formula_repair_blocks_action(
            task, "write_table", {"sheet_name": "Sales Summary"}
        ))
        self.assertFalse(core._pending_formula_repair_blocks_action(
            task, "write_table", {"sheet_name": "Monthly Budget"}
        ))

        task.pending_formula_repair["formula_rewritten"] = True
        self.assertTrue(core._formula_repair_audit_passed(
            task,
            "inspect_workbook",
            {"sheet_name": "Monthly Budget"},
            {"verified": True, "formula_errors": [], "formula_error_count": 0},
        ))

    def test_sheet_tab_failure_snapshot_lists_raw_tabitem_text(self):
        product_tab = _Object(
            element_info=_Object(control_type="TabItem"),
            window_text=lambda: "Product Master",
        )
        normal_tab = _Object(
            element_info=_Object(control_type="TabItem"),
            window_text=lambda: "Normal",
        )
        other = _Object(
            element_info=_Object(control_type="Button"),
            window_text=lambda: "Save",
        )
        window = _Object(
            handle=77,
            window_text=lambda: "Book1 - Excel",
            descendants=lambda: [product_tab, normal_tab, other],
        )

        snapshot = ui_control._sheet_tab_uia_snapshot(window, "test")

        self.assertEqual("test", snapshot["reason"])
        self.assertEqual(["Product Master", "Normal"], [
            item["window_text"] for item in snapshot["tab_items"]
        ])

    def test_bound_window_is_identified_as_microsoft_excel_by_its_executable(self):
        window = _Object(
            handle=77,
            element_info=_Object(process_id=123),
            window_text=lambda: "Book1 - Excel",
        )
        with patch(
            "vision.ui_control._process_executable_path",
            return_value=r"C:\Program Files\Microsoft Office\Office16\EXCEL.EXE",
        ), patch("vision.ui_control._file_product_name", return_value="Microsoft Excel"):
            identity = ui_control._require_microsoft_excel(window)

        self.assertTrue(identity["is_microsoft_excel"])
        self.assertEqual("excel.exe", identity["executable_name"])
        self.assertEqual("Microsoft Excel", identity["product_name"])

    def test_wps_window_is_rejected_before_worksheet_input(self):
        window = _Object(
            handle=77,
            element_info=_Object(process_id=123),
            window_text=lambda: "Book1 - Excel",
        )
        with patch(
            "vision.ui_control._process_executable_path",
            return_value=r"C:\Program Files\WPS Office\office6\et.exe",
        ), patch("vision.ui_control._file_product_name", return_value="WPS Spreadsheets"):
            with self.assertRaisesRegex(RuntimeError, "Microsoft Excel only"):
                ui_control._require_microsoft_excel(window)

    def test_get_cell_value_success_always_has_verified_flag(self):
        with patch("vision.ui_control.go_to_range", return_value={"verified": True}), patch(
            "vision.ui_control.hotkey", return_value={"verified": True}
        ), patch("vision.ui_control.press_key"), patch(
            "vision.ui_control._get_clipboard_text", side_effect=["42", "42"]
        ), patch("vision.ui_control.time.sleep"):
            result = ui_control.get_cell_value("A1")

        self.assertTrue(result["verified"])
        self.assertEqual("42", result["value"])

    def test_capability_catalog_exposes_registered_skills_and_shortcuts(self):
        catalog = build_execution_capabilities()

        self.assertTrue(catalog["verified"])
        self.assertGreaterEqual(catalog["available_layers"]["skills_api"]["skill_count"], 70)
        shortcut_modules = catalog["available_layers"]["name_box_and_shortcuts"]["shortcut_modules"]
        operations = {
            item["operation"]
            for entries in shortcut_modules.values()
            for item in entries
        }
        self.assertIn("insert_table", operations)
        self.assertIn("save", operations)
        self.assertIn("chart_choice", catalog["selection_policy"])
        self.assertIn("no fixed tool order", catalog["selection_policy"]["principle"].lower())

    def test_capability_catalog_is_available_as_a_read_only_tool(self):
        result, layer, generated = core.dispatch_action("get_execution_capabilities", {})

        self.assertTrue(result["verified"])
        self.assertEqual("capability_catalog", layer)
        self.assertIsNone(generated)

    def test_workbook_state_is_included_in_runtime_planning_context(self):
        task = core.AgentTask("Inspect the workbook and add a summary.")
        observed = {
            "verified": True,
            "workbook_name": "Plan.xlsx",
            "formula_error_count": 0,
            "sheet_reports": [{
                "sheet": "Sales Data",
                "used_range": "$A$1:$Q$351",
                "existing_tables": ["SalesData"],
                "existing_charts": [],
                "existing_pivot_tables": [],
                "formula_error_count": 0,
            }],
        }
        with patch("agent.core.dispatch_action", return_value=(observed, "skill", None)):
            state = core._inspect_workbook_state_once(task)

        context = planning_context(state, {"verified": True, "label": "Excel 2016"})
        self.assertTrue(state["verified"])
        self.assertIn("Sales Data", context)
        self.assertIn("get_execution_capabilities", context)

    def test_hybrid_provider_exposes_skills_codegen_and_visual_tools(self):
        with patch("agent.providers.config.VISUAL_ONLY_MODE", False), patch(
            "agent.providers.config.ENABLE_CODEGEN_LAYER", True
        ), patch("agent.providers.config.ENABLE_VISUAL_FALLBACK", True):
            names = {tool["name"] for tool in providers.build_claude_tools()}

        self.assertIn("write_table", names)
        self.assertIn("run_excel_code", names)
        self.assertIn("go_to_range", names)
        self.assertIn("get_execution_capabilities", names)

    def test_hybrid_provider_tool_catalogues_have_no_duplicate_names(self):
        claude_names = [tool["name"] for tool in providers.build_claude_tools()]
        gemini_names = [
            tool["name"]
            for tool in providers.build_gemini_tools()[0]["function_declarations"]
        ]

        self.assertEqual(len(claude_names), len(set(claude_names)))
        self.assertEqual(len(gemini_names), len(set(gemini_names)))
        self.assertIn("create_sheet", gemini_names)
        self.assertIn("rename_sheet", gemini_names)

    def test_provider_catalogue_validation_covers_each_execution_profile(self):
        profiles = [
            (False, True, True),   # hybrid
            (False, False, False), # skills/API only
            (True, True, True),    # visual only
        ]
        for visual_only, codegen, visual_fallback in profiles:
            with patch("agent.providers.config.VISUAL_ONLY_MODE", visual_only), patch(
                "agent.providers.config.ENABLE_CODEGEN_LAYER", codegen
            ), patch("agent.providers.config.ENABLE_VISUAL_FALLBACK", visual_fallback):
                providers.validate_provider_tool_catalogues()

    def test_duplicate_provider_tool_name_fails_before_a_model_request(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate function declaration.*create_sheet"):
            providers._assert_unique_tool_names(
                [{"name": "create_sheet"}, {"name": "create_sheet"}],
                "Gemini",
            )

    def test_visual_prompt_requires_one_final_save_after_verification(self):
        with patch("agent.prompts.config.VISUAL_ONLY_MODE", True), patch(
            "agent.prompts.config.OMNIPARSER_ONLY_MODE", True
        ):
            prompt = build_system_prompt()

        self.assertIn("SAVE ORDER (MANDATORY FOR EVERY CREATE, EDIT, OR BUILD TASK)", prompt)
        self.assertIn("Only after verification succeeds, call save_workbook ONCE", prompt)
        self.assertIn("Never call execute_excel_shortcut('save_as')", prompt)

    def test_skill_worker_inherits_selected_workbook(self):
        excel_shared.bind_workbook_context("OnlyThisWorkbook.xlsx", 4321)

        def fake_skill(_tool_name, **_tool_input):
            return {
                "workbook_name": excel_shared._CURRENT_WORKBOOK_NAME.get(),
                "excel_app_pid": excel_shared._CURRENT_EXCEL_PID.get(),
                "verified": True,
            }

        with patch("agent.core.run_skill", side_effect=fake_skill):
            result = core._run_skill_with_timeout("fake", {})

        self.assertEqual("OnlyThisWorkbook.xlsx", result["workbook_name"])
        self.assertEqual(4321, result["excel_app_pid"])

    def test_batch_sheet_creation_skill_is_available_to_the_planner(self):
        self.assertIn("create_sheets", SKILL_REGISTRY)
        schema = SKILL_REGISTRY["create_sheets"]["input_schema"]
        self.assertEqual(["sheet_names"], schema["required"])

    def test_visible_workbook_session_maximizes_excel_without_forcing_focus(self):
        app = _Object(visible=False, screen_updating=False, api=_Object(WindowState=0))
        workbook = _Object(
            name="Book1.xlsx",
            app=app,
            activate=lambda: setattr(workbook, "activated", True),
            activated=False,
        )

        with patch("skills.excel_shared.config.MAXIMIZE_EXCEL_WINDOW", True):
            details = excel_shared.keep_workbook_visible(workbook)

        self.assertTrue(app.visible)
        self.assertTrue(app.screen_updating)
        self.assertEqual(-4137, app.api.WindowState)
        self.assertTrue(workbook.activated)
        self.assertTrue(details["maximized"])

    def test_startup_capability_profile_does_not_write_a_formula_probe(self):
        app = _Object(pid=751, api=_Object(Version="16.0", Build="4266"))
        workbook = _Object(app=app)

        with patch("skills.excel_shared.supports_dynamic_arrays") as probe:
            profile = excel_shared.get_excel_capabilities(
                workbook,
                probe_dynamic_arrays=False,
            )

        probe.assert_not_called()
        self.assertFalse(profile["dynamic_arrays"])
        self.assertEqual("deferred", profile["dynamic_array_probe"])

    def test_optional_startup_timeout_does_not_restart_excel(self):
        def slow_skill(_tool_name, **_tool_input):
            time.sleep(0.05)
            return {"verified": True}

        with patch("agent.core.run_skill", side_effect=slow_skill), patch(
            "skills.excel_shared.force_restart_excel_and_reopen"
        ) as restart:
            result = core._run_skill_with_timeout(
                "get_excel_version",
                {},
                timeout=0.01,
                recover_excel_on_timeout=False,
            )

        self.assertEqual("timeout", result["status"])
        restart.assert_not_called()

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

    def test_codegen_rejects_global_xlwings_active_workbook_access(self):
        result = run_generated_code(
            "import xlwings as xw\n"
            "wb = xw.books.active\n"
            "result = {'verified': True, 'verification_note': 'Not reached.'}",
            BACKEND_ROOT,
            workbook_name="Pinned.xlsx",
        )

        self.assertFalse(result["verified"])
        self.assertEqual("rejected_by_sandbox", result["status"])
        self.assertIn("get_task_workbook", result["error"])

    def test_codegen_rejects_nonexistent_default_api_before_execution(self):
        result = run_generated_code(
            "default_api.write_table()\n"
            "result = {'verified': True, 'verification_note': 'Not reached.'}",
            BACKEND_ROOT,
        )

        self.assertFalse(result["verified"])
        self.assertEqual("rejected_by_sandbox", result["status"])
        self.assertIn("default_api", result["error"])

    def test_codegen_rejects_openpyxl_sheetnames_on_the_live_xlwings_book(self):
        result = run_generated_code(
            "wb = get_task_workbook()\n"
            "names = wb.sheetnames\n"
            "result = {'verified': True, 'verification_note': 'Not reached.'}",
            BACKEND_ROOT,
            workbook_name="Pinned.xlsx",
        )

        self.assertFalse(result["verified"])
        self.assertEqual("rejected_by_sandbox", result["status"])
        self.assertIn("xlwings Book", result["error"])

    def test_provider_dns_failure_switches_to_configured_claude_with_clean_inspection_handoff(self):
        task = core.AgentTask("Create a sales dashboard.")
        task.active_provider = "gemini"
        task.structured_steps.append({
            "type": "action",
            "tool_name": "create_sheet",
            "status": "success",
            "result": {"verified": True, "verification_note": "Dashboard sheet exists."},
        })

        with patch("agent.providers.config.AI_PROVIDER_FALLBACK_CHAIN", ["claude"]), patch(
            "agent.providers.config.ANTHROPIC_API_KEY", "configured"
        ):
            switched = providers.activate_available_provider_fallback(
                task, OSError("[Errno 11001] getaddrinfo failed")
            )

        self.assertTrue(switched)
        self.assertEqual("claude", task.active_provider)
        self.assertEqual(["gemini"], task.provider_failover_history)
        self.assertEqual("user", task.messages[0]["role"])
        self.assertIn("First inspect the live workbook", task.messages[0]["content"])
        self.assertEqual("retry_pending", task.recovery_state["phase"])

    def test_openrouter_defaults_are_a_curated_function_calling_chain(self):
        self.assertEqual(
            [
                "deepseek/deepseek-v4-flash-0731",
                "xiaomi/mimo-v2.5",
                "tencent/hy3",
                "minimax/minimax-m3:free",
                "openrouter/free",
            ],
            config.OPENROUTER_MODEL_CHAIN,
        )
        self.assertEqual(35, config.OPENROUTER_TIMEOUT_SECONDS)
        self.assertEqual(0, config.OPENROUTER_INTER_MODEL_DELAY_SECONDS)
        self.assertEqual(45, config.OPENROUTER_TOTAL_TIMEOUT_SECONDS)
        self.assertEqual(45, config.GEMINI_TOTAL_TIMEOUT_SECONDS)
        self.assertEqual(35, config.CLAUDE_TIMEOUT_SECONDS)

    def test_openrouter_empty_reply_is_rejected_not_treated_as_completion(self):
        response = _Object(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": ""}}]},
        )
        task = core.AgentTask("Create a workbook.")

        with patch("agent.providers.config.OPENROUTER_API_KEY", "configured"), patch(
            "agent.providers.config.OPENROUTER_MODEL_CHAIN", ["test/model"]
        ), patch("requests.post", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "returned neither text nor a tool call"):
                providers.call_openrouter(task, "Use Excel tools.")

    def test_selected_openrouter_without_a_key_fails_loudly_at_startup(self):
        with patch("config.AI_PROVIDER", "openrouter"), patch(
            "config.OPENROUTER_API_KEY", ""
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
                config.validate_ai_provider_configuration()

    def test_verified_workbook_observation_binds_the_task_for_later_codegen(self):
        task = core.AgentTask("Create a report")
        observed = {
            "verified": True,
            "workbook_name": "Book1_52.xlsx",
            "excel_app_pid": 9821,
        }

        with patch("skills.excel_shared.bind_workbook_context") as bind_context:
            core._adopt_workbook_from_result(task, observed)

        self.assertEqual("Book1_52.xlsx", task.workbook_name)
        self.assertEqual(9821, task.excel_app_pid)
        bind_context.assert_called_once_with("Book1_52.xlsx", 9821)

    def test_codegen_dispatch_forwards_the_task_workbook_identity(self):
        expected = {"verified": True, "verification_note": "Verified the pinned workbook."}

        with patch("agent.core.config.VISUAL_ONLY_MODE", False), patch(
            "agent.core.config.ENABLE_CODEGEN_LAYER", True
        ), patch("agent.core.run_generated_code", return_value=expected) as generated:
            result, layer, code = core.dispatch_action(
                "run_excel_code",
                {
                    "code": "result = {}",
                    "fallback_reason": "The requested batch is too large for a safe tool payload.",
                    "atomic_goal": "Populate raw Sales Data input rows.",
                    "alternatives_considered": [
                        "write_table: the required raw-data payload exceeds the provider limit."
                    ],
                    "reveal_reference": "Sheet1!A1",
                },
                workbook_name="Pinned.xlsx",
                excel_app_pid=9911,
            )

        self.assertEqual(expected, result)
        self.assertEqual("codegen", layer)
        self.assertEqual("result = {}", code)
        self.assertEqual("Pinned.xlsx", generated.call_args.kwargs["workbook_name"])
        self.assertEqual(9911, generated.call_args.kwargs["excel_app_pid"])

    def test_codegen_dispatch_requires_selection_evidence(self):
        result, layer, code = core.dispatch_action(
            "run_excel_code", {"code": "result = {}"}
        )

        self.assertFalse(result["verified"])
        self.assertEqual("codegen_selection_evidence_required", result["status"])
        self.assertEqual("codegen_guard", layer)
        self.assertIsNone(code)

    def test_codegen_rejects_a_multi_sheet_build_before_excel_runs(self):
        result = run_generated_code(
            "wb = get_task_workbook()\n"
            "first = wb.sheets['Sales Data']\n"
            "second = wb.sheets['Sales Summary']\n"
            "result = {'verified': True, 'verification_note': 'Not reached.'}",
            BACKEND_ROOT,
        )

        self.assertFalse(result["verified"])
        self.assertEqual("rejected_by_sandbox", result["status"])
        self.assertIn("one atomic worksheet target", result["error"])

    def test_codegen_rejects_formula_text_written_through_value(self):
        result = run_generated_code(
            "wb = get_task_workbook()\n"
            "ws = wb.sheets['Sales Summary']\n"
            "ws.range('A1').value = '=SUM(A2:A3)'\n"
            "result = {'verified': True, 'verification_note': 'Not reached.'}",
            BACKEND_ROOT,
        )

        self.assertFalse(result["verified"])
        self.assertEqual("rejected_by_sandbox", result["status"])
        self.assertIn("formula-looking string", result["error"])

    def test_visible_reference_quotes_a_multi_word_sheet_name(self):
        reference = core._visible_range_reference(
            "run_excel_code", {"reveal_reference": "Executive Dashboard!A1"}
        )

        self.assertEqual("'Executive Dashboard'!A1", reference)

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
        with patch("agent.core.config.VISUAL_ONLY_MODE", False):
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

    def test_recovery_state_is_visible_in_live_progress_until_verified(self):
        task = core.AgentTask("Create a report")
        task.set_recovery_state(
            "retry_pending",
            "Recovering safely: inspecting the workbook before another write.",
            tool_name="write_table",
        )

        snapshot = progress_snapshot(
            task.structured_steps,
            task.is_done,
            task.final_response,
            task.recovery_state,
        )

        self.assertEqual("retry_pending", snapshot["recovery"]["phase"])
        self.assertEqual(
            "Recovering safely: inspecting the workbook before another write.",
            snapshot["current_task"],
        )

        task.clear_recovery_state("Workbook evidence is current.")
        self.assertIsNone(task.recovery_state)
        self.assertEqual("recovered", task.structured_steps[-1]["phase"])

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

    def test_new_dashboard_initial_tools_allow_a_batch_sheet_skill(self):
        task = core.AgentTask("Create a sales dashboard with generated dummy data.")
        task.structured_steps = [{
            "type": "action", "tool_name": "inspect_workbook", "status": "success",
            "result": {"verified": True},
        }]

        config = providers._gemini_tool_config(task)
        allowed = config["function_calling_config"]["allowed_function_names"]

        self.assertIn("create_sheet", allowed)
        self.assertIn("create_sheets", allowed)

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
        self.assertIn("execute_excel_shortcut", config["function_calling_config"]["allowed_function_names"])
        self.assertIn("go_to_range", config["function_calling_config"]["allowed_function_names"])

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

    def test_gemini_forces_inspection_after_an_unverified_recovery_action(self):
        task = core.AgentTask("Create a sales dashboard in Excel.")
        task.set_recovery_state(
            "retry_pending",
            "Recovering safely.",
            tool_name="run_excel_code",
        )

        tool_config = providers._gemini_tool_config(task)

        self.assertEqual(
            ["inspect_workbook"],
            tool_config["function_calling_config"]["allowed_function_names"],
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

    def test_formula_audit_returns_workbook_errors_to_the_repair_loop(self):
        audit = {
            "verified": True,
            "formula_errors": [{
                "sheet": "Inventory & Reorder Analysis",
                "address": "$A$2",
                "error": "#REF!",
                "formula": "=ProductMaster[MissingColumn]",
            }],
        }
        with patch("agent.core.run_skill", return_value=audit):
            result = core._audit_workbook_formula_errors()

        self.assertEqual(audit, result)
        self.assertIn("Inventory & Reorder Analysis!$A$2 = #REF!", core._formula_error_summary(result["formula_errors"]))

    def test_formula_fill_validation_finds_a_middle_row_error(self):
        class FakeCell:
            def __init__(self, address):
                self.address = address

        class FakeSheet:
            def range(self, coordinates):
                row, column = coordinates
                return FakeCell(f"${chr(64 + column)}${row}")

        class FakeRange:
            row = 2
            column = 3
            value = [[100], ["#REF!"], [200]]

        error = _first_excel_error_in_range(FakeSheet(), FakeRange())

        self.assertEqual({"address": "$C$3", "value": "#REF!"}, error)

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

    def test_parser_cache_reuses_the_same_excel_window_crop(self):
        image = Image.new("RGB", (32, 24), color=(17, 89, 173))
        capture = (image, (100, 200), {"handle": 42, "rect": [100, 200, 132, 224]})
        parsed = {"elements": [{"description": "Insert", "type": "text", "bbox": [1, 1, 10, 10], "center": [5, 5]}]}

        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._capture_excel_window", return_value=capture
        ), patch("vision.ui_control.parse_image", return_value=parsed) as parse_image, patch(
            "vision.ui_control._clear_parse_cache_safe"
        ):
            first = ui_control.parse_screen(zone="ribbon", use_cache=True)
            second = ui_control.parse_screen(zone="ribbon", use_cache=True)

        self.assertTrue(first["verified"])
        self.assertFalse(first["from_cache"])
        self.assertTrue(second["from_cache"])
        self.assertEqual(1, parse_image.call_count)

    def test_popup_parse_keeps_popup_buttons_and_labels(self):
        image = Image.new("RGB", (32, 24), color=(23, 101, 67))
        capture = (image, (0, 0), {"handle": 43, "rect": [0, 0, 32, 24]})
        parsed = {"elements": [{"description": "Save", "type": "button", "bbox": [1, 1, 10, 10], "center": [5, 5]}]}

        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._capture_excel_window", return_value=capture
        ), patch("vision.ui_control.parse_image", return_value=parsed), patch(
            "vision.ui_control._clear_parse_cache_safe"
        ):
            result = ui_control.parse_screen(zone="popup", use_cache=False)

        self.assertEqual("Save", result["elements"][0]["description"])

    def test_named_omniparser_fallback_accepts_normalized_description_field(self):
        parsed = {"elements": [{"description": "Insert", "center": [120, 180]}]}
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control.find_element_uia", return_value=None
        ), patch("vision.ui_control.parse_screen", return_value=parsed), patch(
            "vision.ui_control.click", return_value={"verified": True}
        ) as click:
            result = ui_control.click_element_by_name("Insert")

        self.assertTrue(result["verified"])
        self.assertEqual("omniparser", result["found_by"])
        click.assert_called_once_with(120, 180)

    def test_popup_classifier_never_treats_security_or_overwrite_as_a_safe_accept(self):
        self.assertEqual(
            "security_or_protection",
            ui_control._popup_kind({"normalized": "security warning enable content enable cancel"}),
        )
        self.assertEqual(
            "unsafe_confirmation",
            ui_control._popup_kind({"normalized": "replace existing file yes no cancel"}),
        )
        self.assertEqual(
            "workflow_dialog",
            ui_control._popup_kind({"normalized": "format cells number font alignment ok cancel"}),
        )

    def test_visual_completion_verifier_returns_boolean_evidence(self):
        with patch("vision.ui_control.get_existing_sheet_names", return_value=["Sheet1"]):
            complete = ui_control.verify_task_completion(expected_sheets=["Sheet1"])
            missing = ui_control.verify_task_completion(expected_sheets=["Sales Data"])

        self.assertTrue(complete["verified"])
        self.assertFalse(missing["verified"])
        self.assertIn("wps pdf", ui_control._NON_SHEET_TAB_TITLES)

    def test_find_and_click_routes_an_exact_sheet_name_to_the_sheet_navigator(self):
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._ensure_agent_workbook"), patch(
            "vision.ui_control._focus_excel_for_keyboard"
        ), patch("vision.ui_control.get_existing_sheet_names", return_value=["Sheet1"]), patch(
            "vision.ui_control.go_to_sheet", return_value={"verified": True}
        ) as go_to_sheet:
            result = ui_control.find_and_click("Sheet1")

        self.assertTrue(result["verified"])
        self.assertEqual("worksheet_tab", result["found_by"])
        go_to_sheet.assert_called_once_with("Sheet1")

    def test_shortcut_resolver_accepts_standard_excel_chords_beyond_the_named_catalog(self):
        self.assertEqual((("ctrl", "shift", "l"), "raw_chord"), resolve_shortcut("ctrl+shift+l"))
        self.assertEqual((("ctrl", "alt", "v"), "raw_chord"), resolve_shortcut("ctrl+alt+v"))
        self.assertEqual((("f4",), "raw_chord"), resolve_shortcut("F4"))
        self.assertEqual((("alt", "f1"), "raw_chord"), resolve_shortcut("alt+f1"))
        self.assertIsNone(resolve_shortcut("ctrl+imaginary_key"))

    def test_save_filename_is_safe_and_gets_an_excel_extension(self):
        self.assertEqual(
            "Business_Performance_Control.xlsx",
            ui_control._normalise_save_filename("Business_Performance_Control"),
        )
        with self.assertRaises(ValueError):
            ui_control._normalise_save_filename(r"C:\\Users\\HP\\Desktop\\report.xlsx")

    def test_unsaved_book_title_is_detected_without_misreading_book1_xlsx(self):
        self.assertTrue(ui_control._is_unnamed_excel_workbook(
            _Object(window_text=lambda: "Book1 - Excel")
        ))
        self.assertFalse(ui_control._is_unnamed_excel_workbook(
            _Object(window_text=lambda: "Book1.xlsx - Excel")
        ))

    def test_save_workbook_enters_filename_and_clicks_visible_save_button(self):
        popup = {
            "handle": 99,
            "title": "Save As",
            "message": "",
            "buttons": ["Save", "Cancel"],
            "_buttons": [],
            "normalized": "save as save cancel",
        }
        window = _Object(handle=10, window_text=lambda: "Management Report.xlsx - Excel")
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._find_save_as_popup", return_value=popup), patch(
            "vision.ui_control._select_local_documents_folder", return_value=True
        ) as select_documents, patch(
            "vision.ui_control._set_save_as_filename", return_value=True
        ) as set_name, patch(
            "vision.ui_control._click_popup_button", return_value="Save"
        ) as click_save, patch("vision.ui_control._read_excel_popups", return_value=[]), patch(
            "vision.ui_control._local_documents_folder", return_value=r"C:\\Users\\HP\\Documents"
        ):
            result = ui_control.save_workbook("Management Report")

        self.assertTrue(result["verified"])
        self.assertEqual("Management Report.xlsx", result["file_name"])
        select_documents.assert_called_once_with(popup)
        set_name.assert_called_once_with(popup, "Management Report.xlsx")
        click_save.assert_called_once_with(popup, ("Save",))

    def test_new_workbook_save_uses_browse_and_a_generated_local_filename(self):
        backstage = {
            "handle": None,
            "title": "Save As",
            "message": "Save As",
            "buttons": ["Browse", "OneDrive - Personal"],
            "_buttons": [],
            "normalized": "save as browse onedrive personal",
        }
        native = {
            "handle": 99,
            "title": "Save As",
            "message": "",
            "buttons": ["Save", "Cancel"],
            "_buttons": [],
            "normalized": "save as save cancel",
        }
        filename = "Xelora_Workbook_2026-08-29_120000.xlsx"
        window = _Object(handle=10, window_text=lambda: f"{filename} - Excel")
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._is_unnamed_excel_workbook", return_value=True), patch(
            "vision.ui_control._default_local_save_filename", return_value=filename
        ), patch("vision.ui_control._find_save_as_popup", return_value=None), patch(
            "vision.ui_control._wait_for_save_as_popup", side_effect=[backstage, native]
        ), patch("vision.ui_control._activate_excel_window"), patch(
            "vision.ui_control.pyautogui.press"
        ) as press_f12, patch(
            "vision.ui_control._click_popup_button", side_effect=["Browse", "Save"]
        ) as click_button, patch(
            "vision.ui_control._select_local_documents_folder", return_value=True
        ) as select_documents, patch(
            "vision.ui_control._set_save_as_filename", return_value=True
        ) as set_name, patch("vision.ui_control._read_excel_popups", return_value=[]), patch(
            "vision.ui_control._local_documents_folder", return_value=r"C:\\Users\\HP\\Documents"
        ), patch("vision.ui_control.time.sleep"):
            result = ui_control.save_workbook()

        self.assertTrue(result["verified"])
        self.assertTrue(result["generated_file_name"])
        self.assertEqual(filename, result["file_name"])
        press_f12.assert_called_once_with("f12")
        self.assertEqual([((backstage, ("Browse",)), {}), ((native, ("Save",)), {})], click_button.call_args_list)
        select_documents.assert_called_once_with(native)
        set_name.assert_called_once_with(native, filename)

    def test_lost_agent_excel_window_never_spawns_another_workbook(self):
        with patch.object(ui_control, "_agent_excel_handle", None), patch.object(
            ui_control, "_agent_excel_pid", 4242
        ), patch("vision.ui_control._find_excel_window_for_pid", return_value=None), patch(
            "vision.ui_control.subprocess.Popen"
        ) as launch:
            with self.assertRaisesRegex(RuntimeError, "will not open another blank workbook"):
                ui_control._open_blank_excel_window()

        launch.assert_not_called()

    def test_active_sheet_tool_returns_a_mapping_and_normalises_uia_prefix(self):
        self.assertEqual("Sheet1", ui_control._normalise_sheet_tab_name("Sheet Sheet1"))
        with patch("vision.ui_control._get_active_sheet_name_value", return_value="Sheet1"):
            result = ui_control.get_active_sheet_name()

        self.assertTrue(result["verified"])
        self.assertEqual("Sheet1", result["sheet_name"])

    def test_legacy_visual_primitive_result_cannot_crash_agent_loop(self):
        result = core._normalise_visual_tool_result("get_active_sheet_name", "Sheet1")

        self.assertFalse(result["verified"])
        self.assertEqual("invalid_visual_tool_result", result["status"])

    def test_visual_mapping_without_verified_evidence_is_a_failed_action(self):
        result = core._normalise_visual_tool_result("get_sheet_info", {"error": "read failed"})

        self.assertFalse(result["verified"])
        self.assertEqual("missing_verification_evidence", result["status"])

    def test_raw_input_is_blocked_while_an_excel_dialog_is_open(self):
        popup = {
            "title": "Create Table",
            "buttons": ["OK", "Cancel"],
        }
        with patch("vision.ui_control.inspect_excel_popups", return_value={
            "status": "popup_detected", "popups": [popup], "verified": True,
        }):
            with self.assertRaisesRegex(RuntimeError, "Create Table"):
                ui_control._require_no_open_popup(10)

    def test_lost_excel_window_is_recognised_as_a_terminal_visual_session_failure(self):
        self.assertTrue(core._is_lost_visual_excel_window({
            "error": "The Xelora-owned Excel window is no longer visible. Refusing to create an additional blank workbook."
        }))
        self.assertFalse(core._is_lost_visual_excel_window({"error": "The table range is invalid."}))

    def test_lost_pinned_workbook_is_terminal_in_hybrid_mode_too(self):
        self.assertTrue(core._is_lost_task_workbook({
            "error": "The task's target workbook 'Book1.xlsx' in Excel process 99 is not open in Excel."
        }))

    def test_system_switch_and_close_shortcuts_are_rejected_before_ui_input(self):
        for keys in (
            ["alt", "tab"], ["alt", "f4"], ["ctrl", "f4"], ["ctrl", "shift", "esc"],
            ["ctrl", "shift", "f3"],
        ):
            result = ui_control._blocked_excel_hotkey_result(keys)
            self.assertFalse(result["verified"])
            self.assertEqual("unsafe_system_shortcut_blocked", result["status"])

    def test_ambiguous_raw_key_sequences_are_rejected_before_excel_input(self):
        for keys in (["o", "i"], ["r"], ["alt", "h"], ["shift", "f11"]):
            result = ui_control._blocked_excel_hotkey_result(keys)

            self.assertFalse(result["verified"])
            self.assertEqual("ambiguous_raw_key_input_blocked", result["status"])

    def test_share_ribbon_tab_is_never_treated_as_a_worksheet_tab(self):
        share_tab = _Object(
            element_info=_Object(control_type="TabItem"),
            window_text=lambda: "Share",
        )

        self.assertIsNone(ui_control._sheet_tab_name_from_control(share_tab))

    def test_new_task_clears_only_a_confirmed_dead_excel_process(self):
        with patch.object(ui_control, "_agent_excel_handle", 42), patch.object(
            ui_control, "_agent_excel_pid", 4242
        ), patch("vision.ui_control._is_process_running", return_value=False):
            ui_control.set_workbook_mode(False)

            self.assertIsNone(ui_control._agent_excel_handle)
            self.assertIsNone(ui_control._agent_excel_pid)

    def test_visual_tool_contract_exposes_atomic_sheet_creation(self):
        tool_names = {tool["name"] for tool in providers.VISION_TOOLS_CLAUDE}

        self.assertIn("create_sheet", tool_names)
        self.assertIn("create_sheet", core.VISUAL_TOOL_NAMES)

    def test_create_sheet_renames_only_the_observed_new_tab(self):
        window = _Object(handle=77)
        with patch("vision.ui_control._get_agent_excel_window", return_value=window), patch(
            "vision.ui_control._require_no_open_popup"
        ), patch("vision.ui_control.get_existing_sheet_names", side_effect=[
            ["Sheet1"], ["Sheet1", "Sheet2"],
        ]), patch("vision.ui_control._focus_excel_for_keyboard"), patch(
            "vision.ui_control._activate_excel_window", return_value=True
        ), patch("vision.ui_control.pyautogui.hotkey") as insert_sheet, patch(
            "vision.ui_control.rename_sheet", return_value={"verified": True}
        ) as rename_sheet:
            result = ui_control.create_sheet("Sales Data")

        self.assertTrue(result["verified"])
        self.assertEqual("Sales Data", result["sheet_name"])
        insert_sheet.assert_called_once_with("shift", "f11")
        rename_sheet.assert_called_once_with("Sheet2", "Sales Data")

    def test_visual_save_waits_for_post_change_completion_verification(self):
        task = core.AgentTask("Create a workbook")
        task.structured_steps.append({
            "type": "action",
            "tool_name": "paste_table",
            "status": "success",
            "result": {"verified": True},
        })

        self.assertFalse(core._visual_save_is_ready(task))
        self.assertTrue(core._is_visual_save_attempt("save_workbook", {}))
        self.assertTrue(core._is_visual_save_attempt("execute_excel_shortcut", {"shortcut_name": "save"}))
        self.assertTrue(core._is_visual_save_attempt("hotkey", {"keys": ["ctrl", "s"]}))

        task.structured_steps.append({
            "type": "action",
            "tool_name": "verify_task_completion",
            "status": "success",
            "result": {"verified": True},
        })

        self.assertTrue(core._visual_save_is_ready(task))

    def test_structured_visual_build_cannot_skip_an_unverified_worksheet(self):
        task = core.AgentTask("Create these worksheets in this order:\n1. Product Master\n2. Sales Data")
        task.required_visual_sheet_names = ["Product Master", "Sales Data"]

        self.assertEqual("Product Master", core._next_required_visual_sheet(task))
        task.structured_steps.append({
            "type": "action", "tool_name": "create_sheet", "status": "retried",
            "input": {"sheet_name": "Product Master"},
            "result": {"verified": False},
        })
        self.assertEqual("Product Master", core._next_required_visual_sheet(task))

        task.structured_steps.append({
            "type": "action", "tool_name": "create_sheet", "status": "success",
            "input": {"sheet_name": "Product Master"},
            "result": {"verified": True, "sheet_name": "Product Master"},
        })
        self.assertEqual("Sales Data", core._next_required_visual_sheet(task))

    def test_structured_visual_build_requires_the_exact_requested_sheet_list(self):
        instruction = """Create these worksheets in this order:
1. Product Master
2. Sales Data
3. Executive Dashboard

Before finishing:
- Save the workbook as:
Business_Performance_Control.xlsx
"""
        task = core.AgentTask(instruction)
        task.required_visual_sheet_names = core._required_visual_sheet_names(instruction)

        self.assertEqual(
            ["Product Master", "Sales Data", "Executive Dashboard"],
            task.required_visual_sheet_names,
        )
        self.assertEqual(
            "Business_Performance_Control.xlsx",
            core._requested_workbook_file_name(instruction),
        )

        task.structured_steps.extend([
            {
                "type": "action", "tool_name": "paste_table", "status": "success",
                "result": {"verified": True},
            },
            {
                "type": "action", "tool_name": "verify_task_completion", "status": "success",
                "input": {"expected_sheets": ["Sheet1"]},
                "result": {"verified": True},
            },
        ])
        self.assertFalse(core._visual_save_is_ready(task))

        task.structured_steps.append({
            "type": "action", "tool_name": "verify_task_completion", "status": "success",
            "input": {"expected_sheets": ["Product Master", "Sales Data", "Executive Dashboard"]},
            "result": {"verified": True},
        })
        self.assertTrue(core._visual_save_is_ready(task))

    def test_visual_initial_forced_tools_include_safe_popup_workflow(self):
        task = core.AgentTask("Create a new workbook in Excel.")
        with patch("agent.providers.config.VISUAL_ONLY_MODE", True), patch(
            "agent.providers.config.OMNIPARSER_ONLY_MODE", True
        ):
            tool_config = providers._gemini_tool_config(task)

        allowed = tool_config["function_calling_config"]["allowed_function_names"]
        self.assertIn("inspect_popup", allowed)
        self.assertIn("click_popup_control", allowed)
        self.assertIn("set_popup_text", allowed)
        self.assertIn("click_popup_button", allowed)
        self.assertIn("create_sheet", allowed)

    def test_create_table_shortcut_completes_the_inspected_native_dialog(self):
        popup = {
            "handle": 99,
            "title": "Create Table",
            "message": "Where is the data for your table? $A$1:$I$41",
            "buttons": ["OK", "Cancel"],
            "_buttons": [],
            "_edit_values": ["=$A$1:$I$41"],
            "normalized": "create table where is the data for your table $a$1:$i$41 ok cancel",
        }
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._require_no_open_popup"), patch(
            "vision.ui_control._focus_excel_for_keyboard"
        ), patch("vision.ui_control.execute_shortcut", return_value=True) as shortcut, patch(
            "vision.ui_control._find_create_table_popup", side_effect=[None, popup]
        ), patch("vision.ui_control._click_popup_button", return_value="OK") as click_ok, patch(
            "vision.ui_control.inspect_excel_popups", return_value={"status": "clean", "popups": [], "verified": True}
        ), patch("vision.ui_control.time.sleep"):
            result = ui_control.create_excel_table()

        self.assertTrue(result["verified"])
        self.assertEqual("table_created", result["status"])
        shortcut.assert_called_once_with("insert_table")
        click_ok.assert_called_once_with(popup, ("OK",))

    def test_create_table_completes_an_already_open_valid_dialog_without_reopening_it(self):
        popup = {
            "handle": 99,
            "title": "Create Table",
            "message": "Where is the data for your table? =$A$1:$I$43",
            "buttons": ["OK", "Cancel"],
            "_buttons": [],
            "_edit_values": ["=$A$1:$I$43"],
            "normalized": "create table where is the data for your table =$a$1:$i$43 ok cancel",
        }
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._find_create_table_popup", return_value=popup), patch(
            "vision.ui_control._require_no_open_popup"
        ) as popup_guard, patch("vision.ui_control.execute_shortcut") as shortcut, patch(
            "vision.ui_control._click_popup_button", return_value="OK"
        ), patch("vision.ui_control.inspect_excel_popups", return_value={"status": "clean"}), patch(
            "vision.ui_control.time.sleep"
        ):
            result = ui_control.create_excel_table()

        self.assertTrue(result["verified"])
        popup_guard.assert_not_called()
        shortcut.assert_not_called()

    def test_create_table_popup_is_a_workflow_dialog(self):
        self.assertEqual(
            "workflow_dialog",
            ui_control._popup_kind({"normalized": "create table =$a$1:$i$43 ok cancel"}),
        )

    def test_only_the_task_that_timed_out_opening_a_table_can_auto_complete_it(self):
        task = core.AgentTask("Create an Excel table.")
        task.structured_steps.append({
            "type": "action",
            "tool_name": "execute_excel_shortcut",
            "input": {"shortcut_name": "insert_table"},
            "result": {"verified": False, "status": "create_table_dialog_not_found"},
        })
        popup = [{"title": "Create Table"}]

        self.assertTrue(core._has_pending_create_table_completion(task, popup))
        self.assertFalse(core._has_pending_create_table_completion(task, [{"title": "Save As"}]))

        unrelated_task = core.AgentTask("Format the workbook.")
        self.assertFalse(core._has_pending_create_table_completion(unrelated_task, popup))

    def test_popup_inspection_uses_the_uia_fallback_when_win32_cannot_see_a_dialog(self):
        popup = {
            "handle": 99,
            "title": "Create Table",
            "message": "Where is the data for your table? =$A$2:$I$42",
            "buttons": ["OK", "Cancel"],
            "_buttons": [],
            "_edit_values": ["=$A$2:$I$42"],
            "normalized": "create table where is the data for your table =$a$2:$i$42 ok cancel",
            "signature": "Create Table | =$A$2:$I$42 | OK | Cancel",
        }
        with patch("vision.ui_control._HAS_WIN32GUI", True), patch(
            "vision.ui_control._HAS_PYWINAUTO", True
        ), patch("vision.ui_control._enum_excel_popups", return_value=[]), patch(
            "vision.ui_control._uia_excel_popups", return_value=[popup]
        ):
            result = ui_control.inspect_excel_popups(10)

        self.assertEqual("popup_detected", result["status"])
        self.assertEqual("Create Table", result["popups"][0]["title"])

    def test_excel_workbook_frame_is_not_classified_as_a_popup(self):
        # Excel exposes its normal document frame as a UIA Window with Ribbon
        # buttons.  It must not trip the popup gate merely because it includes
        # labels such as Save and File Tab.
        self.assertTrue(ui_control._is_excel_workbook_frame_title("Book2 - Excel"))
        self.assertTrue(
            ui_control._is_excel_workbook_frame_title(
                "Management Report.xlsx - Excel (Product Activation Failed)"
            )
        )
        self.assertFalse(ui_control._is_excel_workbook_frame_title("Create Table"))
        self.assertFalse(ui_control._is_excel_workbook_frame_title("Save As"))

    def test_rename_sheet_edits_only_a_verified_tab_rename_control(self):
        target_tab = _Object(click_input=lambda: setattr(target_tab, "clicked", True), clicked=False)
        editor = _Object(
            set_edit_text=lambda value: setattr(editor, "value", value),
            type_keys=lambda keys, set_foreground: setattr(editor, "committed", (keys, set_foreground)),
            value=None,
            committed=None,
        )
        window = _Object(handle=77, descendants=lambda: [target_tab])

        with patch("vision.ui_control._HAS_PYWINAUTO", True), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._require_no_open_popup"), patch(
            "vision.ui_control._sheet_tab_name_from_control",
            side_effect=lambda control: "Sheet1" if control is target_tab else None,
        ), patch("vision.ui_control._open_sheet_rename_editor", return_value=editor) as open_editor, patch(
            "vision.ui_control.get_existing_sheet_names", return_value=["Product Master"]
        ), patch("vision.ui_control.hotkey") as hotkey, patch(
            "vision.ui_control.time.sleep"
        ):
            result = ui_control.rename_sheet("Sheet1", "Product Master")

        self.assertTrue(result["verified"])
        self.assertTrue(target_tab.clicked)
        open_editor.assert_called_once_with(window, target_tab, "Sheet1")
        self.assertEqual("Product Master", editor.value)
        self.assertEqual(("{ENTER}", False), editor.committed)
        hotkey.assert_not_called()

    def test_rename_sheet_aborts_without_typing_if_rename_editor_is_not_visible(self):
        target_tab = _Object(click_input=lambda: None)
        window = _Object(handle=77, descendants=lambda: [target_tab])

        with patch("vision.ui_control._HAS_PYWINAUTO", True), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._require_no_open_popup"), patch(
            "vision.ui_control._sheet_tab_name_from_control", return_value="Sheet1"
        ), patch("vision.ui_control._open_sheet_rename_editor", return_value=None), patch(
            "vision.ui_control.time.sleep"
        ):
            result = ui_control.rename_sheet("Sheet1", "Product Master")

        self.assertFalse(result["verified"])
        self.assertEqual("sheet_rename_editor_not_found", result["status"])

    def test_uia_popup_ok_button_is_clicked_without_a_blind_enter_key(self):
        ok_button = _Object(click_input=lambda: setattr(ok_button, "clicked", True), clicked=False)
        popup = {
            "_buttons": [{"label": "OK", "uia_control": ok_button}],
        }

        clicked = ui_control._click_popup_button(popup, ("OK",))

        self.assertEqual("OK", clicked)
        self.assertTrue(ok_button.clicked)

    def test_popup_button_matching_accepts_office_mnemonic_labels(self):
        save_button = _Object(click_input=lambda: setattr(save_button, "clicked", True), clicked=False)
        popup = {"_buttons": [{"label": "&Save", "uia_control": save_button}]}

        clicked = ui_control._click_popup_button(popup, ("Save",))

        self.assertEqual("&Save", clicked)
        self.assertTrue(save_button.clicked)

    def test_popup_action_is_not_verified_while_the_same_dialog_remains_open(self):
        ok_button = _Object(click_input=lambda: setattr(ok_button, "clicked", True), clicked=False)
        popup = {
            "handle": 99,
            "title": "Create Table",
            "signature": "Create Table | =$A$1:$I$41 | OK | Cancel",
            "normalized": "create table ok cancel",
            "_buttons": [{"label": "OK", "uia_control": ok_button}],
        }
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._read_excel_popups", side_effect=[
            [popup], [popup],
        ]), patch("vision.ui_control.time.sleep"):
            result = ui_control.click_popup_button("OK")

        self.assertFalse(result["verified"])
        self.assertEqual("popup_click_not_confirmed", result["status"])
        self.assertTrue(ok_button.clicked)

    def test_unknown_popup_inspection_adds_one_narrow_omniparser_read(self):
        popup = {
            "handle": 99,
            "title": "Custom Excel Dialog",
            "message": "",
            "buttons": ["Continue", "Cancel"],
            "normalized": "custom excel dialog continue cancel",
            "signature": "Custom Excel Dialog | Continue | Cancel",
        }
        window = _Object(handle=10)
        parsed = {"verified": True, "elements": [{"description": "Continue", "center": [1, 1]}]}
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch(
            "vision.ui_control.inspect_excel_popups", return_value={"status": "popup_detected", "popups": [popup], "verified": True}
        ), patch(
            "vision.ui_control._read_excel_popups", return_value=[popup]
        ), patch(
            "vision.ui_control.parse_screen", return_value=parsed
        ) as parse_popup:
            result = ui_control.inspect_popup()

        parse_popup.assert_called_once_with(zone="popup", use_cache=False)
        self.assertEqual("native_plus_omniparser_popup_crop", result["inspection_source"])
        self.assertEqual("Continue", result["popups"][0]["visual_inspection"]["elements"][0]["description"])

    def test_popup_screen_parse_uses_one_parser_attempt(self):
        image = Image.new("RGB", (400, 300), color="white")
        capture = (image, (0, 0), {"handle": 10, "rect": [0, 0, 400, 300]})
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._capture_excel_window", return_value=capture
        ), patch("vision.ui_control._clear_parse_cache_safe"), patch(
            "vision.ui_control.parse_image", return_value={"elements": []}
        ) as parse_image, patch("vision.ui_control.save_to_cache"):
            result = ui_control.parse_screen(zone="popup", use_cache=False)

        self.assertTrue(result["verified"])
        self.assertEqual(1, parse_image.call_args.kwargs["retries"])

    def test_popup_control_rejects_final_decisions(self):
        with patch("vision.ui_control._require_display"):
            result = ui_control.click_popup_control("OK")

        self.assertFalse(result["verified"])
        self.assertEqual("popup_final_button_requires_confirmation", result["status"])

    def test_popup_control_uses_exact_uia_configuration_choice(self):
        choice = _Object(
            window_text=lambda: "Use a formula to determine which cells to format",
            click_input=lambda: setattr(choice, "clicked", True),
            clicked=False,
            element_info=_Object(control_type="RadioButton"),
        )
        popup = {
            "handle": 99,
            "title": "New Formatting Rule",
            "message": "",
            "buttons": ["OK", "Cancel"],
            "normalized": "new formatting rule ok cancel",
            "signature": "New Formatting Rule | OK | Cancel",
        }
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch(
            "vision.ui_control._read_excel_popups", return_value=[popup]
        ), patch(
            "vision.ui_control._popup_uia_descendants", return_value=[choice]
        ), patch("vision.ui_control.time.sleep"):
            result = ui_control.click_popup_control("Use a formula to determine which cells to format")

        self.assertTrue(result["verified"])
        self.assertEqual("uia", result["found_by"])
        self.assertTrue(choice.clicked)

    def test_popup_text_reads_back_the_single_uia_edit_field(self):
        field = _Object(
            window_text=lambda: "",
            set_edit_text=lambda value: setattr(field.iface_value, "CurrentValue", value),
            element_info=_Object(control_type="Edit", automation_id="Formula"),
            iface_value=_Object(CurrentValue=""),
        )
        popup = {
            "handle": 99,
            "title": "New Formatting Rule",
            "message": "",
            "buttons": ["OK", "Cancel"],
            "normalized": "new formatting rule ok cancel",
            "signature": "New Formatting Rule | OK | Cancel",
        }
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch(
            "vision.ui_control._read_excel_popups", return_value=[popup]
        ), patch(
            "vision.ui_control._popup_uia_descendants", return_value=[field]
        ):
            result = ui_control.set_popup_text("=H2<G2", field_hint="formula")

        self.assertTrue(result["verified"])
        self.assertEqual("popup_text_entered", result["status"])

    def test_popup_detector_does_not_treat_save_type_field_as_a_second_dialog(self):
        self.assertTrue(ui_control._is_known_excel_workflow_dialog_title("Save As"))
        self.assertFalse(ui_control._is_known_excel_workflow_dialog_title("Save as type:"))
        self.assertTrue(ui_control._is_embedded_excel_dialog_control("Save as type:"))
        self.assertTrue(ui_control._is_native_save_dialog({"handle": 1, "buttons": ["&Save", "Cancel"]}))

    def test_create_table_never_accepts_a_malformed_dialog_reference(self):
        popup = {
            "handle": 99,
            "title": "Create Table",
            "message": "Where is the data for your table? $1:$1048576A1orProduct Master",
            "buttons": ["OK", "Cancel"],
            "_buttons": [],
            "normalized": "create table invalid range ok cancel",
        }
        window = _Object(handle=10)
        with patch("vision.ui_control._require_display"), patch(
            "vision.ui_control._get_agent_excel_window", return_value=window
        ), patch("vision.ui_control._require_no_open_popup"), patch(
            "vision.ui_control._focus_excel_for_keyboard"
        ), patch("vision.ui_control.execute_shortcut", return_value=True), patch(
            "vision.ui_control._find_create_table_popup", return_value=popup
        ), patch("vision.ui_control._click_popup_button") as click_ok, patch(
            "vision.ui_control.time.sleep"
        ):
            result = ui_control.create_excel_table()

        self.assertFalse(result["verified"])
        self.assertEqual("invalid_create_table_reference", result["status"])
        click_ok.assert_not_called()

    def test_background_excel_keys_support_used_range_navigation(self):
        self.assertEqual("{END}", ui_control._pyautogui_key_to_sendkeys("end"))
        self.assertEqual("+{END}", ui_control._hotkey_to_sendkeys(["shift", "end"]))

    def test_gemini_read_timeouts_are_marked_transient_for_model_fallback(self):
        self.assertTrue(providers._is_transient_gemini_transport_error(
            TimeoutError("The read operation timed out")
        ))
        self.assertTrue(providers._is_transient_gemini_transport_error(
            RuntimeError("Server disconnected without sending a response")
        ))
        self.assertFalse(providers._is_transient_gemini_transport_error(
            ValueError("invalid tool schema")
        ))

    def test_gemini_model_switch_repeats_the_authoritative_original_request(self):
        task = core.AgentTask("Create a 12-month sales dashboard in Excel.")
        continuation = providers._begin_clean_gemini_continuation_after_model_switch(task)

        self.assertIn("Authoritative original user request", continuation)
        self.assertIn(task.instruction, continuation)


if __name__ == "__main__":
    unittest.main()
