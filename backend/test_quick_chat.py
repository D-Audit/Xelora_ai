"""Regression tests for the local quick-chat routing rules."""

import unittest

from quick_chat import canned_reply, classify_message


class QuickChatRoutingTests(unittest.TestCase):
    def test_greeting_stays_on_quick_chat(self):
        decision = classify_message("hello")
        self.assertEqual("chat", decision.kind)
        self.assertIsNotNone(canned_reply("hello"))

    def test_explanatory_excel_question_stays_on_quick_chat(self):
        self.assertEqual("chat", classify_message("How do I create a pivot table?").kind)

    def test_clear_workbook_action_uses_task_flow(self):
        self.assertEqual(
            "task",
            classify_message("Create a pivot table from the active worksheet").kind,
        )

    def test_attachment_always_uses_task_flow(self):
        self.assertEqual(
            "task",
            classify_message("Please review this", workbook_name="sales.xlsx").kind,
        )

    def test_short_follow_up_uses_task_flow_when_context_exists(self):
        self.assertEqual(
            "task",
            classify_message("Format it as currency", has_workbook_context=True).kind,
        )


if __name__ == "__main__":
    unittest.main()
