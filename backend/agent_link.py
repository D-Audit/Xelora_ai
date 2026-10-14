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

Jobs are stored in the agent_jobs table, so a cloud restart (or a free-tier
sleep) loses nothing; open jobs' mirrors are rebuilt at startup.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi import File as FastAPIFile
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

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
HANDOFF_MESSAGE = "Sending this to Xelora Desktop on your PC"

# AgentTask attributes that hold live objects or per-process state and are
# never copied between cloud and agent.
_NOT_SYNCED = {"progress_callback", "excel_app_pid"}
# Identity fields the cloud decides; an agent push never overwrites them.
CLOUD_OWNED = frozenset({"user_id", "has_authenticated_user"})
# Attributes copied on every progress push (cheap, needed by the live UI).
PROGRESS_FIELDS = (
    "structured_steps", "progress_log", "is_done", "is_paused", "final_response",
    "recovery_state", "awaiting_approval", "chat_transcript", "instruction", "live_status",
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
# Jobs live in agent_jobs, so a cloud restart loses nothing: queued jobs are
# claimed later, and their web-UI mirrors are rebuilt at startup.

QUEUED, CLAIMED, DONE, CANCELLED, ABANDONED = "queued", "claimed", "done", "cancelled", "abandoned"
OPEN_STATES = (QUEUED, CLAIMED)
# A claimed job whose agent has not pushed for this long is given up (PC off,
# network gone). Agents push every second while a task runs.
STALE_AFTER_SECONDS = 10 * 60
ABANDONED_MESSAGE = (
    "INCOMPLETE: Xelora Desktop stopped responding while running this task "
    "(the PC may have gone to sleep or lost its connection). Check the workbook, then send the request again."
)


def _db_now() -> datetime:
    """Naive UTC, comparable on both Postgres and SQLite DateTime columns."""
    return _now().replace(tzinfo=None)


class AgentJob(Base):
    __tablename__ = "agent_jobs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String, nullable=False, default=QUEUED, index=True)
    pause_requested = Column(Boolean, nullable=False, default=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_db_now)
    claimed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=_db_now)


_wake = threading.Condition()        # wakes long-polls when this process queues a job
_last_poll: dict[int, float] = {}    # user_id -> monotonic time the agent last called in


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


def _open_job(db, task_id: int):
    return (db.query(AgentJob).filter(AgentJob.task_id == task_id, AgentJob.status.in_(OPEN_STATES))
            .order_by(AgentJob.id.desc()).first())


def dispatch(task, task_id: int) -> None:
    """Queue ``task`` (fresh, or just resumed by /resume) for the user's agent."""
    payload = {"task_id": task_id, "state": export_state(task), "providers": configured_providers()}
    db = _session()
    try:
        db.query(AgentJob).filter(AgentJob.task_id == task_id, AgentJob.status.in_(OPEN_STATES)) \
            .update({"status": CANCELLED}, synchronize_session=False)
        db.add(AgentJob(task_id=task_id, user_id=task.user_id, status=QUEUED, payload=json.dumps(payload)))
        db.commit()
    finally:
        db.close()
    with _wake:
        _wake.notify_all()
    if agent_online(task.user_id):
        task.live_status = HANDOFF_MESSAGE  # until the agent claims it and pushes its own status
    else:
        task.set_recovery_state("waiting_for_agent", WAITING_MESSAGE, safe_to_continue=False)


def request_pause(task_id: int) -> None:
    db = _session()
    try:
        db.query(AgentJob).filter(AgentJob.task_id == task_id, AgentJob.status.in_(OPEN_STATES)) \
            .update({"pause_requested": True}, synchronize_session=False)
        db.commit()
    finally:
        db.close()


def forget(task_id: int) -> None:
    """Drop a deleted task: unqueue it, and stop relaying for it."""
    db = _session()
    try:
        db.query(AgentJob).filter(AgentJob.task_id == task_id, AgentJob.status.in_(OPEN_STATES)) \
            .update({"status": CANCELLED}, synchronize_session=False)
        db.commit()
    finally:
        db.close()


