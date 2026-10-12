"""Database table behind memory/_store.py when DATABASE_URL is set.

Hosts such as Render's free tier wipe local disk on every restart, so learned
skills, task history and chat memory live in Postgres instead of JSON files.
One row holds one (kind, scope) record list, mirroring the file layout.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError

import database
from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MemoryRecord(Base):
    __tablename__ = "memory_records"
    __table_args__ = (UniqueConstraint("kind", "scope", name="uq_memory_records_kind_scope"),)

    id = Column(Integer, primary_key=True)
    kind = Column(String(80), nullable=False)
    scope = Column(String(80), nullable=False, index=True)
    data = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime, default=_now, onupdate=_now)


def available() -> bool:
    return database.SessionLocal is not None


def read(kind: str, scope: str) -> list:
    db = database.SessionLocal()
    try:
        row = db.query(MemoryRecord).filter_by(kind=kind, scope=scope).first()
        value = json.loads(row.data) if row else []
        return value if isinstance(value, list) else []
    finally:
        db.close()


def write(kind: str, scope: str, records: list) -> None:
    data = json.dumps(records, default=str)
    db = database.SessionLocal()
    try:
        row = db.query(MemoryRecord).filter_by(kind=kind, scope=scope).with_for_update().first()
        if row is None:
            db.add(MemoryRecord(kind=kind, scope=scope, data=data))
        else:
            row.data = data
        db.commit()
    finally:
        db.close()


def update(kind: str, scope: str, mutate: Callable[[list], tuple[Any, list]]) -> Any:
    """Read-modify-write one row under a row lock. ``mutate`` returns (result, records)."""
    for attempt in range(2):
        db = database.SessionLocal()
        try:
            row = db.query(MemoryRecord).filter_by(kind=kind, scope=scope).with_for_update().first()
            value = json.loads(row.data) if row else []
            records = value if isinstance(value, list) else []
            result, records = mutate(records)
            data = json.dumps(records, default=str)
            if row is None:
                db.add(MemoryRecord(kind=kind, scope=scope, data=data))
            else:
                row.data = data
            db.commit()
            return result
        except IntegrityError:
            db.rollback()  # another writer created the row first; retry against it
            if attempt:
                raise
        finally:
            db.close()
