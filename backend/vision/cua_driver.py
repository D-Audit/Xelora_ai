"""Optional, schema-discovered client for a local Cua Driver MCP process.

The adapter does not implement or emulate computer control. It starts the
configured Cua Driver (``cua-driver mcp``), discovers its actual MCP tools, and
forwards only a small reviewed desktop tool allowlist. The Driver must run on
the same desktop host as the target application.

Safety model (enforced here, not in prompts):

* Input actions must name an exact ``pid`` + ``window_id`` that this task has
  already observed with ``get_window_state`` (observe before act). Desktop
  scope / raw screen coordinates are refused unless CUA_ALLOW_DESKTOP_SCOPE.
* When the task is bound to an Excel process, input may only target that
  process unless CUA_ALLOW_OTHER_APPS is enabled.
* An input action is never "verified" by the Driver's acknowledgement; only a
  ``verify_state`` with every predicate satisfied counts. ``act_and_verify``
  runs action -> verify in one session with a bounded number of attempts.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

import config
from tools import mcp_client

_LOGGER = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 15
_DISCOVERY_TIMEOUT_SECONDS = 8
_CALL_TIMEOUT_SECONDS = 30
_MAX_ACT_ATTEMPTS = 3
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"expires": 0.0, "tools": [], "error": None}
# Screenshot is deliberately absent: Xelora keeps its own native window
# capture and OmniParser fallback, and structured Cua observation tools
# (get_window_state / verify_state) are preferred over pixels.
# get_window_state can still include a window screenshot when asked.
_ALLOWED_NAMES = {
    "list_apps", "list_windows", "get_desktop_state", "get_screen_size",
    "get_cursor_position", "get_window_state", "verify_state", "move_cursor",
    "set_window_frame", "invoke_menu", "click", "double_click", "right_click",
    "drag", "scroll", "type_text", "press_key", "hotkey", "set_value",
    "clipboard_read", "clipboard_write",
}
_READ_TOOLS = {
    "list_apps", "list_windows", "get_desktop_state", "get_screen_size",
    "get_cursor_position", "get_window_state", "verify_state", "clipboard_read",
}
# Tools that deliver input to a window and therefore need an observed target.
_TARGETED_INPUT_TOOLS = {
    "click", "double_click", "right_click", "drag", "scroll", "type_text",
    "press_key", "hotkey", "set_value", "invoke_menu", "set_window_frame",
}
# Tools that act on the whole desktop by definition.
_DESKTOP_INPUT_TOOLS = {"move_cursor"}
# Input whose effect stacks when delivered twice (typing "abc" again gives
# "abcabc", Enter moves another row). act_and_verify sends these once and only
# re-checks the postcondition on later attempts.
_NON_REPEATABLE_INPUT = {"type_text", "press_key", "hotkey", "invoke_menu", "drag", "scroll"}
_HEALTH_CACHE: dict[str, Any] = {"expires": 0.0, "health": None}
_HEALTH_CACHE_LOCK = threading.Lock()
_HEALTH_CACHE_TTL_SECONDS = 10


def _flag(name: str) -> bool:
    return str(getattr(config, name, os.getenv(name, "false"))).strip().lower() in {"1", "true", "yes"}


def _command() -> tuple[str, list[str]]:
    command = (config.CUA_DRIVER_COMMAND or os.getenv("CUA_DRIVER_COMMAND", "cua-driver")).strip()
    raw_args = config.CUA_DRIVER_ARGS or os.getenv("CUA_DRIVER_ARGS", "mcp")
    args = shlex.split(raw_args, posix=sys.platform != "win32")
    if not command:
        raise RuntimeError("CUA_DRIVER_COMMAND is empty.")
    resolved = shutil.which(command)
    if resolved is None and os.path.isfile(command):
        # Absolute (or CWD-relative) path support for installations outside PATH.
        resolved = os.path.abspath(command)
    if resolved is None:
        raise FileNotFoundError(f"Cua Driver executable '{command}' was not found on PATH.")
    return resolved, args


def _server() -> mcp_client.StdioServer:
    command, args = _command()
    return mcp_client.StdioServer(command=command, args=args)


def _normalize_name(name: str) -> str:
    return "cua__" + re.sub(r"[^A-Za-z0-9_]", "_", name)


def _driver_version_output() -> str | None:
    """Run ``cua-driver --version`` once so health reports the real binary."""
    try:
        command, _ = _command()
    except (RuntimeError, FileNotFoundError):
        return None
    try:
        completed = subprocess.run(
            [command, "--version"], capture_output=True, text=True,
            timeout=5, check=False, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return output.splitlines()[0][:120] if output else None


def _platform_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def health_check(*, force_refresh: bool = False) -> dict[str, Any]:
    """Report whether the local Cua Driver is installed, enabled, and usable.

    Never sends desktop input: it combines configuration, the executable
    lookup, the CLI-reported version, and a live MCP tool discovery.
    Safe to call from a status endpoint on any platform.
    """
    now = time.monotonic()
    with _HEALTH_CACHE_LOCK:
        if not force_refresh and now < _HEALTH_CACHE["expires"] and _HEALTH_CACHE["health"] is not None:
            return dict(_HEALTH_CACHE["health"])

    health: dict[str, Any] = {
        "enabled": bool(config.ENABLE_CUA_DRIVER),
        "platform": _platform_name(),
        "supported_platforms": ["windows", "macos", "linux"],
        "command": (config.CUA_DRIVER_COMMAND or os.getenv("CUA_DRIVER_COMMAND", "cua-driver")).strip() or "cua-driver",
        "args": config.CUA_DRIVER_ARGS or os.getenv("CUA_DRIVER_ARGS", "mcp"),
        "executable_found": False,
        "version": None,
        "mcp_reachable": False,
        "tool_count": 0,
        "status": "disabled",
        "errors": [],
        "setup_hint": "Set ENABLE_CUA_DRIVER=true in backend/.env and restart the backend to activate Cua desktop control.",
    }
    if config.ENABLE_CUA_DRIVER:
        health["status"] = "unavailable"
        health["setup_hint"] = ""
        try:
            _command()
            health["executable_found"] = True
            health["version"] = _driver_version_output()
        except (RuntimeError, FileNotFoundError) as exc:
            health["errors"].append(str(exc))
            health["setup_hint"] = (
                "Install the Cua Driver on this desktop host (Windows PowerShell: "
                "irm https://cua.ai/driver/install.ps1 | iex), or point CUA_DRIVER_COMMAND "
                "at its absolute location. Then run 'cua-driver doctor'."
            )
        if health["executable_found"]:
            discovery = discover_tools(force_refresh=True)
            health["mcp_reachable"] = not discovery["error"] and bool(discovery["tools"])
            health["tool_count"] = len(discovery["tools"])
            if discovery["error"]:
                health["errors"].append(discovery["error"])
                health["setup_hint"] = (
                    "The Cua Driver is installed but its MCP server did not answer. Make sure the "
                    "daemon runs in the interactive desktop session ('cua-driver status'; on Windows "
                    "'cua-driver autostart kick'), then run 'cua-driver doctor'."
                )
            else:
                health["status"] = "ready"
                health["tools"] = [item["name"] for item in discovery["tools"]]

    with _HEALTH_CACHE_LOCK:
        _HEALTH_CACHE.update({"expires": time.monotonic() + _HEALTH_CACHE_TTL_SECONDS, "health": health})
    return dict(health)


def _allowlisted(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools = []
    for schema in schemas:
        name = schema.get("name")
        if name in _ALLOWED_NAMES:
            tools.append({
                "name": _normalize_name(name),
                "driver_name": name,
                "description": str(schema.get("description") or f"Cua Driver {name} operation.")[:1024],
                "input_schema": schema.get("inputSchema") or {"type": "object", "properties": {}},
                "risk": "read" if name in _READ_TOOLS else "write",
            })
    return tools


def discover_tools(*, force_refresh: bool = False) -> dict[str, Any]:
    """Return live Cua MCP tools, cached briefly to avoid spawning per model turn."""
    if not config.ENABLE_CUA_DRIVER:
        return {"enabled": False, "tools": [], "error": "Cua Driver integration is disabled."}
    now = time.monotonic()
    with _CACHE_LOCK:
        if not force_refresh and now < _CACHE["expires"]:
            return {"enabled": True, "tools": list(_CACHE["tools"]), "error": _CACHE["error"]}
    try:
        schemas, _ = mcp_client.run_session(_server(), list_tools=True, timeout_seconds=_DISCOVERY_TIMEOUT_SECONDS)
        tools, error = _allowlisted(schemas or []), None
    except BaseException as exc:  # noqa: BLE001 - includes anyio ExceptionGroups
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        tools, error = [], mcp_client.describe_error(exc)
        _LOGGER.warning("Cua Driver discovery failed: %s", error)
    with _CACHE_LOCK:
        _CACHE.update({"expires": now + (2 if error else _CACHE_TTL_SECONDS), "tools": tools, "error": error})
    return {"enabled": True, "tools": list(tools), "error": error}


def _payload(structured: Any, blocks: list[dict[str, Any]]) -> Any:
    if structured is not None:
        return structured
    for block in blocks:
        text = str(block.get("text") or "").strip()
        try:
            return json.loads(text)
        except (TypeError, json.JSONDecodeError):
            continue
    return None


def _verification_passed(structured: Any, blocks: list[dict[str, Any]]) -> bool:
    """Only treat explicit satisfied Cua predicates as postcondition success.

    ``unknown`` or ``unsatisfied`` anywhere means not verified, matching the
    Driver's contract that unknown findings never imply success.
    """
    statuses: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str):
                statuses.append(status.lower())
            satisfied = value.get("satisfied")
            if isinstance(satisfied, bool):
                statuses.append("satisfied" if satisfied else "unsatisfied")
            for child in value.values():
                if isinstance(child, (dict, list)):
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(_payload(structured, blocks))
    return bool(statuses) and all(status == "satisfied" for status in statuses)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def target_of(arguments: dict[str, Any]) -> tuple[int, int] | None:
    pid, window_id = _as_int(arguments.get("pid")), _as_int(arguments.get("window_id"))
    return (pid, window_id) if pid is not None and window_id is not None else None


def check_target(
    driver_name: str,
    arguments: dict[str, Any],
    *,
    observed_targets: set[tuple[int, int]] | None,
    bound_pid: int | None = None,
) -> dict[str, Any] | None:
    """Return a refusal result when an input action could hit the wrong window.

    ``observed_targets`` holds (pid, window_id) pairs this task has inspected
    with get_window_state. ``None`` disables the observe-first rule (used only
    by direct adapter calls outside a task, e.g. diagnostics).
    """
    if driver_name in _READ_TOOLS or driver_name == "clipboard_write":
        return None
    desktop_scope = str(arguments.get("scope") or "").lower() == "desktop" or driver_name in _DESKTOP_INPUT_TOOLS
    if desktop_scope:
        if _flag("CUA_ALLOW_DESKTOP_SCOPE"):
            return None
        return {
            "verified": False, "status": "target_not_allowed",
            "error": "Desktop-scoped Cua input is disabled. Target an exact pid and window_id observed with get_window_state.",
        }
    if driver_name not in _TARGETED_INPUT_TOOLS:
        return {"verified": False, "status": "unsupported_tool", "error": f"Cua tool '{driver_name}' has no reviewed targeting rule."}
    target = target_of(arguments)
    if target is None:
        return {
            "verified": False, "status": "target_required",
            "error": "Cua input actions must include the exact pid and window_id of the target window.",
        }
    if bound_pid is not None and target[0] != bound_pid and not _flag("CUA_ALLOW_OTHER_APPS"):
        return {
            "verified": False, "status": "wrong_window",
            "error": f"This task is bound to Excel process {bound_pid}; refusing Cua input to process {target[0]}.",
        }
    if observed_targets is not None and target not in observed_targets:
        return {
            "verified": False, "status": "target_not_observed",
            "error": "Call cua__get_window_state for this pid/window_id before acting on it (observe before act).",
        }
    return None


def _result_for(driver_name: str, raw: dict[str, Any]) -> dict[str, Any]:
    blocks, structured, failed = raw["content"], raw["structured_content"], raw["is_error"]
    is_read = driver_name in _READ_TOOLS
    if driver_name == "verify_state":
        passed = not failed and _verification_passed(structured, blocks)
        status = "driver_error" if failed else "verified" if passed else "verification_failed"
        verified: bool | None = passed
        note = "Cua state predicates are satisfied." if passed else "Cua state predicates are unsatisfied or unknown."
    elif failed:
        status, verified, note = "driver_error", False, "The Cua Driver reported an error."
    elif is_read:
        status, verified, note = "observed", True, "Cua returned structured observation."
    else:
        status, verified = "action_dispatched", None
        note = "Cua accepted the action; Xelora must verify the requested postcondition with verify_state."
    result = {
        "status": status, "verified": verified, "driver_tool": driver_name,
        "structured_content": structured, "content": blocks, "verification_note": note,
    }
    if failed:
        result["error"] = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")[:1000] or "Cua Driver error."
    return result


def _live_driver_name(tool_name: str) -> tuple[str | None, dict[str, Any] | None]:
    discovered = discover_tools()
    spec = next((item for item in discovered["tools"] if item["driver_name"] == tool_name), None)
    if spec is None:
        return None, {
            "verified": False, "status": "unavailable",
            "error": discovered["error"] or f"Cua tool '{tool_name}' is not offered by the running Driver.",
        }
    return spec["driver_name"], None


def call_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    observed_targets: set[tuple[int, int]] | None = None,
    bound_pid: int | None = None,
) -> dict[str, Any]:
    """Invoke one allowlisted Cua tool through a fresh, bounded stdio session."""
    if not config.ENABLE_CUA_DRIVER:
        return {"verified": False, "status": "disabled", "error": "Cua Driver integration is disabled."}
    if not isinstance(arguments, dict):
        return {"verified": False, "status": "invalid_arguments", "error": "Cua arguments must be an object."}
    driver_name, unavailable = _live_driver_name(tool_name)
    if unavailable:
        return unavailable
    refusal = check_target(driver_name, arguments, observed_targets=observed_targets, bound_pid=bound_pid)
    if refusal:
        return refusal
    try:
        _, results = mcp_client.run_session(_server(), [(driver_name, arguments)], timeout_seconds=_CALL_TIMEOUT_SECONDS)
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return {"verified": False, "status": "driver_error", "retryable": True, "error": mcp_client.describe_error(exc)}
    try:
        return _result_for(driver_name, results[0])
    except (KeyError, IndexError, TypeError) as exc:
        return {"verified": False, "status": "malformed_response", "error": f"Cua Driver returned an unexpected response: {exc}"}


def act_and_verify(
    action: str,
    arguments: dict[str, Any],
    expect: list[Any],
    *,
    max_attempts: int = 2,
    timeout_ms: int = 5000,
    observed_targets: set[tuple[int, int]] | None = None,
    bound_pid: int | None = None,
) -> dict[str, Any]:
    """Observe-act-verify with bounded retries in one Driver session per attempt.

    Each attempt: send ``action`` then ``verify_state`` with ``expect`` on the
    same pid/window_id. Stops at the first satisfied verification. A
    repeatable action (click, set_value, ...) is re-sent only if verification
    failed *and* attempts remain; input in ``_NON_REPEATABLE_INPUT`` is sent
    at most once and later attempts only re-check. Never loops beyond
    ``_MAX_ACT_ATTEMPTS``.
    """
    if not config.ENABLE_CUA_DRIVER:
        return {"verified": False, "status": "disabled", "error": "Cua Driver integration is disabled."}
    if not isinstance(arguments, dict) or not isinstance(expect, list) or not expect:
        return {"verified": False, "status": "invalid_arguments", "error": "Provide arguments (object) and a non-empty expect list."}
    driver_action, unavailable = _live_driver_name(action)
    if unavailable:
        return unavailable
    if driver_action in _READ_TOOLS:
        return {"verified": False, "status": "invalid_arguments", "error": "act_and_verify needs an input action, not an observation tool."}
    verify_name, unavailable = _live_driver_name("verify_state")
    if unavailable:
        return {**unavailable, "error": "The running Cua Driver does not offer verify_state, so actions cannot be verified."}
    refusal = check_target(driver_action, arguments, observed_targets=observed_targets, bound_pid=bound_pid)
    if refusal:
        return refusal
    target = target_of(arguments)
    if target is None:
        return {"verified": False, "status": "target_required",
                "error": "act_and_verify needs an exact pid and window_id so verify_state can check the same window."}
    verify_args = {"pid": target[0], "window_id": target[1], "expect": expect, "timeout_ms": max(100, min(int(timeout_ms), 30_000))}
    attempts = max(1, min(int(max_attempts), _MAX_ACT_ATTEMPTS))
    history: list[dict[str, Any]] = []
    repeatable = driver_action not in _NON_REPEATABLE_INPUT
    action_sent = False
    action_delivered = False
    for attempt in range(1, attempts + 1):
        # A transport error may hit after the input was delivered, so a
        # non-repeatable action is never re-sent once a send was attempted.
        send_action = repeatable or not action_sent
        calls = [(driver_action, arguments)] if send_action else []
        calls.append((verify_name, verify_args))
        action_sent = action_sent or send_action
        try:
            _, raw_results = mcp_client.run_session(_server(), calls, timeout_seconds=_CALL_TIMEOUT_SECONDS)
            action_result = _result_for(driver_action, raw_results[0]) if send_action else None
            verify_result = _result_for(verify_name, raw_results[-1])
        except BaseException as exc:  # noqa: BLE001
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            history.append({"attempt": attempt, "status": "driver_error", "error": mcp_client.describe_error(exc)})
            continue
        history.append({
            "attempt": attempt,
            "action_status": action_result["status"] if action_result else "not_resent",
            "verify_status": verify_result["status"],
            "verify_detail": verify_result.get("structured_content"),
        })
        if action_result and action_result["status"] == "driver_error":
            # The Driver rejected the action itself; repeating it unchanged won't help.
            return {"verified": False, "status": "action_failed", "attempts": history,
                    "error": action_result.get("error"), "retryable": False}
        action_delivered = action_delivered or action_result is not None
        if verify_result["verified"] is True:
            return {"verified": True, "status": "verified", "attempts": history, "driver_tool": driver_action,
                    "verification_note": f"verify_state confirmed all predicates after attempt {attempt}."}
    if not repeatable and not action_delivered:
        # The single send hit a transport error, so whether the keystrokes
        # landed is unknown; saying "verification failed" would hide that.
        return {
            "verified": False, "status": "delivery_unknown", "attempts": history, "retryable": False,
            "error": (f"The Driver connection failed while sending {driver_action}, so it is unknown whether the input "
                      "reached the window. It was not re-sent, to avoid typing twice. Re-observe the window before acting again."),
        }
    return {
        "verified": False, "status": "verification_failed", "attempts": history, "retryable": False,
        "error": f"The postcondition was not confirmed after {attempts} bounded attempt(s). Re-observe the window before choosing another method.",
    }


def is_available() -> bool:
    """Cheap boolean gate for callers that only need to know Cua usability."""
    return bool(config.ENABLE_CUA_DRIVER) and bool(discover_tools().get("tools"))
