"""
oauth.py
ADDITIVE ONLY - new router mounted from server.py, main.py untouched.

Implements "Continue with Google" / "Continue with Microsoft" using
the standard OAuth 2.0 authorization-code flow. Client secrets for
both providers live only in this backend's environment - the browser
and the Next.js frontend never see them.

Flow:
  1. Frontend redirects the browser to GET /auth/{provider}/login
     (via its own /api/auth/{provider}/start route, which also sets a
     CSRF `state` cookie)
  2. This backend hands back the provider's consent-screen URL; the
     frontend redirects the browser there
  3. Provider redirects the browser back to the FRONTEND's own
     callback route (this exact URL must be registered in the
     provider's console)
  4. Frontend's callback route verifies the CSRF state, then POSTs the
     returned `code` here, to /auth/{provider}/exchange
  5. This backend exchanges the code for tokens with the provider
     (using the client secret), fetches the user's verified
     email/name, finds-or-creates a matching AuthUser (linking by
     email is safe here specifically because the provider has already
     verified that email belongs to this person), and returns a
     normal Xelora session - identical shape to POST /auth/login.

OAuth-created accounts get an unusable password marker rather than a
nullable column, so no schema change is needed on the existing
AuthUser table.  The marker deliberately avoids bcrypt: no password
is ever supplied by an OAuth provider, and hashing a placeholder made
new Google/Microsoft sign-ins dependent on the local bcrypt runtime.
"""
import os
import secrets
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User
from auth_billing_models import AuthUser, Subscription
from auth import create_token, TRIAL_DAYS

router = APIRouter(prefix="/auth", tags=["oauth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_TENANT = os.getenv("MICROSOFT_TENANT", "common")
MICROSOFT_AUTHORIZE_URL = f"https://login.microsoftonline.com/{MICROSOFT_TENANT}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = f"https://login.microsoftonline.com/{MICROSOFT_TENANT}/oauth2/v2.0/token"
MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/oidc/userinfo"


class ExchangeRequest(BaseModel):
    code: str
    redirect_uri: str


def _get_or_create_user(db: Session, email: str, name: str) -> tuple[User, bool]:
    """Finds an existing account by email, or creates a new one.
    Returns (user, is_new_user)."""
    user = db.query(User).filter(User.email.ilike(email)).first()
    if user:
        return user, False

    user = User(name=name or email.split("@")[0], email=email)
    db.add(user)
    db.flush()  # assigns user.id

    now = datetime.now(timezone.utc)
    db.add(AuthUser(
        id=user.id,
        # A non-password marker.  It is rejected by password login and
        # avoids invoking bcrypt for an OAuth-only account.
        password_hash=f"!oauth-only:{secrets.token_urlsafe(32)}",
        plan_tier="trial",
        is_verified=True,  # the provider already verified this email
    ))
    db.add(Subscription(
        user_id=user.id, plan_tier="trial", status="trialing",
        current_period_start=now, current_period_end=now + timedelta(days=TRIAL_DAYS),
        trial_ends_at=now + timedelta(days=TRIAL_DAYS),
    ))
    db.commit()
    db.refresh(user)

    from notify import notify
    notify(db, user.id, "account", "Welcome to Xelora",
           f"Your {TRIAL_DAYS}-day free trial has started.", priority="low")

    return user, True


def _issue_session(db: Session, user: User) -> dict:
    auth_user = db.query(AuthUser).filter(AuthUser.id == user.id).first()
    token, expires_at = create_token(user.id)
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "isAdmin": auth_user.is_admin,
            "isVerified": auth_user.is_verified,
            "plan": auth_user.plan_tier,
            "createdAt": auth_user.created_at.isoformat() if auth_user.created_at else None,
        },
    }


# --- Google ------------------------------------------------------------

@router.get("/google/login")
def google_login(redirect_uri: str, state: str = ""):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state
    return {"url": f"{GOOGLE_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"}


@router.post("/google/exchange")
def google_exchange(req: ExchangeRequest):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured on the backend.")

    try:
        token_res = requests.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": req.code,
            "redirect_uri": req.redirect_uri,
            "grant_type": "authorization_code",
        }, timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach Google to verify sign-in.")
    if not token_res.ok:
        raise HTTPException(status_code=401, detail="Google rejected this sign-in attempt. Please try again.")
    access_token = token_res.json().get("access_token")

    userinfo_res = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if not userinfo_res.ok:
        raise HTTPException(status_code=401, detail="Could not fetch your Google account details.")
    info = userinfo_res.json()
    email = info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="This Google account has no email address to sign in with.")

    db = SessionLocal()
    try:
        user, is_new = _get_or_create_user(db, email, info.get("name", ""))
        session = _issue_session(db, user)
        session["is_new_user"] = is_new
        return session
    finally:
        db.close()


# --- Microsoft ---------------------------------------------------------

@router.get("/microsoft/login")
def microsoft_login(redirect_uri: str, state: str = ""):
    if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Microsoft sign-in is not configured on this server.")
    params = {
        "client_id": MICROSOFT_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile User.Read",
        "response_mode": "query",
    }
    if state:
        params["state"] = state
    return {"url": f"{MICROSOFT_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"}


@router.post("/microsoft/exchange")
def microsoft_exchange(req: ExchangeRequest):
    if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Microsoft sign-in is not configured on this server.")
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured on the backend.")

    try:
        token_res = requests.post(MICROSOFT_TOKEN_URL, data={
            "client_id": MICROSOFT_CLIENT_ID,
            "client_secret": MICROSOFT_CLIENT_SECRET,
            "code": req.code,
            "redirect_uri": req.redirect_uri,
            "grant_type": "authorization_code",
            "scope": "openid email profile User.Read",
        }, timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach Microsoft to verify sign-in.")
    if not token_res.ok:
        raise HTTPException(status_code=401, detail="Microsoft rejected this sign-in attempt. Please try again.")
    access_token = token_res.json().get("access_token")

    userinfo_res = requests.get(MICROSOFT_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if not userinfo_res.ok:
        raise HTTPException(status_code=401, detail="Could not fetch your Microsoft account details.")
    info = userinfo_res.json()
    email = info.get("email") or info.get("preferred_username")
    if not email:
        raise HTTPException(status_code=400, detail="This Microsoft account has no email address to sign in with.")

    db = SessionLocal()
    try:
        user, is_new = _get_or_create_user(db, email, info.get("name", ""))
        session = _issue_session(db, user)
        session["is_new_user"] = is_new
        return session
    finally:
        db.close()
