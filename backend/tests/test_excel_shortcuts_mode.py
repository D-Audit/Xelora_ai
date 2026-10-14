"""Keyboard shortcuts in normal (hybrid) mode, the Excel-task provider, and the method guide."""

import unittest
from unittest.mock import patch

import config
from agent import core, providers
from agent.prompts import BASE_SYSTEM_PROMPT_TEMPLATE


def _names(declarations):
    return {declaration["name"] for declaration in declarations}


class ShortcutCatalogueTests(unittest.TestCase):
    def setUp(self):
        for item in (patch.object(config, "VISUAL_ONLY_MODE", False),
                     patch.object(config, "ENABLE_VISUAL_FALLBACK", False),
                     patch.object(config, "ENABLE_CUA_DRIVER", False),
                     patch.object(config, "ENABLE_MCP_CLIENT", False)):
            item.start()
            self.addCleanup(item.stop)

    def gemini_names(self):
        return _names(providers.build_gemini_tools()[0]["function_declarations"])

    def test_keyboard_tools_are_offered_without_the_visual_fallback(self):
        with patch.object(config, "ENABLE_EXCEL_SHORTCUTS", True):
            claude, gemini = _names(providers.build_claude_tools()), self.gemini_names()
        for names in (claude, gemini):
            self.assertLessEqual({"go_to_range", "execute_excel_shortcut", "press_alt", "inspect_popup"}, names)
            # Screenshot and mouse tools stay off.
            self.assertFalse({"click", "parse_screen", "type_text", "find_and_click"} & names)

    def test_the_setting_turns_them_off(self):
        with patch.object(config, "ENABLE_EXCEL_SHORTCUTS", False):
            self.assertFalse(providers.EXCEL_SHORTCUT_TOOL_NAMES & _names(providers.build_claude_tools()))
            self.assertFalse(providers.EXCEL_SHORTCUT_TOOL_NAMES & self.gemini_names())

    def test_every_keyboard_tool_has_a_declaration(self):
        declared = _names(providers.VISION_TOOLS_CLAUDE)
        self.assertLessEqual(set(providers.EXCEL_SHORTCUT_TOOL_NAMES), declared)

    def test_dispatch_runs_keyboard_tools_but_not_mouse_tools(self):
        with patch.object(config, "ENABLE_EXCEL_SHORTCUTS", True), \
                patch("vision.ui_control.execute_excel_shortcut", return_value={"verified": True}) as shortcut:
            result, layer, _ = core.dispatch_action("execute_excel_shortcut", {"shortcut_name": "bold"})
            blocked, _, _ = core.dispatch_action("click", {"x": 1, "y": 1})
        shortcut.assert_called_once_with(shortcut_name="bold")
        self.assertEqual((True, "visual"), (result["verified"], layer))
        self.assertIn("ENABLE_VISUAL_FALLBACK", blocked["error"])


class TaskProviderTests(unittest.TestCase):
    def test_excel_tasks_use_the_configured_task_provider(self):
        with patch.object(config, "AI_PROVIDER", "gemini"), patch.object(config, "EXCEL_TASK_PROVIDER", "claude"), \
                patch.object(config, "ANTHROPIC_API_KEY", "k"):
            self.assertEqual("claude", providers.task_provider())
            self.assertEqual("claude", core.AgentTask("Build a budget").active_provider)

    def test_without_its_key_the_default_provider_is_kept(self):
        with patch.object(config, "AI_PROVIDER", "gemini"), patch.object(config, "EXCEL_TASK_PROVIDER", "claude"), \
                patch.object(config, "ANTHROPIC_API_KEY", ""):
            self.assertEqual("gemini", providers.task_provider())
        with patch.object(config, "AI_PROVIDER", "gemini"), patch.object(config, "EXCEL_TASK_PROVIDER", ""):
            self.assertEqual("gemini", providers.task_provider())


class MethodGuideTests(unittest.TestCase):
    def test_judgment_with_hard_requirements(self):
        self.assertIn("CHOOSING A METHOD", BASE_SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("HARD REQUIREMENTS always hold", BASE_SYSTEM_PROMPT_TEMPLATE)
        self.assertNotIn("the rule wins", BASE_SYSTEM_PROMPT_TEMPLATE)
        self.assertNotIn("LAST RESORT, but not a refusal", BASE_SYSTEM_PROMPT_TEMPLATE)

    def test_scripts_come_before_clicking_on_screen(self):
        guide = BASE_SYSTEM_PROMPT_TEMPLATE
        self.assertLess(guide.index("- KEYBOARD SHORTCUTS"), guide.index("- SCRIPTS"))
        self.assertLess(guide.index("- SCRIPTS"), guide.index("- DESKTOP CONTROL"))
        self.assertLess(guide.index("- DESKTOP CONTROL"), guide.index("- SCREENSHOT PARSING"))


if __name__ == "__main__":
    unittest.main()
