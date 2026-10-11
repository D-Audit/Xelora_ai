"""Cloud <-> desktop local agent relay (agent_link.py + local_agent.py).

The cloud side is the real FastAPI app (server:app through TestClient) and
the agent side is the real local_agent job loop talking to it over those
routes. Only the Excel work (run_task) and the agent token store are faked.
"""
from __future__ import annotations

import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("LOCAL_API_KEY", "test-api-key")

from fastapi.testclient import TestClient  # noqa: E402

import agent_link  # noqa: E402
import config  # noqa: E402
import local_agent  # noqa: E402
import main  # noqa: E402
import server  # noqa: E402
from agent.core import AgentTask  # noqa: E402
from auth import create_token  # noqa: E402

USER = 41
OTHER_USER = 42
TOKENS = {"xa_user": USER, "xa_other": OTHER_USER}


def _verified_step(text="Wrote the totals row"):
    return {"type": "action", "tool_name": "write_range", "status": "success",
            "input": {"range": "A1"}, "result": {"verified": True, "message": text}}


class AgentLinkCase(unittest.TestCase):
    def setUp(self):
        patches = [
            patch.object(config, "TASK_EXECUTION", "agent"),
            patch.object(config, "LOCAL_API_KEY", "test-api-key"),
            patch.object(config, "GEMINI_API_KEY", "server-gemini-key"),
            patch.object(config, "AI_PROVIDER", "gemini"),
            patch.object(agent_link, "user_for_token", side_effect=lambda token: TOKENS.get(token)),
            patch.dict(main.ACTIVE_TASKS, clear=True),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        for store in (agent_link._queues, agent_link._jobs, agent_link._last_poll, agent_link._running):
            store.clear()
        self.client = TestClient(server.app)
        self.jwt = create_token(USER)[0]
        self.web_headers = {"X-API-Key": "test-api-key", "Authorization": f"Bearer {self.jwt}"}
        self.cloud = local_agent.CloudClient("http://testserver", "xa_user", http=self.client)

    def start_task(self, instruction="Add a totals row", task_id=7, user_id=USER):
        task = AgentTask(instruction, user_id=user_id)
        task.has_authenticated_user = True
        main.ACTIVE_TASKS[task_id] = task
        main._start_task_in_background(task, task_id, user_id, {})
        return task

    def progress(self, task_id=7):
        response = self.client.get(f"/task/{task_id}/progress", headers=self.web_headers)
        self.assertEqual(200, response.status_code, response.text)
        return response.json()


class DispatchTests(AgentLinkCase):
    def test_server_mode_keeps_running_tasks_in_process(self):
        with patch.object(config, "TASK_EXECUTION", "server"):
            task = AgentTask("x", user_id=USER)
            task.has_authenticated_user = True
            self.assertFalse(agent_link.routes_to_agent(task))

    def test_api_key_only_tasks_are_not_routed(self):
        task = AgentTask("x", user_id=USER)
        self.assertFalse(agent_link.routes_to_agent(task))

    def test_task_waits_visibly_until_an_agent_claims_it(self):
        self.start_task()
        snapshot = self.progress()
        self.assertEqual("running", snapshot["status"])
        self.assertEqual("waiting_for_agent", main.ACTIVE_TASKS[7].recovery_state["phase"])

        job = self.cloud.claim(wait=0)
        self.assertEqual(7, job["task_id"])
        self.assertEqual("Add a totals row", job["state"]["instruction"])
        self.assertEqual(["gemini"], job["providers"])
        self.assertIsNone(main.ACTIVE_TASKS[7].recovery_state)

    def test_agent_only_sees_its_own_users_jobs(self):
        self.start_task(task_id=8, user_id=OTHER_USER)
        self.assertIsNone(self.cloud.claim(wait=0))

    def test_unknown_token_is_rejected(self):
        bad = local_agent.CloudClient("http://testserver", "xa_nope", http=self.client)
        with self.assertRaises(local_agent.TokenRejected):
            bad.claim(wait=0)

    def test_agent_status_reports_online_after_a_poll(self):
        headers = {"Authorization": f"Bearer {self.jwt}"}
        self.assertFalse(self.client.get("/agent-link/status", headers=headers).json()["online"])
        self.cloud.claim(wait=0)
        self.assertTrue(self.client.get("/agent-link/status", headers=headers).json()["online"])


class RunJobTests(AgentLinkCase):
    def test_completed_run_is_mirrored_to_the_web_endpoints(self):
        self.start_task()
        seen = {}

        def fake_run(task, db=None, db_task_id=None, user_preferences=None):
            seen["auth_files"] = task.has_authenticated_user
            seen["provider"] = config.AI_PROVIDER
            task.structured_steps.append(_verified_step())
            task.final_response = "Added the totals row in A1."
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})
            task.is_done = True

        local_agent.run_job(self.cloud.claim(wait=0), self.cloud, run=fake_run, log=lambda _m: None)

        self.assertFalse(seen["auth_files"])  # cloud-only file tools stay off locally
        self.assertEqual("gemini", seen["provider"])
        snapshot = self.progress()
        self.assertEqual("completed", snapshot["status"])
        self.assertEqual("Added the totals row in A1.", snapshot["final_response"])
        status = self.client.get("/task/7/status", headers=self.web_headers).json()
        self.assertTrue(status["is_done"])
        self.assertEqual({}, agent_link._jobs)
        self.assertEqual(0, agent_link._running[USER])

    def test_crash_in_run_task_reports_incomplete(self):
        self.start_task()

        def boom(task, **_kwargs):
            raise RuntimeError("Excel is not running")

        local_agent.run_job(self.cloud.claim(wait=0), self.cloud, run=boom, log=lambda _m: None)
        self.assertIn("INCOMPLETE", main.ACTIVE_TASKS[7].final_response)
        self.assertIn("Excel is not running", main.ACTIVE_TASKS[7].final_response)

    def test_pause_from_web_ui_stops_the_local_run(self):
        self.start_task()
        started = threading.Event()

        def slow_run(task, **_kwargs):
            task.structured_steps.append(_verified_step("first step"))
            started.set()
            deadline = time.monotonic() + 10
            while not task.is_paused and time.monotonic() < deadline:
                time.sleep(0.05)

        job = self.cloud.claim(wait=0)
        runner = threading.Thread(target=local_agent.run_job, args=(job, self.cloud),
                                  kwargs={"run": slow_run, "log": lambda _m: None})
        runner.start()
        self.assertTrue(started.wait(5))
        response = self.client.post("/task/7/pause", headers=self.web_headers)
        self.assertEqual(200, response.status_code, response.text)
        runner.join(10)
        self.assertFalse(runner.is_alive(), "agent did not honour the pause")
        self.assertEqual("paused", self.progress()["status"])

    def test_resume_redispatches_with_the_conversation(self):
        self.start_task()

        def answer(task, **_kwargs):
            task.final_response = "Which sheet?"
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})
            task.messages.append({"role": "assistant", "content": "Which sheet?"})
            task.is_done = True

        local_agent.run_job(self.cloud.claim(wait=0), self.cloud, run=answer, log=lambda _m: None)
        response = self.client.post("/task/7/resume", json={"correction": "Use the Sales sheet"},
                                    headers=self.web_headers)
        self.assertEqual(200, response.status_code, response.text)

        job = self.cloud.claim(wait=0)
        texts = [entry.get("text") for entry in job["state"]["chat_transcript"]]
        self.assertIn("Which sheet?", texts)
        self.assertIn("Use the Sales sheet", texts)
        self.assertTrue(job["state"]["has_authenticated_user"])  # agent's local override stays local

    def test_push_after_cloud_restart_rebuilds_the_mirror(self):
        with agent_link._cond:
            agent_link._jobs[9] = {"user_id": USER, "pause_requested": False, "claimed": True}
            agent_link._running[USER] = 1
        state = agent_link.export_state(AgentTask("Format the header", user_id=USER))
        state["final_response"] = "Done."
        state["is_done"] = True
        self.cloud.push(9, state, final=True)
        self.assertEqual("Format the header", main.ACTIVE_TASKS[9].instruction)
        self.assertEqual(USER, main.ACTIVE_TASKS[9].user_id)

    def test_another_users_agent_cannot_push_into_a_task(self):
        self.start_task()
        self.cloud.claim(wait=0)
        other = local_agent.CloudClient("http://testserver", "xa_other", http=self.client)
        response = self.client.post("/agent-link/tasks/7/push", json={"state": {"final_response": "x"}},
                                    headers=other.headers)
        self.assertEqual(403, response.status_code)

    def test_deleted_queued_task_is_never_claimed(self):
        self.start_task()
        agent_link.forget(7)
        self.assertIsNone(self.cloud.claim(wait=0))


