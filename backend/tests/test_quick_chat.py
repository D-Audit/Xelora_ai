"""Quick chat: routing rules, web-search tool loops, and the /chat endpoint."""

import sys
import types as pytypes
import unittest
from unittest.mock import MagicMock, patch

import config
import quick_chat
from quick_chat import canned_reply, classify_message

SEARCH_HIT = {"verified": True, "provider": "tavily", "results": [
    {"title": "Central Bank", "url": "https://bank.example/rate", "snippet": "Policy rate 5.25%"},
]}


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


class SmarterRoutingTests(unittest.TestCase):
    def check(self, expected, text, context=False):
        self.assertEqual(expected, classify_message(text, has_workbook_context=context).kind, text)

    def test_questions_about_the_users_workbook_need_the_agent(self):
        self.check("task", "What is the total in column C?")
        self.check("task", "Summarise my sheet")
        self.check("task", "Is cell B4 correct?")

    def test_general_questions_and_how_tos_are_answered(self):
        self.check("chat", "What is the EUR/USD rate today?")
        self.check("chat", "How do I sum column C in my sheet?")
        self.check("chat", "Who is the president of Kenya?")
        self.check("chat", "write a poem about rain")

    def test_spreadsheet_style_requests_need_the_agent(self):
        self.check("task", "Create a budget for my family")
        self.check("task", "Research the latest inflation rate and put it in a table")
        self.check("task", "Format A1:C10 as currency")

    def test_replies_in_an_excel_conversation_continue_it(self):
        self.check("task", "Use the Sales sheet", context=True)
        self.check("task", "continue", context=True)
        self.check("chat", "continue")
        self.check("chat", "Why did it fail?", context=True)
        self.check("chat", "thanks", context=True)


