"""emailer.py - transactional email (password reset, email verification).

Configure ONE of:
  BREVO_API_KEY             Brevo (https://www.brevo.com) transactional email API
  SMTP_HOST [+ SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_STARTTLS]
and EMAIL_FROM, e.g. "Xelora <no-reply@yourdomain.com>". With Brevo, the
EMAIL_FROM address must be a sender (or domain) verified in your Brevo account.

With neither configured, send_email() logs the message (including any
link) to the server console and returns False, so local development
works without an email account.
"""
from __future__ import annotations

import html
import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

import requests

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
EMAIL_FROM = os.getenv("EMAIL_FROM", "Xelora <no-reply@xelora.app>")


def configured() -> bool:
    return bool(BREVO_API_KEY or SMTP_HOST)


def _html(heading: str, paragraphs: list[str], button: tuple[str, str] | None) -> str:
    body = "".join(f'<p style="margin:0 0 16px;color:#52525B;font-size:15px;line-height:1.6">{html.escape(p)}</p>' for p in paragraphs)
    if button:
        label, url = button
        body += (
            f'<p style="margin:24px 0"><a href="{html.escape(url, quote=True)}" '
            'style="background:#0E7A5A;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;'
            f'font-weight:600;font-size:14px;display:inline-block">{html.escape(label)}</a></p>'
            f'<p style="margin:0 0 16px;color:#71717A;font-size:13px;line-height:1.6">Or paste this link into your browser:<br>'
            f'<span style="word-break:break-all">{html.escape(url)}</span></p>'
        )
    return (
        '<div style="font-family:Inter,Segoe UI,Arial,sans-serif;background:#FAFAFA;padding:32px 16px">'
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #E4E4E7;border-radius:12px;padding:32px">'
        '<p style="margin:0 0 24px;font-weight:700;font-size:18px;color:#18181B">Xelora</p>'
        f'<h1 style="margin:0 0 16px;font-size:20px;color:#18181B">{html.escape(heading)}</h1>{body}'
        '</div></div>'
    )


def send_email(to: str, subject: str, heading: str, paragraphs: list[str],
               button: tuple[str, str] | None = None) -> bool:
    """Send one email. Returns True if handed to a provider. Never raises."""
    text = "\n\n".join([heading, *paragraphs] + ([f"{button[0]}: {button[1]}"] if button else []))
    if not configured():
        logger.warning("Email not configured (set BREVO_API_KEY or SMTP_HOST). Would send to %s: %s\n%s", to, subject, text)
        print(f"[email not configured] To: {to} | {subject}\n{text}", flush=True)
        return False
    try:
        if BREVO_API_KEY:
            sender_name, sender_email = parseaddr(EMAIL_FROM)
            response = requests.post(
                BREVO_API_URL,
                headers={"api-key": BREVO_API_KEY, "accept": "application/json"},
                json={
                    "sender": {"name": sender_name or "Xelora", "email": sender_email},
                    "to": [{"email": to}],
                    "subject": subject,
                    "textContent": text,
                    "htmlContent": _html(heading, paragraphs, button),
                },
                timeout=15,
            )
            if response.status_code >= 400:
                # Brevo explains rejections (unverified sender, bad key) in the body.
                raise RuntimeError(f"Brevo rejected the email ({response.status_code}): {response.text[:300]}")
        else:
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = EMAIL_FROM, to, subject
            message.set_content(text)
            message.add_alternative(_html(heading, paragraphs, button), subtype="html")
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
                if SMTP_STARTTLS:
                    smtp.starttls()
                if SMTP_USER:
                    smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
        return True
    except Exception as exc:  # email trouble must never break sign-up or reset
        logger.exception("email_send_failed to=%s subject=%s: %s", to, subject, exc)
        return False
