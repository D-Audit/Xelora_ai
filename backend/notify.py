"""notify.py - tiny helper used by several routers to drop a
notification row for a user. Kept separate to avoid circular imports
between billing.py, workflows.py, auth.py, etc."""
from sqlalchemy.orm import Session
from workspace_models import Notification


def notify(
    db: Session,
    user_id: int,
    category: str,
    title: str,
    message: str,
    priority: str = "low",
    action_url: str | None = None,
    action_label: str | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            category=category,
            title=title,
            message=message,
            priority=priority,
            action_url=action_url,
            action_label=action_label,
        )
    )
    db.commit()
