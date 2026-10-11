"""agent_link.py - cloud side of the Xelora Desktop local agent.

With ``TASK_EXECUTION=agent`` the cloud API never touches Excel itself. A
signed-in user's task is queued here and run by the local agent
(``local_agent.py``) on that user's own Windows PC, next to their Excel:

    web UI -> POST /task -> queue -> local agent claims -> run_task() locally
                                 <- progress pushes <- (mirrored into ACTIVE_TASKS)

The cloud keeps the ``AgentTask`` in ``main.ACTIVE_TASKS`` as before and
copies the agent's state onto it, so /task/{id}/progress, /status, /reveal,
/pause and /resume work unchanged for the web UI.

Model calls from the agent go through ``/agent-link/llm/<provider>/...``:
the agent authenticates with its own token, and the relay adds the server's
provider key. Provider keys never ship inside the desktop app, and the relay
only serves a user while one of their tasks is running on their agent.

Queued jobs live in memory. A restart of the cloud process drops jobs that no
agent has claimed yet (the task row then stays "running"); claimed jobs carry
their full state, so the agent's next push re-creates the cloud mirror.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String

import config
import database
from database import Base

router = APIRouter(prefix="/agent-link", tags=["agent-link"])

# An agent counts as online if it polled within this window. Agents poll
# continuously (each claim waits up to CLAIM_WAIT_SECONDS).
CLAIM_WAIT_SECONDS = 20
ONLINE_WINDOW_SECONDS = CLAIM_WAIT_SECONDS + 25
WAITING_MESSAGE = (
    "Waiting for Xelora Desktop. Open the desktop app on the Windows PC with Excel "
    "and sign in; this task starts there automatically."
)

# AgentTask attributes that hold live objects or per-process state and are
# never copied between cloud and agent.
_NOT_SYNCED = {"progress_callback", "excel_app_pid"}
# Identity fields the cloud decides; an agent push never overwrites them.
CLOUD_OWNED = frozenset({"user_id", "has_authenticated_user"})
# Attributes copied on every progress push (cheap, needed by the live UI).
PROGRESS_FIELDS = (
    "structured_steps", "progress_log", "is_done", "is_paused", "final_response",
    "recovery_state", "awaiting_approval", "chat_transcript", "instruction",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentToken(Base):
    __tablename__ = "agent_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False, default="Xelora Desktop")
    token_hash = Column(String, nullable=False, unique=True, index=True)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_now)
    last_seen_at = Column(DateTime, nullable=True)


# ── Task state (de)serialisation ────────────────────────────────────────────

def _encode(value):
    if isinstance(value, (set, frozenset)):
        return {"__set__": [_encode(item) for item in value]}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    return value


def _decode(value):
    if isinstance(value, dict):
        if set(value) == {"__set__"}:
            return {_decode(item) for item in value["__set__"]}
        if set(value) == {"__tuple__"}:
            return tuple(_decode(item) for item in value["__tuple__"])
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def export_state(task, fields=None) -> dict:
    """JSON-safe copy of an AgentTask's attributes (all, or just ``fields``)."""
    names = fields if fields is not None else [name for name in vars(task) if name not in _NOT_SYNCED]
    state = {}
    for name in names:
        try:
            encoded = _encode(getattr(task, name))
            json.dumps(encoded)
        except (TypeError, ValueError):
            continue  # not representable; the receiver keeps its own default
        state[name] = encoded
    return state


def apply_state(task, state: dict, skip=frozenset()) -> None:
    for name, value in (state or {}).items():
        if name in _NOT_SYNCED or name in skip or name.startswith("_") or not hasattr(task, name):
            continue
        setattr(task, name, _decode(value))


# ── Tokens ──────────────────────────────────────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session():
    if database.SessionLocal is None:
        raise HTTPException(status_code=503, detail="Desktop agents need DATABASE_URL to be configured.")
    return database.SessionLocal()


def create_token(user_id: int, name: str) -> tuple[int, str]:
    token = "xa_" + secrets.token_urlsafe(32)
    db = _session()
    try:
        row = AgentToken(user_id=user_id, name=name[:80] or "Xelora Desktop", token_hash=_hash(token))
        db.add(row)
        db.commit()
        return row.id, token
    finally:
        db.close()


def user_for_token(token: str) -> int | None:
    if not token or not token.startswith("xa_"):
        return None
    db = _session()
    try:
        row = db.query(AgentToken).filter(AgentToken.token_hash == _hash(token), AgentToken.revoked.is_(False)).first()
        if row is None:
            return None
        seen = row.last_seen_at
        if seen is None or (_now() - (seen if seen.tzinfo else seen.replace(tzinfo=timezone.utc))).total_seconds() > 60:
            row.last_seen_at = _now()
            db.commit()
        return row.user_id
    finally:
        db.close()


