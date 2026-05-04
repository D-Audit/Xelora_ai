"""
billing.py
ADDITIVE ONLY - new router, mounted from server.py (main.py untouched).

Two modes, chosen automatically by whether STRIPE_SECRET_KEY is set:

- STRIPE_SECRET_KEY set  -> POST /billing/checkout creates a real Stripe
  Checkout Session and returns its URL. The subscription only becomes
  "active" once Stripe calls back to POST /billing/webhook - the
  frontend must not treat checkout as complete just because the POST
  returned; it has to redirect the user to Stripe and wait for the
  webhook to land.
- STRIPE_SECRET_KEY unset -> "dev mode": /billing/checkout activates
  the subscription immediately in the database, no real payment. Loud
  warnings are logged so this is never mistaken for a production
  payment flow.
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from auth_billing_models import AuthUser, Subscription, UsageRecord, Invoice
from plan_catalog import PLAN_CATALOG, STRIPE_PRICE_ENV_VARS, get_plan

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)
if STRIPE_ENABLED:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
else:
    print("billing.py: STRIPE_SECRET_KEY not set - running billing in DEV MODE. "
          "Checkouts activate subscriptions instantly with no real payment. "
          "Set STRIPE_SECRET_KEY before taking real money.")

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan_tier: str
    billing_cycle: str = "monthly"  # monthly|annual


class CancelRequest(BaseModel):
    immediately: bool = False


def _period_bounds(cycle: str, start: datetime | None = None) -> tuple[datetime, datetime]:
    start = start or datetime.now(timezone.utc)
    days = 365 if cycle == "annual" else 30
    return start, start + timedelta(days=days)


def _get_or_404(db: Session, user_id: int) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found for this account.")
    return sub


def _current_usage(db: Session, user_id: int, sub: Subscription) -> UsageRecord:
    record = (
        db.query(UsageRecord)
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.period_start <= datetime.now(timezone.utc),
            UsageRecord.period_end >= datetime.now(timezone.utc),
        )
        .first()
    )
    if not record:
        record = UsageRecord(
            user_id=user_id,
            period_start=sub.current_period_start or datetime.now(timezone.utc),
            period_end=sub.current_period_end or (datetime.now(timezone.utc) + timedelta(days=30)),
            ai_actions_used=0,
            workflow_runs_used=0,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def _serialize_subscription(sub: Subscription) -> dict:
    return {
        "id": str(sub.id),
        "planTier": sub.plan_tier,
        "billingCycle": sub.billing_cycle,
        "status": sub.status,
        "currentPeriodStart": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "currentPeriodEnd": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancelAtPeriodEnd": sub.cancel_at_period_end,
        "trialEndsAt": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
    }


def _serialize_plan(plan: dict) -> dict:
    return {
        "tier": plan["tier"],
        "name": plan["name"],
        "description": plan["description"],
        "monthlyPrice": None if plan["monthly_price_cents"] is None else plan["monthly_price_cents"] / 100,
        "annualPrice": None if plan["annual_price_cents"] is None else plan["annual_price_cents"] / 100,
        "limits": {
            "aiActionsPerMonth": plan["ai_actions_per_month"] if plan["ai_actions_per_month"] is not None else "custom",
            "workflowRunsPerMonth": plan["workflow_runs_per_month"] if plan["workflow_runs_per_month"] is not None else "custom",
            "maxFileSizeMB": plan["max_file_size_mb"] if plan["max_file_size_mb"] is not None else "custom",
            "savedWorkflows": plan["saved_workflows"] if plan["saved_workflows"] is not None else "custom",
            "cloudStorageGB": plan["cloud_storage_gb"] if plan["cloud_storage_gb"] is not None else "custom",
            "devices": plan["devices"] if plan["devices"] is not None else "custom",
            "historyDays": plan["history_days"] if plan["history_days"] is not None else "custom",
            "teamMembers": plan["team_members"] if plan["team_members"] is not None else "custom",
            "batchProcessing": plan["batch_processing"],
            "apiAccess": plan["api_access"],
            "prioritySupport": plan["priority_support"],
        },
    }


# --- routes ----------------------------------------------------------------

@router.get("/plans")
def list_plans():
    return {"plans": [_serialize_plan(p) for p in PLAN_CATALOG.values()], "stripe_enabled": STRIPE_ENABLED}


@router.get("/subscription")
def get_subscription(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    sub = _get_or_404(db, user_id)
    usage = _current_usage(db, user_id, sub)
    plan = get_plan(sub.plan_tier)
    return {
        "subscription": _serialize_subscription(sub),
        "usage": {
            "aiActionsUsed": usage.ai_actions_used,
            "aiActionsLimit": plan["ai_actions_per_month"] if plan["ai_actions_per_month"] is not None else "unlimited",
            "workflowRunsUsed": usage.workflow_runs_used,
            "workflowRunsLimit": plan["workflow_runs_per_month"] if plan["workflow_runs_per_month"] is not None else "unlimited",
            "resetDate": sub.current_period_end.isoformat() if sub.current_period_end else None,
        },
    }


@router.get("/invoices")
def list_invoices(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == user_id)
        .order_by(Invoice.issued_at.desc())
        .all()
    )
    return {
        "invoices": [
            {
                "id": str(inv.id),
                "amount": inv.amount_cents / 100,
                "currency": inv.currency,
                "status": inv.status,
                "description": inv.description,
                "issuedAt": inv.issued_at.isoformat() if inv.issued_at else None,
                "periodStart": inv.period_start.isoformat() if inv.period_start else None,
                "periodEnd": inv.period_end.isoformat() if inv.period_end else None,
            }
            for inv in invoices
        ]
    }


@router.post("/checkout")
def checkout(req: CheckoutRequest, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    if req.plan_tier not in PLAN_CATALOG:
        raise HTTPException(status_code=400, detail=f"Unknown plan tier: {req.plan_tier}")
    if req.plan_tier == "business":
        raise HTTPException(status_code=400, detail="Business plan requires contacting sales - no self-serve checkout.")

    db = _require_db(db)
    auth_user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    sub = _get_or_404(db, user_id)

    if STRIPE_ENABLED:
        env_var = STRIPE_PRICE_ENV_VARS.get((req.plan_tier, req.billing_cycle))
        price_id = os.getenv(env_var, "") if env_var else ""
        if not price_id:
            raise HTTPException(
                status_code=500,
                detail=f"Stripe is enabled but {env_var} is not set in the environment.",
            )

        if not sub.stripe_customer_id:
            customer = stripe.Customer.create(metadata={"user_id": str(user_id)})
            sub.stripe_customer_id = customer.id
            db.commit()

        session = stripe.checkout.Session.create(
            customer=sub.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{FRONTEND_URL}/dashboard/billing?checkout=success",
            cancel_url=f"{FRONTEND_URL}/dashboard/billing/plans?checkout=cancelled",
            metadata={"user_id": str(user_id), "plan_tier": req.plan_tier, "billing_cycle": req.billing_cycle},
        )
        return {"checkout_url": session.url, "dev_mode": False}

    # --- dev mode: activate immediately, no payment -----------------------
    start, end = _period_bounds(req.billing_cycle)
    sub.plan_tier = req.plan_tier
    sub.billing_cycle = req.billing_cycle
    sub.status = "active"
    sub.current_period_start = start
    sub.current_period_end = end
    sub.cancel_at_period_end = False
    auth_user.plan_tier = req.plan_tier
    db.commit()
    print(f"[DEV MODE] Activated '{req.plan_tier}' ({req.billing_cycle}) for user_id={user_id} with no real payment.")
    from notify import notify
    notify(db, user_id, "billing", "Plan updated", f"You're now on the {PLAN_CATALOG[req.plan_tier]['name']} plan.", priority="medium")
    return {"checkout_url": None, "dev_mode": True, "subscription": _serialize_subscription(sub)}


@router.post("/cancel")
def cancel(req: CancelRequest, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    sub = _get_or_404(db, user_id)

    if STRIPE_ENABLED and sub.stripe_subscription_id:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=not req.immediately)
        if req.immediately:
            stripe.Subscription.delete(sub.stripe_subscription_id)

    if req.immediately:
        sub.status = "cancelled"
        sub.plan_tier = "trial"
    else:
        sub.cancel_at_period_end = True
    db.commit()
    return {"subscription": _serialize_subscription(sub)}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session | None = Depends(get_db_or_503)):
    """Stripe calls this. Not protected by X-API-Key (Stripe can't send
    it) - protected instead by verifying Stripe's own signature, which
    is the correct mechanism for webhooks."""
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=404, detail="Stripe is not configured on this server.")
    db = _require_db(db)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        # Covers both a malformed payload (ValueError) and a bad/missing
        # signature (stripe.error.SignatureVerificationError in older
        # SDKs, stripe.SignatureVerificationError in newer ones) without
        # pinning behavior to one SDK layout.
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.")

    obj = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        user_id = int(obj["metadata"]["user_id"])
        plan_tier = obj["metadata"]["plan_tier"]
        billing_cycle = obj["metadata"]["billing_cycle"]
        sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
        auth_user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if sub and auth_user:
            start, end = _period_bounds(billing_cycle)
            sub.plan_tier = plan_tier
            sub.billing_cycle = billing_cycle
            sub.status = "active"
            sub.current_period_start = start
            sub.current_period_end = end
            sub.stripe_subscription_id = obj.get("subscription")
            auth_user.plan_tier = plan_tier
            db.commit()

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.updated"):
        stripe_sub_id = obj["id"]
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
        if sub:
            if event["type"] == "customer.subscription.deleted":
                sub.status = "cancelled"
                sub.plan_tier = "trial"
            else:
                sub.status = obj.get("status", sub.status)
                sub.cancel_at_period_end = obj.get("cancel_at_period_end", sub.cancel_at_period_end)
            db.commit()

    elif event["type"] == "invoice.paid":
        user_id = None
        sub = db.query(Subscription).filter(Subscription.stripe_customer_id == obj.get("customer")).first()
        if sub:
            invoice = Invoice(
                user_id=sub.user_id,
                amount_cents=obj.get("amount_paid", 0),
                currency=obj.get("currency", "usd"),
                status="paid",
                description=obj.get("description") or f"{sub.plan_tier} plan",
                stripe_invoice_id=obj.get("id"),
            )
            db.add(invoice)
            db.commit()

    return {"received": True}