class StateTests(unittest.TestCase):
    def test_sets_of_tuples_round_trip(self):
        task = AgentTask("x", user_id=USER)
        task.cua_observed_targets = {(4242, 7)}
        task.successful_action_signatures = {"a", "b"}
        copy = AgentTask("y", user_id=USER)
        agent_link.apply_state(copy, agent_link.export_state(task))
        self.assertEqual({(4242, 7)}, copy.cua_observed_targets)
        self.assertEqual({"a", "b"}, copy.successful_action_signatures)
        self.assertEqual("x", copy.instruction)

    def test_live_objects_are_not_exported(self):
        task = AgentTask("x", user_id=USER)
        task.progress_callback = lambda _message: None
        task.excel_app_pid = 1234
        state = agent_link.export_state(task)
        self.assertNotIn("progress_callback", state)
        self.assertNotIn("excel_app_pid", state)


class RelayTests(AgentLinkCase):
    def relay(self, path="gemini/v1beta/models/gemini-2.5-flash:generateContent", token="xa_user"):
        return self.client.post(f"/agent-link/llm/{path}", content=b'{"contents": []}',
                                headers={"x-goog-api-key": token, "content-type": "application/json"})

    def test_relay_refuses_when_no_task_is_running(self):
        self.assertEqual(403, self.relay().status_code)

    def test_relay_forwards_with_the_server_key(self):
        self.start_task()
        self.cloud.claim(wait=0)
        upstream = MagicMock(status_code=200, content=b'{"candidates": []}', headers={"content-type": "application/json"})
        with patch.object(agent_link.requests, "post", return_value=upstream) as post:
            response = self.relay()
        self.assertEqual(200, response.status_code)
        url = post.call_args.args[0]
        headers = post.call_args.kwargs["headers"]
        self.assertEqual("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", url)
        self.assertEqual("server-gemini-key", headers["x-goog-api-key"])
        self.assertNotIn("xa_user", str(headers))

    def test_relay_only_serves_generation_endpoints(self):
        self.start_task()
        self.cloud.claim(wait=0)
        self.assertEqual(404, self.relay(path="gemini/v1beta/files").status_code)
        self.assertEqual(404, self.relay(path="evil/v1/messages").status_code)

    def test_relay_rejects_unknown_tokens(self):
        self.start_task()
        self.cloud.claim(wait=0)
        self.assertEqual(401, self.relay(token="xa_nope").status_code)


