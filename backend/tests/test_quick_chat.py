"""Quick chat: routing rules, web-search tool loops, and the /chat endpoint."""

import sys
import types as pytypes
import unittest
from unittest.mock import MagicMock, patch

import config
import quick_chat
from quick_chat import classify_message, pre_route

SEARCH_HIT = {"verified": True, "provider": "tavily", "results": [
    {"title": "Central Bank", "url": "https://bank.example/rate", "snippet": "Policy rate 5.25%"},
]}


class QuickChatRoutingTests(unittest.TestCase):
    def test_greeting_stays_on_quick_chat(self):
        decision = classify_message("hello")
        self.assertEqual("chat", decision.kind)

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


class PreRouteTests(unittest.TestCase):
    def test_only_attachments_and_approvals_skip_the_model(self):
        self.assertEqual("task", pre_route("what is in here?", workbook_name="sales.xlsx").kind)
        self.assertEqual("task", pre_route("confirm", has_workbook_context=True).kind)
        self.assertIsNone(pre_route("confirm"))
        self.assertIsNone(pre_route("Create a pivot table from the active worksheet"))
        self.assertIsNone(pre_route("hello"))


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

    def test_general_questions_in_an_excel_conversation_are_answered(self):
        for text in ("between Ronaldo and Messi who is the goat", "Ronaldo vs Messi",
                     "is Messi better than Ronaldo", "tell me who won the 2022 World Cup"):
            self.check("chat", text, context=True)
        for text in ("make it bold", "the second one", "can you make the header bold",
                     "do the same for March", "now the March column instead"):
            self.check("task", text, context=True)


