"""
plan_guard.py
ADDITIVE ONLY. Server-side subscription enforcement - the actual
protection, not just a UI gate. The frontend also hides/disables
buttons for limits it knows about, but that's a UX nicety; THIS is
what actually stops an over-limit or unpaid account from running
another agent task, because it runs on the backend where the user
can't bypass it with devtools.

Used by the middleware registered in server.py, which intercepts
POST /task before it reaches main.py's handler.
"""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from auth_billing_models import Subscription, UsageRecord
from plan_catalog import get_plan


class PlanLimitExceeded(Exception):
    def __init__(self, message: str, status_code: int = 402):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_or_create_usage(db: Session, user_id: int, sub: Subscription) -> UsageRecord:
    now = datetime.now(timezone.utc)
    record = (
        db.query(UsageRecord)
        .filter(UsageRecord.user_id == user_id, UsageRecord.period_start <= now, UsageRecord.period_end >= now)
        .first()
    )
    if record:
        return record

    start = sub.current_period_start or now
    end = sub.current_period_end or (now + timedelta(days=30))
    record = UsageRecord(user_id=user_id, period_start=start, period_end=end, ai_actions_used=0, workflow_runs_used=0)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def check_and_increment_task_usage(db: Session, user_id: int) -> None:
    """Call before starting an agent task. Raises PlanLimitExceeded if
    the account has no active/trialing subscription, or if it's used
    up its workflow-run quota for the current billing period.
    Otherwise increments the counter and returns normally.

    LOCAL TESTING BYPASS: set SKIP_BILLING_CHECKS=true in backend/.env
    to skip all of this entirely - no subscription lookup, no usage
    increment, task always allowed through. This exists specifically
    because a fresh test account (e.g. one created via Google login)
    has no Subscription row at all yet, so the very first check below
    would otherwise always block it with a 403.

    NEVER set this to true anywhere outside your own local .env - it
    completely disables real billing enforcement.
    """
    if os.getenv("SKIP_BILLING_CHECKS", "false").lower() == "true":
        return

    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        raise PlanLimitExceeded("No subscription found for this account.", status_code=403)

    if sub.status not in ("active", "trialing"):
        raise PlanLimitExceeded(
            f"Your subscription is '{sub.status}'. Reactivate your plan to keep running tasks.",
            status_code=402,
        )

    plan = get_plan(sub.plan_tier)
    limit = plan["workflow_runs_per_month"]  # None means unlimited/custom (business tier)

    usage = _get_or_create_usage(db, user_id, sub)

    if limit is not None and usage.workflow_runs_used >= limit:
        from notify import notify
        notify(
            db, user_id, "billing", "Workflow run limit reached",
            f"You've used all {limit} workflow runs included in your {plan['name']} plan this period.",
            priority="high", action_url="/dashboard/billing/plans", action_label="Upgrade plan",
        )
        raise PlanLimitExceeded(
            f"You've used all {limit} workflow runs included in your {plan['name']} plan this billing "
            f"period. Upgrade your plan to keep going.",
            status_code=402,
        )

    usage.workflow_runs_used += 1
    usage.ai_actions_used += 1
    db.commit()