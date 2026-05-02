"""
admin.py
ADDITIVE ONLY. Admin-only endpoints, gated by AuthUser.is_admin (set
manually in the DB for your first admin - see INTEGRATION.md - or via
the /admin/users/{id}/role endpoint once you have one admin account).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from models import User, Task
from auth_billing_models import AuthUser, Subscription
from workspace_models import Workflow, WorkflowRun
from plan_catalog import PLAN_CATALOG

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)) -> Session:
    db = _require_db(db)
    caller = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not caller or not caller.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return db


class SetPlanRequest(BaseModel):
    plan_tier: str


class SetAdminRequest(BaseModel):
    is_admin: bool


@router.get("/users")
def list_users(db: Session = Depends(require_admin)):
    rows = db.query(User, AuthUser, Subscription).join(AuthUser, AuthUser.id == User.id).outerjoin(
        Subscription, Subscription.user_id == User.id
    ).all()
    return {
        "users": [
            {
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "isAdmin": au.is_admin,
                "planTier": au.plan_tier,
                "subscriptionStatus": sub.status if sub else None,
                "createdAt": au.created_at.isoformat() if au.created_at else None,
            }
            for u, au, sub in rows
        ]
    }


@router.get("/subscriptions")
def list_subscriptions(db: Session = Depends(require_admin)):
    subs = db.query(Subscription, User).join(User, User.id == Subscription.user_id).all()
    return {
        "subscriptions": [
            {
                "id": str(sub.id),
                "userId": str(u.id),
                "userEmail": u.email,
                "planTier": sub.plan_tier,
                "billingCycle": sub.billing_cycle,
                "status": sub.status,
                "currentPeriodEnd": sub.current_period_end.isoformat() if sub.current_period_end else None,
                "cancelAtPeriodEnd": sub.cancel_at_period_end,
            }
            for sub, u in subs
        ]
    }


@router.post("/users/{target_user_id}/plan")
def set_user_plan(target_user_id: int, req: SetPlanRequest, db: Session = Depends(require_admin)):
    if req.plan_tier not in PLAN_CATALOG:
        raise HTTPException(status_code=400, detail=f"Unknown plan tier: {req.plan_tier}")
    auth_user = db.query(AuthUser).filter(AuthUser.id == target_user_id).first()
    sub = db.query(Subscription).filter(Subscription.user_id == target_user_id).first()
    if not auth_user or not sub:
        raise HTTPException(status_code=404, detail="User not found.")
    auth_user.plan_tier = req.plan_tier
    sub.plan_tier = req.plan_tier
    sub.status = "active"
    db.commit()
    return {"ok": True}


@router.post("/users/{target_user_id}/role")
def set_user_role(target_user_id: int, req: SetAdminRequest, db: Session = Depends(require_admin)):
    auth_user = db.query(AuthUser).filter(AuthUser.id == target_user_id).first()
    if not auth_user:
        raise HTTPException(status_code=404, detail="User not found.")
    auth_user.is_admin = req.is_admin
    db.commit()
    return {"ok": True}


@router.get("/stats")
def platform_stats(db: Session = Depends(require_admin)):
    total_users = db.query(User).count()
    active_subs = db.query(Subscription).filter(Subscription.status == "active").count()
    trialing_subs = db.query(Subscription).filter(Subscription.status == "trialing").count()
    total_tasks = db.query(Task).count()
    total_workflows = db.query(Workflow).count()
    total_runs = db.query(WorkflowRun).count()
    by_tier = {
        tier: db.query(Subscription).filter(Subscription.plan_tier == tier).count()
        for tier in PLAN_CATALOG.keys()
    }
    return {
        "totalUsers": total_users,
        "activeSubscriptions": active_subs,
        "trialingSubscriptions": trialing_subs,
        "totalTasks": total_tasks,
        "totalWorkflows": total_workflows,
        "totalWorkflowRuns": total_runs,
        "subscriptionsByTier": by_tier,
    }
