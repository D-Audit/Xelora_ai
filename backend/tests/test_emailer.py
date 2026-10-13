"""Transactional email through Brevo's API."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import emailer


class BrevoEmailTests(unittest.TestCase):
    def _send(self, status=201, body="{}"):
        response = MagicMock(status_code=status, text=body)
        with patch.object(emailer, "BREVO_API_KEY", "xkeysib-test"), \
                patch.object(emailer, "SMTP_HOST", ""), \
                patch.object(emailer, "EMAIL_FROM", "Xelora <no-reply@example.com>"), \
                patch("emailer.requests.post", return_value=response) as post:
            sent = emailer.send_email("user@example.com", "Reset your password", "Reset",
                                      ["Use the link below."], ("Reset password", "https://x/reset?t=1"))
        return sent, post

    def test_sends_through_brevo_with_parsed_sender(self):
        sent, post = self._send()
        self.assertTrue(sent)
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertEqual("https://api.brevo.com/v3/smtp/email", url)
        self.assertEqual("xkeysib-test", post.call_args.kwargs["headers"]["api-key"])
        self.assertEqual({"name": "Xelora", "email": "no-reply@example.com"}, payload["sender"])
        self.assertEqual([{"email": "user@example.com"}], payload["to"])
        self.assertIn("https://x/reset?t=1", payload["textContent"])
        self.assertIn("Reset password", payload["htmlContent"])

    def test_rejection_returns_false_instead_of_raising(self):
        sent, _ = self._send(status=400, body='{"message":"sender not valid"}')
        self.assertFalse(sent)

    def test_configured_by_brevo_key(self):
        with patch.object(emailer, "BREVO_API_KEY", "k"), patch.object(emailer, "SMTP_HOST", ""):
            self.assertTrue(emailer.configured())
        with patch.object(emailer, "BREVO_API_KEY", ""), patch.object(emailer, "SMTP_HOST", ""):
            self.assertFalse(emailer.configured())


if __name__ == "__main__":
    unittest.main()
