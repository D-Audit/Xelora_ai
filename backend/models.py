"""
models.py
The database tables.

New compared to the v2 backend:
- ActionLog now records WHICH execution layer handled a step (skill /
  codegen / visual) and the actual generated code, if any - this is
  what both "Reveal Workflow" and pattern-mining read from.
- UserPreference: long-term memory (Long-Term Memory capability).
- WorkflowPattern: detected recurring action sequences (Workflow
  Learning & Pattern Recognition / Continuous Skill Learning).
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=_now)

    tasks = relationship("Task", back_populates="user")
    preferences = relationship("UserPreference", back_populates="user")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    instruction = Column(Text, nullable=False)
    status = Column(String, default="running")
    created_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)
    # Real chat history (not mock data): a JSON-encoded list of
    # {role, text, timestamp} turns - see AgentTask.chat_transcript in
    # agent/core.py, which is what actually gets written here after each
    # run. Powers GET /tasks and GET /tasks/{id} for the chat sidebar.
    transcript = Column(Text, nullable=True)
    # The full raw provider-format conversation (task.messages), needed
    # to genuinely RESUME a task after a server restart - not just show
    # a read-only transcript. transcript above is a simplified display
    # copy; this is the real working memory the AI needs back to
    # actually continue the conversation. See main.py's
    # _get_or_reconstruct_task().
    raw_messages = Column(Text, nullable=True)
    # Needed to correctly rebind the Excel workbook context when
    # reconstructing a task from the DB (see agent/core.py's
    # bind_workbook_context) - previously only lived in the in-memory
    # AgentTask object, lost on restart along with everything else.
    workbook_name = Column(String, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="tasks")
    steps = relationship("ActionLog", back_populates="task")


class ActionLog(Base):
    """
    One row per action the agent took. This is the single source of
    truth that both Reveal Workflow (human-readable replay) and the
    pattern miner (skill promotion) are built on top of.
    """
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))

    action_name = Column(String, nullable=False)
    execution_layer = Column(String, nullable=False)
    input_params = Column(Text, nullable=True)
    generated_code = Column(Text, nullable=True)

    result = Column(Text, nullable=True)
    verified = Column(Boolean, default=False)
    verification_note = Column(Text, nullable=True)
    status = Column(String, default="success")

    created_at = Column(DateTime, default=_now)

    task = relationship("Task", back_populates="steps")


class UserPreference(Base):
    """
    Long-Term Memory: small, structured facts the agent has learned
    about how a specific user likes their work done. Not a chat log -
    just durable key/value settings.
    """
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="preferences")


class WorkflowPattern(Base):
    """
    A recurring sequence of actions detected across a user's task
    history. Once a pattern's occurrence count crosses a threshold,
    it becomes a candidate for promotion into the skill library
    (Continuous Skill Learning).
    """
    __tablename__ = "workflow_patterns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action_sequence = Column(Text, nullable=False)
    occurrence_count = Column(Integer, default=1)
    promoted_to_skill = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=_now)
    last_seen = Column(DateTime, default=_now)
