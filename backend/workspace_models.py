"""
workspace_models.py
ADDITIVE ONLY - new tables covering the product areas the frontend
already has UI for (files, team, devices, notifications, workflows,
templates) but the original backend had no concept of. Registered on
the same Base as everything else; imported by server.py so
database.init_db() creates these tables too.

All tables key off AuthUser.id (auth_billing_models.py), same 1:1
extension pattern used there.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from database import Base


def _now():
    return datetime.now(timezone.utc)


class FileAsset(Base):
    __tablename__ = "file_assets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)

    name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # xlsx|xls|csv|ods|tsv
    size_mb = Column(Float, default=0.0)
    status = Column(String, default="ready")  # ready|processing|completed|needs_review|failed|archived
    storage_path = Column(String, nullable=False)
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    tags = Column(JSON, default=list)

    uploaded_at = Column(DateTime, default=_now)
    last_modified_at = Column(DateTime, default=_now, onupdate=_now)


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="draft")  # draft|published|archived|running
    steps = Column(JSON, default=list)  # list of {id, order, name, description, type, isEnabled, requiresApproval, errorBehaviour, estimatedAiActions}
    tags = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)

    success_rate = Column(Float, default=0.0)
    total_runs = Column(Integer, default=0)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String, nullable=True)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    runs = relationship("WorkflowRun", back_populates="workflow")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    file_id = Column(Integer, ForeignKey("file_assets.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)  # linked agent Task, if actually run

    status = Column(String, default="running")  # running|completed|completed_with_warnings|failed|cancelled|paused|awaiting_approval
    steps_completed = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    ai_actions_used = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)

    started_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)

    workflow = relationship("Workflow", back_populates="runs")


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="general")
    steps = Column(JSON, default=list)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)

    name = Column(String, nullable=False)
    os = Column(String, default="windows")  # windows|macos|linux
    app_version = Column(String, default="")
    region = Column(String, default="")
    status = Column(String, default="active")  # active|inactive|pending|removed
    is_primary = Column(Boolean, default=False)

    authorised_at = Column(DateTime, default=_now)
    last_active_at = Column(DateTime, default=_now, onupdate=_now)


class TeamMember(Base):
    """Single-owner-team model: owner_user_id is the account that
    invited this member. member_user_id is filled in once the invitee
    has (or creates) an account with a matching email."""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    member_user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=True)

    email = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, default="viewer")  # owner|administrator|editor|operator|viewer
    status = Column(String, default="invited")  # active|invited|suspended|removed

    invited_at = Column(DateTime, default=_now)
    joined_at = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)

    category = Column(String, default="account")  # workflow|billing|account|team|product
    title = Column(String, nullable=False)
    message = Column(Text, default="")
    priority = Column(String, default="low")  # low|medium|high
    is_read = Column(Boolean, default=False)
    action_url = Column(String, nullable=True)
    action_label = Column(String, nullable=True)

    created_at = Column(DateTime, default=_now)
