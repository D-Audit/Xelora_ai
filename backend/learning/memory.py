"""
learning/memory.py
Long-Term Memory capability: small, structured preferences the agent
remembers per user (report styles, color themes, favorite chart types,
frequently used formulas) - not a chat transcript, just durable facts
that change how future tasks get planned.
"""

import json
from sqlalchemy.orm import Session
from models import UserPreference


def set_preference(db: Session, user_id: int, category: str, key: str, value) -> UserPreference:
    existing = (
        db.query(UserPreference)
        .filter_by(user_id=user_id, category=category, key=key)
        .first()
    )
    value_json = json.dumps(value)
    if existing:
        existing.value = value_json
        db.commit()
        db.refresh(existing)
        return existing

    pref = UserPreference(user_id=user_id, category=category, key=key, value=value_json)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def get_preference(db: Session, user_id: int, category: str, key: str):
    pref = db.query(UserPreference).filter_by(user_id=user_id, category=category, key=key).first()
    return json.loads(pref.value) if pref else None


def get_all_preferences(db: Session, user_id: int) -> dict:
    """Returns everything remembered about a user, grouped by category -
    this is what gets folded into the system prompt so the agent's plan
    reflects the user's known preferences without them re-stating them."""
    prefs = db.query(UserPreference).filter_by(user_id=user_id).all()
    grouped = {}
    for p in prefs:
        grouped.setdefault(p.category, {})[p.key] = json.loads(p.value)
    return grouped
