"""
main.py
The FastAPI service. Your desktop frontend (Electron/Tauri/whatever)
talks to this over HTTP - this file has no frontend concerns in it.

Security note: EVERY endpoint below depends on security.check_api_key
and security.rate_limit (see security.py). The knowledge/* endpoints
previously had no auth check at all - that's fixed here too, not just
documented.

Run with:  uvicorn main:app --reload
"""

import threading

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import agent_link
import config
import security
from agent import providers
from agent.core import AgentTask, get_task_completion_status, run_task
from agent.reveal import reveal_workflow, progress_snapshot
from auth import decode_token
from database import init_db, get_db
from learning.memory import set_preference, get_all_preferences
from memory.outcome import record_task_outcome, start_task_history, task_actions
from learning.pattern_miner import mine_patterns, promotable_patterns

if config.ENABLE_SSE_STREAMING:
    from streaming.sse import streamer

app = FastAPI(title="AI Excel Agent Backend")

if config.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

ACTIVE_TASKS = {}
_next_local_id = 1
# Excel automation drives one active desktop application. Serializing complete
# task runs prevents two background requests from interleaving clicks or
# workbook operations against the same active Excel window.
_TASK_EXECUTION_LOCK = threading.Lock()


def _require_feature(enabled: bool, feature_name: str) -> None:
    if not enabled:
        raise HTTPException(status_code=404, detail=f"{feature_name} is disabled by server configuration.")


@app.on_event("startup")
def on_startup():
    try:
        config.validate_local_omniparser_configuration()
    except RuntimeError as exc:
        print(f"REFUSING TO START: {exc}")
        raise SystemExit(1) from exc
    try:
        config.validate_terminal_configuration()
    except RuntimeError as exc:
        print(f"REFUSING TO START: {exc}")
        raise SystemExit(1) from exc
    try:
        config.validate_ai_provider_configuration()
    except RuntimeError as exc:
        print(f"REFUSING TO START: {exc}")
        raise SystemExit(1) from exc
    try:
        providers.validate_provider_tool_catalogues()
    except RuntimeError as exc:
        print(f"REFUSING TO START: {exc}")
        raise SystemExit(1) from exc
    if not config.LOCAL_API_KEY and not config.ALLOW_NO_AUTH:
        print("REFUSING TO START: LOCAL_API_KEY is not set. Set it in .env, or set "
              "ALLOW_NO_AUTH=true if you intend to run without authentication.")
        raise SystemExit(1)
    if config.ALLOW_NO_AUTH and not config.LOCAL_API_KEY:
        print("WARNING: running with ALLOW_NO_AUTH=true and no API key - every endpoint "
              "is open to anyone who can reach this server. Only use this for local testing.")
    if config.TASK_EXECUTION not in {"server", "agent"}:
        print(f"REFUSING TO START: TASK_EXECUTION must be 'server' or 'agent', not {config.TASK_EXECUTION!r}.")
        raise SystemExit(1)
    if config.TASK_EXECUTION == "agent" and not config.DATABASE_URL:
        print("REFUSING TO START: TASK_EXECUTION=agent needs DATABASE_URL (desktop agent tokens are stored there).")
        raise SystemExit(1)
    if config.OMNIPARSER_ONLY_MODE and not config.OMNIPARSER_URL:
        print("REFUSING TO START: OMNIPARSER_ONLY_MODE=true requires OMNIPARSER_URL to point "
              "to the separately running OmniParser /parse/ endpoint. Do not use this "
              "backend's own port.")
        raise SystemExit(1)

    if config.DATABASE_URL:
        init_db()
        if config.ENABLE_AUTOMATIONS:
            from automation import get_scheduler
            get_scheduler().start()
    else:
        print("DATABASE_URL not set - running WITHOUT persistence. Tasks will run but "
              "nothing will be saved (no Reveal Workflow history, no memory, no pattern "
              "learning). Set DATABASE_URL in .env for the full feature set.")


