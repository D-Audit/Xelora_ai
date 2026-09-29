"""Structured, secret-safe audit log lines for agent tool execution.

Every tool decision and result is emitted on the ``xelora.audit`` logger as
one JSON object, so a developer can trace task -> capability -> permission ->
result -> verification without a debugger. Values under credential-looking
keys are masked and long values are truncated; file contents and page text
are never logged in full.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

_LOGGER = logging.getLogger("xelora.audit")
_SECRET_KEY = re.compile(r"(pass(word)?|secret|token|api[_-]?key|authorization|cookie|credential)", re.I)
_SECRET_VALUE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
_MAX_STRING = 300


def redact(value: Any, depth: int = 0) -> Any:
    """Mask secrets and bound size, recursively."""
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {
            str(key): "***" if _SECRET_KEY.search(str(key)) else redact(item, depth + 1)
            for key, item in list(value.items())[:40]
        }
    if isinstance(value, (list, tuple)):
        items = [redact(item, depth + 1) for item in list(value)[:20]]
        return items + ["…"] if len(value) > 20 else items
    if isinstance(value, str):
        masked = _SECRET_VALUE.sub("***", value)
        return masked if len(masked) <= _MAX_STRING else masked[:_MAX_STRING] + f"…(+{len(masked) - _MAX_STRING} chars)"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact(str(value), depth + 1)


def record(event: str, **fields: Any) -> None:
    """Emit one audit event. Never raises into the task loop."""
    try:
        _LOGGER.info(json.dumps({"event": event, **redact(fields)}, default=str, ensure_ascii=False))
    except Exception:  # pragma: no cover - logging must not break execution
        pass


def result_summary(result: Any) -> dict[str, Any]:
    """The audit-relevant subset of a tool result (no payload bodies)."""
    if not isinstance(result, dict):
        return {"type": type(result).__name__}
    keys = ("status", "verified", "error", "exit_code", "timed_out", "retryable", "path", "url", "driver_tool")
    return {key: result[key] for key in keys if key in result}
