"""Password reset, email verification, profile and password changes (auth.py)."""
import os
import re
import unittest
from unittest.mock import patch

os.environ.setdefault("LOCAL_API_KEY", "test-api-key")

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
import database  # noqa: E402
import server  # noqa: E402


class AccountAuthTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from database import Base
        import auth_billing_models  # noqa: F401
        import models  # noqa: F401
        import workspace_models  # noqa: F401

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.sent = []
        for item in (patch.object(auth, "SessionLocal", Session), patch.object(database, "SessionLocal", Session),
                     patch("emailer.send_email", side_effect=lambda to, subject, heading, paragraphs, button=None:
                           self.sent.append((to, subject, button)) or True),
                     patch("emailer.configured", return_value=True)):
            item.start()
            self.addCleanup(item.stop)
        self.client = TestClient(server.app)

    def register(self, email="ana@example.com", password="first-password"):
        response = self.client.post("/auth/register", json={"name": "Ana", "email": email, "password": password})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def token_from(self, link):
        return re.search(r"token=([^&]+)", link).group(1)

    def test_registration_sends_a_verification_link_that_verifies(self):
        session = self.register()
        self.assertFalse(session["user"]["isVerified"])
        self.assertTrue(session["user"]["hasPassword"])
        to, subject, (label, link) = self.sent[-1]
        self.assertEqual("ana@example.com", to)
        self.assertIn("/verify-email?token=", link)
        self.assertEqual(200, self.client.post("/auth/verify-email", json={"token": self.token_from(link)}).status_code)
        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {session['token']}"}).json()
        self.assertTrue(me["isVerified"])

    def test_reset_link_sets_a_new_password_and_works_only_once(self):
        self.register()
        self.assertEqual({"sent": True}, self.client.post("/auth/forgot-password", json={"email": "ANA@example.com"}).json())
        token = self.token_from(self.sent[-1][2][1])
        self.assertEqual(200, self.client.post("/auth/reset-password", json={"token": token, "password": "second-password"}).status_code)
        self.assertEqual(401, self.client.post("/auth/login", json={"email": "ana@example.com", "password": "first-password"}).status_code)
        self.assertEqual(200, self.client.post("/auth/login", json={"email": "ana@example.com", "password": "second-password"}).status_code)
        again = self.client.post("/auth/reset-password", json={"token": token, "password": "third-password"})
        self.assertEqual(400, again.status_code)

    def test_forgot_password_does_not_reveal_unknown_emails(self):
        response = self.client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
        self.assertEqual({"sent": True}, response.json())
        self.assertEqual([], self.sent)

    def test_tokens_cannot_be_swapped_between_purposes(self):
        session = self.register()
        verify_token = self.token_from(self.sent[-1][2][1])
        self.assertEqual(400, self.client.post("/auth/reset-password", json={"token": verify_token, "password": "x" * 10}).status_code)
        self.assertEqual(400, self.client.post("/auth/verify-email", json={"token": session["token"]}).status_code)

    def test_profile_and_password_changes(self):
        session = self.register()
        headers = {"Authorization": f"Bearer {session['token']}"}
        self.assertEqual("Ana Lopez", self.client.patch("/auth/me", json={"name": "Ana Lopez"}, headers=headers).json()["name"])
        wrong = self.client.post("/auth/change-password", json={"current_password": "nope", "new_password": "new-password-1"}, headers=headers)
        self.assertEqual(400, wrong.status_code)
        ok = self.client.post("/auth/change-password", json={"current_password": "first-password", "new_password": "new-password-1"}, headers=headers)
        self.assertEqual(200, ok.status_code)

    def test_google_only_accounts_can_set_a_password_and_cannot_log_in_without_one(self):
        from oauth import _get_or_create_user

        db = auth.SessionLocal()
        try:
            user, _ = _get_or_create_user(db, "g@example.com", "G User")
            user_id = user.id
        finally:
            db.close()
        self.assertEqual(401, self.client.post("/auth/login", json={"email": "g@example.com", "password": "anything-1"}).status_code)
        headers = {"Authorization": f"Bearer {auth.create_token(user_id)[0]}"}
        self.assertFalse(self.client.get("/auth/me", headers=headers).json()["hasPassword"])
        self.assertEqual(200, self.client.post("/auth/change-password", json={"new_password": "now-has-one"}, headers=headers).status_code)
        self.assertEqual(200, self.client.post("/auth/login", json={"email": "g@example.com", "password": "now-has-one"}).status_code)


if __name__ == "__main__":
    unittest.main()