def running_jobs(user_id: int) -> int:
    db = _session()
    try:
        return db.query(AgentJob).filter(AgentJob.user_id == user_id, AgentJob.status == CLAIMED).count()
    finally:
        db.close()


def _expire_stale(db, user_id: int) -> None:
    from main import ACTIVE_TASKS

    cutoff = datetime.fromtimestamp(time.time() - STALE_AFTER_SECONDS, timezone.utc).replace(tzinfo=None)
    stale = db.query(AgentJob).filter(AgentJob.user_id == user_id, AgentJob.status == CLAIMED,
                                      AgentJob.updated_at < cutoff).all()
    for job in stale:
        job.status = ABANDONED
        task = ACTIVE_TASKS.get(job.task_id)
        if task is not None and not task.is_done:
            task.is_done = True
            task.final_response = ABANDONED_MESSAGE
            task.chat_transcript.append({"role": "assistant", "text": ABANDONED_MESSAGE})
            _persist(job.task_id, task, "failed")
    if stale:
        db.commit()


def _claim(user_id: int, wait_seconds: float) -> dict | None:
    deadline = time.monotonic() + wait_seconds
    while True:
        _last_poll[user_id] = time.monotonic()
        db = _session()
        try:
            _expire_stale(db, user_id)
            for job in (db.query(AgentJob).filter(AgentJob.user_id == user_id, AgentJob.status == QUEUED)
                        .order_by(AgentJob.id).limit(5).all()):
                # Conditional update: exactly one claimer wins, even across processes.
                won = db.query(AgentJob).filter(AgentJob.id == job.id, AgentJob.status == QUEUED).update(
                    {"status": CLAIMED, "claimed_at": _db_now(), "updated_at": _db_now()}, synchronize_session=False)
                db.commit()
                if won:
                    return {"job_id": job.id, **json.loads(job.payload)}
        finally:
            db.close()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        with _wake:
            # Short waits also pick up jobs queued by another process or before a restart.
            _wake.wait(timeout=min(remaining, 2))


def restore_pending() -> None:
    """After a restart, rebuild web-UI mirrors for jobs that are still open."""
    if config.TASK_EXECUTION != "agent" or database.SessionLocal is None:
        return
    from agent.core import AgentTask
    from main import ACTIVE_TASKS

    db = database.SessionLocal()
    try:
        for job in db.query(AgentJob).filter(AgentJob.status.in_(OPEN_STATES)).order_by(AgentJob.id).all():
            if job.task_id in ACTIVE_TASKS:
                continue
            state = json.loads(job.payload).get("state") or {}
            task = AgentTask(str(state.get("instruction") or ""), user_id=job.user_id)
            apply_state(task, state, skip=CLOUD_OWNED)
            task.has_authenticated_user = True
            if job.status == QUEUED:
                task.set_recovery_state("waiting_for_agent", WAITING_MESSAGE, safe_to_continue=False)
            ACTIVE_TASKS[job.task_id] = task
    finally:
        db.close()


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


def _job_counts(user_id: int) -> dict:
    db = _session()
    try:
        base = db.query(AgentJob).filter(AgentJob.user_id == user_id)
        return {"queued": base.filter(AgentJob.status == QUEUED).count(),
                "running": base.filter(AgentJob.status == CLAIMED).count()}
    finally:
        db.close()


@router.get("/status")
def status(user_id: int = Depends(_jwt_user)):
    return {
        "user_id": user_id,
        "execution": config.TASK_EXECUTION,
        "online": agent_online(user_id),
        **_job_counts(user_id),
    }


@router.post("/claim")
def claim(wait: float = CLAIM_WAIT_SECONDS, user_id: int = Depends(require_agent)):
    """Long-poll for this user's next task. Also serves as the agent heartbeat."""
    job = _claim(user_id, max(0.0, min(float(wait), CLAIM_WAIT_SECONDS)))
    if job is None:
        return {"job": None}
    from main import ACTIVE_TASKS
    task = ACTIVE_TASKS.get(job["task_id"])
    if task is not None:
        if (task.recovery_state or {}).get("phase") == "waiting_for_agent":
            task.clear_recovery_state("Xelora Desktop picked up this task.")
        # An older agent never pushes live_status; don't leave the hand-off line showing.
        task.live_status = None
    return {"job": job}