class QuickChatEndpointTests(unittest.TestCase):
    """POST /chat backs the frontend's /api/chat proxy."""

    def test_endpoint_answers_or_defers_to_task_flow(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        import config
        import main

        with patch.object(config, "LOCAL_API_KEY", "k"):
            client = TestClient(main.app)
            chat = client.post("/chat", json={"instruction": "hello"}, headers={"X-API-Key": "k"})
            task = client.post("/chat", json={"instruction": "Sort column B in this sheet"}, headers={"X-API-Key": "k"})
            denied = client.post("/chat", json={"instruction": "hello"})
        self.assertEqual("chat", chat.json()["route"])
        self.assertTrue(chat.json()["reply"])
        self.assertEqual([], chat.json()["sources"])
        self.assertEqual({"route": "task", "reply": None}, {k: task.json()[k] for k in ("route", "reply")})
        self.assertEqual(401, denied.status_code)


class QuickChatSettingsTests(unittest.TestCase):
    def test_settings_used_by_quick_chat_exist(self):
        # These were once read but never defined, so every model reply failed.
        self.assertGreater(config.FAST_CHAT_TIMEOUT_SECONDS, 0)
        self.assertGreater(config.FAST_CHAT_MAX_OUTPUT_TOKENS, 0)
        self.assertGreaterEqual(config.QUICK_CHAT_MAX_TOOL_ROUNDS, 1)


def _block(**fields):
    return pytypes.SimpleNamespace(**fields)


class ClaudeSearchLoopTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        fake_module = pytypes.ModuleType("anthropic")
        fake_module.Anthropic = MagicMock(return_value=self.client)
        for item in (patch.dict(sys.modules, {"anthropic": fake_module}),
                     patch.object(config, "AI_PROVIDER", "claude"),
                     patch.object(config, "ANTHROPIC_API_KEY", "k"),
                     patch.object(config, "QUICK_CHAT_WEB_SEARCH", True)):
            item.start()
            self.addCleanup(item.stop)

    def test_model_searches_then_answers_with_cited_sources(self):
        self.client.messages.create.side_effect = [
            _block(stop_reason="tool_use", content=[
                _block(type="tool_use", id="t1", name="web_search", input={"query": "policy rate today"})]),
            _block(stop_reason="end_turn", content=[_block(type="text", text="It is 5.25% [1].")]),
        ]
        with patch("tools.web.web_search", return_value=SEARCH_HIT) as search:
            answer = quick_chat.quick_answer("What is the central bank policy rate today?")
        search.assert_called_once()
        self.assertEqual("It is 5.25% [1].", answer["reply"])
        self.assertEqual([{"n": 1, "title": "Central Bank", "url": "https://bank.example/rate"}], answer["sources"])
        second = self.client.messages.create.call_args_list[1].kwargs
        tool_result = second["messages"][-1]["content"][0]
        self.assertEqual(("tool_result", "t1"), (tool_result["type"], tool_result["tool_use_id"]))
        self.assertIn("Today's date is", second["system"])

    def test_last_round_forbids_more_tool_calls(self):
        loop = _block(stop_reason="tool_use", content=[
            _block(type="tool_use", id="t", name="web_search", input={"query": "x"})])
        final = _block(stop_reason="end_turn", content=[_block(type="text", text="Best answer.")])
        with patch.object(config, "QUICK_CHAT_MAX_TOOL_ROUNDS", 1), \
                patch("tools.web.web_search", return_value=SEARCH_HIT):
            self.client.messages.create.side_effect = [loop, final]
            answer = quick_chat.quick_answer("Latest news on X?")
        self.assertEqual("Best answer.", answer["reply"])
        self.assertEqual({"type": "none"}, self.client.messages.create.call_args_list[1].kwargs["tool_choice"])

    def test_search_failure_is_reported_to_the_model_as_an_error(self):
        self.client.messages.create.side_effect = [
            _block(stop_reason="tool_use", content=[_block(type="tool_use", id="t", name="web_search", input={"query": "x"})]),
            _block(stop_reason="end_turn", content=[_block(type="text", text="I could not verify that.")]),
        ]
        with patch("tools.web.web_search", return_value={"verified": False, "error": "offline"}):
            answer = quick_chat.quick_answer("Who won yesterday?")
        result = self.client.messages.create.call_args_list[1].kwargs["messages"][-1]["content"][0]
        self.assertTrue(result["is_error"])
        self.assertEqual([], answer["sources"])

    def test_provider_failure_gives_a_friendly_reply(self):
        self.client.messages.create.side_effect = RuntimeError("boom")
        answer = quick_chat.quick_answer("Explain VLOOKUP")
        self.assertIn("try again", answer["reply"])

    def test_web_search_can_be_disabled(self):
        self.client.messages.create.return_value = _block(stop_reason="end_turn", content=[_block(type="text", text="Hi.")])
        with patch.object(config, "QUICK_CHAT_WEB_SEARCH", False):
            quick_chat.quick_answer("Explain VLOOKUP")
        self.assertNotIn("tools", self.client.messages.create.call_args.kwargs)


class GeminiSearchLoopTests(unittest.TestCase):
    def test_function_call_round_trip(self):
        from google.genai import types

        call = types.FunctionCall(name="web_search", args={"query": "exchange rate"})
        first = MagicMock(function_calls=[call])
        first.candidates = [MagicMock(content=types.Content(role="model", parts=[types.Part(function_call=call)]))]
        second = MagicMock(function_calls=None, text="About 1.08 [1].")
        client = MagicMock()
        client.models.generate_content.side_effect = [first, second]
        with patch.object(config, "AI_PROVIDER", "gemini"), patch.object(config, "GEMINI_API_KEY", "k"), \
                patch.object(config, "QUICK_CHAT_WEB_SEARCH", True), \
                patch("google.genai.Client", return_value=client), \
                patch("tools.web.web_search", return_value=SEARCH_HIT):
            answer = quick_chat.quick_answer("What is the EUR/USD exchange rate now?")
        self.assertEqual("About 1.08 [1].", answer["reply"])
        self.assertEqual("https://bank.example/rate", answer["sources"][0]["url"])
        contents = client.models.generate_content.call_args_list[1].kwargs["contents"]
        response_part = contents[-1].parts[0]
        self.assertEqual("web_search", response_part.function_response.name)


if __name__ == "__main__":
    unittest.main()
