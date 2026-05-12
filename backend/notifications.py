"""notifications.py - ADDITIVE ONLY."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from workspace_models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "category": n.category,
        "title": n.title,
        "message": n.message,
        "priority": n.priority,
        "isRead": n.is_read,
        "actionUrl": n.action_url,
        "actionLabel": n.action_label,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
def list_notifications(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    items = db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(100).all()
    return {"notifications": [_serialize(n) for n in items]}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    n = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found.")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read.is_(False)).update({"is_read": True})
    db.commit()
    return {"ok": True}