def require_agent(x_agent_token: str = Header(default="")) -> int:
    user_id = user_for_token(x_agent_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unknown or revoked agent token. Pair Xelora Desktop again.")
    return user_id


def _jwt_user(authorization: str = Header(default="")) -> int:
    from auth import get_current_user_id
    return get_current_user_id(authorization)


# ── Queue ───────────────────────────────────────────────────────────────────

_cond = threading.Condition()
_queues: dict[int, deque] = {}       # user_id -> pending jobs
_jobs: dict[int, dict] = {}          # task_id -> {"user_id", "pause_requested", "claimed"}
_last_poll: dict[int, float] = {}    # user_id -> monotonic time of last claim
_running: dict[int, int] = {}        # user_id -> number of claimed, unfinished jobs


def configured_providers() -> list[str]:
    """Providers the relay can serve, primary first."""
    available = [name for name, provider in (("gemini", "gemini"), ("claude", "anthropic"), ("openrouter", "openrouter"))
                 if _server_key(provider)]
    return sorted(available, key=lambda name: name != config.AI_PROVIDER)


def routes_to_agent(task) -> bool:
    return (
        config.TASK_EXECUTION == "agent"
        and bool(getattr(task, "has_authenticated_user", False))
        and task.user_id is not None
    )


def agent_online(user_id: int) -> bool:
    last = _last_poll.get(user_id)
    return last is not None and time.monotonic() - last < ONLINE_WINDOW_SECONDS


def dispatch(task, task_id: int) -> None:
    """Queue ``task`` (fresh, or just resumed by /resume) for the user's agent."""
    job = {
        "job_id": uuid.uuid4().hex,
        "task_id": task_id,
        "state": export_state(task),
        "providers": configured_providers(),
    }
    with _cond:
        _jobs[task_id] = {"user_id": task.user_id, "pause_requested": False, "claimed": False}
        _queues.setdefault(task.user_id, deque()).append(job)
        _cond.notify_all()
    if not agent_online(task.user_id):
        task.set_recovery_state("waiting_for_agent", WAITING_MESSAGE, safe_to_continue=False)


def request_pause(task_id: int) -> None:
    with _cond:
        if task_id in _jobs:
            _jobs[task_id]["pause_requested"] = True


def forget(task_id: int) -> None:
    """Drop a deleted task: unqueue it, and stop relaying for it."""
    with _cond:
        info = _jobs.pop(task_id, None)
        if info is None:
            return
        queue = _queues.get(info["user_id"])
        if queue:
            for job in list(queue):
                if job["task_id"] == task_id:
                    queue.remove(job)
        if info["claimed"]:
            _running[info["user_id"]] = max(0, _running.get(info["user_id"], 0) - 1)


def _claim(user_id: int, wait_seconds: float) -> dict | None:
    deadline = time.monotonic() + wait_seconds
    with _cond:
        while True:
            _last_poll[user_id] = time.monotonic()
            queue = _queues.get(user_id)
            if queue:
                job = queue.popleft()
                info = _jobs.get(job["task_id"])
                if info is None:
                    continue  # deleted while queued
                info["claimed"] = True
                _running[user_id] = _running.get(user_id, 0) + 1
                return job
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            _cond.wait(timeout=min(remaining, 5))


# ── Agent endpoints ─────────────────────────────────────────────────────────

class PairRequest(BaseModel):
    name: str = "Xelora Desktop"


def _request_origin(request: Request) -> str:
    # Hosts like Render terminate TLS at a proxy, so the app itself sees http.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


@router.post("/pair")
def pair(req: PairRequest, request: Request, user_id: int = Depends(_jwt_user)):
    """Issue a token for this user's desktop agent (called by the signed-in web app)."""
    token_id, token = create_token(user_id, req.name)
    api_url = config.PUBLIC_API_URL or _request_origin(request)
    return {"token": token, "token_id": token_id, "api_url": api_url}


@router.delete("/tokens/{token_id}")
def revoke(token_id: int, user_id: int = Depends(_jwt_user)):
    """Unpair one desktop agent."""
    db = _session()
    try:
        row = db.query(AgentToken).filter(AgentToken.id == token_id, AgentToken.user_id == user_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        row.revoked = True
        db.commit()
        return {"token_id": token_id, "revoked": True}
    finally:
        db.close()


@router.get("/status")
def status(user_id: int = Depends(_jwt_user)):
    return {
        "user_id": user_id,
        "execution": config.TASK_EXECUTION,
        "online": agent_online(user_id),
        "queued": len(_queues.get(user_id, ())),
        "running": _running.get(user_id, 0),
    }


@router.post("/claim")
def claim(wait: float = CLAIM_WAIT_SECONDS, user_id: int = Depends(require_agent)):
    """Long-poll for this user's next task. Also serves as the agent heartbeat."""
    job = _claim(user_id, max(0.0, min(float(wait), CLAIM_WAIT_SECONDS)))
    if job is None:
        return {"job": None}
    from main import ACTIVE_TASKS
    task = ACTIVE_TASKS.get(job["task_id"])
    if task is not None and (task.recovery_state or {}).get("phase") == "waiting_for_agent":
        task.clear_recovery_state("Xelora Desktop picked up this task.")
    return {"job": job}


class PushRequest(BaseModel):
    state: dict
    final: bool = False


@router.post("/tasks/{task_id}/push")
def push(task_id: int, req: PushRequest, user_id: int = Depends(require_agent)):
    """Mirror the agent's task state into the cloud; returns pending control flags."""
    from agent.core import AgentTask, get_task_completion_status
    from main import ACTIVE_TASKS

    with _cond:
        info = _jobs.get(task_id)
        if info is not None and info["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="This task belongs to a different user.")
        pause_requested = bool(info and info["pause_requested"])
        _last_poll[user_id] = time.monotonic()  # a busy agent is still online

    task = ACTIVE_TASKS.get(task_id)
    if task is None:
        # The cloud restarted after the agent claimed this job: rebuild the mirror.
        instruction = str(req.state.get("instruction") or "")
        task = AgentTask(instruction, user_id=user_id)
        task.has_authenticated_user = True  # only signed-in users' tasks reach agents
        ACTIVE_TASKS[task_id] = task
    elif task.user_id != user_id:
        raise HTTPException(status_code=403, detail="This task belongs to a different user.")

    apply_state(task, req.state, skip=CLOUD_OWNED)
    if pause_requested and not req.final:
        task.is_paused = True  # keep showing the user's pause until the agent stops

    if req.final:
        with _cond:
            if _jobs.pop(task_id, None) is not None:
                _running[user_id] = max(0, _running.get(user_id, 0) - 1)
        _persist(task_id, task, get_task_completion_status(task))
    return {"pause_requested": pause_requested}


def _persist(task_id: int, task, status_value: str) -> None:
    if database.SessionLocal is None:
        return
    from models import Task
    db = database.SessionLocal()
    try:
        values = {
            "status": status_value,
            "transcript": json.dumps(task.chat_transcript, default=str),
            "raw_messages": json.dumps(task.messages, default=str),
        }
        if task.is_done:
            values["completed_at"] = _now()
        db.query(Task).filter_by(id=task_id).update(values)
        db.commit()
    finally:
        db.close()


# ── Model relay ─────────────────────────────────────────────────────────────

_UPSTREAMS = {
    "anthropic": ("https://api.anthropic.com/", re.compile(r"^v1/messages$")),
    "gemini": ("https://generativelanguage.googleapis.com/", re.compile(r"^v1(beta)?/models/[\w.\-]+:generateContent$")),
    "openrouter": ("https://openrouter.ai/api/v1/", re.compile(r"^chat/completions$")),
}
_FORWARDED_HEADERS = ("content-type", "anthropic-version", "anthropic-beta", "http-referer", "x-title")


def _relay_token(provider: str, request: Request) -> str:
    if provider == "anthropic":
        return request.headers.get("x-api-key", "")
    if provider == "gemini":
        return request.headers.get("x-goog-api-key", "") or request.query_params.get("key", "")
    return request.headers.get("authorization", "").removeprefix("Bearer ").strip()


def _server_key(provider: str) -> str:
    return {
        "anthropic": config.ANTHROPIC_API_KEY,
        "gemini": config.GEMINI_API_KEY,
        "openrouter": getattr(config, "OPENROUTER_API_KEY", ""),
    }[provider]


def _relay_error(status_code: int, message: str) -> Response:
    body = {"error": {"code": status_code, "message": message, "type": "relay_error"}}
    return Response(content=json.dumps(body), status_code=status_code, media_type="application/json")


@router.post("/llm/{provider}/{path:path}")
async def llm_relay(provider: str, path: str, request: Request):
    upstream = _UPSTREAMS.get(provider)
    if upstream is None or not upstream[1].match(path):
        return _relay_error(404, "This model endpoint is not relayed.")
    user_id = user_for_token(_relay_token(provider, request))
    if user_id is None:
        return _relay_error(401, "Unknown or revoked agent token.")
    if _running.get(user_id, 0) <= 0:
        return _relay_error(403, "Model calls are relayed only while one of your tasks is running.")
    key = _server_key(provider)
    if not key:
        return _relay_error(503, f"The server has no {provider} API key configured.")

    headers = {name: request.headers[name] for name in _FORWARDED_HEADERS if name in request.headers}
    if provider == "anthropic":
        headers["x-api-key"] = key
    elif provider == "gemini":
        headers["x-goog-api-key"] = key
    else:
        headers["authorization"] = f"Bearer {key}"
    body = await request.body()

    from starlette.concurrency import run_in_threadpool

    def _send():
        return requests.post(upstream[0] + path, data=body, headers=headers, timeout=180)

    try:
        reply = await run_in_threadpool(_send)
    except requests.RequestException as exc:
        return _relay_error(502, f"The model provider could not be reached: {type(exc).__name__}")
    return Response(
        content=reply.content,
        status_code=reply.status_code,
        media_type=reply.headers.get("content-type", "application/json"),
    )