@app.exception_handler(Exception)
async def catch_all_handler(request: Request, exc: Exception):
    print(f"UNHANDLED ERROR on {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"error": "Something went wrong. Check the server logs."})


def _get_db_optional():
    if not config.DATABASE_URL:
        yield None
        return
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


_AUTH = [Depends(security.check_api_key), Depends(security.rate_limit)]


def _current_user_id_from_jwt(authorization: str = Header(default="")) -> int | None:
    """Soft version of auth.get_current_user_id: returns the verified
    user id from a Bearer JWT if one was sent, or None if the caller
    isn't using JWT auth at all (e.g. a direct /docs test with only an
    X-API-Key). Only raises if a token WAS sent but is invalid/expired -
    an absent token is not an error here, an invalid one is."""
    if not authorization.startswith("Bearer "):
        return None
    return decode_token(authorization.removeprefix("Bearer ").strip())


def _assert_task_owner(task_user_id: int | None, current_user_id: int | None):
    """Security fix: previously ANY task_id could be paused/resumed/read
    by anyone who guessed or enumerated it - task ids are sequential
    integers, so this was genuinely walkable. Now, whenever we know both
    who owns the task and who's asking (i.e. the caller sent a real JWT),
    we enforce that they match. If either side is unknown (no DB, or the
    caller used API-key-only auth with no user context), we skip the
    check rather than break existing non-user-scoped usage."""
    if task_user_id is not None and current_user_id is not None and task_user_id != current_user_id:
        raise HTTPException(status_code=403, detail="This task belongs to a different user.")


def _assert_user_scope(requested_user_id: int, current_user_id: int | None):
    """Keep legacy API-key-only clients working while scoping JWT callers.

    The Next.js app always supplies a JWT. It must never be able to read or
    write preference, pattern, or knowledge records for a different account
    simply by changing a numeric user id in a request.
    """
    if current_user_id is not None and requested_user_id != current_user_id:
        raise HTTPException(status_code=403, detail="This data belongs to a different user.")


class InstructionRequest(BaseModel):
    instruction: str
    user_id: int | None = None
    workbook_name: str | None = None
    # True when the client already routed this message through /chat: run it as Excel work.
    routed: bool = False


class CorrectionRequest(BaseModel):
    correction: str | None = None
    routed: bool = False


class PreferenceRequest(BaseModel):
    user_id: int
    category: str
    key: str
    value: str


@app.post("/task", dependencies=_AUTH)
def start_task(
    req: InstructionRequest,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    global _next_local_id
    user_id = jwt_user_id if jwt_user_id is not None else req.user_id
    user_prefs = get_all_preferences(db, user_id) if (db and user_id) else {}

    task = AgentTask(req.instruction, user_id=user_id, workbook_name=req.workbook_name)
    # A client using only the local API key may retain legacy task behavior,
    # but it must not gain access to a user-scoped file workspace by supplying
    # a numeric user_id in its request body.
    task.has_authenticated_user = jwt_user_id is not None

    db_task_id = None
    if db is not None:
        from models import Task
        db_task = Task(user_id=user_id, instruction=req.instruction, workbook_name=req.workbook_name)
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        db_task_id = db_task.id
        task_id = db_task_id
    else:
        task_id = _next_local_id
        _next_local_id += 1

    ACTIVE_TASKS[task_id] = task
    if config.ENABLE_SSE_STREAMING:
        task.progress_callback = lambda message: streamer.emit_step(task_id, "progress", message)
    _start_task_in_background(task, task_id, user_id, user_prefs, allow_direct_answer=not req.routed)

    return {"task_id": task_id, "status": "started",
            "message": f"Poll GET /task/{task_id}/progress or /task/{task_id}/reveal to watch it run."}


class ChatRequest(BaseModel):
    instruction: str
    workbook_name: str | None = None
    has_workbook_context: bool = False
    history: list[dict] = []
    # The open conversation, so a quick answer is saved into it.
    task_id: int | None = None


def _chat_has_excel_work(req: ChatRequest, db: Session | None, jwt_user_id: int | None) -> bool:
    from quick_chat import has_agent_work

    if req.task_id is not None and db is not None and jwt_user_id is not None:
        # The saved conversation decides: replies in an Excel conversation go to the agent.
        return _conversation_has_agent_work(db, req.task_id, jwt_user_id, has_agent_work)
    return req.has_workbook_context


@app.post("/chat", dependencies=_AUTH)
def quick_chat(
    req: ChatRequest,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    """Route one composer message: a quick answer, or the Excel task flow.

    Called by the frontend's /api/chat proxy. The model decides whether the
    message is Excel work (route "task": no reply is generated, and the client
    submits POST /task so workbook changes go through the governed agent loop)
    or something it answers itself. Quick answers may use web search and cite
    "sources"; a signed-in user's memory adds context. A signed-in user's
    exchange is saved to their chat history (``task_id``).
    """
    from quick_chat import pre_route, quick_answer

    has_context = _chat_has_excel_work(req, db, jwt_user_id)
    fixed = pre_route(req.instruction, workbook_name=req.workbook_name, has_workbook_context=has_context)
    if fixed is not None:
        return {"route": fixed.kind, "reason": fixed.reason, "reply": None, "sources": []}
    answer = quick_answer(req.instruction, req.history[-12:], user_id=jwt_user_id, route=True, excel_context=has_context)
    if answer.get("route") == "task":
        return {"route": "task", "reason": answer["reason"], "reply": None, "sources": []}
    task_id = None
    if db is not None and jwt_user_id is not None and not answer.get("failed"):
        task_id = _save_quick_exchange(db, jwt_user_id, req.task_id, req.instruction, answer)
    return {"route": "chat", "reason": "Answered in conversation.", "task_id": task_id, **answer}


@app.post("/chat/stream", dependencies=_AUTH)
def quick_chat_stream(
    req: ChatRequest,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    """/chat as newline-delimited JSON events, so the UI shows what is happening.

    Events: {"type": "status", "text": ...} while the model works (searching,
    switching model), {"type": "ping"} every few seconds of silence, then
    {"type": "route", "route": "chat"|"task"} and, for a chat,
    {"type": "answer", "reply", "sources", "task_id", "failed"?}.
    """
    import json
    import queue

    from fastapi.responses import StreamingResponse
    from quick_chat import pre_route, quick_answer

    has_context = _chat_has_excel_work(req, db, jwt_user_id)
    fixed = pre_route(req.instruction, workbook_name=req.workbook_name, has_workbook_context=has_context)

    def events():
        if fixed is not None:
            yield json.dumps({"type": "route", "route": fixed.kind, "reason": fixed.reason}) + "\n"
            return
        # Sent at once, so the client knows the server is awake and working.
        yield json.dumps({"type": "status", "text": "Thinking"}) + "\n"
        updates: queue.Queue = queue.Queue()
        result: dict = {}

        def work():
            try:
                result["answer"] = quick_answer(req.instruction, req.history[-12:], user_id=jwt_user_id,
                                                on_status=updates.put, route=True, excel_context=has_context)
            finally:
                updates.put(None)

        threading.Thread(target=work, name="xelora-quick-chat", daemon=True).start()
        while True:
            try:
                text = updates.get(timeout=5)
            except queue.Empty:
                yield json.dumps({"type": "ping"}) + "\n"  # keeps proxies from closing a quiet stream
                continue
            if text is None:
                break
            yield json.dumps({"type": "status", "text": text}) + "\n"
        answer = result.get("answer") or {"route": "chat", "reply": None, "sources": [], "failed": True}
        if answer.get("route") == "task":
            yield json.dumps({"type": "route", "route": "task", "reason": answer.get("reason") or ""}) + "\n"
            return
        yield json.dumps({"type": "route", "route": "chat", "reason": "Answered in conversation."}) + "\n"
        task_id = None
        if jwt_user_id is not None and not answer.get("failed"):
            # The request's session is closed once streaming starts; save with a fresh one.
            from database import SessionLocal
            if SessionLocal is not None:
                session = SessionLocal()
                try:
                    task_id = _save_quick_exchange(session, jwt_user_id, req.task_id, req.instruction, answer)
                except Exception as exc:
                    print(f"Could not save quick answer to history: {exc}")
                finally:
                    session.close()
        reply = {key: value for key, value in answer.items() if key != "route"}
        yield json.dumps({"type": "answer", "task_id": task_id, **reply}, default=str) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _conversation_has_agent_work(db: Session, task_id: int, user_id: int, has_agent_work) -> bool:
    import json

    live = ACTIVE_TASKS.get(task_id)
    row = _owned_conversation(db, task_id, user_id)  # 403 before spending a model call
    if live is not None:
        _assert_task_owner(live.user_id, user_id)
        return has_agent_work(live.chat_transcript)
    return bool(row and row.transcript and has_agent_work(json.loads(row.transcript)))


def _utc_iso(value):
    """ISO time with an explicit UTC offset. DB columns are naive UTC; without the
    offset, browsers read them as local time ("2h ago" for a new chat)."""
    if value is None:
        return None
    from datetime import timezone
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def _owned_conversation(db: Session, task_id: int, user_id: int):
    from models import Task
    row = db.query(Task).filter(Task.id == task_id).first()
    if row is not None:
        _assert_task_owner(row.user_id, user_id)
    return row


def _save_quick_exchange(db: Session, user_id: int, task_id: int | None, question: str, answer: dict) -> int:
    """Append a quick question and its answer to the conversation, or start one.

    Turns are tagged ``kind: "chat"`` so the UI shows them as answers (not
    task results) and a later Excel request in the same conversation can see them.
    """
    import json
    from datetime import datetime, timezone
    from models import Task

    now = datetime.now(timezone.utc)
    turns = [
        {"role": "user", "text": question, "kind": "chat", "timestamp": now.isoformat()},
        {"role": "assistant", "text": answer["reply"], "kind": "chat", "sources": answer.get("sources") or [],
         "timestamp": now.isoformat()},
    ]
    row = _owned_conversation(db, task_id, user_id) if task_id is not None else None
    if row is None:
        row = Task(user_id=user_id, instruction=question, status="answered", completed_at=now,
                   transcript=json.dumps(turns, default=str), is_read=True)
        db.add(row)
    else:
        live = ACTIVE_TASKS.get(row.id)
        if live is not None:
            # The in-memory task writes its transcript back to this row; keep both in step.
            live.chat_transcript.extend(turns)
            transcript = live.chat_transcript
        else:
            transcript = (json.loads(row.transcript) if row.transcript else []) + turns
        row.transcript = json.dumps(transcript, default=str)
        row.is_read = True
    db.commit()
    db.refresh(row)
    return row.id


def _answer_directly(task, task_id, user_id) -> bool:
    """Answer a greeting or a question that needs no workbook, without Excel.

    Clients that send everything to /task (older web builds, the API) would
    otherwise open Excel, or wait for Xelora Desktop, just to reply to "hi".
    The answer uses the conversation so far and may search the web.
    """
    from quick_chat import classify_message, has_agent_work, quick_answer

    earlier = task.chat_transcript[:-1]
    route = classify_message(
        task.instruction,
        # A first message names an attachment; later ones inherit the conversation's workbook.
        workbook_name=None if earlier else task.workbook_name,
        has_workbook_context=has_agent_work(earlier),
    )
    if route.kind != "chat":
        return False
    history = [{"role": turn.get("role"), "text": turn.get("text")} for turn in earlier]
    answer = quick_answer(task.instruction, history, user_id=user_id)
    task.chat_transcript[-1]["kind"] = "chat"
    task.chat_transcript.append({"role": "assistant", "text": answer["reply"], "kind": "chat",
                                 "sources": answer.get("sources") or []})
    task.final_response = answer["reply"]
    task.answered_conversationally = True
    task.awaiting_approval = False  # there was no plan to approve
    task.defer_excel_until_approval = False
    task.is_done = True
    task.log_step(f"Answered directly ({route.reason})")
    try:
        agent_link._persist(task_id, task, get_task_completion_status(task))
    except Exception as exc:
        task.log_step(f"Could not save this answer to history: {exc}")
    return True


def _start_task_in_background(task, task_id, user_id, user_preferences, *, allow_direct_answer=True):
    if allow_direct_answer and _answer_directly(task, task_id, user_id):
        return
    if agent_link.routes_to_agent(task):
        # Cloud deployment: the user's Xelora Desktop agent runs it next to Excel.
        agent_link.dispatch(task, task_id)
        return

    def _worker():
        import json
        from datetime import datetime, timezone
        from database import SessionLocal
        acquired_immediately = _TASK_EXECUTION_LOCK.acquire(blocking=False)
        if not acquired_immediately:
            wait_message = "Waiting for the current Excel task to finish before this task can safely use the workbook."
            task.set_recovery_state(
                "waiting_for_workbook",
                wait_message,
                safe_to_continue=False,
            )
            task.structured_steps.append({"type": "reasoning", "text": wait_message})
            _TASK_EXECUTION_LOCK.acquire()
            task.clear_recovery_state("The workbook is available; starting this task now.")

        history_task_id = None
        try:
            history_task_id = start_task_history(task, user_id)
        except Exception as exc:
            task.log_step(f"Task history was unavailable: {exc}")

        if config.ENABLE_SSE_STREAMING:
            streamer.emit_step(task_id, "start", f"Task started: {task.instruction[:160]}")

        db = None
        try:
            db = SessionLocal() if SessionLocal is not None else None
            run_task(task, db=db, db_task_id=task_id if db is not None else None, user_preferences=user_preferences)
        except Exception as e:
            task.log_step(f"Task stopped unexpectedly: {e}")
            task.is_done = True
            task.final_response = (
                "INCOMPLETE: The task stopped before its result could be verified. "
                f"Reason: {e}"
            )
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})
            if config.ENABLE_SSE_STREAMING:
                streamer.emit_error(task_id, str(e))
        finally:
            status = get_task_completion_status(task)
            success = status == "completed"
            try:
                record_task_outcome(task, user_id, history_task_id)
            except Exception as exc:
                task.log_step(f"Task learning was unavailable: {exc}")
            if config.ENABLE_SSE_STREAMING:
                streamer.emit_completion(task_id, success, task.final_response or status)
            try:
                if db is not None:
                    try:
                        from models import Task

                        values = {
                            "status": get_task_completion_status(task),
                            "transcript": json.dumps(task.chat_transcript, default=str),
                            "raw_messages": json.dumps(task.messages, default=str),
                        }
                        if task.is_done:
                            values["completed_at"] = datetime.now(timezone.utc)
                        db.query(Task).filter_by(id=task_id).update(values)
                        db.commit()
                    finally:
                        db.close()
            finally:
                _TASK_EXECUTION_LOCK.release()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


@app.post("/task/{task_id}/pause", dependencies=_AUTH)
def pause_task(
    task_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    _assert_task_owner(task.user_id, jwt_user_id)
    task.pause()
    agent_link.request_pause(task_id)
    if db is not None:
        from models import Task
        db.query(Task).filter_by(id=task_id).update({"status": "paused"})
        db.commit()
    return {"task_id": task_id, "is_paused": True}


def _reconstruct_task_from_db(task_id: int, db: Session):
    """Rebuilds a working AgentTask from persisted DB state when the
    server has restarted since this conversation last ran (so
    ACTIVE_TASKS no longer has it). Needs Task.raw_messages to have been
    saved (see main worker + providers.py's call_claude fix) - older
    rows saved before that fix won't have it, and this returns None for
    those (the caller falls back to a clear 404 rather than a broken
    resume)."""
    if db is None:
        return None
    from models import Task
    row = db.query(Task).filter(Task.id == task_id).first()
    # A conversation of quick answers only has a transcript and no model history;
    # its next message simply starts a fresh run in the same conversation.
    if row is None or not (row.raw_messages or row.transcript):
        return None

    import json
    task = AgentTask(row.instruction, user_id=row.user_id, workbook_name=row.workbook_name)
    task.messages = json.loads(row.raw_messages) if row.raw_messages else []
    if row.transcript:
        task.chat_transcript = json.loads(row.transcript)
    task.is_done = True
    ACTIVE_TASKS[task_id] = task
    return task


def _get_or_reconstruct_task(task_id: int, db: Session):
    """The single lookup path /resume uses: prefer the live in-memory
    task (has full structured_steps/progress_log for this run), fall
    back to reconstructing one from the DB if the server restarted."""
    task = ACTIVE_TASKS.get(task_id)
    if task is not None:
        return task
    return _reconstruct_task_from_db(task_id, db)


@app.post("/task/{task_id}/resume", dependencies=_AUTH)
def resume_task(
    task_id: int,
    req: CorrectionRequest,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    task = _get_or_reconstruct_task(task_id, db)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found and could not be reconstructed - either it never "
                   "completed a run, or it ran before persistence was enabled.",
        )
    _assert_task_owner(task.user_id, jwt_user_id)
    if jwt_user_id is not None:
        # A task rebuilt from the database after a restart starts unflagged;
        # without this, a reply in an existing chat ran on this server
        # (Linux, no Excel) instead of being handed to the user's desktop.
        task.has_authenticated_user = True

    if not task.is_done and not task.is_paused:
        raise HTTPException(status_code=409, detail="This conversation is still processing the previous message.")
    if not req.correction and task.is_done:
        raise HTTPException(status_code=400, detail="Send a message to continue a completed conversation.")

    user_prefs = get_all_preferences(db, task.user_id) if (db and task.user_id) else {}
    # A reply to a proposed plan ("Confirm", "Continue") always goes to the agent.
    replying_to_plan = bool(task.awaiting_approval)
    task.resume(correction=req.correction)
    if db is not None:
        from models import Task
        db.query(Task).filter_by(id=task_id).update({"status": "running"})
        db.commit()
    _start_task_in_background(task, task_id, task.user_id, user_prefs,
                              allow_direct_answer=not (replying_to_plan or req.routed))

    return {"task_id": task_id, "status": "resumed",
            "message": f"Poll GET /task/{task_id}/progress or /task/{task_id}/reveal to watch it continue."}


@app.get("/task/{task_id}/status", dependencies=_AUTH)
def get_status(task_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    _assert_task_owner(task.user_id, jwt_user_id)
    return {
        "task_id": task_id,
        "is_done": task.is_done,
        "is_paused": task.is_paused,
        "status": get_task_completion_status(task),
        "recovery": task.recovery_state,
        "progress_log": task.progress_log,
        "final_response": task.final_response,
    }


@app.get("/task/{task_id}/reveal", dependencies=_AUTH)
def get_reveal_workflow(task_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    _assert_task_owner(task.user_id, jwt_user_id)
    return {
        "task_id": task_id,
        "workflow": reveal_workflow(task.structured_steps),
        "final_response": task.final_response,
        "is_done": task.is_done,
        "is_paused": task.is_paused,
        "status": get_task_completion_status(task),
    }


@app.get("/task/{task_id}/progress", dependencies=_AUTH)
def get_progress(task_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    _assert_task_owner(task.user_id, jwt_user_id)
    snapshot = progress_snapshot(
        task.structured_steps,
        task.is_done,
        task.final_response,
        task.recovery_state,
        getattr(task, "live_status", None),
    )
    snapshot["task_id"] = task_id
    snapshot["is_paused"] = task.is_paused
    snapshot["status"] = get_task_completion_status(task)
    snapshot["progress_log"] = task.progress_log
    if task.answered_conversationally and task.chat_transcript:
        snapshot["sources"] = task.chat_transcript[-1].get("sources") or []
    return snapshot


@app.get("/tasks", dependencies=_AUTH)
def list_tasks(
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    if jwt_user_id is None:
        raise HTTPException(status_code=401, detail="Sign in to view chat history.")

    from models import Task
    tasks = (
        db.query(Task)
        .filter(Task.user_id == jwt_user_id)
        .order_by(Task.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": t.id,
            "title": (t.instruction[:80] + "…") if len(t.instruction) > 80 else t.instruction,
            "status": t.status,
            "created_at": _utc_iso(t.created_at),
            "completed_at": _utc_iso(t.completed_at),
            "is_read": t.is_read,
        }
        for t in tasks
    ]


@app.get("/tasks/{task_id}", dependencies=_AUTH)
def get_task_detail(
    task_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    if jwt_user_id is None:
        raise HTTPException(status_code=401, detail="Sign in to view chat history.")

    import json
    from models import Task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    _assert_task_owner(task.user_id, jwt_user_id)

    transcript = json.loads(task.transcript) if task.transcript else []
    return {
        "id": task.id,
        "instruction": task.instruction,
        "status": task.status,
        "created_at": _utc_iso(task.created_at),
        "completed_at": _utc_iso(task.completed_at),
        "transcript": transcript,
        "resumable": (task_id in ACTIVE_TASKS) or bool(task.raw_messages or task.transcript),
    }


@app.post("/tasks/{task_id}/mark-read", dependencies=_AUTH)
def mark_task_read(
    task_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")

    from models import Task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    _assert_task_owner(task.user_id, jwt_user_id)

    task.is_read = True
    db.commit()
    return {"id": task_id, "is_read": True}


@app.delete("/tasks/{task_id}", dependencies=_AUTH)
def delete_task(
    task_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")

    from models import ActionLog, Task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    _assert_task_owner(task.user_id, jwt_user_id)

    db.query(ActionLog).filter(ActionLog.task_id == task_id).delete(synchronize_session=False)
    db.delete(task)
    db.commit()
    ACTIVE_TASKS.pop(task_id, None)
    agent_link.forget(task_id)
    return {"id": task_id, "deleted": True}


@app.post("/preferences", dependencies=_AUTH)
def save_preference(
    req: PreferenceRequest,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured - preferences require persistence.")
    _assert_user_scope(req.user_id, jwt_user_id)
    pref = set_preference(db, req.user_id, req.category, req.key, req.value)
    return {"id": pref.id, "category": pref.category, "key": pref.key, "value": pref.value}


@app.get("/preferences/{user_id}", dependencies=_AUTH)
def list_preferences(
    user_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    _assert_user_scope(user_id, jwt_user_id)
    return get_all_preferences(db, user_id)


@app.post("/patterns/{user_id}/mine", dependencies=_AUTH)
def mine_user_patterns(
    user_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    _assert_user_scope(user_id, jwt_user_id)
    newly_promotable = mine_patterns(db, user_id)
    return {
        "newly_promotable": [
            {"id": p.id, "action_sequence": p.action_sequence, "occurrence_count": p.occurrence_count}
            for p in newly_promotable
        ]
    }


@app.get("/patterns/{user_id}", dependencies=_AUTH)
def list_promotable_patterns(
    user_id: int,
    db: Session = Depends(_get_db_optional),
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    _assert_user_scope(user_id, jwt_user_id)
    patterns = promotable_patterns(db, user_id)
    return [
        {"id": p.id, "action_sequence": p.action_sequence, "occurrence_count": p.occurrence_count}
        for p in patterns
    ]


class KnowledgeAddRequest(BaseModel):
    user_id: int
    doc_id: str
    text: str | None = None
    file_path: str | None = None


class KnowledgeSearchRequest(BaseModel):
    user_id: int
    query: str
    top_k: int = 5


@app.post("/knowledge/add", dependencies=_AUTH)
def add_knowledge_document(req: KnowledgeAddRequest, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    from knowledge.rag import KnowledgeBase

    _assert_user_scope(req.user_id, jwt_user_id)

    if req.text:
        text = req.text
    elif req.file_path:
        safe_path = security.validate_ingest_path(req.file_path)
        from ingestion.document_ingest import extract_document, UnsupportedFileType
        try:
            text = extract_document(safe_path)["text"]
        except (UnsupportedFileType, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'file_path'.")

    kb = KnowledgeBase(req.user_id)
    chunks_added = kb.add_document(req.doc_id, text)
    return {"doc_id": req.doc_id, "chunks_added": chunks_added}


@app.post("/knowledge/search", dependencies=_AUTH)
def search_knowledge(req: KnowledgeSearchRequest, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    from knowledge.rag import KnowledgeBase
    _assert_user_scope(req.user_id, jwt_user_id)
    kb = KnowledgeBase(req.user_id)
    return {"results": kb.search(req.query, top_k=req.top_k)}


@app.get("/knowledge/{user_id}/documents", dependencies=_AUTH)
def list_knowledge_documents(user_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    from knowledge.rag import KnowledgeBase
    _assert_user_scope(user_id, jwt_user_id)
    kb = KnowledgeBase(user_id)
    return {"documents": kb.list_documents()}


@app.get("/")
def health_check():
    return {"status": "backend is running", "ai_provider": config.AI_PROVIDER,
            "persistence": bool(config.DATABASE_URL), "visual_fallback": config.ENABLE_VISUAL_FALLBACK,
            "visual_only_mode": config.VISUAL_ONLY_MODE,
            "codegen_layer": config.ENABLE_CODEGEN_LAYER,
            "agent_expansion": {
                "task_planner": config.ENABLE_TASK_PLANNER,
                "subagents": config.ENABLE_SUBAGENTS,
                "skill_extraction": config.ENABLE_SKILL_EXTRACTION,
                "data_profiling": config.ENABLE_DATA_PROFILING,
                "pdf_reports": config.ENABLE_PDF_REPORTS,
                "sse_streaming": config.ENABLE_SSE_STREAMING,
                "memory_storage": config.ENABLE_MEMORY_STORAGE,
                "terminal_tools": config.ENABLE_TERMINAL_TOOLS,
                "cua_driver": config.ENABLE_CUA_DRIVER,
                "mcp_client": config.ENABLE_MCP_CLIENT,
                "automations": config.ENABLE_AUTOMATIONS,
            }}


@app.get("/agent/cua/health", dependencies=_AUTH)
def cua_health():
    """Report whether the local Cua Driver is enabled, installed, and reachable.

    Safe to call on any platform: on Linux without a Driver it reports
    disabled/unavailable instead of failing, so the frontend can show real
    desktop-control readiness before a task needs it.
    """
    from vision.cua_driver import health_check
    return health_check()


@app.get("/agent/tools", dependencies=_AUTH)
def agent_tool_catalogue():
    """The runtime tool registry: schemas, risk, permissions, availability."""
    from agent.tool_registry import catalogue_summary
    from agent.providers import _available_vision_tools
    visual_tool_names = (
        {tool["name"] for tool in _available_vision_tools()}
        if (config.ENABLE_VISUAL_FALLBACK or config.VISUAL_ONLY_MODE) else set()
    )
    return catalogue_summary(visual_tool_names=visual_tool_names)


# ── Automations: user-approved scheduled workflow runs ──────────────

class AutomationScheduleRequest(BaseModel):
    workflow_id: int
    enabled: bool = True
    interval_minutes: int = 60


@app.get("/automations", dependencies=_AUTH)
def list_automations(jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_AUTOMATIONS, "Automations")
    from automation import get_scheduler, _serialize_schedule
    from database import get_db
    from workspace_models import AutomationSchedule

    db = next(get_db())
    try:
        schedules = (
            db.query(AutomationSchedule)
            .filter(AutomationSchedule.user_id == jwt_user_id)
            .order_by(AutomationSchedule.id.desc())
            .limit(100)
            .all()
        )
        return {"schedules": [_serialize_schedule(s) for s in schedules], "scheduler": get_scheduler().status()}
    finally:
        db.close()


@app.post("/automations", dependencies=_AUTH)
def create_automation(
    req: AutomationScheduleRequest,
    jwt_user_id: int | None = Depends(_current_user_id_from_jwt),
):
    _require_feature(config.ENABLE_AUTOMATIONS, "Automations")
    if jwt_user_id is None:
        raise HTTPException(status_code=403, detail="Automations require a signed-in user.")
    from automation import get_scheduler, _serialize_schedule, _validate_interval
    from database import get_db
    from workspace_models import AutomationSchedule, Workflow
    from datetime import datetime, timedelta, timezone

    interval = _validate_interval(req.interval_minutes)
    db = next(get_db())
    try:
        workflow = (
            db.query(Workflow)
            .filter(Workflow.id == req.workflow_id, Workflow.user_id == jwt_user_id)
            .first()
        )
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        existing = (
            db.query(AutomationSchedule)
            .filter(AutomationSchedule.workflow_id == workflow.id, AutomationSchedule.user_id == jwt_user_id)
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.enabled = req.enabled
            existing.interval_minutes = interval
            existing.next_run_at = (now + timedelta(minutes=interval)) if req.enabled else None
            db.commit()
            db.refresh(existing)
            schedule = existing
        else:
            schedule = AutomationSchedule(
                workflow_id=workflow.id,
                user_id=jwt_user_id,
                enabled=req.enabled,
                interval_minutes=interval,
                next_run_at=(now + timedelta(minutes=interval)) if req.enabled else None,
            )
            db.add(schedule)
            db.commit()
            db.refresh(schedule)
        return _serialize_schedule(schedule)
    finally:
        db.close()


@app.delete("/automations/{schedule_id}", dependencies=_AUTH)
def delete_automation(schedule_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_AUTOMATIONS, "Automations")
    from database import get_db
    from workspace_models import AutomationSchedule

    db = next(get_db())
    try:
        schedule = (
            db.query(AutomationSchedule)
            .filter(AutomationSchedule.id == schedule_id, AutomationSchedule.user_id == jwt_user_id)
            .first()
        )
        if schedule is None:
            raise HTTPException(status_code=404, detail="Automation schedule not found.")
        db.delete(schedule)
        db.commit()
        return {"deleted": True}
    finally:
        db.close()


# ── Agent memory, learned skills, and reporting ─────────────────────

@app.get("/memory/{user_id}", dependencies=_AUTH)
def get_user_memory(user_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_MEMORY_STORAGE, "Agent memory")
    _assert_user_scope(user_id, jwt_user_id)
    from memory.chat_memory import get_user_profile
    profile = get_user_profile(user_id)
    return {"profile": profile, "memory_count": profile["total_tasks"]}


@app.get("/memory/{user_id}/similar", dependencies=_AUTH)
def get_similar_memories(user_id: int, query: str, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_MEMORY_STORAGE, "Agent memory")
    _assert_user_scope(user_id, jwt_user_id)
    from memory.chat_memory import get_relevant_memories
    return {"memories": get_relevant_memories(user_id, query)}


@app.get("/skills", dependencies=_AUTH)
def list_agent_skills(jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_MEMORY_STORAGE, "Learned skills")
    from memory.skill_store import get_all_skills
    return {"skills": get_all_skills(user_id=jwt_user_id)}


@app.get("/skills/recommend", dependencies=_AUTH)
def recommend_skills(instruction: str, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_MEMORY_STORAGE, "Learned skills")
    from agent.skills import get_skill_recommendations
    skills = get_skill_recommendations(instruction, user_id=jwt_user_id)
    return {"skills": [{"name": skill["name"], "description": skill["description"]} for skill in skills]}


@app.get("/agent/stats", dependencies=_AUTH)
def get_agent_stats(jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_MEMORY_STORAGE, "Agent statistics")
    from memory.chat_memory import get_memory_count
    from memory.skill_store import get_all_skills
    from memory.task_history import get_stats
    return {
        **get_stats(user_id=jwt_user_id),
        "skill_count": len(get_all_skills(user_id=jwt_user_id)),
        "memory_entries": get_memory_count(jwt_user_id),
    }


@app.post("/profile", dependencies=_AUTH)
def profile_sheet(jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_DATA_PROFILING, "Data profiling")
    from reporting.data_profiler import generate_profile_report, profile_current_sheet
    if not _TASK_EXECUTION_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An Excel task is running; profile the workbook after it finishes.")
    try:
        profile = profile_current_sheet()
    finally:
        _TASK_EXECUTION_LOCK.release()
    return {"profile": profile, "report": generate_profile_report(profile)}


@app.post("/report/generate", dependencies=_AUTH)
def generate_report(req: InstructionRequest, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_PDF_REPORTS, "PDF reporting")
    from pathlib import Path
    from reporting.pdf_generator import generate_task_report

    profile = None
    if config.ENABLE_DATA_PROFILING:
        acquired = _TASK_EXECUTION_LOCK.acquire(blocking=False)
        if acquired:
            try:
                from reporting.data_profiler import profile_current_sheet
                profile = profile_current_sheet()
            except Exception:
                pass
            finally:
                _TASK_EXECUTION_LOCK.release()
    report_path = generate_task_report(
        instruction=req.instruction,
        actions=[],
        outcome="Report generated through the Xelora API.",
        success=True,
        profile=profile,
        user_id=jwt_user_id,
    )
    return {"report_name": Path(report_path).name, "message": "Report generated"}


@app.get("/reports", dependencies=_AUTH)
def list_reports(jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    _require_feature(config.ENABLE_PDF_REPORTS, "PDF reporting")
    from reporting.pdf_generator import list_reports as list_all_reports
    return {"reports": list_all_reports(jwt_user_id)}


@app.get("/task/{task_id}/stream", dependencies=_AUTH)
async def stream_task_progress(task_id: int, jwt_user_id: int | None = Depends(_current_user_id_from_jwt)):
    """Open an authenticated SSE stream for a task's live progress."""
    _require_feature(config.ENABLE_SSE_STREAMING, "Task progress streaming")
    from fastapi.responses import StreamingResponse
    from streaming.sse import task_event_generator

    task = ACTIVE_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    _assert_task_owner(task.user_id, jwt_user_id)
    return StreamingResponse(
        task_event_generator(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
