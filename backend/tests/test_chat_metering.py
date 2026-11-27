"""Quick chat answers count against each plan's ai_actions_per_month (server.py)."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("LOCAL_API_KEY", "test-api-key")

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
import main  # noqa: E402
import plan_guard  # noqa: E402
from auth import create_token  # noqa: E402

USER = 71
ANSWER = {"route": "chat", "reply": "XLOOKUP finds a value.", "sources": []}


class ChatMeteringTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        import auth_billing_models  # noqa: F401
        import database
        import models  # noqa: F401
        from database import Base

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
        answer_patch = patch("quick_chat.quick_answer", side_effect=lambda *a, **k: dict(ANSWER))
        self.quick_answer = answer_patch.start()
        self.addCleanup(answer_patch.stop)
        for item in (patch.object(config, "LOCAL_API_KEY", "test-api-key"),
                     patch.object(database, "SessionLocal", self.Session),
                     patch.dict(main.ACTIVE_TASKS, clear=True),
                     patch.dict(os.environ, {"SKIP_BILLING_CHECKS": "false"}),
                     patch.object(main, "chat_usage_guard", plan_guard.ChatUsageGuard())):
            item.start()
            self.addCleanup(item.stop)
        self.client = TestClient(main.app)

    def _subscribe(self, used=0, tier="trial", status="trialing"):
        from auth_billing_models import Subscription, UsageRecord

        db = self.Session()
        sub = Subscription(user_id=USER, plan_tier=tier, status=status)
        db.add(sub)
        db.commit()
        record = plan_guard._get_or_create_usage(db, USER, sub)
        record.ai_actions_used = used
        db.commit()
        db.close()
        return UsageRecord

    def _used(self):
        from auth_billing_models import UsageRecord

        db = self.Session()
        try:
            return db.query(UsageRecord).filter(UsageRecord.user_id == USER).one().ai_actions_used
        finally:
            db.close()

    def chat(self, path="/chat"):
        response = self.client.post(path, json={"instruction": "What does XLOOKUP do?"},
                                    headers={"X-API-Key": "test-api-key",
                                             "Authorization": f"Bearer {create_token(USER)[0]}"})
        self.assertEqual(200, response.status_code, response.text)
        return response

    def test_answer_counts_as_one_ai_action(self):
        self._subscribe(used=3)
        self.assertEqual("XLOOKUP finds a value.", self.chat().json()["reply"])
        self.assertEqual(4, self._used())

    def test_exhausted_allowance_explains_instead_of_calling_the_model(self):
        self._subscribe(used=30)  # trial plan: 30 AI actions
        body = self.chat().json()
        self.assertTrue(body["limit_reached"])
        self.assertIn("30 AI actions", body["reply"])
        self.quick_answer.assert_not_called()
        self.assertEqual(30, self._used())

    def test_streamed_chat_is_metered_too(self):
        self._subscribe(used=30)
        lines = self.chat("/chat/stream").text.strip().splitlines()
        self.assertIn("30 AI actions", lines[-1])
        self.quick_answer.assert_not_called()

    def test_hand_off_to_excel_is_not_counted_twice(self):
        self._subscribe(used=3)
        self.quick_answer.side_effect = lambda *a, **k: {"route": "task", "reason": "Workbook work."}
        self.assertEqual("task", self.chat().json()["route"])
        self.assertEqual(3, self._used(), "the Excel task itself is metered by POST /task")

    def test_unlimited_plan_is_never_blocked(self):
        self._subscribe(used=10_000, tier="business", status="active")
        self.assertEqual("XLOOKUP finds a value.", self.chat().json()["reply"])


if __name__ == "__main__":
    unittest.main()
