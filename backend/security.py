"""
security.py
Cross-cutting security helpers used by main.py. Kept in one file so
every endpoint goes through the same checks rather than each route
hand-rolling its own.

What this covers:
  - API key check: constant-time comparison (secrets.compare_digest)
    instead of `!=`, which leaks timing information about how many
    leading characters matched. Also refuses to boot wide-open unless
    ALLOW_NO_AUTH is explicitly set.
  - Rate limiting: a simple in-memory sliding window per API key (or
    IP if no key). This is NOT a substitute for a real reverse-proxy
    rate limiter in production (it resets on restart and doesn't share
    state across multiple server processes) - it's a baseline so a
    single misbehaving client can't hammer the Excel-automation and
    LLM-calling endpoints into the ground.
  - Path validation: confines file_path/image_path style inputs to a
    configured directory, so a request can't read or write arbitrary
    files elsewhere on disk (path traversal / arbitrary file access).
"""

import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

import config


def check_api_key(x_api_key: str = Header(default="")):
    """Raises 401 on a bad/missing key. If no key is configured at all,
    raises 500 UNLESS ALLOW_NO_AUTH=true - silently running wide open
    because someone forgot to set an env var is exactly the failure
    mode worth refusing to allow by default."""
    if not config.LOCAL_API_KEY:
        if config.ALLOW_NO_AUTH:
            return
        raise HTTPException(
            status_code=500,
            detail="LOCAL_API_KEY is not set. Set it in .env, or set ALLOW_NO_AUTH=true "
                   "if you specifically intend to run this without authentication (e.g. "
                   "local-only testing).",
        )
    if not secrets.compare_digest(x_api_key, config.LOCAL_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# --- Rate limiting -----------------------------------------------------
# key -> deque of request timestamps within the current window
_request_log: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, x_api_key: str = Header(default="")):
    """Call as a FastAPI dependency alongside check_api_key. Keys the
    limit by API key when present, falling back to client IP - so an
    unauthenticated request still gets rate-limited rather than bypassing
    the limit entirely."""
    key = x_api_key or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    window = config.RATE_LIMIT_WINDOW_SECONDS
    log = _request_log[key]

    while log and now - log[0] > window:
        log.popleft()

    if len(log) >= config.RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {config.RATE_LIMIT_MAX_REQUESTS} requests "
                   f"per {window}s. Try again shortly.",
        )
    log.append(now)


def validate_ingest_path(file_path: str) -> str:
    """Resolves file_path and confirms it's inside
    config.KNOWLEDGE_INGEST_ALLOWED_DIR - blocks '../' traversal and
    absolute paths pointing anywhere else on disk. Returns the resolved
    path if valid; raises HTTPException(400) otherwise."""
    allowed_root = os.path.realpath(config.KNOWLEDGE_INGEST_ALLOWED_DIR)
    resolved = os.path.realpath(os.path.join(allowed_root, file_path) if not os.path.isabs(file_path) else file_path)

    if os.path.commonpath([allowed_root, resolved]) != allowed_root:
        raise HTTPException(
            status_code=400,
            detail=f"file_path must be inside {allowed_root} - refusing to read files "
                   f"outside the allowed ingestion directory.",
        )
    return resolved
