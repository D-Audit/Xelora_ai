"""Contract tests for Cua, routing, outbound MCP, policy, and audit.

The Cua and MCP tests run Xelora's adapters against test_support/
fake_cua_driver.py, a real stdio MCP server. They prove the adapter contract
over the genuine protocol; they are NOT Windows + Excel runtime tests and
send no desktop input.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

import config
from agent import audit
from agent.permissions import decide_action
from agent.router import route_instruction
from agent.tool_registry import get_tool_spec, validate_tool_input, web_tool_spec
from vision import cua_driver

FAKE_DRIVER = str(Path(__file__).with_name("test_support") / "fake_cua_driver.py")
EXCEL = (4242, 7)
ALL_ON = {"codegen": True, "terminal": True, "cua": True, "visual": True, "omniparser": True, "mcp": True,
          "shortcuts": True}


class FakeDriverCase(unittest.TestCase):
    """Point the Cua adapter at the fake stdio MCP driver."""

    mode = "ok"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = os.path.join(self._tmp.name, "state.json")
        patches = [
            patch.object(config, "ENABLE_CUA_DRIVER", True),
            patch.object(config, "CUA_DRIVER_COMMAND", sys.executable),
            patch.object(config, "CUA_DRIVER_ARGS", f'"{FAKE_DRIVER}"'),
            patch.object(config, "CUA_ALLOW_DESKTOP_SCOPE", False),
            patch.object(config, "CUA_ALLOW_OTHER_APPS", False),
            patch.dict(os.environ, {"FAKE_CUA_MODE": self.mode, "FAKE_CUA_STATE": self.state}),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        cua_driver._CACHE.update({"expires": 0.0, "tools": [], "error": None})
        cua_driver._HEALTH_CACHE.update({"expires": 0.0, "health": None})

    def counts(self) -> dict:
        if not os.path.exists(self.state):
            return {}
        return json.loads(Path(self.state).read_text())


class CuaDriverAvailableTests(FakeDriverCase):
    def test_health_reports_ready_and_only_allowlisted_tools(self):
        health = cua_driver.health_check(force_refresh=True)
        self.assertEqual("ready", health["status"], health)
        self.assertTrue(health["mcp_reachable"])
        self.assertIn("cua__verify_state", health["tools"])
        self.assertIn("cua__set_value", health["tools"])
        self.assertNotIn("cua__kill_app", health["tools"])  # driver offers it; Xelora never exposes it

    def test_accessibility_tree_observation(self):
        result = cua_driver.call_tool("get_window_state", {"pid": 4242, "window_id": 7}, observed_targets=set())
        self.assertTrue(result["verified"])
        self.assertEqual("observed", result["status"])
        self.assertIn("Sort", json.dumps(result["content"]))

    def test_window_not_found_is_a_driver_error(self):
        result = cua_driver.call_tool("get_window_state", {"pid": 1, "window_id": 1}, observed_targets=set())
        self.assertFalse(result["verified"])
        self.assertEqual("driver_error", result["status"])
        self.assertIn("window not found", result["error"])

    def test_input_requires_exact_target(self):
        result = cua_driver.call_tool("click", {"element_index": 3}, observed_targets={EXCEL})
        self.assertEqual("target_required", result["status"])

    def test_input_requires_prior_observation(self):
        result = cua_driver.call_tool("click", {"pid": 4242, "window_id": 7}, observed_targets=set())
        self.assertEqual("target_not_observed", result["status"])
        self.assertEqual({}, self.counts())  # nothing was sent to the driver

    def test_wrong_window_is_refused_when_task_is_bound_to_excel(self):
        result = cua_driver.call_tool(
            "click", {"pid": 999, "window_id": 1}, observed_targets={(999, 1)}, bound_pid=4242,
        )
        self.assertEqual("wrong_window", result["status"])
        with patch.object(config, "CUA_ALLOW_OTHER_APPS", True):
            allowed = cua_driver.check_target("click", {"pid": 999, "window_id": 1}, observed_targets={(999, 1)}, bound_pid=4242)
        self.assertIsNone(allowed)

    def test_desktop_scope_is_refused_by_default(self):
        result = cua_driver.call_tool("click", {"x": 10, "y": 10, "scope": "desktop"}, observed_targets=set())
        self.assertEqual("target_not_allowed", result["status"])

    def test_dispatched_input_is_not_verified_by_acknowledgement(self):
        result = cua_driver.call_tool("click", {"pid": 4242, "window_id": 7, "element_index": 3}, observed_targets={EXCEL})
        self.assertEqual("action_dispatched", result["status"])
        self.assertIsNone(result["verified"])
        self.assertEqual(1, self.counts()["click"])

    def test_act_and_verify_success(self):
        result = cua_driver.act_and_verify(
            "click", {"pid": 4242, "window_id": 7, "element_index": 3}, [{"element": 3, "focused": True}],
            observed_targets={EXCEL},
        )
        self.assertTrue(result["verified"], result)
        self.assertEqual(1, len(result["attempts"]))

    def test_dispatch_routes_cua_with_task_observed_targets(self):
        from agent.core import dispatch_action
        refused, layer, _ = dispatch_action("cua__click", {"pid": 4242, "window_id": 7}, cua_observed_targets=set())
        self.assertEqual("cua_driver", layer)
        self.assertEqual("target_not_observed", refused["status"])
        sent, _, _ = dispatch_action("cua__click", {"pid": 4242, "window_id": 7}, cua_observed_targets={EXCEL})
        self.assertEqual("action_dispatched", sent["status"])


class CuaVerificationFailureTests(FakeDriverCase):
    mode = "verify_fails"

    def test_bounded_retry_exhaustion(self):
        result = cua_driver.act_and_verify(
            "click", {"pid": 4242, "window_id": 7}, [{"x": 1}], max_attempts=10, observed_targets={EXCEL},
        )
        self.assertFalse(result["verified"])
        self.assertEqual("verification_failed", result["status"])
        self.assertEqual(3, len(result["attempts"]))  # clamped to the hard maximum
        self.assertEqual(3, self.counts()["click"])

    def test_typed_input_is_sent_once_and_only_rechecked(self):
        result = cua_driver.act_and_verify(
            "press_key", {"pid": 4242, "window_id": 7, "key": "enter"}, [{"x": 1}],
            max_attempts=3, observed_targets={EXCEL},
        )
        self.assertEqual("verification_failed", result["status"])
        self.assertEqual(3, len(result["attempts"]))
        self.assertEqual(1, self.counts()["press_key"])  # Enter twice would move two rows

    def test_typed_input_with_lost_connection_reports_unknown_delivery(self):
        cua_driver.discover_tools()  # warm the tool cache before the transport breaks
        with patch.object(cua_driver.mcp_client, "run_session", side_effect=ConnectionError("pipe closed")):
            result = cua_driver.act_and_verify(
                "press_key", {"pid": 4242, "window_id": 7, "key": "enter"}, [{"x": 1}],
                max_attempts=3, observed_targets={EXCEL},
            )
        self.assertEqual("delivery_unknown", result["status"])
        self.assertFalse(result["verified"])
        self.assertEqual(3, len(result["attempts"]))


class CuaRetryTests(FakeDriverCase):
    mode = "verify_after_2"

    def test_retry_succeeds_on_second_attempt(self):
        result = cua_driver.act_and_verify(
            "click", {"pid": 4242, "window_id": 7}, [{"x": 1}], max_attempts=3, observed_targets={EXCEL},
        )
        self.assertTrue(result["verified"], result)
        self.assertEqual(2, len(result["attempts"]))


class CuaRecheckTests(FakeDriverCase):
    mode = "verify_on_recheck"

    def test_typed_input_is_verified_by_recheck_without_resending(self):
        result = cua_driver.act_and_verify(
            "press_key", {"pid": 4242, "window_id": 7, "key": "enter"}, [{"x": 1}],
            max_attempts=3, observed_targets={EXCEL},
        )
        self.assertTrue(result["verified"], result)
        self.assertEqual("not_resent", result["attempts"][1]["action_status"])
        self.assertEqual(1, self.counts()["press_key"])


class CuaActionFailureTests(FakeDriverCase):
    mode = "click_error"

    def test_click_failure_stops_without_retry(self):
        result = cua_driver.act_and_verify(
            "click", {"pid": 4242, "window_id": 7}, [{"x": 1}], max_attempts=3, observed_targets={EXCEL},
        )
        self.assertEqual("action_failed", result["status"])
        self.assertEqual(1, len(result["attempts"]))
        self.assertIn("not clickable", result["error"])

    def test_keyboard_failure_is_reported(self):
        result = cua_driver.call_tool("press_key", {"pid": 4242, "window_id": 7, "key": "enter"}, observed_targets={EXCEL})
        self.assertFalse(result["verified"])
        self.assertIn("keyboard input was rejected", result["error"])


class CuaMalformedResponseTests(FakeDriverCase):
    mode = "malformed"

    def test_malformed_verify_state_never_counts_as_success(self):
        result = cua_driver.call_tool("verify_state", {"pid": 4242, "window_id": 7, "expect": [{}]}, observed_targets={EXCEL})
        self.assertFalse(result["verified"])
        self.assertEqual("verification_failed", result["status"])


class CuaTimeoutTests(FakeDriverCase):
    mode = "hang"

    def test_health_check_failure_on_unresponsive_driver(self):
        with patch.object(cua_driver, "_DISCOVERY_TIMEOUT_SECONDS", 2):
            health = cua_driver.health_check(force_refresh=True)
        self.assertEqual("unavailable", health["status"])
        self.assertFalse(health["mcp_reachable"])
        self.assertTrue(any("did not respond" in error for error in health["errors"]), health["errors"])
        self.assertIn("cua-driver doctor", health["setup_hint"])


class CuaUnavailableTests(unittest.TestCase):
    def test_missing_executable_is_reported_not_raised(self):
        cua_driver._HEALTH_CACHE.update({"expires": 0.0, "health": None})
        cua_driver._CACHE.update({"expires": 0.0, "tools": [], "error": None})
        with patch.object(config, "ENABLE_CUA_DRIVER", True), \
             patch.object(config, "CUA_DRIVER_COMMAND", "xelora-no-such-cua-driver"):
            health = cua_driver.health_check(force_refresh=True)
            result = cua_driver.call_tool("click", {"pid": 1, "window_id": 1})
        self.assertEqual("unavailable", health["status"])
        self.assertFalse(health["executable_found"])
        self.assertIn("install.ps1", health["setup_hint"])
        self.assertEqual("unavailable", result["status"])
        self.assertFalse(result["verified"])


class ExternalMcpTests(unittest.TestCase):
    def setUp(self):
        from tools import mcp_external
        self.mcp = mcp_external
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = os.path.join(self._tmp.name, "servers.json")
        Path(self.config_path).write_text(json.dumps({"servers": {"fake": {
            "command": sys.executable, "args": [FAKE_DRIVER],
            "read_tools": ["list_windows"], "write_tools": ["click"], "timeout_seconds": 20,
        }}}))
        for item in (
            patch.object(config, "ENABLE_MCP_CLIENT", True),
            patch.object(config, "MCP_SERVERS_FILE", self.config_path),
            patch.dict(os.environ, {"FAKE_CUA_MODE": "ok", "FAKE_CUA_STATE": ""}),
        ):
            item.start()
            self.addCleanup(item.stop)
        mcp_external._CACHE.update({"expires": 0.0, "tools": [], "errors": {}})

    def test_only_allowlisted_tools_are_exposed(self):
        names = {tool["name"] for tool in self.mcp.discover_tools(force_refresh=True)["tools"]}
        self.assertEqual({"mcp__fake__list_windows", "mcp__fake__click"}, names)

    def test_read_and_write_results_and_policy(self):
        self.mcp.discover_tools(force_refresh=True)
        read = self.mcp.call_tool("mcp__fake__list_windows", {})
        self.assertTrue(read["verified"])
        self.assertIn("Microsoft Excel", read["text"])
        write = self.mcp.call_tool("mcp__fake__click", {"pid": 1, "window_id": 2})
        self.assertIsNone(write["verified"])  # a write is unverified until read back
        write_spec = get_tool_spec("mcp__fake__click", visual_tool_names=set())
        self.assertFalse(decide_action(write_spec, planning_only=True).allowed)
        self.assertTrue(decide_action(get_tool_spec("mcp__fake__list_windows", visual_tool_names=set()), planning_only=True).allowed)
        from agent.core import _OBSERVATION_TOOL_NAMES
        self.assertIn("mcp__fake__list_windows", _OBSERVATION_TOOL_NAMES)
        self.assertNotIn("mcp__fake__click", _OBSERVATION_TOOL_NAMES)

    def test_unknown_and_unavailable_servers_fail_cleanly(self):
        self.assertEqual("unavailable", self.mcp.call_tool("mcp__fake__kill_app", {"pid": 1})["status"])
        Path(self.config_path).write_text(json.dumps({"servers": {"gone": {
            "command": "xelora-no-such-mcp-server", "read_tools": ["x"]}}}))
        discovery = self.mcp.discover_tools(force_refresh=True)
        self.assertEqual([], discovery["tools"])
        self.assertIn("gone", discovery["errors"])

    def test_invalid_configuration_is_rejected(self):
        for bad in (
            {"servers": {"a": {"command": "x"}}},  # no allowlist
            {"servers": {"a__b": {"command": "x", "read_tools": ["t"]}}},  # ambiguous name
            {"servers": {"a": {"command": "x", "read_tools": ["t"], "write_tools": ["t"]}}},
            {"nope": {}},
        ):
            Path(self.config_path).write_text(json.dumps(bad))
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                self.mcp.load_server_config(self.config_path)


class RouterTests(unittest.TestCase):
    def caps(self, text, **kwargs):
        return route_instruction(text, available=kwargs.pop("available", ALL_ON), **kwargs).capabilities()

    def test_excel_range_update_uses_skills(self):
        self.assertEqual(["excel_skills", "excel_shortcuts"], self.caps("Format column B as currency in Sheet1"))
        self.assertEqual(["excel_skills", "excel_shortcuts"], self.caps("Write these values into A1:C5"))

    def test_shortcuts_follow_their_setting(self):
        self.assertEqual(["excel_skills"], self.caps("Write these values into A1:C5",
                                                     available={**ALL_ON, "shortcuts": False, "visual": False}))
        gui = self.caps("Click the Sort button in the Data ribbon")
        self.assertEqual(1, gui.count("excel_shortcuts"))
        self.assertLess(gui.index("excel_shortcuts"), gui.index("cua_accessibility"))

    def test_large_transformation_uses_python(self):
        caps = self.caps("Use pandas to merge and deduplicate thousands of rows, then put the result in a sheet")
        self.assertEqual("python_codegen", caps[0])
        self.assertIn("excel_skills", caps)
        self.assertEqual("python_codegen", self.caps("Generate 5000 rows of sample transaction data")[0])
        self.assertEqual("python_codegen", self.caps("Load 12,000 rows and group by region")[0])

    def test_dedicated_skills_are_not_sent_to_codegen(self):
        cases = {
            "Unpivot the months into rows": "unpivot_data",
            "Remove duplicate customers": "remove_duplicates",
            "Merge the first and last name columns": "merge_columns",
            "Sort by date descending": "sort_range",
        }
        for text, skill in cases.items():
            with self.subTest(text=text):
                plan = route_instruction(text, available=ALL_ON)
                self.assertNotIn("python_codegen", plan.capabilities())
                self.assertEqual("excel_skills", plan.capabilities()[0])
                self.assertIn(skill, {tool for step in plan.steps for tool in step.tools})

    def test_research_uses_web_then_excel(self):
        caps = self.caps("Find the latest inflation rate for Rwanda and put it into the sheet")
        self.assertEqual(["web_research", "excel_skills", "excel_shortcuts"], caps)
        self.assertEqual(["web_research"], self.caps("What is the latest news about solar panels?"))

    def test_file_reading_uses_files(self):
        self.assertEqual(["user_files", "excel_skills", "excel_shortcuts"], self.caps("Put this CSV into Excel"))
        plan = route_instruction("Summarize my uploaded csv", file_access=False, available=ALL_ON)
        self.assertNotIn("user_files", plan.capabilities())
        self.assertTrue(plan.unavailable)

    def test_terminal_task_respects_configuration(self):
        self.assertEqual(["terminal"], self.caps("Open a terminal and run git status"))
        plan = route_instruction("run git status in the terminal", available={**ALL_ON, "terminal": False})
        self.assertNotIn("terminal", plan.capabilities())
        self.assertIn("ENABLE_TERMINAL_TOOLS", plan.unavailable[0])

    def test_gui_interaction_prefers_cua_before_omniparser(self):
        caps = self.caps("Click the Sort button in the Data ribbon")
        self.assertLess(caps.index("cua_accessibility"), caps.index("omniparser"))
        self.assertLess(caps.index("excel_skills"), caps.index("cua_accessibility"))

    def test_cua_unavailable_falls_back_and_says_so(self):
        plan = route_instruction("Click the checkbox in the dialog", available={**ALL_ON, "cua": False})
        self.assertNotIn("cua_accessibility", plan.capabilities())
        self.assertIn("ui_automation", plan.capabilities())
        self.assertTrue(any("cua" in item for item in plan.unavailable))

    def test_nothing_visual_when_everything_visual_is_off(self):
        plan = route_instruction("click the button", available={**ALL_ON, "cua": False, "visual": False, "omniparser": False})
        self.assertFalse({"cua_accessibility", "ui_automation", "omniparser"} & set(plan.capabilities()))


class PolicyAndValidationTests(unittest.TestCase):
    def test_schema_validation_rejects_unknown_and_wrong_types(self):
        spec = web_tool_spec("web_search")
        self.assertIsNone(validate_tool_input(spec, {"query": "x", "max_results": "3"})[1])  # quoted ints accepted
        self.assertEqual(3, validate_tool_input(spec, {"query": "x", "max_results": "3"})[0]["max_results"])
        self.assertIn("Unsupported", validate_tool_input(spec, {"query": "x", "shell": "rm"})[1])
        self.assertIn("Missing", validate_tool_input(spec, {})[1])
        self.assertIn("type", validate_tool_input(spec, {"query": ["x"]})[1])

    def test_file_tools_require_authenticated_session(self):
        spec = get_tool_spec("read_workspace_file", visual_tool_names=set())
        decision = decide_action(spec, planning_only=False, tool_input={"path": "a.csv"}, file_access_authorized=False)
        self.assertEqual("authenticated_file_access_required", decision.status)

    def test_disabled_terminal_is_blocked_by_policy(self):
        spec = get_tool_spec("run_terminal", visual_tool_names=set())
        with patch.object(config, "ENABLE_TERMINAL_TOOLS", False):
            decision = decide_action(spec, planning_only=False, tool_input={"argv": ["git", "status"]})
        self.assertEqual("disabled", decision.status)

    def test_failed_web_fetch_is_not_an_unresolved_workbook_action(self):
        from agent.core import _is_unresolved_workbook_action
        step = {"type": "action", "tool_name": "web_fetch", "status": "success",
                "result": {"verified": False, "status": "http_error"}}
        self.assertFalse(_is_unresolved_workbook_action(step))
        excel_step = {"type": "action", "tool_name": "write_cell", "status": "success", "result": {"verified": False}}
        self.assertTrue(_is_unresolved_workbook_action(excel_step))


class CompletionStatusTests(unittest.TestCase):
    def _task(self, requires_workbook, steps):
        from agent.core import AgentTask
        task = AgentTask("x")
        task.is_done = True
        task.awaiting_approval = False
        task.is_paused = False
        task.started_in_execution_mode = True
        task.route_requires_workbook = requires_workbook
        task.structured_steps = steps
        return task

    def test_research_only_task_completes_on_verified_sources(self):
        from agent.core import get_task_completion_status
        steps = [{"type": "action", "tool_name": "web_search", "status": "success", "result": {"verified": True}}]
        self.assertEqual("completed", get_task_completion_status(self._task(False, steps)))

    def test_excel_task_still_requires_a_workbook_change(self):
        from agent.core import get_task_completion_status
        steps = [{"type": "action", "tool_name": "web_search", "status": "success", "result": {"verified": True}}]
        self.assertEqual("failed", get_task_completion_status(self._task(True, steps)))

    def test_failed_terminal_command_is_not_success_evidence(self):
        from agent.core import get_task_completion_status
        steps = [{"type": "action", "tool_name": "run_terminal", "status": "success",
                  "result": {"verified": True, "succeeded": False, "exit_code": 128}}]
        self.assertEqual("failed", get_task_completion_status(self._task(False, steps)))


class RegistryProviderParityTests(unittest.TestCase):
    def test_every_offered_tool_resolves_in_the_registry(self):
        from agent import providers
        from agent.core import VISUAL_TOOL_NAMES
        profiles = (
            {"ENABLE_VISUAL_FALLBACK": True, "ENABLE_TERMINAL_TOOLS": True, "ENABLE_CODEGEN_LAYER": True, "OMNIPARSER_URL": "http://parser"},
            {"VISUAL_ONLY_MODE": True, "OMNIPARSER_URL": "http://parser"},
            {"ENABLE_VISUAL_FALLBACK": False, "ENABLE_TERMINAL_TOOLS": False},
        )
        for flags in profiles:
            patches = [patch.object(config, key, value) for key, value in flags.items()]
            for item in patches:
                item.start()
            try:
                names = {tool["name"] for tool in providers.build_claude_tools()}
                names |= {d["name"] for d in providers.build_gemini_tools()[0]["function_declarations"]}
            finally:
                for item in patches:
                    item.stop()
            with self.subTest(flags=flags):
                unresolved = [n for n in names if get_tool_spec(n, visual_tool_names=VISUAL_TOOL_NAMES) is None]
                self.assertEqual([], unresolved)
                self.assertEqual("run_terminal" in names, bool(flags.get("ENABLE_TERMINAL_TOOLS")))


class TerminalHardeningTests(unittest.TestCase):
    def test_program_paths_are_rejected(self):
        from tools.terminal import _command_policy
        for argv in (["/tmp/evil/git", "status"], ["..\\git.exe", "status"], ["./ls"]):
            with self.subTest(argv=argv):
                self.assertFalse(_command_policy(argv, Path("/tmp"))[0])

    def test_child_environment_excludes_secrets(self):
        from tools.mcp_client import scrubbed_environment
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-secret", "DATABASE_URL": "postgres://x", "XELORA_SAFE": "1"}):
            env = scrubbed_environment()
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("DATABASE_URL", env)
        self.assertEqual("1", env["XELORA_SAFE"])

    def test_portable_in_process_listing(self):
        from tools.terminal import run_terminal
        with tempfile.TemporaryDirectory() as root:
            Path(root, "report.csv").write_text("a")
            Path(root, "sub").mkdir()
            with patch.dict(os.environ, {"XELORA_TERMINAL_ROOT": root}):
                listing = run_terminal(["dir"])
                where = run_terminal(["pwd"], cwd="sub")
                escape = run_terminal(["ls", "../.."])
        self.assertEqual("success", listing["status"])
        self.assertIn("report.csv", listing["stdout"])
        self.assertIn("sub/", listing["stdout"])
        self.assertTrue(where["stdout"].strip().endswith("sub"))
        self.assertFalse(escape["verified"])


class AuditRedactionTests(unittest.TestCase):
    def test_secrets_are_masked_and_values_bounded(self):
        cleaned = audit.redact({
            "api_key": "abc", "headers": {"Authorization": "Bearer x"},
            "text": "token sk-abcdefghijklmnopqrstuv here", "content": "y" * 5000,
        })
        self.assertEqual("***", cleaned["api_key"])
        self.assertEqual("***", cleaned["headers"]["Authorization"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuv", cleaned["text"])
        self.assertLess(len(cleaned["content"]), 400)


if __name__ == "__main__":
    unittest.main()
