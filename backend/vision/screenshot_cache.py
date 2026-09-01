"""Small in-memory cache for recent OmniParser screen results.

The cache is deliberately process-local: screen parses describe a live Excel
window and must never be reused after a backend restart or written to disk.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from threading import RLock
from time import monotonic
from typing import Any


_CACHE_TTL_SECONDS = 20.0
_cache: dict[tuple[str, str], dict[str, Any]] = {}
_latest_by_zone: dict[str, dict[str, Any]] = {}
_lock = RLock()


def _key(image_bytes: bytes, zone: str) -> tuple[str, str]:
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise TypeError("image_bytes must be bytes")
    return zone, sha256(bytes(image_bytes)).hexdigest()


def _is_fresh(entry: dict[str, Any]) -> bool:
    return monotonic() - entry["created_at"] <= _CACHE_TTL_SECONDS


def _prune_expired() -> None:
    expired = [key for key, value in _cache.items() if not _is_fresh(value)]
    for key in expired:
        _cache.pop(key, None)
    for zone, value in list(_latest_by_zone.items()):
        if not _is_fresh(value):
            _latest_by_zone.pop(zone, None)


def save_to_cache(image_bytes: bytes, parsed: dict[str, Any], zone: str) -> None:
    """Cache one verified parse result for the exact captured screen image."""
    if not isinstance(parsed, dict):
        raise TypeError("parsed must be a dictionary")
    if not isinstance(zone, str) or not zone:
        raise ValueError("zone must be a non-empty string")

    data = deepcopy(parsed)
    # The parser itself does not know which Excel region was cropped.  Keep
    # that context beside every element so a later caller can safely reuse a
    # cached Ribbon result without confusing it with a popup or worksheet
    # result.
    elements = data.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if isinstance(element, dict):
                element.setdefault("context", zone)

    entry = {
        "created_at": monotonic(),
        "data": data,
    }
    with _lock:
        _prune_expired()
        _cache[_key(image_bytes, zone)] = entry
        _latest_by_zone[zone] = entry


def load_from_cache(image_bytes: bytes, zone: str) -> dict[str, Any] | None:
    """Return a fresh result only when the current image exactly matches."""
    with _lock:
        _prune_expired()
        entry = _cache.get(_key(image_bytes, zone))
        return deepcopy(entry["data"]) if entry and _is_fresh(entry) else None


def _element_text(element: dict[str, Any]) -> str:
    values = (
        element.get("description"),
        element.get("text"),
        element.get("label"),
        element.get("name"),
        element.get("type"),
        element.get("role"),
        element.get("context"),
    )
    return " ".join(str(value) for value in values if value is not None).lower()


def find_cached_elements(text: str, context: str = "") -> list[dict[str, Any]]:
    """Find OCR/UI elements in the most recent fresh parse.

    ``context`` is an optional second text filter; returning copies prevents a
    caller from changing cached coordinates or descriptions in place.
    """
    query = " ".join(str(text).lower().split())
    context_query = " ".join(str(context).lower().split())
    if not query:
        return []

    with _lock:
        _prune_expired()
        entries = sorted(
            _latest_by_zone.values(),
            key=lambda entry: entry["created_at"],
            reverse=True,
        )
        for entry in entries:
            elements = entry["data"].get("elements", [])
            matches = [
                deepcopy(element)
                for element in elements
                if isinstance(element, dict)
                and query in _element_text(element)
                and (not context_query or context_query in _element_text(element))
            ]
            if matches:
                return matches
    return []


def get_cached_screen_context(zone: str | None = None) -> dict[str, Any] | None:
    """Return metadata from the newest fresh parse, without image bytes."""
    with _lock:
        _prune_expired()
        candidates = (
            [(_latest_by_zone.get(zone), zone)]
            if zone
            else [(entry, entry_zone) for entry_zone, entry in _latest_by_zone.items()]
        )
        candidates = [item for item in candidates if item[0] is not None]
        if not candidates:
            return None
        entry, entry_zone = max(candidates, key=lambda item: item[0]["created_at"])
        data = deepcopy(entry["data"])
        return {
            "zone": entry_zone,
            "age_seconds": round(monotonic() - entry["created_at"], 3),
            "elements": data.get("elements", []),
            "element_count": len(data.get("elements", [])),
            "window": data.get("window"),
        }
