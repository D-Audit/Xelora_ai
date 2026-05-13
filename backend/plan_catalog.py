"""
plan_catalog.py
Single source of truth for plan limits/pricing on the backend, mirrored
from the frontend's src/data/mock-plans.ts so the two never disagree
about what a tier is allowed to do. If you change a limit here, update
mock-plans.ts to match (see INTEGRATION.md).
"""

PLAN_CATALOG = {
    "trial": {
        "tier": "trial",
        "name": "Free Trial",
        "description": "Explore Xelora for 14 days with no commitment.",
        "monthly_price_cents": 0,
        "annual_price_cents": 0,
        "ai_actions_per_month": 30,
        "workflow_runs_per_month": 5,
        "max_file_size_mb": 5,
        "saved_workflows": 2,
        "cloud_storage_gb": 0,
        "devices": 1,
        "history_days": 7,
        "team_members": 1,
        "batch_processing": False,
        "api_access": False,
        "priority_support": False,
    },
    "starter": {
        "tier": "starter",
        "name": "Starter",
        "description": "For individuals getting started with spreadsheet automation.",
        "monthly_price_cents": 1200,
        "annual_price_cents": 900,
        "ai_actions_per_month": 300,
        "workflow_runs_per_month": 50,
        "max_file_size_mb": 25,
        "saved_workflows": 10,
        "cloud_storage_gb": 2,
        "devices": 2,
        "history_days": 30,
        "team_members": 1,
        "batch_processing": False,
        "api_access": False,
        "priority_support": False,
    },
    "professional": {
        "tier": "professional",
        "name": "Professional",
        "description": "For analysts and teams who need more power and collaboration.",
        "monthly_price_cents": 3500,
        "annual_price_cents": 2800,
        "ai_actions_per_month": 1500,
        "workflow_runs_per_month": 300,
        "max_file_size_mb": 100,
        "saved_workflows": 100,
        "cloud_storage_gb": 25,
        "devices": 5,
        "history_days": 90,
        "team_members": 5,
        "batch_processing": True,
        "api_access": True,
        "priority_support": True,
    },
    "business": {
        "tier": "business",
        "name": "Business",
        "description": "Custom limits, SSO, and dedicated support for larger teams.",
        "monthly_price_cents": None,
        "annual_price_cents": None,
        "ai_actions_per_month": None,   # None = "custom", negotiated
        "workflow_runs_per_month": None,
        "max_file_size_mb": None,
        "saved_workflows": None,
        "cloud_storage_gb": None,
        "devices": None,
        "history_days": None,
        "team_members": None,
        "batch_processing": True,
        "api_access": True,
        "priority_support": True,
    },
}

# Maps tier -> Stripe Price IDs, filled in from env at runtime by billing.py.
# Kept here so both billing.py and any future admin tooling read the same shape.
STRIPE_PRICE_ENV_VARS = {
    ("starter", "monthly"): "STRIPE_PRICE_STARTER_MONTHLY",
    ("starter", "annual"): "STRIPE_PRICE_STARTER_ANNUAL",
    ("professional", "monthly"): "STRIPE_PRICE_PROFESSIONAL_MONTHLY",
    ("professional", "annual"): "STRIPE_PRICE_PROFESSIONAL_ANNUAL",
}


def get_plan(tier: str) -> dict:
    plan = PLAN_CATALOG.get(tier)
    if not plan:
        raise ValueError(f"Unknown plan tier: {tier}")
    return plan
