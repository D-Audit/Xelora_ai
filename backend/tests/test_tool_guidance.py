"""The model is told when to use every Excel skill, and only real ones."""
from __future__ import annotations

import os
import re
import unittest

from agent.prompts import BASE_SYSTEM_PROMPT_TEMPLATE
from agent.router import _FEATURE_HINTS, route_instruction
from skills.loader import LIBRARY_DIR

SKILLS = {
    name for name in os.listdir(LIBRARY_DIR)
    if os.path.isfile(os.path.join(LIBRARY_DIR, name, "SKILL.md"))
}
NON_SKILL_TOOLS = {"web_search", "web_fetch"}


class ToolGuidanceTests(unittest.TestCase):
    def test_every_skill_is_in_the_toolbox_map(self):
        missing = sorted(name for name in SKILLS if not re.search(rf"\b{name}\b", BASE_SYSTEM_PROMPT_TEMPLATE))
        self.assertEqual([], missing, "Add these skills to the TOOLBOX MAP in agent/prompts.py")

    def test_router_hints_name_only_real_tools(self):
        unknown = sorted({tool for _, tools, _ in _FEATURE_HINTS for tool in tools} - SKILLS - NON_SKILL_TOOLS)
        self.assertEqual([], unknown)

    def test_requests_route_to_their_dedicated_skills(self):
        cases = {
            "export the summary sheet to PDF in landscape": {"set_page_layout", "export_to_pdf"},
            "build a sales dashboard": {"create_pivot_table", "create_chart", "arrange_dashboard_layout"},
            "add a dropdown list of regions in column B": {"data_validation"},
            "remove duplicates then highlight the top 10": {"remove_duplicates", "conditional_formatting"},
            "compare budget vs actual by department": {"variance_analysis"},
        }
        for instruction, expected in cases.items():
            with self.subTest(instruction=instruction):
                tools = {tool for step in route_instruction(instruction).steps for tool in step.tools}
                self.assertLessEqual(expected, tools)

    def test_plain_data_entry_gets_no_extra_features(self):
        steps = route_instruction("put this data in excel").steps
        self.assertEqual(["excel_skills"], [step.capability for step in steps])



class ResearchHintTests(unittest.TestCase):
    def test_second_failure_of_a_tool_gets_one_research_hint(self):
        from agent.core import AgentTask, _add_research_hint

        task = AgentTask("build a lease schedule")
        first, second, third = {"error": "x"}, {"error": "Method Range.Foo failed"}, {"error": "x"}
        _add_research_hint(task, "run_excel_code", first)
        _add_research_hint(task, "run_excel_code", second)
        _add_research_hint(task, "run_excel_code", third)
        self.assertNotIn("research_hint", first)
        self.assertIn("web_search", second["research_hint"])
        self.assertIn("Method Range.Foo failed", second["research_hint"])
        self.assertNotIn("research_hint", third)

    def test_web_tools_are_never_told_to_research_themselves(self):
        from agent.core import AgentTask, _add_research_hint

        task = AgentTask("x")
        for _ in range(3):
            result = {"error": "timeout"}
            _add_research_hint(task, "web_search", result)
            self.assertNotIn("research_hint", result)


if __name__ == "__main__":
    unittest.main()