class QuickChatEndpointTests(unittest.TestCase):
    """POST /chat backs the frontend's /api/chat proxy."""

    def test_endpoint_answers_or_defers_to_task_flow(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        import config
        import main

        # No model configured: the wording rules decide, and the chat reply says to try again.
        with patch.object(config, "LOCAL_API_KEY", "k"), patch.object(config, "GEMINI_API_KEY", ""), \
                patch.object(config, "ANTHROPIC_API_KEY", ""), patch.object(config, "OPENROUTER_API_KEY", ""):
            client = TestClient(main.app)
            chat = client.post("/chat", json={"instruction": "hello"}, headers={"X-API-Key": "k"})
            task = client.post("/chat", json={"instruction": "Sort column B in this sheet"}, headers={"X-API-Key": "k"})
            denied = client.post("/chat", json={"instruction": "hello"})
        self.assertEqual("chat", chat.json()["route"])
        self.assertTrue(chat.json()["reply"])
        self.assertEqual([], chat.json()["sources"])
        self.assertEqual({"route": "task", "reply": None}, {k: task.json()[k] for k in ("route", "reply")})
        self.assertEqual(401, denied.status_code)


    def test_stream_reports_route_status_and_answer(self):
        import json
        from fastapi.testclient import TestClient
        import main

        def answer(instruction, history, *, user_id=None, on_status=None, route=False, excel_context=False):
            self.assertTrue(route)
            if instruction.startswith("Sort"):
                return {"route": "task", "reason": "Sorting a column.", "reply": None, "sources": []}
            on_status("Searching the web for “goat”")
            return {"route": "chat", "reply": "Both are great.", "sources": []}

        with patch.object(config, "LOCAL_API_KEY", "k"), patch.object(quick_chat, "quick_answer", side_effect=answer):
            client = TestClient(main.app)
            chat = client.post("/chat/stream", json={"instruction": "Who is the GOAT, Messi or Ronaldo?"},
                               headers={"X-API-Key": "k"})
            task = client.post("/chat/stream", json={"instruction": "Sort column B in this sheet"},
                               headers={"X-API-Key": "k"})
        events = [json.loads(line) for line in chat.text.splitlines() if line.strip()]
        self.assertEqual(["status", "status", "route", "answer"], [event["type"] for event in events])
        self.assertEqual(["Thinking", "Searching the web for “goat”"], [event["text"] for event in events[:2]])
        self.assertEqual("chat", events[2]["route"])
        self.assertEqual("Both are great.", events[3]["reply"])
        self.assertNotIn("route", events[3])
        task_events = [json.loads(line) for line in task.text.splitlines() if line.strip()]
        self.assertEqual({"type": "route", "route": "task", "reason": "Sorting a column."}, task_events[-1])


    def test_a_routed_task_is_not_routed_again(self):
        from fastapi.testclient import TestClient
        import main

        with patch.object(config, "LOCAL_API_KEY", "k"), patch.object(config, "DATABASE_URL", ""), \
                patch.object(main, "_start_task_in_background") as start:
            client = TestClient(main.app)
            client.post("/task", json={"instruction": "Who is the GOAT?", "routed": True}, headers={"X-API-Key": "k"})
            client.post("/task", json={"instruction": "Who is the GOAT?"}, headers={"X-API-Key": "k"})
        self.assertEqual([False, True], [call.kwargs["allow_direct_answer"] for call in start.call_args_list])


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
                     patch.object(config, "AI_PROVIDER_FALLBACK_CHAIN", []),
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
        self.assertTrue(answer["failed"])

    def test_reports_what_it_is_doing(self):
        self.client.messages.create.side_effect = [
            _block(stop_reason="tool_use", content=[
                _block(type="tool_use", id="t1", name="web_search", input={"query": "policy rate today"})]),
            _block(stop_reason="end_turn", content=[_block(type="text", text="5.25% [1].")]),
        ]
        statuses = []
        with patch("tools.web.web_search", return_value=SEARCH_HIT):
            quick_chat.quick_answer("What is the policy rate today?", on_status=statuses.append)
        self.assertEqual(["Searching the web for “policy rate today”", "Writing the answer"], statuses)

    def test_a_short_time_budget_answers_without_searching(self):
        self.client.messages.create.return_value = _block(stop_reason="end_turn", content=[_block(type="text", text="Hi.")])
        with patch.object(config, "QUICK_CHAT_DEADLINE_SECONDS", 8):
            quick_chat.quick_answer("Who won yesterday?")
        request = self.client.messages.create.call_args.kwargs
        self.assertEqual({"type": "none"}, request["tool_choice"])
        self.assertLessEqual(request["timeout"], 8)

    def test_falls_back_to_the_next_configured_provider(self):
        self.client.messages.create.side_effect = RuntimeError("overloaded")
        reply = MagicMock(status_code=200)
        reply.json.return_value = {"choices": [{"message": {"content": "Messi or Ronaldo: it's a debate."}}]}
        statuses = []
        with patch.object(config, "AI_PROVIDER_FALLBACK_CHAIN", ["openrouter"]), \
                patch.object(config, "OPENROUTER_API_KEY", "or-key"), \
                patch.object(config, "OPENROUTER_MODEL_CHAIN", ["some/model"]), \
                patch("requests.post", return_value=reply) as post:
            answer = quick_chat.quick_answer("Who is the GOAT, Messi or Ronaldo?", on_status=statuses.append)
        self.assertEqual("Messi or Ronaldo: it's a debate.", answer["reply"])
        self.assertNotIn("failed", answer)
        self.assertEqual("some/model", post.call_args.kwargs["json"]["model"])
        self.assertIn("Still working on it, trying another AI model", statuses)

    def test_unconfigured_fallbacks_are_skipped(self):
        with patch.object(config, "AI_PROVIDER_FALLBACK_CHAIN", ["openrouter", "gemini"]), \
                patch.object(config, "OPENROUTER_API_KEY", ""), patch.object(config, "GEMINI_API_KEY", ""):
            self.assertEqual(["claude"], quick_chat._providers())

    def test_the_model_hands_excel_work_to_the_agent(self):
        self.client.messages.create.return_value = _block(stop_reason="tool_use", content=[
            _block(type="tool_use", id="h", name="start_excel_task", input={"reason": "Build a budget sheet."})])
        answer = quick_chat.quick_answer("Set up a monthly budget for my family", route=True)
        self.assertEqual({"route": "task", "reason": "Build a budget sheet.", "reply": None, "sources": []}, answer)
        request = self.client.messages.create.call_args.kwargs
        self.assertIn("start_excel_task", [tool["name"] for tool in request["tools"]])
        self.assertNotIn("tool_choice", request)
        self.assertIn("start_excel_task", request["system"])

    def test_the_model_answers_greetings_itself(self):
        self.client.messages.create.return_value = _block(stop_reason="end_turn", content=[
            _block(type="text", text="Hi! What are we working on today?")])
        with patch.object(config, "QUICK_CHAT_WEB_SEARCH", False):
            answer = quick_chat.quick_answer("hello", route=True)
        self.assertEqual(("chat", "Hi! What are we working on today?"), (answer["route"], answer["reply"]))
        tools = self.client.messages.create.call_args.kwargs["tools"]
        self.assertEqual(["start_excel_task"], [tool["name"] for tool in tools])

    def test_excel_conversations_tell_the_model_follow_ups_continue_the_task(self):
        self.client.messages.create.return_value = _block(stop_reason="end_turn", content=[_block(type="text", text="Ok.")])
        quick_chat.quick_answer("make it bold", route=True, excel_context=True)
        self.assertIn("already has Excel work", self.client.messages.create.call_args.kwargs["system"])

    def test_without_a_model_the_wording_rules_route(self):
        self.client.messages.create.side_effect = RuntimeError("down")
        self.assertEqual("task", quick_chat.quick_answer("Sort column B in this sheet", route=True)["route"])
        failed = quick_chat.quick_answer("Who won the match?", route=True)
        self.assertEqual(("chat", True), (failed["route"], failed["failed"]))

    def test_web_search_can_be_disabled(self):
        self.client.messages.create.return_value = _block(stop_reason="end_turn", content=[_block(type="text", text="Hi.")])
        with patch.object(config, "QUICK_CHAT_WEB_SEARCH", False):
            quick_chat.quick_answer("Explain VLOOKUP")
        self.assertNotIn("tools", self.client.messages.create.call_args.kwargs)


class OpenRouterSearchLoopTests(unittest.TestCase):
    def test_tool_call_round_trip(self):
        first = MagicMock(status_code=200)
        first.json.return_value = {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "rate"}'}}]}}]}
        second = MagicMock(status_code=200)
        second.json.return_value = {"choices": [{"message": {"content": "It is 5.25% [1]."}}]}
        with patch.object(config, "AI_PROVIDER", "openrouter"), patch.object(config, "AI_PROVIDER_FALLBACK_CHAIN", []), \
                patch.object(config, "OPENROUTER_API_KEY", "k"), patch.object(config, "OPENROUTER_MODEL_CHAIN", ["m"]), \
                patch.object(config, "QUICK_CHAT_WEB_SEARCH", True), \
                patch("requests.post", side_effect=[first, second]) as post, \
                patch("tools.web.web_search", return_value=SEARCH_HIT):
            answer = quick_chat.quick_answer("What is the policy rate?")
        self.assertEqual("It is 5.25% [1].", answer["reply"])
        self.assertEqual("https://bank.example/rate", answer["sources"][0]["url"])
        messages = post.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(("tool", "c1"), (messages[-1]["role"], messages[-1]["tool_call_id"]))


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