class PushRequest(BaseModel):
    state: dict
    final: bool = False


@router.post("/tasks/{task_id}/push")
def push(task_id: int, req: PushRequest, user_id: int = Depends(require_agent)):
    """Mirror the agent's task state into the cloud; returns pending control flags."""
    from agent.core import AgentTask, get_task_completion_status
    from main import ACTIVE_TASKS

    _last_poll[user_id] = time.monotonic()  # a busy agent is still online
    db = _session()
    try:
        job = _open_job(db, task_id)
        if job is not None and job.user_id != user_id:
            raise HTTPException(status_code=403, detail="This task belongs to a different user.")
        pause_requested = bool(job and job.pause_requested)
        if job is not None:
            job.updated_at = _db_now()
            if req.final:
                job.status = DONE
            db.commit()
    finally:
        db.close()

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


# ── Memory and files for the agent ─────────────────────────────────────────
# The agent reads/writes its user's learning memory here (memory/_store.py's
# remote backend) and mirrors the user's cloud files into a local workspace.

_MEMORY_KIND = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MAX_MEMORY_BYTES = 5 * 1024 * 1024


def _memory_kind(kind: str) -> str:
    if not _MEMORY_KIND.fullmatch(kind):
        raise HTTPException(status_code=400, detail="Invalid memory kind.")
    return kind


@router.get("/memory/{kind}")
def read_memory(kind: str, user_id: int = Depends(require_agent)):
    from memory._store import read_stored
    return {"records": read_stored(_memory_kind(kind), user_id)}


@router.put("/memory/{kind}")
async def write_memory(kind: str, request: Request, user_id: int = Depends(require_agent)):
    from starlette.concurrency import run_in_threadpool

    from memory._store import write_stored

    body = await request.body()
    if len(body) > MAX_MEMORY_BYTES:
        raise HTTPException(status_code=413, detail="Memory payload too large.")
    try:
        records = json.loads(body).get("records")
    except (ValueError, AttributeError):
        records = None
    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="Send {\"records\": [...]}.")
    await run_in_threadpool(write_stored, _memory_kind(kind), user_id, records)
    return {"stored": len(records)}


@router.get("/files")
def list_user_files(user_id: int = Depends(require_agent)):
    import files

    db = _session()
    try:
        return files.list_files(user_id=user_id, db=db)
    finally:
        db.close()


@router.get("/files/{file_id}/download")
def download_user_file(file_id: int, user_id: int = Depends(require_agent)):
    import files

    db = _session()
    try:
        return files.download_file(file_id, user_id=user_id, db=db)
    finally:
        db.close()


@router.post("/files")
async def upload_user_file(
    background_tasks: BackgroundTasks,
    upload: UploadFile = FastAPIFile(...),
    file_id: int | None = Form(default=None),
    user_id: int = Depends(require_agent),
):
    """Store a file the agent created (new file) or changed (new version of file_id)."""
    import files

    db = _session()
    try:
        if file_id is None:
            return await files.upload_file(background_tasks, upload, user_id=user_id, db=db)
        return await files.upload_new_version(file_id, background_tasks, upload, user_id=user_id, db=db)
    finally:
        db.close()


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


@router.post("/web-search")
def agent_web_search(req: SearchRequest, user_id: int = Depends(require_agent)):
    """Web search for a running desktop task, with the server's search API keys."""
    if running_jobs(user_id) <= 0:
        raise HTTPException(status_code=403, detail="Search is relayed only while one of your tasks is running.")
    from tools.web import search_providers, web_search

    if search_providers() == ["duckduckgo"]:
        # No keyed provider here; the desktop's own connection does DuckDuckGo better than a cloud IP.
        return {"verified": False, "status": "no_keyed_provider", "error": "The server has no search API key."}
    return web_search(req.query[:400], max(1, min(int(req.max_results), 10)))


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
    if running_jobs(user_id) <= 0:
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