class PairTests(AgentLinkCase):
    def test_pair_returns_the_public_https_origin_behind_a_proxy(self):
        with patch.object(agent_link, "create_token", return_value=(5, "xa_new")), \
                patch.object(config, "PUBLIC_API_URL", ""):
            response = self.client.post(
                "/agent-link/pair", json={"name": "Office PC"},
                headers={"Authorization": f"Bearer {self.jwt}", "x-forwarded-proto": "https",
                         "host": "xelora-api.onrender.com"},
            )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual({"token": "xa_new", "token_id": 5, "api_url": "https://xelora-api.onrender.com"}, response.json())

    def test_pair_requires_a_signed_in_user(self):
        self.assertEqual(401, self.client.post("/agent-link/pair", json={}).status_code)


class TokenStoreTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        agent_link.AgentToken.__table__.create(engine)
        factory = patch.object(agent_link.database, "SessionLocal", sessionmaker(bind=engine))
        factory.start()
        self.addCleanup(factory.stop)
        self.factory = agent_link.database.SessionLocal

    def test_tokens_are_stored_hashed_and_can_be_revoked(self):
        token_id, token = agent_link.create_token(USER, "Office PC")
        self.assertTrue(token.startswith("xa_"))
        self.assertEqual(USER, agent_link.user_for_token(token))
        self.assertIsNone(agent_link.user_for_token(token + "x"))
        db = self.factory()
        row = db.get(agent_link.AgentToken, token_id)
        self.assertNotEqual(token, row.token_hash)
        row.revoked = True
        db.commit()
        db.close()
        self.assertIsNone(agent_link.user_for_token(token))


class ScheduledRunTests(unittest.TestCase):
    def test_scheduled_run_submits_as_the_schedule_owner(self):
        import automation
        from auth import decode_token

        schedule = MagicMock(workflow_id=3, user_id=USER)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        reply = MagicMock(ok=True, status_code=200)
        reply.json.return_value = {"task_id": 12}
        with patch("database.SessionLocal", return_value=db), \
                patch("workflows._instruction_from_steps", return_value="Refresh the report"), \
                patch.object(automation.requests, "post", return_value=reply) as post:
            result = automation._submit_scheduled_run(schedule)
        self.assertEqual({"submitted": True, "task_id": 12}, result)
        bearer = post.call_args.kwargs["headers"]["Authorization"].removeprefix("Bearer ")
        self.assertEqual(USER, decode_token(bearer))


class ConfigureEnvironmentTests(unittest.TestCase):
    def test_agent_points_every_provider_at_the_relay(self):
        with patch.dict(os.environ, {}, clear=False):
            local_agent.configure_environment("https://api.example.com/", "xa_tok")
            self.assertEqual("https://api.example.com/agent-link/llm/gemini", os.environ["GEMINI_BASE_URL"])
            self.assertEqual("https://api.example.com/agent-link/llm/anthropic", os.environ["ANTHROPIC_BASE_URL"])
            self.assertEqual("xa_tok", os.environ["GEMINI_API_KEY"])
            self.assertEqual("server", os.environ["TASK_EXECUTION"])
            self.assertEqual("", os.environ["DATABASE_URL"])


if __name__ == "__main__":
    unittest.main()
