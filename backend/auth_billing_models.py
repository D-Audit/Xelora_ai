"""
auth_billing_models.py
ADDITIVE ONLY - new tables for web auth + subscriptions. Nothing in
models.py is modified. These tables are registered on the SAME
SQLAlchemy `Base` from database.py, so they're created automatically
by database.init_db() (which does `import models` then
`Base.metadata.create_all()`) as long as this module has been
imported first - server.py imports it at startup for exactly that
reason.

Design note on the User link:
  models.User (in models.py) is the table agent Task/UserPreference
  rows already point to via ForeignKey("users.id"). Rather than forking
  a second, disconnected "users" concept (which would break those FKs
  the moment a web-registered user submits an agent task), AuthUser is
  a 1:1 *extension* of models.User: AuthUser.id IS models.User.id
  (shared primary key, FK'd back to users.id). Registration creates
  both rows in the same transaction. This keeps models.py untouched
  while giving every web user a real, working agent user_id.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from database import Base


def _now():
    return datetime.now(timezone.utc)


class AuthUser(Base):
    """Password + role + plan extension of models.User."""
    __tablename__ = "auth_users"

    id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    plan_tier = Column(String, default="trial", nullable=False)  # trial|starter|professional|business
    created_at = Column(DateTime, default=_now)

    subscription = relationship("Subscription", back_populates="auth_user", uselist=False)
    usage_records = relationship("UsageRecord", back_populates="auth_user")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False, unique=True)

    plan_tier = Column(String, default="trial", nullable=False)
    billing_cycle = Column(String, default="monthly")  # monthly|annual
    status = Column(String, default="trialing")  # active|trialing|cancelled|past_due|paused
    current_period_start = Column(DateTime, default=_now)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    trial_ends_at = Column(DateTime, nullable=True)

    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)

    updated_at = Column(DateTime, default=_now, onupdate=_now)

    auth_user = relationship("AuthUser", back_populates="subscription")


class UsageRecord(Base):
    """One row per user per billing period. Incremented by plan_guard
    on every action that counts against a plan limit."""
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)

    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    ai_actions_used = Column(Integer, default=0)
    workflow_runs_used = Column(Integer, default=0)

    auth_user = relationship("AuthUser", back_populates="usage_records")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)

    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="usd")
    status = Column(String, default="paid")  # paid|pending|failed|refunded
    description = Column(String, nullable=True)

    stripe_invoice_id = Column(String, nullable=True)

    issued_at = Column(DateTime, default=_now)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
