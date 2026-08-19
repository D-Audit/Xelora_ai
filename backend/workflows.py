"""
workflows.py
ADDITIVE ONLY. Named, reusable, multi-step "workflows" - the concept
your frontend's Workflow Builder UI already expects, layered on top of
the backend's single-instruction agent Task model.

Running a workflow synthesizes one natural-language instruction from
its enabled steps and submits it to the existing POST /task endpoint
via a real internal HTTP call (not a duplicated copy of the agent
orchestration code) - so it goes through the exact same plan-limit
middleware and agent pipeline a direct /task call would. The resulting
WorkflowRun links to that task's id, and GET /workflows/runs/{id}
syncs its status by reading the task's live progress on each call.
"""
import os
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from workspace_models import Workflow, WorkflowRun, WorkflowTemplate
from notify import notify

INTERNAL_BASE_URL = os.getenv("INTERNAL_BASE_URL", "http://localhost:8000")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "")

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowStepIn(BaseModel):
    name: str
    description: str | None = ""
    type: str = "custom"
    isEnabled: bool = True
    requiresApproval: bool = False
    errorBehaviour: str = "stop"
    estimatedAiActions: int = 1


class WorkflowIn(BaseModel):
    name: str
    description: str | None = ""
    steps: list[WorkflowStepIn] = []
    tags: list[str] = []
    isPublic: bool = False


def _serialize(w: Workflow) -> dict:
    return {
        "id": str(w.id),
        "name": w.name,
        "description": w.description,
        "status": w.status,
        "steps": w.steps or [],
        "tags": w.tags or [],
        "isPublic": w.is_public,
        "successRate": w.success_rate,
        "totalRuns": w.total_runs,
        "lastRunAt": w.last_run_at.isoformat() if w.last_run_at else None,
        "lastRunStatus": w.last_run_status,
        "createdAt": w.created_at.isoformat() if w.created_at else None,
        "updatedAt": w.updated_at.isoformat() if w.updated_at else None,
    }


def _serialize_run(r: WorkflowRun, workflow_name: str = "") -> dict:
    return {
        "id": str(r.id),
        "workflowId": str(r.workflow_id),
        "workflowName": workflow_name,
        "taskId": r.task_id,
        "status": r.status,
        "stepsCompleted": r.steps_completed,
        "totalSteps": r.total_steps,
        "aiActionsUsed": r.ai_actions_used,
        "durationSeconds": r.duration_seconds,
        "startedAt": r.started_at.isoformat() if r.started_at else None,
        "completedAt": r.completed_at.isoformat() if r.completed_at else None,
    }



