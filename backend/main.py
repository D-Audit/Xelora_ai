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

import config
import security
from agent.core import AgentTask, get_task_completion_status, run_task
from agent.reveal import reveal_workflow, progress_snapshot
from auth import decode_token
from database import init_db, get_db
from learning.memory import set_preference, get_all_preferences
from learning.pattern_miner import mine_patterns, promotable_patterns

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


@app.on_event("startup")
def on_startup():
    if not config.LOCAL_API_KEY and not config.ALLOW_NO_AUTH:
        print("REFUSING TO START: LOCAL_API_KEY is not set. Set it in .env, or set "
              "ALLOW_NO_AUTH=true if you intend to run without authentication.")
        raise SystemExit(1)
    if config.ALLOW_NO_AUTH and not config.LOCAL_API_KEY:
        print("WARNING: running with ALLOW_NO_AUTH=true and no API key - every endpoint "
              "is open to anyone who can reach this server. Only use this for local testing.")

    if config.DATABASE_URL:
        init_db()
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


class CorrectionRequest(BaseModel):
    correction: str | None = None


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
    _start_task_in_background(task, task_id, user_id, user_prefs)

    return {"task_id": task_id, "status": "started",
            "message": f"Poll GET /task/{task_id}/progress or /task/{task_id}/reveal to watch it run."}


def _start_task_in_background(task, task_id, user_id, user_preferences):
    def _worker():
        import json
        from datetime import datetime, timezone
        from database import SessionLocal
        acquired_immediately = _TASK_EXECUTION_LOCK.acquire(blocking=False)
        if not acquired_immediately:
            wait_message = "Waiting for the current Excel task to finish before this task can safely use the workbook."
            task.log_step(wait_message)
            task.structured_steps.append({"type": "reasoning", "text": wait_message})
            _TASK_EXECUTION_LOCK.acquire()

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
        finally:
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
    if row is None or not row.raw_messages:
        return None

    import json
    task = AgentTask(row.instruction, user_id=row.user_id, workbook_name=row.workbook_name)
    task.messages = json.loads(row.raw_messages)
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

    if not task.is_done and not task.is_paused:
        raise HTTPException(status_code=409, detail="This conversation is still processing the previous message.")
    if not req.correction and task.is_done:
        raise HTTPException(status_code=400, detail="Send a message to continue a completed conversation.")

    user_prefs = get_all_preferences(db, task.user_id) if (db and task.user_id) else {}
    task.resume(correction=req.correction)
    if db is not None:
        from models import Task
        db.query(Task).filter_by(id=task_id).update({"status": "running"})
        db.commit()
    _start_task_in_background(task, task_id, task.user_id, user_prefs)

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
    snapshot = progress_snapshot(task.structured_steps, task.is_done, task.final_response)
    snapshot["task_id"] = task_id
    snapshot["is_paused"] = task.is_paused
    snapshot["status"] = get_task_completion_status(task)
    snapshot["progress_log"] = task.progress_log
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
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
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
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "transcript": transcript,
        "resumable": (task_id in ACTIVE_TASKS) or bool(task.raw_messages),
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
            "codegen_layer": config.ENABLE_CODEGEN_LAYER}
