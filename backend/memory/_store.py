"""Small, process-safe JSON persistence helpers for agent memory."""

from __future__ import annotations

import json
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

import config

_SCOPE_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_LOCK = threading.RLock()


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
    path = data_path(kind, user_id)
    with _LOCK:
        if not path.exists():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    return value if isinstance(value, list) else []


def write_records(kind: str, user_id: int | str | None, records: list[dict[str, Any]]) -> None:
    path = data_path(kind, user_id)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
            json.dump(records, handle, indent=2, default=str)
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