@router.get("")
def list_workflows(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    items = db.query(Workflow).filter(Workflow.user_id == user_id).order_by(Workflow.updated_at.desc()).all()
    return {"workflows": [_serialize(w) for w in items]}


@router.post("")
def create_workflow(req: WorkflowIn, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    w = Workflow(
        user_id=user_id,
        name=req.name,
        description=req.description or "",
        steps=[s.model_dump() for s in req.steps],
        tags=req.tags,
        is_public=req.isPublic,
        status="draft",
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _serialize(w)


@router.get("/{workflow_id:int}")
def get_workflow(workflow_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    w = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.user_id == user_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return _serialize(w)


@router.patch("/{workflow_id:int}")
def update_workflow(workflow_id: int, req: WorkflowIn, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    w = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.user_id == user_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    w.name = req.name
    w.description = req.description or ""
    w.steps = [s.model_dump() for s in req.steps]
    w.tags = req.tags
    w.is_public = req.isPublic
    db.commit()
    db.refresh(w)
    return _serialize(w)


@router.delete("/{workflow_id:int}")
def delete_workflow(workflow_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    w = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.user_id == user_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    db.delete(w)
    db.commit()
    return {"deleted": True}



def _instruction_from_steps(workflow: Workflow) -> str:
    enabled = [s for s in (workflow.steps or []) if s.get("isEnabled", True)]
    if not enabled:
        raise HTTPException(status_code=400, detail="This workflow has no enabled steps to run.")
    lines = [f"{i+1}. {s.get('name')}" + (f" - {s['description']}" if s.get("description") else "") for i, s in enumerate(enabled)]
    return f"Run the following steps on the active workbook, in order:\n" + "\n".join(lines)


def _workflow_run_status(progress: dict) -> str:
    """Map the agent's truthful task state to a workflow-run state.

    A stopped worker is not automatically a completed workflow: it may be
    waiting for confirmation, paused, have failed, or have finished with
    verification warnings.
    """
    task_status = str(progress.get("status", ""))
    if task_status in {"completed", "completed_with_warnings", "failed", "awaiting_approval", "paused"}:
        return task_status
    if progress.get("is_paused"):
        return "paused"
    if progress.get("is_done"):
        final_response = str(progress.get("final_response") or "").lstrip().upper()
        return "completed_with_warnings" if final_response.startswith("INCOMPLETE:") else "completed"
    return "running"


@router.post("/{workflow_id:int}/run")
def run_workflow(
    workflow_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session | None = Depends(get_db_or_503),
    authorization: str = Header(default=""),
):
    db = _require_db(db)
    w = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.user_id == user_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    instruction = _instruction_from_steps(w)

    headers = {"Content-Type": "application/json"}
    if LOCAL_API_KEY:
        headers["X-API-Key"] = LOCAL_API_KEY
    if authorization:
        headers["Authorization"] = authorization

    try:
        resp = requests.post(
            f"{INTERNAL_BASE_URL}/task",
            json={"instruction": instruction, "user_id": user_id},
            headers=headers,
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach the agent task endpoint.")

    if resp.status_code == 402:
        raise HTTPException(status_code=402, detail=resp.json().get("error", "Plan limit reached."))
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail="Could not start the workflow run.")

    task_id = resp.json().get("task_id")

    run = WorkflowRun(
        workflow_id=w.id,
        user_id=user_id,
        task_id=task_id,
        status="running",
        total_steps=len([s for s in w.steps if s.get("isEnabled", True)]),
    )
    db.add(run)
    w.status = "running"
    w.total_runs = (w.total_runs or 0) + 1
    w.last_run_at = datetime.now(timezone.utc)
    w.last_run_status = "running"
    db.commit()
    db.refresh(run)

    notify(db, user_id, "workflow", "Workflow started", f"'{w.name}' is now running.", priority="low")

    return _serialize_run(run, workflow_name=w.name)


@router.get("/runs/list")
def list_runs(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    runs = db.query(WorkflowRun).filter(WorkflowRun.user_id == user_id).order_by(WorkflowRun.started_at.desc()).limit(50).all()
    names = {w.id: w.name for w in db.query(Workflow).filter(Workflow.user_id == user_id).all()}
    return {"runs": [_serialize_run(r, workflow_name=names.get(r.workflow_id, "")) for r in runs]}


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session | None = Depends(get_db_or_503),
    authorization: str = Header(default=""),
):
    db = _require_db(db)
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id, WorkflowRun.user_id == user_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    if run.status in {"running", "paused", "awaiting_approval"} and run.task_id:
        headers = {}
        if LOCAL_API_KEY:
            headers["X-API-Key"] = LOCAL_API_KEY
        if authorization:
            headers["Authorization"] = authorization
        try:
            resp = requests.get(f"{INTERNAL_BASE_URL}/task/{run.task_id}/progress", headers=headers, timeout=10)
            if resp.ok:
                data = resp.json()
                completed_actions = data.get("completed_actions", [])
                run.steps_completed = min(len(completed_actions), run.total_steps)
                run.ai_actions_used = len(completed_actions)
                run_status = _workflow_run_status(data)
                run.status = run_status
                if run_status in {"completed", "completed_with_warnings", "failed"}:
                    run.completed_at = datetime.now(timezone.utc)
                    if run.started_at:
                        run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
                    workflow = db.query(Workflow).filter(Workflow.id == run.workflow_id).first()
                    if workflow:
                        if run_status in {"completed", "completed_with_warnings"}:
                            workflow.status = "published"
                        workflow.last_run_status = run_status
                        completed_runs = db.query(WorkflowRun).filter(
                            WorkflowRun.workflow_id == workflow.id, WorkflowRun.status == "completed"
                        ).count()
                        workflow.success_rate = round(100 * completed_runs / max(workflow.total_runs, 1), 1)
                    if run_status == "completed":
                        notify(db, user_id, "workflow", "Workflow finished", "Your workflow run completed and was verified.", priority="medium")
                    elif run_status == "completed_with_warnings":
                        notify(db, user_id, "workflow", "Workflow needs review", "Your workflow stopped with verification warnings. Review the task result before relying on it.", priority="high")
                    else:
                        notify(db, user_id, "workflow", "Workflow failed", "Your workflow stopped before its result could be verified.", priority="high")
                db.commit()
        except requests.RequestException:
            pass  # leave status as-is; frontend will retry on next poll

    workflow = db.query(Workflow).filter(Workflow.id == run.workflow_id).first()
    return _serialize_run(run, workflow_name=workflow.name if workflow else "")



@router.get("/templates/list")
def list_templates(db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    items = db.query(WorkflowTemplate).filter(WorkflowTemplate.is_public.is_(True)).all()
    return {
        "templates": [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "steps": t.steps or [],
            }
            for t in items
        ]
    }


@router.post("/templates/{template_id}/use")
def use_template(template_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    t = db.query(WorkflowTemplate).filter(WorkflowTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    w = Workflow(user_id=user_id, name=t.name, description=t.description, steps=t.steps, status="draft")
    db.add(w)
    db.commit()
    db.refresh(w)
    return _serialize(w)
