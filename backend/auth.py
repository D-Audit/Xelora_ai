"""
auth.py
ADDITIVE ONLY - new router, not referenced by main.py. Mounted onto
the existing FastAPI app from server.py (see server.py's docstring
for why it's done that way instead of editing main.py).

Provides real password auth + JWT for the web frontend, on top of the
existing X-API-Key scheme in security.py (which keeps protecting the
agent endpoints in main.py exactly as before - this does not replace
it, it adds a second, per-user layer for /auth and /billing).
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.orm import Session

import config
from database import SessionLocal
from models import User
from auth_billing_models import AuthUser, Subscription

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "14"))

if not JWT_SECRET:
    if config.ALLOW_NO_AUTH:
        JWT_SECRET = "dev-only-insecure-secret-change-me"
    else:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\" "
            "and put it in your .env."
        )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/auth", tags=["auth"])


# --- schemas -------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    country: str | None = None
    primary_use: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    expires_at: str
    user: dict


# --- helpers ---------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user_id: int) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expires_at}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> int:
    """Returns the user_id encoded in a valid token, or raises HTTPException(401)."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")


def get_current_user_id(authorization: str = Header(default="")) -> int:
    """FastAPI dependency: extracts and validates the Bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token> header.")
    return decode_token(authorization.removeprefix("Bearer ").strip())


def _serialize_user(user: User, auth_user: AuthUser) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "isAdmin": auth_user.is_admin,
        "isVerified": auth_user.is_verified,
        "plan": auth_user.plan_tier,
        "createdAt": auth_user.created_at.isoformat() if auth_user.created_at else None,
    }


def get_db_or_503():
    """Like database.get_db(), but never crashes when SessionLocal is
    None (DATABASE_URL unset) - yields None instead so routes can raise
    a clean 503 rather than an unhandled TypeError from the dependency
    itself. Accounts and billing genuinely require persistence, unlike
    main.py's agent endpoints which can run DB-less."""
    if SessionLocal is None:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not configured on the backend - accounts require persistence.",
        )
    return db


# --- routes ------------------------------------------------------------

@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)

    existing = db.query(User).filter(User.email.ilike(req.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(name=req.name, email=req.email)
    db.add(user)
    db.flush()  # assigns user.id without committing yet

    now = datetime.now(timezone.utc)
    auth_user = AuthUser(
        id=user.id,
        password_hash=hash_password(req.password),
        plan_tier="trial",
    )
    db.add(auth_user)

    subscription = Subscription(
        user_id=user.id,
        plan_tier="trial",
        status="trialing",
        current_period_start=now,
        current_period_end=now + timedelta(days=TRIAL_DAYS),
        trial_ends_at=now + timedelta(days=TRIAL_DAYS),
    )
    db.add(subscription)

    db.commit()
    db.refresh(user)
    db.refresh(auth_user)

    # Local import to avoid a circular import at module load time
    # (notify.py has no dependency on auth.py, so this is safe).
    from notify import notify
    notify(
        db, user.id, "account", "Welcome to Xelora",
        f"Your {TRIAL_DAYS}-day free trial has started. Explore the AI Agent page to run your first task.",
        priority="low",
    )

    token, expires_at = create_token(user.id)
    return AuthResponse(token=token, expires_at=expires_at.isoformat(), user=_serialize_user(user, auth_user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)

    user = db.query(User).filter(User.email.ilike(req.email)).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == user.id).first() if user else None

    if not user or not auth_user or not verify_password(req.password, auth_user.password_hash):
        # Same error for "no such user" and "wrong password" - don't leak which.
        raise HTTPException(status_code=401, detail="Invalid email address or password.")

    token, expires_at = create_token(user.id)
    return AuthResponse(token=token, expires_at=expires_at.isoformat(), user=_serialize_user(user, auth_user))


@router.get("/me")
def me(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    user = db.query(User).filter(User.id == user_id).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user or not auth_user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _serialize_user(user, auth_user)
