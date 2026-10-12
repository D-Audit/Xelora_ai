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
import hashlib
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header
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
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
RESET_TOKEN_MINUTES = 60
VERIFY_TOKEN_HOURS = 48
OAUTH_ONLY_PREFIX = "!oauth-only:"

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



def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash or password_hash.startswith(OAUTH_ONLY_PREFIX):
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


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
        "hasPassword": not (auth_user.password_hash or "").startswith(OAUTH_ONLY_PREFIX),
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



@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, background_tasks: BackgroundTasks, db: Session | None = Depends(get_db_or_503)):
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

    from notify import notify
    notify(
        db, user.id, "account", "Welcome to Xelora",
        f"Your {TRIAL_DAYS}-day free trial has started. Open Chat to run your first task.",
        priority="low",
    )
    background_tasks.add_task(_send_verification_email, user.email, user.name, user.id)

    token, expires_at = create_token(user.id)
    return AuthResponse(token=token, expires_at=expires_at.isoformat(), user=_serialize_user(user, auth_user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)

    user = db.query(User).filter(User.email.ilike(req.email)).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == user.id).first() if user else None

    if not user or not auth_user or not verify_password(req.password, auth_user.password_hash):
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


# ── Password reset, email verification, profile ────────────────────────────
# Links carry a signed, expiring token. A reset token also embeds a
# fingerprint of the current password hash, so it stops working as soon as
# the password changes (single use in practice).

def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


def _purpose_token(user_id: int, purpose: str, lifetime: timedelta, **claims) -> str:
    payload = {"sub": str(user_id), "purpose": purpose, "exp": datetime.now(timezone.utc) + lifetime, **claims}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _read_purpose_token(token: str, purpose: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        payload = {}
    if payload.get("purpose") != purpose or "sub" not in payload:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired. Request a new one.")
    return payload


def _send_verification_email(email: str, name: str, user_id: int) -> bool:
    from emailer import send_email

    token = _purpose_token(user_id, "verify", timedelta(hours=VERIFY_TOKEN_HOURS), email=email.lower())
    return send_email(
        email, "Confirm your email for Xelora", "Confirm your email address",
        [f"Hi {name or 'there'}, please confirm that this is your email address for your Xelora account.",
         f"This link expires in {VERIFY_TOKEN_HOURS} hours. If you did not create an account, you can ignore this email."],
        ("Confirm email", f"{FRONTEND_URL}/verify-email?token={token}"),
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    password: str = Field(min_length=8, max_length=200)


class TokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2000)


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, background_tasks: BackgroundTasks,
                    db: Session | None = Depends(get_db_or_503)):
    """Email a reset link. Always answers the same way, so it cannot reveal which emails have accounts."""
    db = _require_db(db)
    user = db.query(User).filter(User.email.ilike(req.email)).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == user.id).first() if user else None
    if user and auth_user:
        token = _purpose_token(user.id, "reset", timedelta(minutes=RESET_TOKEN_MINUTES),
                               pwd=_password_fingerprint(auth_user.password_hash))
        from emailer import send_email
        background_tasks.add_task(
            send_email, user.email, "Reset your Xelora password", "Reset your password",
            [f"We received a request to reset the password for your Xelora account ({user.email}).",
             f"This link expires in {RESET_TOKEN_MINUTES} minutes. If you did not ask for it, you can ignore this email; your password stays the same."],
            ("Choose a new password", f"{FRONTEND_URL}/reset-password?token={token}"),
        )
    return {"sent": True}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    payload = _read_purpose_token(req.token, "reset")
    auth_user = db.query(AuthUser).filter(AuthUser.id == int(payload["sub"])).first()
    if auth_user is None or payload.get("pwd") != _password_fingerprint(auth_user.password_hash):
        raise HTTPException(status_code=400, detail="This link is invalid or has already been used. Request a new one.")
    auth_user.password_hash = hash_password(req.password)
    auth_user.is_verified = True  # following the emailed link proves the address
    db.commit()
    return {"reset": True}


@router.post("/verify-email")
def verify_email(req: TokenRequest, db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    payload = _read_purpose_token(req.token, "verify")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == int(payload["sub"])).first()
    if not user or not auth_user or (user.email or "").lower() != payload.get("email"):
        raise HTTPException(status_code=400, detail="This link is invalid or has expired. Request a new one.")
    auth_user.is_verified = True
    db.commit()
    return {"verified": True}


@router.post("/send-verification")
def send_verification(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    user = db.query(User).filter(User.id == user_id).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user or not auth_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if auth_user.is_verified:
        return {"sent": False, "alreadyVerified": True}
    from emailer import configured
    if not configured():
        raise HTTPException(status_code=503, detail="Email sending is not set up on this server yet.")
    if not _send_verification_email(user.email, user.name, user.id):
        raise HTTPException(status_code=502, detail="We could not send the email. Please try again shortly.")
    return {"sent": True}


@router.patch("/me")
def update_me(req: ProfileUpdate, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    user = db.query(User).filter(User.id == user_id).first()
    auth_user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user or not auth_user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.name = req.name.strip()
    db.commit()
    return _serialize_user(user, auth_user)


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user_id: int = Depends(get_current_user_id),
                    db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    auth_user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if auth_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    has_password = not (auth_user.password_hash or "").startswith(OAUTH_ONLY_PREFIX)
    # Accounts created with Google have no password yet and may set one.
    if has_password and not verify_password(req.current_password or "", auth_user.password_hash):
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")
    auth_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"changed": True}
