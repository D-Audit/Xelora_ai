"""Quick answers are saved to chat history and carry into later Excel requests (main.py)."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("LOCAL_API_KEY", "test-api-key")

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
import main  # noqa: E402
from auth import create_token  # noqa: E402

USER, OTHER = 61, 62
ANSWER = {"reply": "It is 1.08 [1].", "sources": [{"n": 1, "title": "ECB", "url": "https://ecb.example"}]}


class ChatHistoryTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from database import Base
        import models  # noqa: F401

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

        def session():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main._get_db_optional] = session
        self.addCleanup(main.app.dependency_overrides.clear)
        import database
        for item in (patch.object(config, "LOCAL_API_KEY", "test-api-key"),
                     patch.object(database, "SessionLocal", self.Session),
                     patch.dict(main.ACTIVE_TASKS, clear=True),
                     patch("quick_chat.quick_answer", return_value=dict(ANSWER))):
            item.start()
            self.addCleanup(item.stop)
        self.client = TestClient(main.app)

    def headers(self, user=USER):
        return {"X-API-Key": "test-api-key", "Authorization": f"Bearer {create_token(user)[0]}"}

    def chat(self, text, task_id=None, user=USER):
        response = self.client.post("/chat", json={"instruction": text, "task_id": task_id}, headers=self.headers(user))
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def test_first_question_starts_a_saved_conversation(self):
        body = self.chat("What is the EUR/USD rate today?")
        self.assertIsNotNone(body["task_id"])
        listed = self.client.get("/tasks", headers=self.headers()).json()
        self.assertEqual(["What is the EUR/USD rate today?"], [t["title"] for t in listed])
        detail = self.client.get(f"/tasks/{body['task_id']}", headers=self.headers()).json()
        self.assertEqual(["user", "assistant"], [t["role"] for t in detail["transcript"]])
        self.assertEqual(ANSWER["sources"], detail["transcript"][1]["sources"])
        self.assertEqual("chat", detail["transcript"][1]["kind"])
        self.assertTrue(detail["resumable"])

    def test_follow_up_questions_append_to_the_same_conversation(self):
        first = self.chat("What is the EUR/USD rate today?")["task_id"]
        second = self.chat("And GBP/USD?", task_id=first)["task_id"]
        self.assertEqual(first, second)
        detail = self.client.get(f"/tasks/{first}", headers=self.headers()).json()
        self.assertEqual(4, len(detail["transcript"]))
        self.assertEqual(1, len(self.client.get("/tasks", headers=self.headers()).json()))

    def test_cannot_write_into_another_users_conversation(self):
        mine = self.chat("Question")["task_id"]
        response = self.client.post("/chat", json={"instruction": "Hijack?", "task_id": mine},
                                    headers=self.headers(OTHER))
        self.assertEqual(403, response.status_code)

    def test_live_task_transcript_stays_in_step(self):
        from agent.core import AgentTask

        conversation = self.chat("Question")["task_id"]
        live = AgentTask("Question", user_id=USER)
        live.is_done = True
        main.ACTIVE_TASKS[conversation] = live
        self.chat("Another question?", task_id=conversation)
        self.assertEqual("Another question?", live.chat_transcript[-2]["text"])

    def test_excel_request_after_quick_answers_continues_with_their_context(self):
        conversation = self.chat("What is the EUR/USD rate today?")["task_id"]
        with patch.object(main, "_start_task_in_background") as start:
            response = self.client.post(f"/task/{conversation}/resume", json={"correction": "Put that rate in cell B2"},
                                        headers=self.headers())
        self.assertEqual(200, response.status_code, response.text)
        task = start.call_args.args[0]
        self.assertEqual("Put that rate in cell B2", task.instruction)
        prompt = task.messages[0]["content"]
        self.assertIn("It is 1.08 [1].", prompt)
        self.assertTrue(prompt.endswith("Current request: Put that rate in cell B2"))

    def test_api_key_only_callers_are_not_saved(self):
        response = self.client.post("/chat", json={"instruction": "What is VAT?"}, headers={"X-API-Key": "test-api-key"})
        self.assertIsNone(response.json()["task_id"])


class DirectAnswerTests(ChatHistoryTests):
    """Messages sent straight to /task (older clients, the API) are answered without Excel when they can be."""

    def start(self, text):
        with patch.object(main, "run_task") as run, patch.object(main.agent_link, "dispatch") as dispatch:
            response = self.client.post("/task", json={"instruction": text}, headers=self.headers())
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["task_id"], run, dispatch

    def test_greeting_is_answered_without_excel_or_the_desktop(self):
        task_id, run, dispatch = self.start("hi")
        run.assert_not_called()
        dispatch.assert_not_called()
        progress = self.client.get(f"/task/{task_id}/progress", headers=self.headers()).json()
        self.assertEqual("answered", progress["status"])
        self.assertEqual(ANSWER["reply"], progress["final_response"])
        self.assertEqual(ANSWER["sources"], progress["sources"])
        detail = self.client.get(f"/tasks/{task_id}", headers=self.headers()).json()
        self.assertEqual("answered", detail["status"])
        self.assertEqual(["chat", "chat"], [turn.get("kind") for turn in detail["transcript"]])

    def test_workbook_request_still_runs_the_agent(self):
        from agent.core import AgentTask

        with patch("quick_chat.quick_answer") as answer:
            self.assertFalse(main._answer_directly(AgentTask("Sort column B in my sheet", user_id=USER), 1, USER))
        answer.assert_not_called()

    def test_reply_to_the_agents_question_goes_to_the_agent(self):
        from agent.core import AgentTask

        task_id = self.chat("Question")["task_id"]
        live = AgentTask("Add a totals row", user_id=USER)
        live.chat_transcript.append({"role": "assistant", "text": "Which sheet?"})
        live.is_done = True
        main.ACTIVE_TASKS[task_id] = live
        with patch.object(main, "_start_task_in_background") as start:
            self.client.post(f"/task/{task_id}/resume", json={"correction": "Use the Sales sheet"}, headers=self.headers())
        with patch("quick_chat.quick_answer") as answer:
            self.assertFalse(main._answer_directly(start.call_args.args[0], task_id, USER))
        answer.assert_not_called()
        routed = self.client.post("/chat", json={"instruction": "Use the Sales sheet", "task_id": task_id},
                                  headers=self.headers()).json()
        self.assertEqual("task", routed["route"])

    def test_confirming_a_plan_is_never_answered_directly(self):
        from agent.core import AgentTask

        task_id = self.chat("Question")["task_id"]
        live = AgentTask("Delete the empty rows", user_id=USER)
        live.awaiting_approval = True
        live.is_done = True
        main.ACTIVE_TASKS[task_id] = live
        with patch.object(main, "_start_task_in_background") as start:
            self.client.post(f"/task/{task_id}/resume", json={"correction": "Confirm"}, headers=self.headers())
        self.assertFalse(start.call_args.kwargs["allow_direct_answer"])


class ConversationContextTests(unittest.TestCase):
    def test_follow_up_carries_the_recent_conversation(self):
        from agent.core import AgentTask

        task = AgentTask("Add a totals row to the Sales sheet", user_id=USER)
        task.chat_transcript.append({"role": "assistant", "text": "Added the totals row in row 14."})
        task.is_done = True
        task.resume(correction="Now make it bold")
        prompt = task.messages[0]["content"]
        self.assertIn("User: Add a totals row to the Sales sheet", prompt)
        self.assertIn("Xelora: Added the totals row in row 14.", prompt)
        self.assertTrue(prompt.endswith("Current request: Now make it bold"))
        self.assertEqual("Now make it bold", task.instruction)

    def test_context_is_bounded(self):
        from agent.core import conversation_context

        transcript = [{"role": "user", "text": f"message {i} " + "x" * 2000} for i in range(30)]
        context = conversation_context(transcript)
        self.assertNotIn("message 0 ", context)
        self.assertIn("message 29 ", context)
        self.assertLess(len(context), 8 * 800)
        self.assertEqual("", conversation_context([]))


class WorkbookGateTests(unittest.TestCase):
    def test_excel_opens_only_for_workbook_work(self):
        from agent.core import AgentTask, _route_needs_workbook

        self.assertFalse(_route_needs_workbook(AgentTask("Research the latest inflation rate in Rwanda")))
        self.assertTrue(_route_needs_workbook(AgentTask("Add a SUM formula to column D")))
        self.assertTrue(_route_needs_workbook(AgentTask("Build a sales dashboard")))


if __name__ == "__main__":
    unittest.main()
