"""A fake Cua Driver: a real stdio MCP server with Cua-shaped tools.

Used only by tests to exercise Xelora's Cua adapter over the genuine MCP
transport. It performs no desktop input. Behaviour is selected with
environment variables:

FAKE_CUA_MODE   ok | verify_fails | verify_after_2 | verify_on_recheck | click_error | hang | malformed
FAKE_CUA_STATE  path to a JSON file used to count actions across sessions
"""
from __future__ import annotations

import json
import os
import time

from mcp.server.fastmcp import FastMCP

MODE = os.environ.get("FAKE_CUA_MODE", "ok")
STATE = os.environ.get("FAKE_CUA_STATE", "")
EXCEL = {"pid": 4242, "window_id": 7, "app": "Microsoft Excel", "title": "Book1 - Excel"}

if MODE == "hang":
    time.sleep(60)

server = FastMCP("fake-cua-driver")


def _bump(key: str) -> int:
    data = {}
    if STATE and os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as handle:
            data = json.load(handle)
    data[key] = data.get(key, 0) + 1
    if STATE:
        with open(STATE, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    return data[key]


@server.tool()
def list_windows(on_screen_only: bool = True) -> dict:
    """List top-level windows."""
    return {"windows": [EXCEL]}


@server.tool()
def get_window_state(pid: int, window_id: int, include_screenshot: bool = False) -> dict:
    """Return the accessibility tree of one window."""
    if (pid, window_id) != (EXCEL["pid"], EXCEL["window_id"]):
        raise ValueError("window not found")
    return {"pid": pid, "window_id": window_id, "elements": [{"index": 3, "role": "button", "name": "Sort"}]}


@server.tool()
def click(pid: int, window_id: int, element_index: int | None = None, x: float | None = None, y: float | None = None) -> dict:
    """Click an element or point in a window."""
    if MODE == "click_error":
        raise RuntimeError("element is not clickable")
    _bump("click")
    return {"delivered": True}


@server.tool()
def press_key(pid: int, window_id: int, key: str) -> dict:
    """Press one key in a window."""
    if MODE == "click_error":
        raise RuntimeError("keyboard input was rejected")
    _bump("press_key")
    return {"delivered": True}


@server.tool()
def set_value(pid: int, window_id: int, value: str, element_index: int | None = None) -> dict:
    """Set an accessibility value."""
    _bump("set_value")
    return {"delivered": True}


@server.tool()
def verify_state(pid: int, window_id: int, expect: list[dict], timeout_ms: int = 5000) -> dict:
    """Evaluate predicates against one window."""
    if MODE == "malformed":
        return {"unexpected": "shape"}
    if MODE == "verify_fails":
        return {"predicates": [{"status": "unsatisfied"}]}
    if MODE == "verify_after_2":
        clicks = 0
        if STATE and os.path.exists(STATE):
            with open(STATE, encoding="utf-8") as handle:
                clicks = json.load(handle).get("click", 0)
        return {"predicates": [{"status": "satisfied" if clicks >= 2 else "unknown"}]}
    if MODE == "verify_on_recheck":
        # The UI settles late: the first check is unsatisfied, later ones pass.
        checks = _bump("verify_state")
        return {"predicates": [{"status": "satisfied" if checks >= 2 else "unknown"}]}
    return {"predicates": [{"status": "satisfied"} for _ in expect]}


@server.tool()
def kill_app(pid: int) -> dict:
    """Not allowlisted by Xelora; must never be exposed."""
    return {"killed": pid}


if __name__ == "__main__":
    server.run()
