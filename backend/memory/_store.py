"""Persistence for agent memory (skills, task history, chat memory).

One chokepoint with three backends, picked per call:
- remote: the desktop local agent reads/writes its user's memory through the
  cloud API (set by local_agent.py via ``use_remote``),
- database: the ``memory_records`` table whenever DATABASE_URL is configured,
- JSON files under MEMORY_STORE_DIR otherwise (single-PC installs, tests).
"""

from __future__ import annotations

import json
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

import config

_SCOPE_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_LOCK = threading.RLock()
_remote = None  # (reader, writer) when running as the desktop local agent


def use_remote(reader, writer) -> None:
    """Route all memory through the cloud (``reader(kind)``, ``writer(kind, records)``)."""
    global _remote
    _remote = (reader, writer) if reader and writer else None


def _database():
    from memory import records
    return records if records.available() else None


def _scope(user_id: int | str | None) -> str:
    value = "anonymous" if user_id is None else str(user_id)
    if not _SCOPE_RE.fullmatch(value):
        raise ValueError("user_id contains unsupported characters")
    return value


def data_path(kind: str, user_id: int | str | None) -> Path:
    if not _SCOPE_RE.fullmatch(kind):
        raise ValueError("memory store kind contains unsupported characters")
    return Path(config.MEMORY_STORE_DIR) / _scope(user_id) / f"{kind}.json"


def read_records(kind: str, user_id: int | str | None) -> list[dict[str, Any]]:
    if _remote is not None:
        data_path(kind, user_id)  # validates kind and scope
        value = _remote[0](kind)
        return value if isinstance(value, list) else []
    return read_stored(kind, user_id)


def read_stored(kind: str, user_id: int | str | None) -> list[dict[str, Any]]:
    """This process's own store (database or files), never the remote one.

    The cloud's /agent-link/memory endpoints use this so they serve their
    storage even when the same process also runs an agent (tests).
    """
    path = data_path(kind, user_id)  # also validates kind and scope
    db = _database()
    if db is not None:
        return db.read(kind, _scope(user_id))
    with _LOCK:
        if not path.exists():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    return value if isinstance(value, list) else []


_STOPWORDS = frozenset(
    "a an and are as at be by can could do for from how i in into is it its me my of on or our please "
    "should so that the their them then there these this to us was we what when where which who why "
    "will with would you your".split()
)


def keywords(text: str) -> set[str]:
    """Meaningful lowercase words, for matching a new request against stored memory."""
    return {word for word in re.findall(r"[a-z0-9]+", str(text or "").lower())
            if len(word) > 1 and word not in _STOPWORDS}


def cap_records(kind: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest entries (for skills: the most proven ones) within the configured limit."""
    limit = config.MEMORY_MAX_RECORDS.get(kind)
    if not limit or len(records) <= limit:
        return records
    if kind == "skills":
        def rank(skill):
            return (int(skill.get("success_count") or 0), skill.get("last_used") or skill.get("created_at") or 0)
        keep = {id(skill) for skill in sorted(records, key=rank, reverse=True)[:limit]}
        return [skill for skill in records if id(skill) in keep]
    return records[-limit:]


def update_records(kind: str, user_id: int | str | None, mutate: Callable[[list], Any]) -> Any:
    """Atomically read a list, let ``mutate`` change it in place, and save it.

    Two tasks finishing at once each append their own entry instead of one
    overwriting the other. Returns whatever ``mutate`` returns.
    """
    data_path(kind, user_id)  # validates kind and scope
    if _remote is None:
        db = _database()
        if db is not None:
            return db.update(kind, _scope(user_id), lambda records: (mutate(records), cap_records(kind, records)))
    with _LOCK:
        records = read_records(kind, user_id)
        result = mutate(records)
        write_records(kind, user_id, records)
        return result


def write_records(kind: str, user_id: int | str | None, records: list[dict[str, Any]]) -> None:
    records = cap_records(kind, records)
    if _remote is not None:
        data_path(kind, user_id)  # validates kind and scope
        _remote[1](kind, records)
        return
    write_stored(kind, user_id, records)


def write_stored(kind: str, user_id: int | str | None, records: list[dict[str, Any]]) -> None:
    """Counterpart of read_stored()."""
    path = data_path(kind, user_id)  # also validates kind and scope
    records = cap_records(kind, records)
    db = _database()
    if db is not None:
        db.write(kind, _scope(user_id), records)
        return
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
            json.dump(records, handle, indent=2, default=str)
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
