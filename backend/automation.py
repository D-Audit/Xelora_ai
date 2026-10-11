"""Automation scheduler for user-approved, scheduled workflow runs.

Design boundaries (deliberately conservative):

- It reuses the existing Workflow/WorkflowRun models and submits runs through
  the same internal ``/task`` endpoint as a manual run, so scheduled work
  passes the same plan-limit middleware, task lock, and verification path.
- A schedule can only be created or changed explicitly by its owner through
  the API; the scheduler never promotes an ordinary workflow into a scheduled
  one on its own, and it never mutates the workbook outside the normal
  dispatch/permission path.
- Feature-gated by ENABLE_AUTOMATIONS (default false). A disabled scheduler
  starts no threads and runs nothing, so existing deployments are unaffected.
- Interval-based scheduling with an explicit ``interval_minutes`` (bounded to
  >= 5 minutes) keeps the model simple and testable; no hidden cron syntax.
- The scheduler is idempotent: each due schedule is claimed with an atomic
  UPDATE before submission, so restarting the backend cannot double-run.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

_MIN_INTERVAL_MINUTES = 5
_MAX_INTERVAL_MINUTES = 60 * 24 * 7
_LOOP_INTERVAL_SECONDS = 60
_RUN_SUBMIT_TIMEOUT_SECONDS = 10


def _interval_bounds() -> tuple[int, int]:
    return _MIN_INTERVAL_MINUTES, _MAX_INTERVAL_MINUTES


def _serialize_schedule(schedule) -> dict[str, Any]:
    return {
        "id": schedule.id,
        "workflow_id": schedule.workflow_id,
        "user_id": schedule.user_id,
        "enabled": bool(schedule.enabled),
        "interval_minutes": schedule.interval_minutes,
        "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        "last_status": schedule.last_status,
        "last_task_id": schedule.last_task_id,
    }


def _validate_interval(interval_minutes: Any) -> int:
    try:
        value = int(interval_minutes)
    except (TypeError, ValueError):
        raise ValueError("interval_minutes must be an integer number of minutes.")
    minimum, maximum = _interval_bounds()
    if not minimum <= value <= maximum:
        raise ValueError(f"interval_minutes must be between {minimum} and {maximum}.")
    return value


def _submit_scheduled_run(schedule) -> dict[str, Any]:
    """Submit one workflow run through the same endpoint a manual run uses."""
    from workflows import _instruction_from_steps, INTERNAL_BASE_URL, LOCAL_API_KEY
    from database import SessionLocal
    from workspace_models import Workflow

    db = SessionLocal()
    try:
        workflow = (
            db.query(Workflow)
            .filter(Workflow.id == schedule.workflow_id, Workflow.user_id == schedule.user_id)
            .first()
        )
        if workflow is None:
            return {"submitted": False, "reason": "workflow_not_found"}
        instruction = _instruction_from_steps(workflow)
    finally:
        db.close()

    from auth import create_token

    # server.py's plan guard requires a signed-in user on POST /task; acting as
    # the schedule's owner also routes the run to their desktop agent when hosted.
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {create_token(schedule.user_id)[0]}"}
    if LOCAL_API_KEY:
        headers["X-API-Key"] = LOCAL_API_KEY
    try:
        resp = requests.post(
            f"{INTERNAL_BASE_URL}/task",
            json={"instruction": instruction, "user_id": schedule.user_id},
            headers=headers,
            timeout=_RUN_SUBMIT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"submitted": False, "reason": f"request_failed: {exc}"}
    if resp.status_code == 402:
        return {"submitted": False, "reason": "plan_limit_reached"}
    if not resp.ok:
        return {"submitted": False, "reason": f"task_endpoint_status_{resp.status_code}"}
    task_id = resp.json().get("task_id")
    return {"submitted": True, "task_id": task_id}


class AutomationScheduler:
    """A single background loop that claims due schedules and submits them."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None
        self._started_at: datetime | None = None

    def start(self) -> None:
        if not self._thread or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="xelora-automation", daemon=True)
            self._thread.start()
            self._started_at = datetime.now(timezone.utc)
            _LOGGER.info("Automation scheduler started (interval check every %ss).", _LOOP_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        _LOGGER.info("Automation scheduler stopped.")

    def status(self) -> dict[str, Any]:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_error": self._last_error,
            "min_interval_minutes": _MIN_INTERVAL_MINUTES,
        }

    def _run_loop(self) -> None:
        from database import SessionLocal
        from workspace_models import AutomationSchedule

        while not self._stop_event.wait(_LOOP_INTERVAL_SECONDS):
            try:
                self._claim_and_submit_due()
                self._last_error = None
            except Exception as exc:  # never let one bad row kill the loop
                self._last_error = f"{type(exc).__name__}: {exc}"
                _LOGGER.exception("Automation scheduler pass failed")

    def _claim_and_submit_due(self) -> None:
        from database import SessionLocal
        from workspace_models import AutomationSchedule

        if SessionLocal is None:
            raise RuntimeError("Automations need DATABASE_URL; the scheduler cannot run without persistence.")
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        claimed: dict[str, Any] = {}
        try:
            due = (
                db.query(AutomationSchedule)
                .filter(
                    AutomationSchedule.enabled.is_(True),
                    AutomationSchedule.next_run_at.isnot(None),
                    AutomationSchedule.next_run_at <= now,
                )
                .limit(5)
                .all()
            )
            for schedule in due:
                # Atomic claim: only one process wins for this due tick.
                updated = (
                    db.query(AutomationSchedule)
                    .filter(
                        AutomationSchedule.id == schedule.id,
                        AutomationSchedule.next_run_at == schedule.next_run_at,
                    )
                    .update({"next_run_at": now + timedelta(minutes=schedule.interval_minutes)})
                )
                db.commit()
                if not updated:
                    continue
                claimed["id"] = schedule.id
                result = _submit_scheduled_run(schedule)
                status = "submitted" if result.get("submitted") else result.get("reason", "failed")
                db.query(AutomationSchedule).filter(AutomationSchedule.id == schedule.id).update({
                    "last_run_at": now,
                    "last_status": status,
                    "last_task_id": result.get("task_id"),
                })
                db.commit()
                if not result.get("submitted"):
                    _LOGGER.warning("Scheduled workflow %s not submitted: %s", schedule.id, result.get("reason"))
        finally:
            db.close()


_scheduler: AutomationScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> AutomationScheduler:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = AutomationScheduler()
        return _scheduler
