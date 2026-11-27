"""GPT (OpenAI Responses API) as Xelora's provider: agent turns, chat, relay."""
import copy
import json
import unittest
from unittest.mock import patch

import config
from agent import core, openai_responses as oai, providers


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class _FakeOpenAI:
    """Records every POST /responses payload and replies from a script."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.payloads = []
        self.urls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.urls.append(url)
        self.payloads.append(copy.deepcopy(json))
        reply = self.replies.pop(0)
        return reply(json) if callable(reply) else reply


def _call(name, arguments, call_id):
    return {"type": "function_call", "id": f"fc_{call_id}", "call_id": call_id, "name": name,
            "arguments": json.dumps(arguments), "status": "completed"}


def _text(text):
    return {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


_REASONING = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "opaque"}


def _ok(*items):
    return _Response(200, {"status": "completed", "output": list(items)})


def _gpt_settings():
    return patch.multiple(
        config, OPENAI_API_KEY="sk-test", OPENAI_MODEL_CHAIN=["gpt-main", "gpt-backup"],
        OPENAI_STORE=False, OPENAI_REASONING_EFFORT="", OPENAI_MAX_TOOLS=128,
    )


class ToolCatalogueTests(unittest.TestCase):
    def test_array_without_items_is_given_items(self):
        schema = {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "array"}}}}
        cleaned = oai.openai_schema(schema)
        self.assertIn("items", cleaned["properties"]["rows"]["items"])
        self.assertNotIn("items", schema["properties"]["rows"]["items"], "input schema must not be mutated")

    def test_whole_catalogue_is_valid_for_openai(self):
        tools = providers.build_openai_tools()
        self.assertLessEqual(len(tools), config.OPENAI_MAX_TOOLS)
        names = [tool["name"] for tool in tools]
        self.assertEqual(len(names), len(set(names)))

        def arrays_without_items(node):
            if isinstance(node, dict):
                if node.get("type") == "array" and "items" not in node:
                    return True
                return any(arrays_without_items(value) for value in node.values())
            if isinstance(node, list):
                return any(arrays_without_items(value) for value in node)
            return False

        for tool in tools:
            self.assertEqual("function", tool["type"])
            self.assertEqual("object", tool["parameters"]["type"], tool["name"])
            self.assertFalse(arrays_without_items(tool["parameters"]), tool["name"])

    def test_over_the_limit_mouse_controls_go_first_and_keyboard_stays(self):
        with patch.object(config, "ENABLE_VISUAL_FALLBACK", True):
            full = providers.build_claude_tools()
            limit = len(full) - 5
            with patch.object(config, "OPENAI_MAX_TOOLS", limit):
                task = core.AgentTask("Format the sales sheet.")
                tools = providers.build_openai_tools(task)
        names = {tool["name"] for tool in tools}
        self.assertEqual(limit, len(tools))
        self.assertTrue({"insert_formula", "run_excel_code", "inspect_workbook", "go_to_range",
                         "press_alt", "verify_task_completion"} <= names)
        dropped = {tool["name"] for tool in full} - names
        self.assertTrue(dropped <= providers._OPENAI_DROP_FIRST, dropped)
        self.assertTrue(any("not offered to GPT" in line for line in task.progress_log))


class ConversationReplayTests(unittest.TestCase):
    def test_call_left_unrun_by_a_pause_gets_an_explicit_output(self):
        messages = [
            {"role": "user", "content": "Build the report."},
            {"role": "assistant", "content": {oai.ITEMS_KEY: [_call("inspect_workbook", {}, "c1"),
                                                              _call("create_sheet", {}, "c2")]}},
            {"role": "user", "content": {oai.ITEMS_KEY: [oai.function_call_output("c1", {"verified": True})]}},
            {"role": "user", "content": "Continue."},
        ]
        items = oai.input_items(messages)
        outputs = [item for item in items if item.get("type") == "function_call_output"]
        self.assertEqual(["c1", "c2"], [item["call_id"] for item in outputs])
        self.assertIn("not_executed", outputs[1]["output"])
        # The synthetic output precedes the next user turn.
        self.assertEqual("Continue.", items[-1]["content"])

    def test_orphan_and_duplicate_outputs_are_dropped(self):
        messages = [
            {"role": "user", "content": {oai.ITEMS_KEY: [oai.function_call_output("gone", {})]}},
            {"role": "assistant", "content": {oai.ITEMS_KEY: [_call("read_range", {}, "c1")]}},
            {"role": "user", "content": {oai.ITEMS_KEY: [oai.function_call_output("c1", {"a": 1}),
                                                         oai.function_call_output("c1", {"a": 2})]}},
        ]
        outputs = [item for item in oai.input_items(messages) if item.get("type") == "function_call_output"]
        self.assertEqual([json.dumps({"a": 1})], [item["output"] for item in outputs])

    def test_messages_from_another_provider_become_plain_text(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Earlier Claude turn"}]},
            {"role": "assistant", "content": {"text": "Earlier OpenRouter reply"}},
        ]
        self.assertEqual(
            [{"role": "user", "content": "Earlier Claude turn"},
             {"role": "assistant", "content": "Earlier OpenRouter reply"}],
            oai.input_items(messages),
        )


class AgentTurnTests(unittest.TestCase):
    def test_tool_turn_then_result_is_replayed_faithfully(self):
        task = core.AgentTask("Add a total row to the sales table.")
        fake = _FakeOpenAI(
            _ok(_REASONING, _call("inspect_workbook", {"sheet": "Sales"}, "call_1")),
            _ok(_text("Done: the total row is in place.")),
        )
        with _gpt_settings(), patch("requests.post", fake):
            calls, texts, stop = providers.call_openai(task, "SYSTEM")
            self.assertEqual("tool_use", stop)
            self.assertEqual([{"name": "inspect_workbook", "arguments": {"sheet": "Sales"}, "id": "call_1"}], calls)
            self.assertEqual({"sheet": "Sales"}, providers.tool_input(calls[0]))

            task.active_provider = "openai"
            providers.submit_tool_result(task, calls[0], {"verified": True, "sheets": ["Sales"]})
            calls, texts, stop = providers.call_openai(task, "SYSTEM")

        self.assertEqual(([], ["Done: the total row is in place."], "end_turn"), (calls, texts, stop))
        first, second = fake.payloads
        self.assertTrue(fake.urls[0].endswith("/responses"))
        self.assertEqual("SYSTEM", first["instructions"])
        self.assertEqual("gpt-main", first["model"])
        self.assertIs(False, first["store"])
        self.assertEqual(["reasoning.encrypted_content"], first["include"])
        self.assertEqual("auto", first["tool_choice"])
        self.assertNotIn("temperature", first)
        replay = second["input"]
        self.assertEqual("reasoning", replay[1]["type"])
        self.assertEqual("opaque", replay[1]["encrypted_content"])
        self.assertEqual({"type": "function_call", "call_id": "call_1", "name": "inspect_workbook",
                          "arguments": json.dumps({"sheet": "Sales"})}, replay[2])
        self.assertEqual("function_call_output", replay[3]["type"])
        self.assertEqual("call_1", replay[3]["call_id"])

    def test_core_required_codegen_fallback_is_forced(self):
        task = core.AgentTask("Run Goal Seek on B5.")
        task.pending_codegen_fallback = {"tool_name": "insert_formula"}
        fake = _FakeOpenAI(_ok(_call("run_excel_code", {"code": "result = {}"}, "c1")))
        with _gpt_settings(), patch("requests.post", fake):
            providers.call_openai(task, "SYSTEM")
        self.assertEqual({"type": "function", "name": "run_excel_code"}, fake.payloads[0]["tool_choice"])

    def test_unavailable_model_falls_through_to_the_next(self):
        task = core.AgentTask("Sort the data.")
        fake = _FakeOpenAI(
            _Response(404, {"error": {"message": "The model does not exist", "code": "model_not_found"}}),
            _ok(_text("Sorted.")),
        )
        with _gpt_settings(), patch("requests.post", fake):
            _, texts, _ = providers.call_openai(task, "SYSTEM")
        self.assertEqual(["Sorted."], texts)
        self.assertEqual(["gpt-main", "gpt-backup"], [payload["model"] for payload in fake.payloads])

    def test_bad_key_stops_with_a_clear_reason_instead_of_trying_models(self):
        task = core.AgentTask("Sort the data.")
        fake = _FakeOpenAI(_Response(401, {"error": {"message": "Incorrect API key", "code": "invalid_api_key"}}))
        with _gpt_settings(), patch("requests.post", fake):
            with self.assertRaisesRegex(oai.OpenAIError, "OPENAI_API_KEY"):
                providers.call_openai(task, "SYSTEM")
        self.assertEqual(1, len(fake.payloads))

    def test_rate_limit_on_every_model_hands_off_to_the_fallback_provider(self):
        task = core.AgentTask("Sort the data.")
        limited = _Response(429, {"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}})
        with _gpt_settings(), patch("requests.post", _FakeOpenAI(limited, limited)):
            with self.assertRaises(oai.OpenAIError) as raised:
                providers.call_openai(task, "SYSTEM")
        self.assertTrue(providers._is_provider_availability_failure(raised.exception))

    def test_unsupported_reasoning_setting_is_dropped_not_fatal(self):
        task = core.AgentTask("Sort the data.")
        fake = _FakeOpenAI(
            _Response(400, {"error": {"message": "Unsupported parameter: 'reasoning.effort' is not supported with this model.",
                                      "param": "reasoning.effort", "code": "unsupported_parameter"}}),
            _ok(_text("Sorted.")),
        )
        with _gpt_settings(), patch.object(config, "OPENAI_REASONING_EFFORT", "high"), patch("requests.post", fake):
            _, texts, _ = providers.call_openai(task, "SYSTEM")
        self.assertEqual(["Sorted."], texts)
        self.assertIn("reasoning", fake.payloads[0])
        self.assertNotIn("reasoning", fake.payloads[1])

    def test_empty_reply_is_never_a_completion(self):
        task = core.AgentTask("Create a workbook.")
        empty = _Response(200, {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                                "output": [_REASONING]})
        with _gpt_settings(), patch("requests.post", _FakeOpenAI(empty, empty)):
            with self.assertRaisesRegex(RuntimeError, "max_output_tokens"):
                providers.call_openai(task, "SYSTEM")

    def test_openai_is_a_first_class_provider(self):
        task = core.AgentTask("Sort the data.")
        task.active_provider = "openai"
        self.assertEqual("openai", providers.active_provider_name(task))
        with patch.multiple(config, EXCEL_TASK_PROVIDER="openai", OPENAI_API_KEY="sk-test"):
            self.assertEqual("openai", providers.task_provider())
        with patch.multiple(config, AI_PROVIDER="openai", OPENAI_API_KEY=""):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                config.validate_ai_provider_configuration()
        with patch.multiple(config, AI_PROVIDER="openai", OPENAI_API_KEY="sk-test"):
            config.validate_ai_provider_configuration()

    def test_gemini_outage_can_fail_over_to_gpt(self):
        task = core.AgentTask("Sort the data.")
        task.active_provider = "gemini"
        with patch.multiple(config, OPENAI_API_KEY="sk-test", AI_PROVIDER_FALLBACK_CHAIN=["openai"]):
            self.assertTrue(providers.activate_available_provider_fallback(task, TimeoutError("timed out")))
        self.assertEqual("openai", task.active_provider)


class QuickChatTests(unittest.TestCase):
    def _answer(self, fake, instruction="What does XLOOKUP do?", **kwargs):
        import quick_chat

        with _gpt_settings(), patch.multiple(config, AI_PROVIDER="openai", AI_PROVIDER_FALLBACK_CHAIN=[],
                                              QUICK_CHAT_OPENAI_MODEL="gpt-chat", QUICK_CHAT_WEB_SEARCH=False), \
                patch("requests.post", fake):
            return quick_chat.quick_answer(instruction, [], **kwargs)

    def test_question_is_answered_by_gpt(self):
        fake = _FakeOpenAI(_ok(_text("XLOOKUP finds a value in a range.")))
        answer = self._answer(fake)
        self.assertEqual("chat", answer["route"])
        self.assertEqual("XLOOKUP finds a value in a range.", answer["reply"])
        self.assertEqual("gpt-chat", fake.payloads[0]["model"])
        self.assertEqual({"effort": "low"}, fake.payloads[0]["reasoning"])

    def test_gpt_decides_to_hand_excel_work_to_the_agent(self):
        import quick_chat

        fake = _FakeOpenAI(_ok(_call(quick_chat._HANDOFF, {"reason": "This changes the workbook."}, "c1")))
        answer = self._answer(fake, "Can you tidy up my budget sheet?", route=True)
        self.assertEqual("task", answer["route"])
        self.assertIsNone(answer["reply"])
        self.assertEqual(1, len(fake.payloads), "GPT, not a wording rule, made the routing decision")
        self.assertIn(quick_chat._HANDOFF, [tool["name"] for tool in fake.payloads[0]["tools"]])


class RelayTests(unittest.TestCase):
    def test_desktop_agent_reaches_gpt_through_the_relay(self):
        import agent_link
        import local_agent

        base, path_rule = agent_link._UPSTREAMS["openai"]
        self.assertEqual("https://api.openai.com/", base)
        self.assertTrue(path_rule.match("v1/responses"))
        self.assertFalse(path_rule.match("v1/files"))
        with patch.object(config, "OPENAI_API_KEY", "sk-server"):
            self.assertEqual("sk-server", agent_link._server_key("openai"))
            self.assertIn("openai", agent_link.configured_providers())
        with patch.dict("os.environ", {}, clear=False):
            local_agent.configure_environment("https://api.example.com", "xa_token")
            import os
            self.assertEqual("https://api.example.com/agent-link/llm/openai/v1", os.environ["OPENAI_BASE_URL"])
            self.assertEqual("xa_token", os.environ["OPENAI_API_KEY"])


if __name__ == "__main__":
    unittest.main()
