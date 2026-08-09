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

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
import security
from agent.core import AgentTask, run_task
from agent.reveal import reveal_workflow, progress_snapshot
from database import init_db, get_db
from learning.memory import set_preference, get_all_preferences
from learning.pattern_miner import mine_patterns, promotable_patterns

app = FastAPI(title="AI Excel Agent Backend")

if config.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

ACTIVE_TASKS = {}
_next_local_id = 1


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
    x_xelora_user_id: str = Header(default=""),
):
    global _next_local_id
    user_id = int(x_xelora_user_id) if x_xelora_user_id else req.user_id
    user_prefs = get_all_preferences(db, user_id) if (db and user_id) else {}

    task = AgentTask(req.instruction, user_id=user_id, workbook_name=req.workbook_name)

    db_task_id = None
    if db is not None:
        from models import Task
        db_task = Task(user_id=user_id, instruction=req.instruction)
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
    import threading

    def _worker():
        from database import SessionLocal
        db = SessionLocal() if SessionLocal is not None else None
        try:
            run_task(task, db=db, db_task_id=task_id if db is not None else None, user_preferences=user_preferences)
            if db is not None and task.is_done:
                from models import Task
                from datetime import datetime, timezone
                db.query(Task).filter_by(id=task_id).update(
                    {"status": "done", "completed_at": datetime.now(timezone.utc)})
                db.commit()
        except Exception as e:
            task.log_step(f"Task crashed: {e}")
            task.is_done = True
        finally:
            if db is not None:
                db.close()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


@app.post("/task/{task_id}/pause", dependencies=_AUTH)
def pause_task(task_id: int):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    task.pause()
    return {"task_id": task_id, "is_paused": True}


@app.post("/task/{task_id}/resume", dependencies=_AUTH)
def resume_task(task_id: int, req: CorrectionRequest, db: Session = Depends(_get_db_optional)):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    user_prefs = get_all_preferences(db, task.user_id) if (db and task.user_id) else {}
    task.resume(correction=req.correction)
    _start_task_in_background(task, task_id, task.user_id, user_prefs)

    return {"task_id": task_id, "status": "resumed",
            "message": f"Poll GET /task/{task_id}/progress or /task/{task_id}/reveal to watch it continue."}


@app.get("/task/{task_id}/status", dependencies=_AUTH)
def get_status(task_id: int):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {
        "task_id": task_id,
        "is_done": task.is_done,
        "is_paused": task.is_paused,
        "status": "paused" if task.is_paused else ("done" if task.is_done else "running"),
        "progress_log": task.progress_log,
        "final_response": task.final_response,
    }


@app.get("/task/{task_id}/reveal", dependencies=_AUTH)
def get_reveal_workflow(task_id: int):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {
        "task_id": task_id,
        "workflow": reveal_workflow(task.structured_steps),
        "final_response": task.final_response,
        "is_done": task.is_done,
        "is_paused": task.is_paused,
    }


@app.get("/task/{task_id}/progress", dependencies=_AUTH)
def get_progress(task_id: int):
    task = ACTIVE_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    snapshot = progress_snapshot(task.structured_steps, task.is_done, task.final_response)
    snapshot["task_id"] = task_id
    snapshot["is_paused"] = task.is_paused
    snapshot["progress_log"] = task.progress_log
    return snapshot


@app.post("/preferences", dependencies=_AUTH)
def save_preference(req: PreferenceRequest, db: Session = Depends(_get_db_optional)):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured - preferences require persistence.")
    pref = set_preference(db, req.user_id, req.category, req.key, req.value)
    return {"id": pref.id, "category": pref.category, "key": pref.key, "value": pref.value}


@app.get("/preferences/{user_id}", dependencies=_AUTH)
def list_preferences(user_id: int, db: Session = Depends(_get_db_optional)):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    return get_all_preferences(db, user_id)


@app.post("/patterns/{user_id}/mine", dependencies=_AUTH)
def mine_user_patterns(user_id: int, db: Session = Depends(_get_db_optional)):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
    newly_promotable = mine_patterns(db, user_id)
    return {
        "newly_promotable": [
            {"id": p.id, "action_sequence": p.action_sequence, "occurrence_count": p.occurrence_count}
            for p in newly_promotable
        ]
    }


@app.get("/patterns/{user_id}", dependencies=_AUTH)
def list_promotable_patterns(user_id: int, db: Session = Depends(_get_db_optional)):
    if db is None:
        raise HTTPException(status_code=400, detail="DATABASE_URL is not configured.")
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
def add_knowledge_document(req: KnowledgeAddRequest):
    from knowledge.rag import KnowledgeBase

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
def search_knowledge(req: KnowledgeSearchRequest):
    from knowledge.rag import KnowledgeBase
    kb = KnowledgeBase(req.user_id)
    return {"results": kb.search(req.query, top_k=req.top_k)}


@app.get("/knowledge/{user_id}/documents", dependencies=_AUTH)
def list_knowledge_documents(user_id: int):
    from knowledge.rag import KnowledgeBase
    kb = KnowledgeBase(user_id)
    return {"documents": kb.list_documents()}


@app.get("/")
def health_check():
    return {"status": "backend is running", "ai_provider": config.AI_PROVIDER,
            "persistence": bool(config.DATABASE_URL), "visual_fallback": config.ENABLE_VISUAL_FALLBACK}
