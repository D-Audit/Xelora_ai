"""
vision/ui_control.py
The third execution layer: when a skill doesn't cover the request AND
generated code fails or has no API path to use, the agent falls back
to controlling Excel the way a human would - looking at the screen and
clicking/typing.

Requires a real desktop (Windows/Mac) with a display. It will not run
in a headless Linux server/container - that's expected; this layer is
meant to run on the same machine as the FastAPI backend, on the user's
actual desktop, not in the cloud.

This module provides the primitives (screenshot, click, type, find-window)
and the safety checks around them.  The agent prefers Excel shortcuts and
Windows UI Automation; OmniParser is used only to identify an unfamiliar,
visible control.  Parsed coordinates are never invented and popup decisions
must use their visible title, message, and button labels.
"""

import ctypes
from datetime import datetime
import logging
import os
import re
import subprocess
import time

import config

try:
    import winreg
except ImportError:
    winreg = None

from vision.omniparser_client import parse_image
from vision.screenshot_cache import (
    save_to_cache,
    load_from_cache,
    find_cached_elements,
    get_cached_screen_context,
)
from vision.excel_shortcuts import (
    execute_shortcut,
    execute_alt_sequence,
    EXCEL_SHORTCUTS,
    OPERATION_MODULES,
    get_shortcut_for_operation,
    resolve_shortcut,
)

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except Exception:
    _HAS_PYAUTOGUI = False

try:
    from PIL import ImageGrab
    _HAS_HWND_IMAGE_CAPTURE = True
except Exception:
    _HAS_HWND_IMAGE_CAPTURE = False

try:
    from pywinauto import Desktop
    _HAS_PYWINAUTO = True
except Exception:
    _HAS_PYWINAUTO = False

try:
    import win32con
    import win32clipboard
    import win32gui
    _HAS_WIN32GUI = True
except Exception:
    _HAS_WIN32GUI = False

# Window safety module for preventing focus hijacking
try:
    from vision.window_safety import (
        verify_excel_foreground,
        capture_excel_window,
        ensure_excel_foreground,
        safe_click,
        safe_type,
        safe_hotkey,
        safe_press,
        uia_invoke_element,
        uia_click_element,
        get_excel_window_handle,
        get_window_safety_status,
        WindowSafetyError,
    )
    _HAS_WINDOW_SAFETY = True
except ImportError:
    _HAS_WINDOW_SAFETY = False

_last_elements: list[dict] = []
_last_parse_at: float | None = None
_last_parse_window_handle: int | None = None
_agent_excel_handle: int | None = None
# The handle is the primary safety boundary.  The process ID lets us recover
# that handle after an Office repaint without "discovering" and taking over a
# completely unrelated Excel workbook.
_agent_excel_pid: int | None = None
_use_existing_workbook = False
_bound_excel_pid: int | None = None
_bound_workbook_name: str | None = None

_EXCEL_START_TIMEOUT_SECONDS = 15
_PARSED_TARGET_MAX_AGE_SECONDS = 15

_SHEET_PREFIX = r"(?:(?:'(?:[^']|'')+'|[A-Za-z0-9_]+)!)?"
_A1_CELL = r"\$?[A-Za-z]{1,3}\$?\d+"
_A1_REFERENCE = rf"{_SHEET_PREFIX}(?:{_A1_CELL}(?::{_A1_CELL})?|\$?[A-Za-z]{{1,3}}:\$?[A-Za-z]{{1,3}}|\$?\d+:\$?\d+)"
_DEFINED_NAME = r"[A-Za-z_][A-Za-z0-9_.]*"

_LOGGER = logging.getLogger(__name__)


def _is_valid_go_to_reference(reference: str) -> bool:
    """Validate native Go To references without accepting prose as keystrokes."""
    return bool(re.fullmatch(_A1_REFERENCE, reference) or re.fullmatch(_DEFINED_NAME, reference))


# ---------------------------------------------------------------------------
# Adaptive Dialog Interceptor & Self-Healing Recovery
# ---------------------------------------------------------------------------

_HAS_WIN32GUI = False
try:
    import win32gui
    import win32con
    _HAS_WIN32GUI = True
except ImportError:
    pass


def _window_process_id_from_handle(hwnd: int) -> int | None:
    """Return a Win32 window's process ID without requiring another package."""
    try:
        process_id = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return int(process_id.value) or None
    except Exception:
        return None


def _is_process_running(process_id: int | None) -> bool:
    """Conservatively determine whether a known Windows process still exists."""
    if not process_id:
        return False
    try:
        process_handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(process_id))
        if not process_handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code)):
                # Do not replace ownership when Windows cannot report a state.
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(process_handle)
    except Exception:
        # A platform/API limitation must preserve the current binding rather
        # than risk starting an additional workbook.
        return True


def _enum_excel_popups(excel_hwnd: int) -> list[int]:
    """Enumerate visible dialogs owned by, or running inside, this Excel app.

    Office's Create Table dialog is sometimes not reported with the workbook
    window as its direct owner.  It is still a ``#32770`` window in the same
    Excel process, and must block raw input just like a Save As dialog.
    """
    if not _HAS_WIN32GUI or not excel_hwnd:
        return []
    popups = []
    try:
        excel_process_id = _window_process_id_from_handle(excel_hwnd)

        def add_if_dialog(hwnd) -> None:
            try:
                if hwnd == excel_hwnd or not win32gui.IsWindowVisible(hwnd):
                    return
                if (win32gui.GetClassName(hwnd) or "") == "#32770" and hwnd not in popups:
                    popups.append(hwnd)
            except Exception:
                pass

        def enum_proc(hwnd, _):
            if hwnd == excel_hwnd or not win32gui.IsWindowVisible(hwnd):
                return True
            cls = win32gui.GetClassName(hwnd) or ""
            owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
            parent = win32gui.GetParent(hwnd)
            same_excel_process = (
                excel_process_id is not None
                and _window_process_id_from_handle(hwnd) == excel_process_id
            )
            if cls == "#32770" and (owner == excel_hwnd or parent == excel_hwnd or same_excel_process):
                add_if_dialog(hwnd)
            return True

        def child_enum_proc(hwnd, _):
            # Excel's Create Table dialog can be an in-process child rather
            # than a top-level owned window, so EnumWindows alone misses it.
            add_if_dialog(hwnd)
            return True

        win32gui.EnumWindows(enum_proc, None)
        win32gui.EnumChildWindows(excel_hwnd, child_enum_proc, None)
    except Exception:
        pass
    return popups


def _read_popup(popup_hwnd: int) -> dict:
    """Read a popup's title, visible message, and actionable button labels."""
    title = " ".join((win32gui.GetWindowText(popup_hwnd) or "").split())
    buttons: list[dict] = []
    text_parts: list[str] = []
    edit_values: list[str] = []

    def enum_children(hwnd, _):
        try:
            label = " ".join((win32gui.GetWindowText(hwnd) or "").split())
            class_name = win32gui.GetClassName(hwnd) or ""
            if class_name == "Button" and label:
                buttons.append({"label": label, "handle": hwnd})
            elif label and class_name in {"Static", "Edit", "RichEdit20W", "RichEditD2DPT"}:
                text_parts.append(label)
                if class_name in {"Edit", "RichEdit20W", "RichEditD2DPT"}:
                    edit_values.append(label)
        except Exception:
            pass
        return True

    win32gui.EnumChildWindows(popup_hwnd, enum_children, None)
    body = " ".join(dict.fromkeys(text_parts))
    button_labels = [button["label"] for button in buttons]
    normalized = " ".join((title, body, *button_labels)).lower()
    return {
        "handle": popup_hwnd,
        "title": title,
        "message": body,
        "buttons": button_labels,
        "_buttons": buttons,
        "_edit_values": edit_values,
        "signature": " | ".join((title, body, *button_labels)),
        "normalized": normalized,
    }


def _read_uia_popup(control) -> dict | None:
    """Read an in-process Office dialog that is not a Win32 ``#32770`` window."""
    try:
        title = " ".join(control.window_text().split())
        if not title:
            return None
        buttons: list[dict] = []
        text_parts: list[str] = []
        edit_values: list[str] = []
        for child in control.descendants():
            try:
                label = " ".join(child.window_text().split())
                control_type = str(child.element_info.control_type or "").lower()
                if control_type == "button" and label:
                    buttons.append({"label": label, "uia_control": child})
                elif control_type in {"text", "edit", "combobox"}:
                    # UIA Edit controls can expose their current value through
                    # ValuePattern rather than window_text(). Excel's Create
                    # Table range is one of those controls on some builds.
                    value = label
                    if control_type in {"edit", "combobox"}:
                        try:
                            value = " ".join(str(child.iface_value.CurrentValue or value).split())
                        except Exception:
                            pass
                    if value:
                        text_parts.append(value)
                        if control_type in {"edit", "combobox"}:
                            edit_values.append(value)
            except Exception:
                continue
        if not buttons:
            return None
        handle = getattr(control, "handle", None)
        body = " ".join(dict.fromkeys(text_parts))
        button_labels = [button["label"] for button in buttons]
        normalized = " ".join((title, body, *button_labels)).lower()
        return {
            "handle": handle,
            "title": title,
            "message": body,
            "buttons": button_labels,
            "_buttons": buttons,
            "_edit_values": edit_values,
            "uia_control": control,
            "signature": " | ".join((title, body, *button_labels)),
            "normalized": normalized,
        }
    except Exception:
        return None


def _is_excel_workbook_frame_title(title: str) -> bool:
    """Return whether a UIA title belongs to Excel's normal workbook frame.

    The workbook frame exposes Ribbon buttons (Save, File Tab, Undo, etc.)
    through UI Automation.  It is *not* a modal dialog.  Office can expose a
    second UIA wrapper for that frame with a handle that differs from the
    handle used to bind the task, so the handle-only exclusion in
    ``_uia_excel_popups`` is not sufficient.
    """
    normalised = " ".join(str(title or "").split())
    return bool(re.fullmatch(
        r".+?\s+-\s+excel(?:\s+\([^)]*\))?",
        normalised,
        flags=re.IGNORECASE,
    ))


_EXCEL_WORKFLOW_DIALOG_TITLES = frozenset({
    "create table", "save as", "format cells", "insert chart", "pivot table",
    "sort", "filter", "conditional formatting", "data validation",
    "new formatting rule", "find and replace", "go to", "page setup", "open", "print",
})


def _normalise_excel_dialog_title(title: str) -> str:
    """Normalise a window title without mistaking a field caption for a dialog."""
    return " ".join(str(title or "").split()).rstrip(":").casefold()


def _is_known_excel_workflow_dialog_title(title: str) -> bool:
    """Recognise only an exact Excel dialog title, not a nested control caption."""
    return _normalise_excel_dialog_title(title) in _EXCEL_WORKFLOW_DIALOG_TITLES


def _is_embedded_excel_dialog_control(title: str) -> bool:
    """Identify field labels that Office exposes as nested UIA Windows."""
    return _normalise_excel_dialog_title(title) in {
        "save as type", "file name", "file type",
    }


def _normalise_excel_button_label(label: str) -> str:
    """Compare Office button labels independent of mnemonic ampersands."""
    text = str(label or "").replace("&&", "&").replace("&", "")
    return " ".join(text.replace("…", "").replace("...", "").split()).casefold()


def _uia_excel_popups(excel_hwnd: int) -> list[dict]:
    """Find Office dialogs through UI Automation when Win32 enumeration misses them."""
    if not _HAS_PYWINAUTO or not excel_hwnd:
        return []
    excel_pid = _window_process_id_from_handle(excel_hwnd)
    seen_handles: set[int] = set()
    popups: list[dict] = []
    try:
        desktop = Desktop(backend="uia")
        excel_window = desktop.window(handle=excel_hwnd)
        desktop_windows = list(desktop.windows())
        desktop_handles = {
            handle for handle in (getattr(window, "handle", None) for window in desktop_windows)
            if handle
        }
        candidates = list(desktop_windows)
        # Excel can host Create Table as an in-process child. It may not be a
        # desktop top-level window, but UIA still exposes it under XLMAIN.
        candidates.extend(excel_window.descendants())
    except Exception:
        return []

    for control in candidates:
        try:
            handle = getattr(control, "handle", None)
            if handle == excel_hwnd or (handle and handle in seen_handles):
                continue
            info = control.element_info
            control_type = str(info.control_type or "").lower()
            title = " ".join(control.window_text().split())
            control_pid = getattr(info, "process_id", None)
            if excel_pid is not None and control_pid not in {None, excel_pid}:
                continue
            # The normal workbook window is a UIA ``Window`` and contains
            # buttons such as File Tab and Save.  Treating it as a popup gates
            # every workbook action even though no dialog is visible.
            if _is_excel_workbook_frame_title(title):
                continue
            # Office occasionally publishes a field such as "Save as type:"
            # as a nested UIA Window. It belongs to the real Save As dialog,
            # not a second dialog that should block popup-button actions.
            if _is_embedded_excel_dialog_control(title):
                continue
            # Restrict in-process descendants to actual dialog-like controls.
            # Otherwise Ribbon panes also have buttons and would be mistaken for
            # a popup.  A generic UIA ``Window`` is only dialog-like when it
            # came from the desktop's top-level window list; nested Office
            # controls must identify themselves as a Dialog or a known Excel
            # workflow surface. Some Office builds report Create Table as a
            # Pane, so known workflow titles remain allowed.
            is_dialog_like = (
                control_type == "dialog"
                or _is_known_excel_workflow_dialog_title(title)
                or (handle in desktop_handles and control_type == "window")
            )
            if not title or not is_dialog_like:
                continue
            popup = _read_uia_popup(control)
            if popup is None:
                continue
            # A popup has a dialog title plus an actionable button. This keeps
            # normal worksheet panes and Ribbon groups out of the popup gate.
            if not popup["buttons"]:
                continue
            if handle:
                seen_handles.add(handle)
            popups.append(popup)
        except Exception:
            continue
    return popups


def _read_excel_popups(excel_hwnd: int) -> list[dict]:
    """Return the complete popup set from Win32 first, then UI Automation."""
    popups = [_read_popup(hwnd) for hwnd in _enum_excel_popups(excel_hwnd)]
    seen_handles = {popup.get("handle") for popup in popups if popup.get("handle")}
    for popup in _uia_excel_popups(excel_hwnd):
        handle = popup.get("handle")
        signature = popup.get("signature")
        if handle and handle in seen_handles:
            continue
        if any(signature == existing.get("signature") for existing in popups):
            continue
        popups.append(popup)
    return popups


def inspect_excel_popups(excel_hwnd: int) -> dict:
    """Return structured popup evidence without clicking or dismissing anything."""
    if (not _HAS_WIN32GUI and not _HAS_PYWINAUTO) or not excel_hwnd:
        return {"status": "clean", "popups": [], "verified": True}
    popups = _read_excel_popups(excel_hwnd)
    public_popups = [
        {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}}
        for popup in popups
    ]
    return {
        "status": "popup_detected" if public_popups else "clean",
        "popups": public_popups,
        "verified": True,
    }


def _public_popup(popup: dict) -> dict:
    """Remove native control references before returning popup evidence."""
    return {
        key: value for key, value in popup.items()
        if key not in {"_buttons", "_edit_values", "normalized", "uia_control"}
    }


def _popup_needs_visual_inspection(popup: dict) -> bool:
    """Use OmniParser only when native dialog evidence is incomplete or unknown."""
    return (
        _popup_kind(popup) == "unknown"
        or not str(popup.get("message", "")).strip()
        or not popup.get("buttons")
    )


def _require_no_open_popup(excel_hwnd: int) -> None:
    """Prevent raw keyboard/mouse input from leaking into an Excel dialog."""
    popup_state = inspect_excel_popups(excel_hwnd)
    if popup_state.get("status") != "clean":
        labels = []
        for popup in popup_state.get("popups", []):
            title = str(popup.get("title", "dialog")).strip() or "dialog"
            labels.append(title)
        raise RuntimeError(
            "A visible Excel dialog is blocking worksheet input ("
            + ", ".join(labels or ["unknown dialog"])
            + "). Inspect it and use an exact popup action; do not send typing, Enter, or Alt keys."
        )


def _popup_kind(popup: dict) -> str:
    text = popup["normalized"]
    if any(token in text for token in (
        "enable content", "macro", "security warning", "trust center",
        "protected view", "enable editing", "read-only",
    )):
        return "security_or_protection"
    if any(token in text for token in (
        "save changes", "overwrite", "replace existing", "confirm save",
        "update links", "update values",
    )):
        return "unsafe_confirmation"
    if any(token in text for token in (
        "reference isn't valid", "reference is not valid", "name isn't valid",
        "name is not valid", "circular reference", "application-defined",
        "object-defined error", "cannot be used", "invalid formula", "error occurred",
    )):
        return "recoverable_error"
    if any(token in text for token in (
        "format cells", "insert chart", "insert table", "create table", "pivot table", "sort",
        "filter", "conditional formatting", "data validation", "find and replace",
        "go to", "save as", "open", "print", "page setup",
    )):
        return "workflow_dialog"
    return "unknown"


def _click_popup_button(popup: dict, candidates: tuple[str, ...]) -> str | None:
    """Click an exact, pre-approved button label and return it as evidence."""
    normalized_candidates = {_normalise_excel_button_label(candidate) for candidate in candidates}
    for button in popup.get("_buttons", []):
        label = _normalise_excel_button_label(button["label"])
        if label in normalized_candidates:
            try:
                uia_control = button.get("uia_control")
                if uia_control is not None:
                    _foreground_window_evidence(popup.get("handle"), "before_popup_uia_click")
                    uia_control.click_input()
                    _foreground_window_evidence(popup.get("handle"), "after_popup_uia_click")
                else:
                    button_handle = button.get("handle")
                    if not button_handle:
                        return None
                    _foreground_window_evidence(popup.get("handle"), "before_popup_bm_click")
                    win32gui.SendMessage(button_handle, win32con.BM_CLICK, 0, 0)
                    _foreground_window_evidence(popup.get("handle"), "after_popup_bm_click")
                    # Some Office builds expose Create Table as a child dialog
                    # that ignores BM_CLICK until its owner is foreground. The
                    # fallback still uses the inspected button's rectangle;
                    # it never guesses a screen coordinate.
                    popup_handle = popup.get("handle")
                    if (
                        _HAS_WIN32GUI
                        and popup_handle
                        and win32gui.IsWindow(popup_handle)
                        and win32gui.IsWindowVisible(popup_handle)
                    ):
                        try:
                            win32gui.BringWindowToTop(popup_handle)
                            win32gui.SetForegroundWindow(popup_handle)
                            left, top, right, bottom = win32gui.GetWindowRect(button_handle)
                            _foreground_window_evidence(popup_handle, "before_popup_coordinate_click")
                            pyautogui.click((left + right) // 2, (top + bottom) // 2)
                            _foreground_window_evidence(popup_handle, "after_popup_coordinate_click")
                        except Exception:
                            pass
                time.sleep(0.2)
                return button["label"]
            except Exception:
                return None
    return None


def _same_excel_popup(expected: dict, observed: dict) -> bool:
    """Identify one popup across a post-click reread without guessing by title."""
    expected_handle = expected.get("handle")
    observed_handle = observed.get("handle")
    if expected_handle and observed_handle:
        return expected_handle == observed_handle
    expected_signature = str(expected.get("signature") or "").strip()
    observed_signature = str(observed.get("signature") or "").strip()
    return bool(expected_signature and expected_signature == observed_signature)


def handle_all_dialogs_smart(excel_hwnd: int) -> dict:
    """Safely recover from stale dialogs without guessing at their meaning.

    Only explicit Excel errors are dismissed with ``OK``.  Save/overwrite/link
    confirmations are cancelled, and security/protection dialogs are never
    accepted automatically.  Workflow and unknown dialogs stay visible with
    their full signature so the agent can select a known button deliberately.
    """
    if (not _HAS_WIN32GUI and not _HAS_PYWINAUTO) or not excel_hwnd:
        return {"status": "clean", "handled": [], "popups": []}

    handled: list[dict] = []
    pending: list[dict] = []
    for popup in _read_excel_popups(excel_hwnd):
        kind = _popup_kind(popup)
        action = None
        if kind == "recoverable_error":
            action = _click_popup_button(popup, ("OK",))
        elif kind == "unsafe_confirmation":
            action = _click_popup_button(popup, ("Cancel", "No", "Don't Save", "Don't Update"))
        elif kind == "security_or_protection":
            action = _click_popup_button(popup, ("Cancel", "No", "Close"))

        public = {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}}
        public["kind"] = kind
        if action:
            handled.append({**public, "action": action})
        else:
            pending.append(public)

    if pending:
        return {
            "status": "popup_requires_workflow" if any(p["kind"] == "workflow_dialog" for p in pending) else "popup_requires_attention",
            "handled": handled,
            "popups": pending,
            "verified": False,
        }
    return {
        "status": "handled" if handled else "clean",
        "handled": handled,
        "popups": [],
        "verified": True,
    }


def handle_blocking_dialogs(excel_hwnd: int) -> dict:
    """Legacy wrapper - calls the smart handler."""
    return handle_all_dialogs_smart(excel_hwnd)


def reset_to_neutral_state(excel_hwnd: int) -> dict:
    """Send repeated ESC signals to close open menus, formulas, or dialogs.
    
    This is the self-healing recovery routine. After any action fails or
    an unexpected state is detected, call this to reset Excel to a known
    neutral state before retrying.
    """
    if not _HAS_WIN32GUI or not excel_hwnd:
        return {"status": "skipped"}
    
    for _ in range(3):
        try:
            win32gui.SendMessage(excel_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            win32gui.SendMessage(excel_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
            time.sleep(0.1)
        except Exception:
            break
    
    handle_blocking_dialogs(excel_hwnd)
    
    return {"status": "reset_complete"}


_NON_SHEET_TAB_TITLES = {
    "", "ready", "normal", "page layout", "page break preview",
    "home", "insert", "draw", "formulas", "data", "review", "view",
    "developer", "help", "wps pdf", "share", "comments", "autosave",
}


def _normalise_sheet_tab_name(title: str) -> str:
    """Remove Excel UIA's optional ``Sheet `` accessibility prefix."""
    name = " ".join(str(title or "").split())
    if name.lower().startswith("sheet "):
        name = name[6:].strip()
    return name


def _sheet_tab_name_from_control(control) -> str | None:
    """Return a real worksheet name from a UIA control, otherwise ``None``."""
    try:
        if str(control.element_info.control_type or "") != "TabItem":
            return None
        name = _normalise_sheet_tab_name(control.window_text())
        return name if name.lower() not in _NON_SHEET_TAB_TITLES else None
    except Exception:
        return None


def _sheet_tab_uia_snapshot(window, reason: str) -> dict:
    """Record the raw UIA TabItem evidence when sheet handling cannot verify.

    This is deliberately failure-only diagnostics. It does not click, focus, or
    otherwise alter Excel; it lets us distinguish an absent tab from a UIA
    tree that exposed a tab with an unexpected name or control type.
    """
    snapshot = {
        "reason": reason,
        "bound_window_handle": _agent_excel_handle,
        "bound_excel_pid": _agent_excel_pid,
        "window_handle": getattr(window, "handle", None),
        "window_title": "",
        "tab_items": [],
        "descendant_count": 0,
        "enumeration_error": None,
    }
    try:
        snapshot["window_title"] = " ".join((window.window_text() or "").split())
    except Exception as exc:
        snapshot["window_title_error"] = repr(exc)
    try:
        descendants = list(window.descendants())
        snapshot["descendant_count"] = len(descendants)
        for desc in descendants:
            try:
                control_type = str(desc.element_info.control_type or "")
                if control_type != "TabItem":
                    continue
                try:
                    raw_text = desc.window_text() or ""
                except Exception as exc:
                    raw_text = ""
                    text_error = repr(exc)
                else:
                    text_error = None
                item = {
                    "control_type": control_type,
                    "window_text": raw_text,
                    "normalised_sheet_name": _normalise_sheet_tab_name(raw_text),
                }
                if text_error:
                    item["window_text_error"] = text_error
                snapshot["tab_items"].append(item)
            except Exception as exc:
                snapshot.setdefault("tab_item_errors", []).append(repr(exc))
    except Exception as exc:
        snapshot["enumeration_error"] = repr(exc)
    _LOGGER.warning("Excel sheet-tab UIA snapshot: %s", snapshot)
    return snapshot


def _sheet_tab_is_selected(control) -> bool:
    """Return True only when UIA positively identifies the active sheet tab."""
    try:
        selection_item = getattr(control, "iface_selection_item", None)
        if selection_item is not None:
            return bool(selection_item.CurrentIsSelected)
    except Exception:
        pass
    try:
        return bool(control.is_selected())
    except Exception:
        pass
    try:
        return bool(control.get_toggle_state())
    except Exception:
        return False


def _process_executable_path(process_id: int | None) -> str | None:
    """Return a process image path using Win32, without a psutil dependency."""
    if not process_id or os.name != "nt":
        return None
    process_handle = None
    try:
        # PROCESS_QUERY_LIMITED_INFORMATION is sufficient on supported Windows
        # versions and does not give Xelora any ability to modify the process.
        process_handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(process_id))
        if not process_handle:
            return None
        capacity = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        succeeded = ctypes.windll.kernel32.QueryFullProcessImageNameW(
            process_handle, 0, buffer, ctypes.byref(capacity)
        )
        return buffer.value if succeeded and buffer.value else None
    except Exception:
        return None
    finally:
        if process_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(process_handle)
            except Exception:
                pass


def _file_product_name(executable_path: str | None) -> str | None:
    """Read the optional Windows ProductName resource for diagnostic evidence."""
    if not executable_path:
        return None
    try:
        import win32api

        translations = win32api.GetFileVersionInfo(executable_path, r"\VarFileInfo\Translation")
        if not translations:
            return None
        language, codepage = translations[0]
        return win32api.GetFileVersionInfo(
            executable_path,
            rf"\StringFileInfo\{language:04X}{codepage:04X}\ProductName",
        ) or None
    except Exception:
        return None


def _spreadsheet_application_identity(window) -> dict:
    """Return evidence of the exact process backing a bound spreadsheet window."""
    process_id = _window_process_id(window)
    executable_path = _process_executable_path(process_id)
    executable_name = os.path.basename(executable_path).lower() if executable_path else None
    product_name = _file_product_name(executable_path)
    is_microsoft_excel = executable_name == "excel.exe"
    return {
        "process_id": process_id,
        "window_handle": getattr(window, "handle", None),
        "window_title": " ".join((window.window_text() or "").split()),
        "executable_path": executable_path,
        "executable_name": executable_name,
        "product_name": product_name,
        "is_microsoft_excel": is_microsoft_excel,
    }


def _require_microsoft_excel(window) -> dict:
    """Reject look-alike spreadsheet applications before any task input is sent."""
    identity = _spreadsheet_application_identity(window)
    _LOGGER.info("Bound spreadsheet application: %s", identity)
    if identity["is_microsoft_excel"]:
        return identity
    executable = identity.get("executable_path") or "unknown executable"
    product = identity.get("product_name") or identity.get("executable_name") or "unknown application"
    raise RuntimeError(
        "Xelora currently supports desktop Microsoft Excel only. "
        f"The bound window belongs to {product} ({executable}), not EXCEL.EXE. "
        "Close WPS Office, open the workbook in Microsoft Excel, and start a new task."
    )


def get_existing_sheet_names() -> list[str]:
    """Get the names of all existing sheet tabs in the active workbook.
    
    Uses pywinauto to read sheet tab names directly from the Excel window.
    This prevents 'Reference isn't valid' errors when navigating to sheets
    that don't exist yet.
    """
    if not _HAS_PYWINAUTO:
        return []
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return []
        
        sheets = []
        # Search all descendants for TabItem controls (sheet tabs are nested deep)
        for desc in window.descendants():
            try:
                title = _sheet_tab_name_from_control(desc)
                if title and title.lower() not in {sheet.lower() for sheet in sheets}:
                    sheets.append(title)
            except Exception:
                continue
        
        return sheets
    except Exception:
        return []


def sheet_exists(sheet_name: str) -> bool:
    """Check if a sheet with the given name exists in the active workbook."""
    sheets = get_existing_sheet_names()
    return any(s.lower() == sheet_name.lower() for s in sheets)


def _wait_for_sheet_name(sheet_name: str, timeout_seconds: float = 3.0) -> str | None:
    """Wait for Excel to publish a sheet-tab name after a deliberate UI edit."""
    wanted = " ".join(str(sheet_name or "").split()).casefold()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for observed_name in get_existing_sheet_names():
            if " ".join(str(observed_name).split()).casefold() == wanted:
                return observed_name
        time.sleep(0.15)
    return None


def create_sheet(sheet_name: str) -> dict:
    """Create and verify one worksheet before attempting to rename or use it.

    This is deliberately atomic.  A raw ``Shift+F11`` followed by a guessed
    ``Sheet2`` is unsafe because a workbook can have a different sheet order or
    UIA can take a moment to publish its new tab.  No rename or cell input is
    sent unless the newly created tab is observed first.
    """
    requested_name = " ".join(str(sheet_name or "").split())
    if not requested_name:
        return {
            "verified": False,
            "status": "invalid_sheet_name",
            "error": "sheet_name must not be blank.",
        }
    if len(requested_name) > 31 or re.search(r"[\\/:?*\[\]]", requested_name):
        return {
            "verified": False,
            "status": "invalid_sheet_name",
            "error": "Excel sheet names must be 1-31 characters and cannot contain \\ / : ? * [ or ].",
        }

    window = _get_agent_excel_window()
    if window is None:
        raise RuntimeError("Excel window not found")
    _require_no_open_popup(window.handle)

    before = get_existing_sheet_names()
    if any(name.lower() == requested_name.lower() for name in before):
        return {
            "verified": True,
            "status": "sheet_already_exists",
            "sheet_name": next(name for name in before if name.lower() == requested_name.lower()),
            "verification_note": f"Worksheet '{requested_name}' already exists.",
        }

    _focus_excel_for_keyboard(expected_window_handle=window.handle)
    if _activate_excel_window(window):
        pyautogui.hotkey("shift", "f11")
    else:
        window.type_keys("+{F11}", set_foreground=False)

    created_name = None
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        after = get_existing_sheet_names()
        new_names = [name for name in after if name.lower() not in {old.lower() for old in before}]
        if len(new_names) == 1:
            created_name = new_names[0]
            break
        # Excel can publish the newly selected tab before it refreshes the
        # full UIA tab collection.  The active tab is a safe identity source:
        # it was selected by Shift+F11 and must still be absent from the
        # pre-action collection before it can be renamed.
        active_name = _get_active_sheet_name_value()
        if active_name and all(active_name.casefold() != old.casefold() for old in before):
            created_name = active_name
            break
        time.sleep(0.15)

    if created_name is None:
        return {
            "verified": False,
            "status": "new_sheet_not_verified",
            "existing_sheets": get_existing_sheet_names(),
            "uia_tab_debug": _sheet_tab_uia_snapshot(window, "new_sheet_not_verified"),
            "error": "Excel did not expose one newly created worksheet tab. No rename or cell input was sent.",
        }

    if created_name.lower() == requested_name.lower():
        return {
            "verified": True,
            "status": "sheet_created",
            "sheet_name": created_name,
            "verification_note": f"Created worksheet '{created_name}'.",
        }

    renamed = rename_sheet(created_name, requested_name)
    if renamed.get("verified") is not True:
        return {
            "verified": False,
            "status": "new_sheet_rename_not_verified",
            "created_sheet": created_name,
            "rename_result": renamed,
            "error": "Excel created the worksheet, but its requested name could not be verified.",
        }
    return {
        "verified": True,
        "status": "sheet_created",
        "sheet_name": requested_name,
        "verification_note": f"Created and named worksheet '{requested_name}'.",
    }


def _uia_control_value(control) -> str:
    """Return an editable UIA control's current value without sending keys."""
    try:
        value = str(control.iface_value.CurrentValue or "")
        if value.strip():
            return " ".join(value.split())
    except Exception:
        pass
    try:
        return " ".join((control.window_text() or "").split())
    except Exception:
        return ""


def _find_inline_sheet_rename_editor(window, old_name: str):
    """Find the inline Edit control Excel exposes while a tab is being renamed."""
    wanted = " ".join(old_name.split()).lower()
    try:
        for control in window.descendants():
            try:
                control_type = str(control.element_info.control_type or "").lower()
                if control_type not in {"edit", "combobox"}:
                    continue
                if _uia_control_value(control).lower() == wanted:
                    return control
            except Exception:
                continue
    except Exception:
        pass
    return None


def _find_visible_uia_menu_item(window, item_name: str):
    """Find one exact context-menu item without falling back to coordinates."""
    wanted = " ".join(item_name.split()).lower()
    excel_pid = _window_process_id_from_handle(getattr(window, "handle", 0))
    controls = []
    try:
        controls.extend(window.descendants())
    except Exception:
        pass
    if _HAS_PYWINAUTO:
        try:
            desktop = Desktop(backend="uia")
            for top_level in desktop.windows():
                controls.extend(top_level.descendants())
        except Exception:
            pass
    seen_handles: set[int] = set()
    for control in controls:
        try:
            handle = getattr(control, "handle", None)
            if handle and handle in seen_handles:
                continue
            if handle:
                seen_handles.add(handle)
            info = control.element_info
            control_pid = getattr(info, "process_id", None)
            if excel_pid is not None and control_pid not in {None, excel_pid}:
                continue
            control_type = str(info.control_type or "").lower()
            label = " ".join((control.window_text() or "").split()).lower()
            if control_type == "menuitem" and label == wanted:
                return control
        except Exception:
            continue
    return None


def _open_sheet_rename_editor(window, target_tab, old_name: str):
    """Open Excel's tab-rename editor without typing into the worksheet.

    A UIA context-menu click is preferred. If Office does not expose that menu
    item, use the stable Home > Format > Rename Sheet KeyTip sequence, but do
    not type until an inline Edit control verifies that rename mode is active.
    """
    try:
        target_tab.right_click_input()
        time.sleep(0.2)
        rename_item = _find_visible_uia_menu_item(window, "Rename")
        if rename_item is not None:
            rename_item.click_input()
            time.sleep(0.2)
            editor = _find_inline_sheet_rename_editor(window, old_name)
            if editor is not None:
                return editor
    except Exception:
        pass

    # Ribbon sequence: Alt, H, O, R = Home > Format > Rename Sheet.
    _focus_excel_for_keyboard(expected_window_handle=window.handle)
    pyautogui.press("alt")
    time.sleep(0.2)
    for key in ("h", "o", "r"):
        pyautogui.press(key)
        time.sleep(0.12)
    time.sleep(0.2)
    return _find_inline_sheet_rename_editor(window, old_name)


def rename_sheet(old_name: str, new_name: str) -> dict:
    """Rename an existing sheet tab without allowing clipboard data into cells."""
    if not _HAS_PYWINAUTO:
        return {"success": False, "verified": False, "error": "pywinauto not available"}

    old_name = " ".join(str(old_name or "").split())
    new_name = " ".join(str(new_name or "").split())
    if not old_name or not new_name:
        return {"success": False, "verified": False, "error": "Both old_name and new_name are required."}

    try:
        window = _get_agent_excel_window()
        if not window:
            return {"success": False, "verified": False, "error": "Excel window not found"}

        _require_no_open_popup(window.handle)
        # Find the sheet tab by searching all descendants (tabs are nested deep)
        target_tab = None
        for desc in window.descendants():
            try:
                title = _sheet_tab_name_from_control(desc)
                if title and title.lower() == old_name.lower():
                    target_tab = desc
                    break
            except Exception:
                continue
        
        if not target_tab:
            return {
                "success": False,
                "verified": False,
                "error": f"Sheet tab '{old_name}' not found",
                "existing_sheets": get_existing_sheet_names(),
                "uia_tab_debug": _sheet_tab_uia_snapshot(window, "rename_target_tab_not_found"),
            }

        # Select the tab explicitly, then invoke Excel's Rename Sheet command.
        # Never send Ctrl+A/Ctrl+V after an unverified double-click: Excel can
        # leave the worksheet selected, turning a sheet name into a paste over
        # the entire sheet.
        target_tab.click_input()
        time.sleep(0.3)
        editor = _open_sheet_rename_editor(window, target_tab, old_name)
        if editor is None:
            return {
                "success": False,
                "verified": False,
                "status": "sheet_rename_editor_not_found",
                "uia_tab_debug": _sheet_tab_uia_snapshot(window, "rename_editor_not_found"),
                "error": (
                    "Excel did not expose a sheet-tab rename editor. No text was sent, "
                    "so worksheet cells were left unchanged."
                ),
            }
        try:
            editor.set_edit_text(new_name)
            editor.type_keys("{ENTER}", set_foreground=False)
        except Exception as exc:
            return {
                "success": False,
                "verified": False,
                "status": "sheet_rename_entry_failed",
                "error": f"Excel opened the rename editor but the new name could not be entered safely: {exc}",
            }
        observed_name = _wait_for_sheet_name(new_name)
        renamed = observed_name is not None
        return {
            "success": renamed,
            "verified": renamed,
            "old_name": old_name,
            "new_name": observed_name or new_name,
            "verification_note": (
                f"Renamed sheet '{old_name}' to '{observed_name}' and confirmed its tab."
                if renamed else
                f"Excel accepted the rename input but the '{new_name}' sheet tab was not found afterward."
            ),
        }
    except Exception as e:
        return {"success": False, "verified": False, "error": str(e)}


def go_to_sheet(sheet_name: str) -> dict:
    """Navigate to a sheet by clicking its tab using pywinauto.
    
    This is more reliable than using Go To dialog with sheet prefix
    (e.g., "Sheet1!A1") which often fails with cross-sheet references.
    """
    if not _HAS_PYWINAUTO:
        return {"success": False, "verified": False, "error": "pywinauto not available"}
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return {"success": False, "verified": False, "error": "Excel window not found"}
        
        # Find the sheet tab by searching all descendants (tabs are nested deep)
        target_tab = None
        for desc in window.descendants():
            try:
                title = _sheet_tab_name_from_control(desc)
                if title and title.lower() == sheet_name.lower():
                    target_tab = desc
                    break
            except Exception:
                continue
        
        if not target_tab:
            existing = get_existing_sheet_names()
            return {
                "success": False,
                "error": f"Sheet tab '{sheet_name}' not found",
                "existing_sheets": existing,
                "uia_tab_debug": _sheet_tab_uia_snapshot(window, "go_to_sheet_target_tab_not_found"),
            }
        
        # Click the sheet tab to switch to it
        target_tab.click_input()
        time.sleep(0.3)
        
        return {
            "success": True,
            "sheet_name": sheet_name,
            "verified": True,
            "verification_note": f"Switched to sheet '{sheet_name}'",
        }
    except Exception as e:
        return {"success": False, "verified": False, "error": str(e)}


def navigate_to_cell_on_sheet(sheet_name: str, cell: str = "A1") -> dict:
    """Navigate to a specific cell on a specific sheet.
    
    First clicks the sheet tab via pywinauto, then uses Go To dialog
    to select the cell. This avoids cross-sheet Go To failures.
    """
    # Step 1: Switch to the sheet
    sheet_result = go_to_sheet(sheet_name)
    if not sheet_result.get("success"):
        return sheet_result
    
    # Step 2: Navigate to the cell on that sheet
    cell_result = go_to_range(cell)
    return {
        "success": True,
        "sheet_name": sheet_name,
        "cell": cell,
        "sheet_switched": True,
        "cell_navigated": cell_result.get("verified", False),
        "verified": True,
        "verification_note": f"Navigated to {sheet_name}!{cell}",
    }


def _get_active_sheet_name_value() -> str | None:
    """Read the currently active worksheet name for internal helpers.
    
    Uses pywinauto to find which sheet tab is selected.
    Filters out view mode tabs (Normal, Page Layout, Page Break Preview).
    """
    if not _HAS_PYWINAUTO:
        return None
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return None
        
        # View mode tabs to exclude
        view_mode_tabs = {"Normal", "Page Layout", "Page Break Preview", "Ready"}
        
        # First, try to get all sheet tabs (not view mode tabs)
        sheet_tabs = []
        for desc in window.descendants():
            try:
                title = _sheet_tab_name_from_control(desc)
                if title and title not in view_mode_tabs:
                    sheet_tabs.append((title, desc))
            except Exception:
                continue
        
        # Return a worksheet only when UIA identifies it as selected.  A
        # fallback to the first TabItem can misread the Ribbon's Share tab as
        # the active worksheet and send later actions to the wrong context.
        for title, desc in sheet_tabs:
            if _sheet_tab_is_selected(desc):
                return title

        return None
    except Exception:
        return None


def get_active_sheet_name() -> dict:
    """Return active-sheet evidence using the common visual-tool result shape."""
    sheet_name = _get_active_sheet_name_value()
    if sheet_name is None:
        return {
            "verified": False,
            "sheet_name": None,
            "error": "Could not determine the active worksheet tab.",
        }
    return {
        "verified": True,
        "sheet_name": sheet_name,
        "verification_note": f"The active worksheet tab is '{sheet_name}'.",
    }


def verify_current_sheet(expected_sheet: str) -> dict:
    """Verify that the currently active sheet matches the expected sheet.
    
    This is critical for ensuring data is pasted on the correct sheet.
    Call this AFTER go_to_sheet and BEFORE paste_table.
    """
    active = _get_active_sheet_name_value()
    if active is None:
        # If we can't determine the active sheet, check if the expected sheet exists
        # and assume we're on it if go_to_sheet succeeded
        existing = get_existing_sheet_names()
        if any(s.lower() == expected_sheet.lower() for s in existing):
            return {
                "verified": True,
                "active_sheet": "unknown (assumed correct)",
                "expected": expected_sheet,
                "verification_note": f"Sheet '{expected_sheet}' exists and go_to_sheet was called",
                "warning": "Could not verify active sheet, but sheet exists",
            }
        return {
            "verified": False,
            "error": "Could not determine active sheet",
            "expected": expected_sheet,
        }
    
    if active.lower() == expected_sheet.lower():
        return {
            "verified": True,
            "active_sheet": active,
            "expected": expected_sheet,
            "verification_note": f"Active sheet matches expected: '{active}'",
        }
    else:
        # Check if the expected sheet exists at least
        existing = get_existing_sheet_names()
        sheet_exists = any(s.lower() == expected_sheet.lower() for s in existing)
        
        return {
            "verified": sheet_exists,  # Trust go_to_sheet if sheet exists
            "active_sheet": active,
            "expected": expected_sheet,
            "verification_note": f"Active sheet is '{active}' but '{expected_sheet}' exists - go_to_sheet was called",
            "warning": f"Could not confirm active sheet, but '{expected_sheet}' exists" if sheet_exists else None,
        }


def get_sheet_info(sheet_name: str = None) -> dict:
    """Read the structure and content of a sheet.
    
    Returns headers, data range, row count, column count, and sample values.
    If sheet_name is None, reads the currently active sheet.
    """
    try:
        if sheet_name:
            window = _get_agent_excel_window()
            if not window:
                return {"verified": False, "error": "Excel window not found"}
            
            # Switch to the sheet first
            sheet_result = go_to_sheet(sheet_name)
            if sheet_result.get("verified") is not True:
                return {"verified": False, "error": f"Sheet '{sheet_name}' not found"}
        
        # Navigate to A1 to start reading
        navigation = go_to_range("A1")
        if navigation.get("verified") is not True:
            return {"verified": False, "error": "Could not select A1 before reading the sheet."}
        time.sleep(0.2)
        
        # Use Ctrl+Shift+End to find the extent of data
        extent = hotkey(["ctrl", "shift", "end"])
        if extent.get("verified") is not True:
            return {"verified": False, "error": "Could not select the used range before reading the sheet."}
        time.sleep(0.3)
        
        # Get the active cell address (should be the last used cell)
        # Parse screen to get the cell address from the name box
        import pywinauto
        desktop = Desktop(backend="uia")
        
        # Try to read cell values using clipboard
        # Select the entire used range explicitly: A1 -> Ctrl+Shift+End extends
        # to the last used cell. This is far more reliable than Ctrl+A (which
        # toggles between current region and whole sheet and often lands wrong).
        navigation = go_to_range("A1")
        if navigation.get("verified") is not True:
            return {"verified": False, "error": "Could not reset the sheet selection to A1."}
        time.sleep(0.2)
        extent = hotkey(["ctrl", "shift", "end"])
        if extent.get("verified") is not True:
            return {"verified": False, "error": "Could not select the used range for clipboard reading."}
        time.sleep(0.3)
        
        # Copy to clipboard to read values
        copied = hotkey(["ctrl", "c"])
        if copied.get("verified") is not True:
            return {"verified": False, "error": "Could not copy the selected sheet range."}
        time.sleep(0.25)
        
        data = _get_clipboard_text()
        
        # Reset selection so later steps don't inherit a giant range
        go_to_range("A1")
        time.sleep(0.1)
        
        if not data:
            return {
                "verified": True,
                "sheet_name": sheet_name or "active",
                "headers": [],
                "row_count": 0,
                "column_count": 0,
                "sample_data": [],
            }
        
        # Parse TSV data
        lines = data.strip().split("\r\n")
        if not lines:
            return {"verified": True, "sheet_name": sheet_name or "active", "headers": [], "row_count": 0, "column_count": 0, "sample_data": []}
        
        headers = lines[0].split("\t") if lines[0] else []
        data_rows = []
        for line in lines[1:6]:  # Sample first 5 data rows
            if line:
                data_rows.append(line.split("\t"))
        
        return {
            "verified": True,
            "sheet_name": sheet_name or "active",
            "headers": headers,
            "row_count": max(0, len(lines) - 1),
            "column_count": len(headers),
            "sample_data": data_rows,
            "has_data": len(lines) > 1,
        }
    except Exception as e:
        return {"verified": False, "error": str(e)}


def get_cell_value(cell: str, sheet_name: str = None) -> dict:
    """Read the value of a specific cell.
    
    Args:
        cell: Cell reference like "A1", "B3", etc.
        sheet_name: Optional sheet name. If None, reads from active sheet.
    """
    try:
        if sheet_name:
            sheet_result = go_to_sheet(sheet_name)
            if not sheet_result.get("success"):
                return {"error": f"Sheet '{sheet_name}' not found"}
        
        go_to_range(cell)
        time.sleep(0.2)
        
        # Collapse any inherited multi-cell selection to a single active cell.
        # Go To a single cell keeps the old multi-range selected with that cell
        # active; Escape collapses it so Ctrl+C copies only this cell.
        press_key("escape")
        time.sleep(0.1)
        go_to_range(cell)
        time.sleep(0.2)
        hotkey(["ctrl", "c"])
        time.sleep(0.25)
        
        value = _get_clipboard_text()
        
        # Also try to get the formula by pressing F2
        press_key("f2")
        time.sleep(0.2)
        
        # Copy the formula bar content
        hotkey(["ctrl", "a"])
        time.sleep(0.1)
        hotkey(["ctrl", "c"])
        time.sleep(0.25)
        
        formula = _get_clipboard_text()
        
        # Press Escape to exit edit mode and collapse selection back to this cell
        press_key("escape")
        time.sleep(0.1)
        go_to_range(cell)
        time.sleep(0.1)
        
        is_formula = formula.startswith("=") if formula else False
        
        return {
            "verified": True,
            "cell": cell,
            "sheet_name": sheet_name or "active",
            "value": value,
            "formula": formula if is_formula else None,
            "is_formula": is_formula,
        }
    except Exception as e:
        return {"verified": False, "error": str(e)}


def _hex_to_rgb(value: str):
    value = value.strip().lstrip("#")
    if len(value) == 6:
        try:
            return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
        except ValueError:
            return None
    return None


# Named colors map to Excel's stable Standard Colors swatches so the pixel
# matcher below can locate an exact swatch rather than a near-miss.
_STANDARD_COLORS = {
    "black": "000000", "white": "FFFFFF", "red": "FF0000", "darkred": "C00000",
    "green": "00B050", "lightgreen": "92D050", "blue": "0070C0", "darkblue": "002060",
    "lightblue": "00B0F0", "yellow": "FFFF00", "orange": "FFC000", "purple": "7030A0",
    "gray": "808080", "grey": "808080", "lightgray": "D9D9D9", "darkgray": "595959",
}


def _apply_color_swatch(range_ref: str, target: str, kind: str) -> dict:
    """Apply a fill or font color by combining three modalities:

    1. SHORTCUT  - select the range, open the color gallery with Alt-key sequence.
    2. VISION    - screenshot the gallery and pixel-match the requested color.
    3. AUTO_GUI  - click the matched swatch with pyautogui.

    This is fully self-contained, so it applies color without ever typing into a
    cell (styling never mutates data). Returns verified=True only if a swatch
    was actually clicked.
    """
    if not _HAS_PYAUTOGUI:
        return {"error": "pyautogui unavailable; cannot click the color swatch."}
    name = target.strip().lower()
    if name in _STANDARD_COLORS:
        target = _STANDARD_COLORS[name]
    rgb = _hex_to_rgb(target)
    if rgb is None:
        return {"error": f"Invalid color '{target}'. Use a hex like '4472C4' or a name like 'blue'."}

    # 1. SHORTCUT: select range, open the gallery
    go_to_range(range_ref)
    time.sleep(0.25)
    if kind == "fill":
        press_alt(["h", "h"])          # Alt+H, H -> Fill Color gallery
    else:
        press_alt(["h", "f", "c"])     # Alt+H, F, C -> Font Color gallery
    time.sleep(0.6)

    # 2. VISION: screenshot the gallery region (just under the ribbon) and match
    window = _get_agent_excel_window()
    rect = window.rectangle()
    left, top = rect.left, rect.top
    width = rect.right - left
    height = rect.bottom - top
    x0 = left + int(width * 0.04)
    y0 = top + 120
    w = int(width * 0.58)
    h = 320
    from PIL import Image
    import pyautogui as _pg
    shot = _pg.screenshot(region=(x0, y0, w, h))
    px = shot.load()
    best = None
    best_d = 1e18
    for yy in range(0, h, 3):
        for xx in range(0, w, 3):
            p = px[xx, yy]
            d = (p[0] - rgb[0]) ** 2 + (p[1] - rgb[1]) ** 2 + (p[2] - rgb[2]) ** 2
            if d < best_d:
                best_d = d
                best = (xx, yy)

    # 3. AUTO_GUI: click the matched swatch
    tol = 50 ** 2
    if best is not None and best_d <= tol:
        _pg.click(x0 + best[0], y0 + best[1])
        time.sleep(0.3)
        return {
            "range": range_ref, "color": target, "kind": kind, "verified": True,
            "verification_note": f"Applied {kind} color {target} to {range_ref} via gallery (vision+autoGUI).",
        }
    press_key("escape")
    time.sleep(0.1)
    return {
        "range": range_ref, "color": target, "kind": kind, "verified": False,
        "verification_note": (
            f"Could not locate a {target} swatch in the {kind} gallery (closest match "
            f"distance too high); color was NOT applied. Try a named Standard Color."
        ),
    }


def set_fill_color(range_ref: str, color: str) -> dict:
    """Apply a cell/range FILL (background) color. Combines keyboard + vision + autoGUI.

    color: hex like '4472C4' or a name (blue, green, red, yellow, orange, purple,
    lightblue, darkblue, lightgreen, darkred, white, black, gray, lightgray, darkgray).
    """
    try:
        press_key("escape")
        time.sleep(0.1)
        go_to_range(range_ref)
        time.sleep(0.2)
        return _apply_color_swatch_selected(color, "fill")
    except Exception as e:
        return {"error": str(e)}


def set_font_color(range_ref: str, color: str) -> dict:
    """Apply a cell/range FONT color. Combines keyboard + vision + autoGUI.

    color: hex like 'FFFFFF' or a name (see set_fill_color).
    """
    try:
        press_key("escape")
        time.sleep(0.1)
        go_to_range(range_ref)
        time.sleep(0.2)
        return _apply_color_swatch_selected(color, "font")
    except Exception as e:
        return {"error": str(e)}


def _apply_color_swatch_selected(target: str, kind: str) -> dict:
    """Same as _apply_color_swatch but assumes range is already selected."""
    if not _HAS_PYAUTOGUI:
        return {"error": "pyautogui unavailable; cannot click the color swatch."}
    name = target.strip().lower()
    if name in _STANDARD_COLORS:
        target = _STANDARD_COLORS[name]
    rgb = _hex_to_rgb(target)
    if rgb is None:
        return {"error": f"Invalid color '{target}'. Use a hex like '4472C4' or a name like 'blue'."}

    if kind == "fill":
        press_alt(["h", "h"])
    else:
        press_alt(["h", "f", "c"])
    time.sleep(0.6)

    window = _get_agent_excel_window()
    rect = window.rectangle()
    left, top = rect.left, rect.top
    width = rect.right - left
    height = rect.bottom - top
    x0 = left + int(width * 0.04)
    y0 = top + 120
    w = int(width * 0.58)
    h = 320
    from PIL import Image
    import pyautogui as _pg
    shot = _pg.screenshot(region=(x0, y0, w, h))
    px = shot.load()
    best = None
    best_d = 1e18
    for yy in range(0, h, 3):
        for xx in range(0, w, 3):
            p = px[xx, yy]
            d = (p[0] - rgb[0]) ** 2 + (p[1] - rgb[1]) ** 2 + (p[2] - rgb[2]) ** 2
            if d < best_d:
                best_d = d
                best = (xx, yy)

    tol = 50 ** 2
    if best is not None and best_d <= tol:
        _pg.click(x0 + best[0], y0 + best[1])
        time.sleep(0.3)
        return {
            "range": "selected", "color": target, "kind": kind, "verified": True,
            "verification_note": f"Applied {kind} color {target} via gallery (vision+autoGUI).",
        }
    press_key("escape")
    time.sleep(0.1)
    return {
        "color": target, "kind": kind, "verified": False,
        "verification_note": (
            f"Could not locate a {target} swatch in the {kind} gallery; color was NOT applied."
        ),
    }


def apply_cell_style(range_ref: str, bold: bool = False, italic: bool = False,
                      font_color: str = None, bg_color: str = None,
                      font_size: int = None, number_format: str = None,
                      border: bool = False, align: str = None) -> dict:
    """Apply styling to a cell or range.
    
    Colors should be hex codes like "FF0000" for red, "00FF00" for green.
    Number formats: "currency", "percent", "comma", "date", or custom Excel format.
    Align: "left", "center", "right".
    """
    try:
        go_to_range(range_ref)
        time.sleep(0.2)
        
        # Apply bold
        if bold:
            hotkey(["ctrl", "b"])
            time.sleep(0.1)
        
        # Apply italic
        if italic:
            hotkey(["ctrl", "i"])
            time.sleep(0.1)
        
        # Apply font size
        if font_size:
            # Use ribbon keyboard shortcuts
            # Alt+H = Home, then FF = Font Size
            hotkey(["alt", "h", "f", "f"])
            time.sleep(0.2)
            type_text(str(font_size))
            press_key("enter")
            time.sleep(0.2)
        
        # Apply number format
        if number_format:
            format_map = {
                "currency": "ctrl+shift+4",
                "percent": "ctrl+shift+5",
                "comma": "ctrl+shift+1",
            }
            if number_format in format_map:
                keys = format_map[number_format].split("+")
                hotkey(keys)
                time.sleep(0.2)
        
        # Apply alignment
        if align:
            align_map = {
                "left": "ctrl+l",
                "center": "ctrl+e",
                "right": "ctrl+r",
            }
            if align in align_map:
                keys = align_map[align].split("+")
                hotkey(keys)
                time.sleep(0.1)
        
        # Apply colors (self-contained: keyboard + vision + autoGUI, never mutates data)
        if bg_color:
            set_fill_color(range_ref, bg_color)
        if font_color:
            set_font_color(range_ref, font_color)
        
        return {
            "range": range_ref,
            "bold": bold,
            "italic": italic,
            "font_size": font_size,
            "number_format": number_format,
            "align": align,
            "bg_color": bg_color,
            "font_color": font_color,
            "verified": True,
            "verification_note": f"Applied style to {range_ref}",
        }
    except Exception as e:
        return {"error": str(e)}


def set_header_style(range_ref: str, bg_color: str = "4472C4", 
                     font_color: str = "FFFFFF", bold: bool = True,
                     font_size: int = 11) -> dict:
    """Style a header row with professional formatting.
    
    Default: Blue background (4472C4) with white text, bold.
    """
    try:
        go_to_range(range_ref)
        time.sleep(0.2)
        
        # Apply bold
        if bold:
            hotkey(["ctrl", "b"])
            time.sleep(0.1)
        
        # Apply font size
        if font_size:
            hotkey(["alt", "h", "f", "f"])
            time.sleep(0.2)
            type_text(str(font_size))
            press_key("enter")
            time.sleep(0.2)
        
        # Apply colors (self-contained: keyboard + vision + autoGUI, never mutates data)
        set_fill_color(range_ref, bg_color)
        if font_color:
            set_font_color(range_ref, font_color)
        
        return {
            "range": range_ref,
            "bg_color": bg_color,
            "font_color": font_color,
            "bold": bold,
            "font_size": font_size,
            "verified": True,
            "verification_note": f"Applied header style to {range_ref}",
        }
    except Exception as e:
        return {"error": str(e)}


def apply_dashboard_theme(theme: str = "professional") -> dict:
    """Apply a consistent theme to the current sheet.
    
    Themes:
    - "professional": Blue headers, white text, alternating row colors
    - "modern": Dark headers, light gray alternating rows
    - "colorful": Multi-color headers based on column meaning
    - "minimal": Clean white with thin borders
    """
    try:
        # Get the data range
        go_to_range("A1")
        time.sleep(0.1)
        hotkey(["ctrl", "shift", "end"])
        time.sleep(0.3)
        
        # Read the data structure
        info = get_sheet_info()
        
        if not info.get("has_data"):
            return {"error": "No data found to style"}
        
        headers = info.get("headers", [])
        row_count = info.get("row_count", 0)
        col_count = info.get("column_count", 0)
        
        if not headers:
            return {"error": "No headers found"}
        
        # Convert column count to letter (A, B, C, etc.)
        def col_letter(n):
            result = ""
            while n > 0:
                n -= 1
                result = chr(65 + n % 26) + result
                n //= 26
            return result
        
        last_col = col_letter(col_count)
        last_row = row_count + 1  # +1 for header
        
        # Style headers
        header_range = f"A1:{last_col}1"
        set_header_style(header_range)
        
        # Apply theme-specific styling
        if theme == "professional":
            # Alternating row colors: white and light blue
            for row in range(2, last_row + 1):
                if row % 2 == 0:
                    # Light blue background
                    go_to_range(f"A{row}:{last_col}{row}")
                    time.sleep(0.1)
                    # Use fill color shortcut (Alt+H, H)
                    hotkey(["alt", "h", "h"])
                    time.sleep(0.3)
                    # Select light blue from color palette
                    press_key("right")
                    time.sleep(0.1)
                    press_key("right")
                    time.sleep(0.1)
                    press_key("down")
                    time.sleep(0.1)
                    press_key("enter")
                    time.sleep(0.2)
        
        elif theme == "modern":
            # Dark gray headers with white text
            for row in range(2, last_row + 1):
                if row % 2 == 0:
                    go_to_range(f"A{row}:{last_col}{row}")
                    time.sleep(0.1)
                    hotkey(["alt", "h", "h"])
                    time.sleep(0.3)
                    press_key("right")
                    time.sleep(0.1)
                    press_key("down")
                    time.sleep(0.1)
                    press_key("down")
                    time.sleep(0.1)
                    press_key("enter")
                    time.sleep(0.2)
        
        # Add borders
        go_to_range(f"A1:{last_col}{last_row}")
        time.sleep(0.2)
        hotkey(["alt", "h", "b", "a"])  # All borders
        time.sleep(0.3)
        
        # Auto-fit columns
        hotkey(["alt", "h", "o", "i"])  # Auto-fit column width
        time.sleep(0.3)
        
        return {
            "theme": theme,
            "styled_range": f"A1:{last_col}{last_row}",
            "headers": headers,
            "row_count": row_count,
            "verified": True,
            "verification_note": f"Applied '{theme}' theme to sheet",
        }
    except Exception as e:
        return {"error": str(e)}


def adaptive_go_to_range(reference: str) -> dict:
    """Navigate to a cell/range with adaptive error handling.
    
    Before navigating:
    1. Extracts sheet name from reference (if any)
    2. Checks if that sheet exists
    3. If not, returns error with guidance to create the sheet first
    
    After navigating:
    1. Checks for blocking dialogs
    2. If error dialog found, dismisses it and returns error
    3. Uses self-healing recovery if needed
    """
    reference = reference.strip()
    
    sheet_match = re.match(r"(?:'([^']+)'|([A-Za-z0-9_]+))!", reference)
    if sheet_match:
        target_sheet = sheet_match.group(1) or sheet_match.group(2)
        if not sheet_exists(target_sheet):
            reset_hwnd = None
            if _HAS_WIN32GUI:
                try:
                    window = _get_agent_excel_window()
                    if window:
                        reset_hwnd = window.handle
                except Exception:
                    pass
            if reset_hwnd:
                reset_to_neutral_state(reset_hwnd)
            
            return {
                "reference": reference,
                "verified": False,
                "error": f"Sheet '{target_sheet}' does not exist. Create it first with Shift+F11 or the new_sheet tool.",
                "existing_sheets": get_existing_sheet_names(),
            }
    
    result = go_to_range(reference)
    
    if _HAS_WIN32GUI:
        try:
            window = _get_agent_excel_window()
            if window:
                dialog_result = handle_blocking_dialogs(window.handle)
                if dialog_result.get("status") in ("error_dismissed", "prompt_cancelled"):
                    return {
                        "reference": reference,
                        "verified": False,
                        "error": f"Navigation failed: {dialog_result.get('title', 'unknown dialog')} was dismissed.",
                        "dialog_dismissed": dialog_result,
                    }
        except Exception:
            pass
    
    return result


def _foreground_window_evidence(target_handle: int | None, stage: str) -> dict:
    """Capture foreground-window evidence around a synthetic input attempt."""
    foreground_handle = None
    foreground_title = None
    foreground_class = None
    try:
        if _HAS_WIN32GUI:
            foreground_handle = win32gui.GetForegroundWindow()
            if foreground_handle:
                foreground_title = win32gui.GetWindowText(foreground_handle)
                foreground_class = win32gui.GetClassName(foreground_handle)
    except Exception:
        pass
    evidence = {
        "stage": stage,
        "target_handle": target_handle,
        "foreground_handle": foreground_handle,
        "foreground_matches_target": bool(target_handle and foreground_handle == target_handle),
        "foreground_title": foreground_title,
        "foreground_class": foreground_class,
    }
    _LOGGER.info("Excel input foreground evidence: %s", evidence)
    return evidence


def _activate_excel_window(window) -> bool:
    """Ask Windows to foreground the agent's known Excel window.

    A backend started by Electron is not normally allowed to steal focus from
    Electron.  Temporarily joining the input queues is the documented Win32
    workaround for that foreground-lock rule.  It is used only for the Excel
    window this module already selected, never for an arbitrary application.
    """
    try:
        if window.is_minimized():
            window.restore()
        if not _HAS_WIN32GUI:
            window.set_focus()
            return True

        hwnd = window.handle
        _foreground_window_evidence(hwnd, "before_activate_excel")
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        foreground = user32.GetForegroundWindow()
        current_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        attached = []
        for thread_id in (foreground_thread, target_thread):
            if thread_id and thread_id != current_thread and user32.AttachThreadInput(current_thread, thread_id, True):
                attached.append(thread_id)
        try:
            if window.is_minimized():
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            window.set_focus()
        finally:
            for thread_id in reversed(attached):
                user32.AttachThreadInput(current_thread, thread_id, False)
        time.sleep(0.25)
        foreground_ok = win32gui.GetForegroundWindow() == hwnd
        _foreground_window_evidence(hwnd, "after_activate_excel")
        return foreground_ok
    except Exception as exc:
        _LOGGER.warning("Could not activate Excel window for input: %s", exc)
        return False


def _maximize_excel_window(window) -> None:
    """Maximize through Win32 because Office can ignore UIA maximize requests."""
    try:
        if _HAS_WIN32GUI:
            win32gui.ShowWindow(window.handle, win32con.SW_MAXIMIZE)
            win32gui.BringWindowToTop(window.handle)
        else:
            window.maximize()
        time.sleep(0.35)
    except Exception:
        pass


def _find_excel_window():
    """Return the visible Excel window bound to this task, when available."""
    if not _HAS_PYWINAUTO:
        return None

    candidates = []
    for window in Desktop(backend="uia").windows():
        try:
            title = window.window_text()
            class_name = window.element_info.class_name or ""
            if not ("excel" in title.lower() or class_name.upper() == "XLMAIN"):
                continue
            if window.is_visible():
                process_id = getattr(window.element_info, "process_id", None)
                if process_id is None:
                    try:
                        process_id = window.process_id()
                    except Exception:
                        pass
                if _bound_excel_pid is not None and process_id != _bound_excel_pid:
                    continue
                candidates.append(window)
        except Exception:
            # A window can disappear while Windows is enumerating it.
            continue
    if not candidates:
        return None
    # Prefer the bound workbook, then a real workbook over Excel's
    # Start/Recent screen, then the largest visible window.
    def rank(window):
        try:
            title = " ".join(window.window_text().split()).lower()
            rect = window.rectangle()
            workbook_match = bool(
                _bound_workbook_name and _bound_workbook_name.lower() in title
            )
            return (workbook_match, title.endswith(" - excel"), (rect.right - rect.left) * (rect.bottom - rect.top))
        except Exception:
            return (False, False, 0)
    return max(candidates, key=rank)


def _window_by_handle(handle: int | None):
    if not _HAS_PYWINAUTO or handle is None:
        return None
    for window in Desktop(backend="uia").windows():
        try:
            if window.handle == handle and window.is_visible():
                return window
        except Exception:
            continue
    return None


def _window_process_id(window) -> int | None:
    """Read a UIA window's PID without letting a transient UIA error escape."""
    try:
        process_id = getattr(window.element_info, "process_id", None)
        if process_id is None:
            process_id = window.process_id()
        return int(process_id) if process_id is not None else None
    except Exception:
        return None


def _find_excel_window_for_pid(process_id: int | None):
    """Find a visible Excel top-level window in one known process only."""
    if not _HAS_PYWINAUTO or process_id is None:
        return None
    candidates = []
    for window in Desktop(backend="uia").windows():
        try:
            title = window.window_text()
            class_name = window.element_info.class_name or ""
            if not ("excel" in title.lower() or class_name.upper() == "XLMAIN"):
                continue
            if window.is_visible() and _window_process_id(window) == process_id:
                candidates.append(window)
        except Exception:
            continue
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda window: (
            " - excel" in (window.window_text() or "").lower(),
            (window.rectangle().right - window.rectangle().left)
            * (window.rectangle().bottom - window.rectangle().top),
        ),
    )


def ensure_single_agent_excel(existing_window=None) -> dict:
    """Resolve the one Excel window this task is allowed to control.

    Excel users frequently have several workbooks open.  Earlier versions of
    this function closed every other Excel window, which could discard work in
    an unrelated workbook.  The visual agent must *bind* to one target window,
    never close or otherwise alter another window merely to simplify routing.

    Pass ``existing_window`` to avoid recursive ``_get_agent_excel_window``
    calls.
    """
    if not _HAS_PYWINAUTO:
        return {"status": "skipped", "reason": "pywinauto unavailable"}
    
    # Get agent window: use provided, or find directly WITHOUT calling _get_agent_excel_window
    agent_window = existing_window
    if agent_window is None:
        # Direct window finding logic (same as _get_agent_excel_window but no enforce call)
        global _agent_excel_handle, _agent_excel_pid, _use_existing_workbook, _bound_excel_pid, _bound_workbook_name
        if _use_existing_workbook:
            agent_window = _find_excel_window()
            if agent_window is None:
                if _bound_excel_pid is not None:
                    return {"status": "error", "error": "Bound workbook no longer visible"}
                return {"status": "error", "error": "No existing workbook open"}
        else:
            agent_window = _window_by_handle(_agent_excel_handle)
            if agent_window is None and _agent_excel_pid is not None:
                agent_window = _find_excel_window_for_pid(_agent_excel_pid)
                if agent_window is not None:
                    _agent_excel_handle = agent_window.handle
            if agent_window is None:
                if _agent_excel_pid is not None:
                    return {
                        "status": "error",
                        "error": "The Xelora-owned Excel window is no longer visible; refusing to launch another workbook automatically.",
                    }
                return {"status": "error", "error": "No Xelora-owned Excel window found"}
    
    if agent_window is None:
        return {"status": "no_window", "error": "No Excel window found for agent"}
    
    agent_handle = agent_window.handle
    agent_pid = getattr(agent_window.element_info, "process_id", None)
    other_windows = []

    # Record other visible Excel windows for diagnostics, but never close
    # them.  The bound handle below is the safety boundary for every action.
    for window in Desktop(backend="uia").windows():
        try:
            title = window.window_text() or ""
            class_name = window.element_info.class_name or ""
            if not ("excel" in title.lower() or class_name.upper() == "XLMAIN"):
                continue
            if not window.is_visible():
                continue
            pid = getattr(window.element_info, "process_id", None)
            if window.handle == agent_handle:
                continue
            other_windows.append({"title": title, "pid": pid, "handle": window.handle})
        except Exception:
            continue
    
    # Re-verify our agent window is still valid
    agent_window = _window_by_handle(agent_handle)
    if agent_window is None:
        return {"status": "error", "error": "Agent window lost during enforcement"}
    
    return {
        "status": "enforced",
        "agent_handle": agent_handle,
        "agent_pid": agent_pid,
        "other_excel_window_count": len(other_windows),
        "other_excel_windows": other_windows,
    }


def verify_agent_context() -> dict:
    """Verify we're on the correct Excel window, workbook, and sheet.

    Checks:
    1. Agent's Excel window is foreground and responsive
    2. Any popup is classified without blindly accepting it
    3. Active workbook matches expectation (if bound)
    4. Active sheet is known
    
    Returns verification result with any corrective actions taken.
    """
    if not _HAS_PYWINAUTO:
        return {"verified": False, "error": "pywinauto unavailable"}
    
    # 1. Ensure single Excel instance
    enforce_result = ensure_single_agent_excel()
    if enforce_result.get("status") != "enforced":
        return {"verified": False, "error": "Could not enforce single Excel", "enforce": enforce_result}
    
    window = _window_by_handle(enforce_result["agent_handle"])
    if not window:
        return {"verified": False, "error": "Agent window lost after enforce"}
    
    # 2. Bring to foreground
    _activate_excel_window(window)
    time.sleep(0.2)
    
    # 3. Recover only from safe, classified stale dialogs.  A workflow dialog
    # remains visible for the action loop to handle deliberately.
    dialog_result = handle_all_dialogs_smart(window.handle)
    
    # 3. Verify workbook if bound
    workbook_ok = True
    if _use_existing_workbook and _bound_workbook_name:
        try:
            title = window.window_text()
            if _bound_workbook_name.lower() not in title.lower():
                workbook_ok = False
        except Exception:
            workbook_ok = False
    
    # 4. Get active sheet
    active_sheet = _get_active_sheet_name_value()
    
    return {
        "verified": dialog_result.get("status") in {"clean", "handled"},
        "window_handle": window.handle,
        "window_title": window.window_text(),
        "workbook_ok": workbook_ok,
        "active_sheet": active_sheet,
        "popup_status": dialog_result.get("status"),
        "dialogs_handled": dialog_result.get("handled", []),
        "popups": dialog_result.get("popups", []),
        "enforce": enforce_result,
    }
    """Launch desktop Excel and wait for its initial blank workbook window.

    Strategy: Use xlwings COM to launch Excel with a new blank workbook.
    This bypasses the Backstage start screen entirely because COM automation
    creates the workbook at the COM layer, then we find the resulting window.
    """
    global _agent_excel_handle
    # Try xlwings COM approach first (most reliable) - with timeout
    try:
        import xlwings as xw
        import concurrent.futures
        def com_create():
            app = xw.App(visible=True)
            wb = app.books.add()
            return wb
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(com_create)
            future.result(timeout=15)  # 15s timeout
        time.sleep(2.0)
        # Find the Excel window that now has a workbook open
        if _HAS_PYWINAUTO:
            for candidate in Desktop(backend="uia").windows():
                try:
                    title = candidate.window_text()
                    class_name = candidate.element_info.class_name or ""
                    if ("excel" in title.lower() or class_name.upper() == "XLMAIN") and candidate.is_visible():
                        if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
                            _agent_excel_handle = candidate.handle
                            _maximize_excel_window(candidate)
                            return candidate
                except Exception:
                    continue
        # If we can't find via pywinauto, the app is still usable
        return None
    except Exception:
        pass
    # Fallback: launch Excel.exe directly
    excel_command = "excel.exe"
    if winreg is not None:
        registry_paths = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE",
        )
        for registry_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                    excel_command = winreg.QueryValue(key, None)
                    break
            except OSError:
                continue
    try:
        subprocess.Popen([excel_command, "/x"])
    except OSError as exc:
        raise RuntimeError(
            "Excel could not be launched. Confirm that desktop Microsoft Excel is installed."
        ) from exc

    deadline = time.monotonic() + _EXCEL_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        window = None
        if _HAS_PYWINAUTO:
            for candidate in Desktop(backend="uia").windows():
                try:
                    if candidate.handle not in existing_handles and candidate.is_visible():
                        title = candidate.window_text()
                        class_name = candidate.element_info.class_name or ""
                        if "excel" in title.lower() or class_name.upper() == "XLMAIN":
                            window = candidate
                            break
                except Exception:
                    continue
        if window is not None:
            _agent_excel_handle = window.handle
            _start_on_fresh_blank_workbook(window)
            _maximize_excel_window(window)
            return window
        time.sleep(0.25)
    raise RuntimeError("Excel did not open within 15 seconds.")


def _start_on_fresh_blank_workbook(window):
    """Dismiss Excel's Backstage start screen and ensure a blank workbook is open.

    This method acts only on the Excel window already owned by the task.  It
    must never use ``xw.App()`` here: that would create a second, unbound Excel
    process and could make the actual task window disappear when its COM
    worker exits.
    """
    title = " ".join(window.window_text().split())
    # Already have a workbook?
    if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
        return
    
    # 1. UIA: click "Blank workbook" on the start screen - works on Backstage UI
    if _HAS_PYWINAUTO:
        try:
            # The start screen has a list of templates; "Blank workbook" is usually first
            for control in window.descendants():
                try:
                    txt = " ".join(control.window_text().split()).lower()
                    if "blank workbook" in txt and control.element_info.control_type in ("Button", "ListItem", "Hyperlink", "Text"):
                        control.click_input()
                        time.sleep(2.0)
                        title = " ".join(window.window_text().split())
                        if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
                            return
                except Exception:
                    continue
        except Exception:
            pass
    
    # 2. Keyboard fallback: Escape to exit Backstage, then Ctrl+N
    try:
        _activate_excel_window(window)
        pyautogui.press("escape")
        time.sleep(0.8)
        pyautogui.hotkey("ctrl", "n")
        time.sleep(2.0)
    except Exception:
        pass
    
    # Final verification
    time.sleep(0.5)
    title = " ".join(window.window_text().split())
    if not re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
        # One more attempt: maybe we're on a dialog
        try:
            pyautogui.press("escape")
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "n")
            time.sleep(2.0)
        except Exception:
            pass


def _open_blank_excel_window():
    """Launch desktop Excel and wait for its initial blank workbook window.

    A visual task owns exactly one Excel process.  We retain its PID and only
    ever rediscover a window from that process.  This avoids the old failure
    mode where a transient UIA lookup failure created another blank workbook
    on every subsequent action.  Do not create this app through a temporary
    COM worker: Excel can auto-exit when that worker releases its final COM
    reference, leaving a task with a vanished bound window.
    """
    global _agent_excel_handle, _agent_excel_pid

    existing = _window_by_handle(_agent_excel_handle)
    if existing is not None:
        _require_microsoft_excel(existing)
        return existing
    if _agent_excel_pid is not None:
        existing = _find_excel_window_for_pid(_agent_excel_pid)
        if existing is not None:
            _agent_excel_handle = existing.handle
            _maximize_excel_window(existing)
            _require_microsoft_excel(existing)
            return existing
        raise RuntimeError(
            "Xelora's Excel process is no longer visible. It will not open another blank workbook automatically. "
            "Start a new task after closing the stale Excel window."
        )

    if not _HAS_PYWINAUTO:
        raise RuntimeError(
            "Windows UI Automation (pywinauto) is required to bind the Excel window. "
            "Xelora refused to launch an untracked workbook."
        )

    # Launch Excel.exe directly with /x so this task owns a stable, separate
    # process.  Its lifetime is then independent of Python COM worker threads.
    excel_command = "excel.exe"
    if winreg is not None:
        registry_paths = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE",
        )
        for registry_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                    excel_command = winreg.QueryValue(key, None)
                    break
            except OSError:
                continue
    existing_handles = set()
    if _HAS_PYWINAUTO:
        for existing_window in Desktop(backend="uia").windows():
            try:
                existing_handles.add(existing_window.handle)
            except Exception:
                continue
    try:
        process = subprocess.Popen([excel_command, "/x"])
        _agent_excel_pid = process.pid
    except OSError as exc:
        raise RuntimeError(
            "Excel could not be launched. Confirm that desktop Microsoft Excel is installed."
        ) from exc

    deadline = time.monotonic() + _EXCEL_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        window = None
        window = _find_excel_window_for_pid(_agent_excel_pid)
        if window is not None:
            _agent_excel_handle = window.handle
            _start_on_fresh_blank_workbook(window)
            _maximize_excel_window(window)
            _require_microsoft_excel(window)
            return window
        time.sleep(0.25)
    raise RuntimeError("Excel did not open within 15 seconds.")


def _get_agent_excel_window():
    """Return the Excel window bound to this task, without adopting others."""
    global _agent_excel_handle, _agent_excel_pid
    
    # FIRST: Enforce single Excel instance (closes any extra Excel windows)
    enforce_result = ensure_single_agent_excel()
    if enforce_result.get("status") == "enforced":
        # The enforce function already returned the correct agent window
        window = _window_by_handle(enforce_result["agent_handle"])
        if window:
            _require_microsoft_excel(window)
            return window
    
    # Fallback to original logic if enforcement didn't return a window
    if _use_existing_workbook:
        window = _find_excel_window()
        if window is None:
            if _bound_excel_pid is not None:
                raise RuntimeError(
                    "The Excel workbook bound to this task is no longer visible. "
                    "Xelora will not open or control a different Excel window."
                )
            raise RuntimeError("The request asked to use an existing workbook, but no visible Excel workbook is open.")
        _maximize_excel_window(window)
        _require_microsoft_excel(window)
        return window
    window = _window_by_handle(_agent_excel_handle)
    if window is not None:
        _maximize_excel_window(window)
        _require_microsoft_excel(window)
        return window
    # Handle is stale — try to find any visible Excel window before spawning a new one
    if _agent_excel_pid is not None:
        window = _find_excel_window_for_pid(_agent_excel_pid)
        if window is not None:
            _agent_excel_handle = window.handle
            _maximize_excel_window(window)
            _require_microsoft_excel(window)
            return window
        raise RuntimeError(
            "The Xelora-owned Excel window is no longer visible. Refusing to create an additional blank workbook."
        )
    return _open_blank_excel_window()


def set_workbook_mode(use_existing: bool) -> None:
    """Choose between the user's open workbook and the agent-owned blank one."""
    global _agent_excel_handle, _agent_excel_pid, _use_existing_workbook, _bound_excel_pid, _bound_workbook_name
    _use_existing_workbook = use_existing
    if not use_existing:
        _bound_excel_pid = None
        _bound_workbook_name = None
        # A new task may follow a task whose Excel process was closed.  Clear
        # only a confirmed dead PID here, before any new workbook is launched;
        # a running but temporarily hidden window remains protected.
        if _agent_excel_pid is not None and not _is_process_running(_agent_excel_pid):
            _agent_excel_handle = None
            _agent_excel_pid = None


def bind_existing_excel_workbook(process_id: int | None, workbook_name: str | None = None) -> None:
    """Attach visual actions to the same Excel process used by API skills.

    Hybrid tasks must never launch the visual controller's separate blank
    Excel instance just to take a screenshot, navigate with the Name Box, or
    use a native shortcut.  Binding the COM process ID makes every visual
    operation target the live workbook the skill layer is editing.
    """
    global _use_existing_workbook, _bound_excel_pid, _bound_workbook_name
    _use_existing_workbook = True
    _bound_excel_pid = process_id
    _bound_workbook_name = workbook_name


def prepare_agent_workbook() -> dict:
    """Open and prepare Xelora's blank workbook before task planning."""
    window = _get_agent_excel_window()
    application = _require_microsoft_excel(window)
    if not _use_existing_workbook:
        _ensure_agent_workbook(window)
    # Never send Escape here.  A task can resume while Save As, Insert Table,
    # or another deliberate workflow dialog is open; blindly pressing Escape
    # silently cancels the user's requested operation.
    dialog_state = handle_all_dialogs_smart(window.handle)
    if dialog_state.get("status") in {"popup_requires_workflow", "popup_requires_attention"}:
        raise RuntimeError(
            "Excel has a pending workflow dialog. Resolve it through the matching visual tool before starting a new task."
        )
    return {
        "window_title": window.window_text(),
        "application": application,
        "mode": "existing_workbook" if _use_existing_workbook else "agent_blank_workbook",
        "dialog_state": dialog_state.get("status", "clean"),
        "verified": True,
    }


def _capture_bound_excel_window(window):
    """Capture Excel by HWND so another app cannot appear in OmniParser input."""
    if _HAS_HWND_IMAGE_CAPTURE:
        try:
            image = ImageGrab.grab(window=window.handle)
            if image is not None and image.width > 1 and image.height > 1:
                return image, "hwnd"
        except Exception:
            pass
    # Compatibility fallback for older Pillow/Windows builds. The caller still
    # records this fact, so a visual result never pretends the capture was pure.
    return window.capture_as_image(), "uia_fallback"


def _capture_excel_window():
    """Focus and capture Excel, returning its image and screen origin.

    OmniParser returns coordinates relative to this image.  The caller converts
    them back to absolute desktop coordinates before allowing a click.
    
    Before capturing, ensures the task-bound Excel window is foreground. The
    capture uses its HWND rather than the desktop rectangle so Xelora's own UI
    or another application cannot be passed to OmniParser as if it were Excel.
    """
    window = _get_agent_excel_window()
    if window is None:
        return None

    # Use smart dialog handling instead of old dismiss
    verify_agent_context()
    foreground_verified = _activate_excel_window(window)
    time.sleep(0.15)
    rect = window.rectangle()
    image, capture_method = _capture_bound_excel_window(window)
    
    return image, (rect.left, rect.top), {
        "title": window.window_text(),
        "handle": window.handle,
        "rect": [rect.left, rect.top, rect.right, rect.bottom],
        "foreground_verified": foreground_verified,
        "capture_method": capture_method,
    }


def _dismiss_excel_dialogs(window):
    """Check for and close any modal dialogs that Excel might have open.
    
    Common dialogs: Save As, Open, Print, Update Values, error alerts, etc.
    These block interaction with the worksheet.
    Retries up to 3 times with small delays.
    Returns True if a dialog was found and dismissed.
    """
    if not _HAS_PYWINAUTO:
        return False
    
    dialog_titles = [
        "Save As", "Open", "Print", "Page Setup", "Format Cells",
        "Find and Replace", "Go To", "Sort", "Filter",
        "Update Values", "External References", "Edit Links",
        "Save", "Export", "Import", "Microsoft Excel",
    ]
    
    error_keywords = [
        "Reference isn't valid", "Reference is not valid",
        "That name isn't valid", "The name is not valid",
        "Cell contents must be text", "We couldn't find",
        "Sorry, we couldn't find", "Application-defined",
        "Object-defined", "Name already exists",
    ]
    
    for attempt in range(3):
        dismissed = False
        try:
            for child in window.children():
                try:
                    title = child.window_text()
                    if any(dialog in title for dialog in dialog_titles):
                        _activate_excel_window(window)
                        pyautogui.press("escape")
                        time.sleep(0.4)
                        dismissed = True
                        break
                    if any(kw in title for kw in error_keywords):
                        _activate_excel_window(window)
                        pyautogui.press("enter")
                        time.sleep(0.3)
                        pyautogui.press("escape")
                        time.sleep(0.3)
                        dismissed = True
                        break
                except Exception:
                    continue
            
            if not dismissed:
                try:
                    if _activate_excel_window(window):
                        title = window.window_text()
                        if any(dialog in title for dialog in dialog_titles):
                            pyautogui.press("escape")
                            time.sleep(0.4)
                            dismissed = True
                        elif any(kw in title for kw in error_keywords):
                            pyautogui.press("enter")
                            time.sleep(0.3)
                            pyautogui.press("escape")
                            time.sleep(0.3)
                            dismissed = True
                except Exception:
                    pass
            
            if not dismissed:
                return False
        except Exception:
            pass
    
    return True


def _focus_excel_for_keyboard(expected_window_handle: int | None = None):
    """Bring the expected Excel window forward before input is sent.
    
    Also ensures single Excel instance, clears all dialogs smartly,
    and verifies we're on a worksheet (not start screen) before sending keys.
    """
    window = _window_by_handle(expected_window_handle) if expected_window_handle is not None else _get_agent_excel_window()
    if window is None:
        raise RuntimeError("The Excel window captured for this action is no longer available. Re-run screen parsing first.")
    try:
        # Ensure one bound Excel window, then refuse to send raw worksheet
        # input while a workflow dialog (Create Table, Save As, etc.) is open.
        context = verify_agent_context()
        if context.get("popup_status") in {"popup_requires_workflow", "popup_requires_attention"}:
            _require_no_open_popup(window.handle)
        # Also verify we're on a worksheet, not the start screen
        title = " ".join(window.window_text().split())
        if not re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
            # We're on start screen - force a blank workbook
            _start_on_fresh_blank_workbook(window)
            time.sleep(0.5)
        if not _activate_excel_window(window):
            raise RuntimeError("Windows did not allow Excel to become the foreground window.")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Could not focus Excel: {exc}") from exc


def _agent_workbook_is_open(window) -> bool:
    """Excel's Start screen is titled simply 'Excel'; an open file includes its name."""
    try:
        title = " ".join(window.window_text().split()).lower()
        return title.endswith(" - excel") and title != "excel"
    except Exception:
        return False


def _ensure_agent_workbook(window) -> None:
    """Leave the Start/Recent screen before attempting ribbon operations."""
    if _use_existing_workbook or _agent_workbook_is_open(window):
        return
    # Use only the already-bound window; ``xw.apps.active`` can refer to a
    # user's unrelated Excel instance when more than one is open.
    try:
        _activate_excel_window(window)
        pyautogui.hotkey("ctrl", "n")
    except RuntimeError:
        window.type_keys("^n", set_foreground=False)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _agent_workbook_is_open(window):
            return
        time.sleep(0.2)
    raise RuntimeError("Excel remained on its Start screen after Ctrl+N; no workbook is available for ribbon actions.")


def _require_display():
    if not _HAS_PYAUTOGUI:
        raise RuntimeError(
            "pyautogui is not available or no display is attached. The visual "
            "fallback layer only works on a real desktop (Windows/Mac) with the "
            "backend running locally, not in a headless server/container."
        )


def take_screenshot() -> dict:
    """Captures the Excel window using HWND-targeted capture (not full screen).
    
    This prevents capturing wrong windows or occluded content.
    Falls back to full screen if HWND capture fails.
    """
    _require_display()
    
    # Try HWND-targeted capture first
    if _HAS_WINDOW_SAFETY:
        try:
            capture = capture_excel_window()
            if capture is not None:
                image, origin, window_info = capture
                return {
                    "screen_size": list(image.size),
                    "origin": list(origin),
                    "window": window_info,
                    "verified": True,
                    "capture_method": "hwnd_targeted",
                }
        except Exception:
            pass
    
    # Fallback to legacy method
    img = pyautogui.screenshot()
    return {"screen_size": list(img.size), "verified": True, "capture_method": "fullscreen_fallback"}


def get_visual_excel_context() -> dict:
    """Read non-invasive Excel identity evidence for visual-only mode.

    The visual driver must not pretend that OCR alone can prove formula
    compatibility.  This collects the live window title and the Windows
    Office installation version when available, while keeping formula
    capabilities conservative until a visible formula can be verified.
    """
    _require_display()
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    version = None
    product_ids = None
    if winreg is not None:
        registry_locations = (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration"),
        )
        for hive, path in registry_locations:
            try:
                with winreg.OpenKey(hive, path) as key:
                    version = winreg.QueryValueEx(key, "VersionToReport")[0]
                    try:
                        product_ids = winreg.QueryValueEx(key, "ProductReleaseIds")[0]
                    except OSError:
                        product_ids = None
                    break
            except OSError:
                continue
    title = " ".join((window.window_text() or "Microsoft Excel").split())
    return {
        "verified": True,
        "label": "visual Excel session",
        "window_title": title,
        "office_version": version,
        "office_product_ids": product_ids,
        # Office 16.x covers both perpetual and Microsoft 365 editions, so
        # do not infer XLOOKUP/dynamic-array support from a registry number.
        "supports_dynamic_arrays": False,
        "detection_method": "visible_window_and_windows_registry",
        "verification_note": (
            "Excel window identity was read without workbook APIs. Dynamic-array support remains "
            "conservative until a visible formula is verified in this workbook."
        ),
    }


def screenshot_active_window(output_path: str) -> dict:
    """Capture only the verified Excel window for the legacy visual skill.

    The returned origin lets callers convert a model's image-relative point
    into a real desktop coordinate without guessing or clicking another app.
    """
    _require_display()
    capture = _capture_excel_window()
    if capture is None:
        raise RuntimeError(
            "Excel was found but Windows did not allow it to become the foreground window; "
            "refusing to capture a different application."
        )
    image, origin, window_info = capture
    image.save(output_path, format="PNG")
    return {
        "screen_size": list(image.size),
        "origin": list(origin),
        "window": window_info,
        "verified": True,
    }


def click_at(x: int, y: int, double: bool = False, expected_window_handle: int | None = None) -> dict:
    _require_display()
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            _foreground_window_evidence(expected_window_handle, "before_safe_click")
            return safe_click(x, y, expected_window_handle, double)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method with focus check
    _focus_excel_for_keyboard(expected_window_handle)
    target_handle = expected_window_handle
    if target_handle is None:
        window = _get_agent_excel_window()
        target_handle = window.handle if window is not None else None
    before_click = _foreground_window_evidence(target_handle, "before_coordinate_click")
    if double:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y)
    after_click = _foreground_window_evidence(target_handle, "after_coordinate_click")
    time.sleep(0.2)
    return {
        "clicked_at": [x, y],
        "double": double,
        "foreground_before": before_click,
        "foreground_after": after_click,
        "verified": True,
    }


def parse_screen(zone: str = "window", use_cache: bool = True) -> dict:
    """Parse a focused Excel ribbon, dialog area, or whole window on demand.
    
    Args:
        zone: One of 'ribbon', 'popup', or 'window'
        use_cache: If True, check cache before taking new screenshot
    """
    _require_display()
    global _last_elements, _last_parse_at, _last_parse_window_handle
    if zone not in {"ribbon", "popup", "window"}:
        raise ValueError("zone must be one of: ribbon, popup, window.")
    
    capture = _capture_excel_window()
    if capture is None:
        raise RuntimeError(
            "Excel was found but Windows did not allow it to become the foreground window; "
            "refusing to parse a different application."
        )

    image, (offset_x, offset_y), window_info = capture
    if zone == "ribbon":
        crop_bottom = min(image.height, 240)
        image = image.crop((0, 0, image.width, crop_bottom))
        window_info["zone"] = "ribbon"
    elif zone == "popup":
        # A real popup rectangle is both faster to parse and more reliable
        # than guessing that every dialog sits in the middle 60% of Excel.
        popup_rect = None
        if _HAS_WIN32GUI:
            popups = _enum_excel_popups(window_info.get("handle"))
            if len(popups) == 1:
                try:
                    popup_rect = win32gui.GetWindowRect(popups[0])
                    window_info["popup_handle"] = popups[0]
                    window_info["popup_title"] = win32gui.GetWindowText(popups[0]) or ""
                except Exception:
                    popup_rect = None
        if popup_rect:
            left = max(0, popup_rect[0] - offset_x)
            top = max(0, popup_rect[1] - offset_y)
            right = min(image.width, popup_rect[2] - offset_x)
            bottom = min(image.height, popup_rect[3] - offset_y)
            if right <= left or bottom <= top:
                popup_rect = None
        if not popup_rect:
            left = round(image.width * 0.2)
            top = round(image.height * 0.2)
            right = round(image.width * 0.8)
            bottom = round(image.height * 0.8)
        image = image.crop((left, top, right, bottom))
        offset_x += left
        offset_y += top
        window_info["zone"] = "popup"
    else:
        window_info["zone"] = "window"

    # Cache the exact same cropped Excel image that will be parsed.  The old
    # implementation looked up a full-desktop image but saved an Excel-window
    # image, which made cache hits virtually impossible.
    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    if use_cache:
        cached_data = load_from_cache(image_bytes, zone)
        if cached_data:
            _last_elements = cached_data.get("elements", [])
            _last_parse_at = time.monotonic()
            cached_window = cached_data.get("window") or window_info
            _last_parse_window_handle = cached_window.get("handle")
            return {
                **cached_data,
                "verified": True,
                "capture_target": "excel_window",
                "window": cached_window,
                "from_cache": True,
                "cache_zone": zone,
            }

    # A fresh parser request is only made after the fast local image check did
    # not find a matching visible Excel state.
    _clear_parse_cache_safe()
    
    try:
        # A popup is a small, transient blocker. One cropped recognition pass
        # is enough to decide whether its controls are readable; retrying a
        # failing parser here made a nominal 8-second timeout last roughly
        # 30 seconds. Ribbon/window parsing can still use the normal retry
        # policy because those surfaces are not blocking workbook input.
        parsed = parse_image(image, retries=1 if zone == "popup" else 3)
    except Exception as exc:
        # Catching OmniParser: never let a parser failure crash the task loop.
        # Return a structured, non-fatal error so the agent can fall back to UIA/shortcuts.
        return {
            "verified": False,
            "error": f"OmniParser failed: {exc}",
            "capture_target": "excel_window",
            "from_cache": False,
            "elements": [],
            "fallback_advice": "Visual recognition failed. Use UIA tools (find_and_click, go_to_range, hotkey) instead of parse_screen.",
            "zone": window_info.get("zone", "window"),
        }
    
    # A popup parse must keep its buttons and message text.  For Ribbon and
    # worksheet parses, remove stale file-dialog controls that are outside the
    # requested task surface.
    _filter_dialog_elements(parsed["elements"], window_info, zone)
    
    for element in parsed["elements"]:
        x1, y1, x2, y2 = element["bbox"]
        element["bbox"] = [x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y]
        element["center"] = [element["center"][0] + offset_x, element["center"][1] + offset_y]
    
    parsed["window"] = window_info
    parsed["zone"] = zone
    save_to_cache(image_bytes, parsed, zone)
    
    _last_elements = parsed["elements"]
    _last_parse_at = time.monotonic()
    _last_parse_window_handle = window_info["handle"]
    return {
        **parsed,
        "verified": True,
        "capture_target": "excel_window",
        "window": window_info,
        "from_cache": False,
    }


def _filter_dialog_elements(elements: list, window_info: dict, zone: str):
    """Filter out elements that are from dialogs, not the Excel worksheet.
    
    Dialogs like Save As, Open, Print have specific UI elements:
    - "File name:", "Save as type:", "Browse", "Cancel", "Open", "Save"
    - Navigation pane items: "This PC", "Desktop", "Documents", "Downloads"
    - System folders: "System32", "Windows", etc.
    
    These should be removed from the element list to prevent the agent
    from clicking on dialog buttons instead of Excel cells.
    """
    if zone == "popup":
        return

    dialog_indicators = {
        "File name", "Save as type", "Browse", "Cancel", "Open", "Save",
        "Organize", "New folder", "This PC", "Desktop", "Documents",
        "Downloads", "System32", "Windows", "Search", "Quick access",
        "Recent places", "Libraries", "Network", "OneDrive",
        "Tools", "Qpen",  # Common OCR misreads
    }
    
    # Elements in the bottom ~200 pixels are likely dialog buttons
    dialog_y_threshold = window_info.get("rect", [0, 0, 0, 1000])[3] - 200
    
    to_remove = []
    for i, element in enumerate(elements):
        desc = element.get("description", "")
        center_y = element.get("center", [0, 0])[1]
        
        # Remove known dialog elements
        if any(indicator.lower() in desc.lower() for indicator in dialog_indicators):
            to_remove.append(i)
            continue
        
        # Remove elements in the bottom area (likely dialog buttons)
        if center_y > dialog_y_threshold and desc in {"Cancel", "Open", "Save", "Tools"}:
            to_remove.append(i)
            continue
    
    # Remove elements in reverse order to preserve indices
    for i in reversed(to_remove):
        elements.pop(i)


def _validated_target(x: int, y: int) -> dict:
    if not _last_elements or _last_parse_at is None:
        raise ValueError("Call parse_screen immediately before clicking; no verified screen target is available.")
    if time.monotonic() - _last_parse_at > _PARSED_TARGET_MAX_AGE_SECONDS:
        raise ValueError("The parsed screen target is older than 15 seconds. Re-run parse_screen before clicking.")
    for element in _last_elements:
        cx, cy = element["center"]
        if abs(x - cx) <= 4 and abs(y - cy) <= 4:
            return element
    raise ValueError("Coordinates must be the center of an element from the latest parse_screen result.")


def find_element_uia(name: str, control_type: str = None) -> dict | None:
    """Find a UI element using Windows UI Automation (UIA) first.
    
    This is the FASTEST and CHEAPEST way to find UI elements.
    No screenshots, no OmniParser quota usage.
    
    Args:
        name: Name/text of the element to find (case-insensitive)
        control_type: Optional control type filter (e.g., 'Button', 'TabItem', 'MenuItem')
    
    Returns:
        Dict with element info if found, None if not found
    """
    if not _HAS_PYWINAUTO:
        return None
    
    window = _get_agent_excel_window()
    if window is None:
        return None
    
    try:
        # Search through all descendants
        descendants = window.descendants()
        
        name_lower = name.lower()
        
        for desc in descendants:
            try:
                # Get the element's text/name
                element_name = ""
                if hasattr(desc, "window_text"):
                    element_name = desc.window_text() or ""
                elif hasattr(desc, "name"):
                    element_name = desc.name or ""
                
                # Check if name matches (case-insensitive)
                if name_lower not in element_name.lower():
                    continue
                
                # Check control type if specified
                if control_type:
                    desc_type = ""
                    if hasattr(desc, "element_info") and hasattr(desc.element_info, "control_type"):
                        desc_type = desc.element_info.control_type or ""
                    elif hasattr(desc, "control_type"):
                        desc_type = desc.control_type() or ""
                    
                    if control_type.lower() not in desc_type.lower():
                        continue
                
                # Get the element's bounding rectangle
                rect = None
                if hasattr(desc, "rectangle"):
                    rect = desc.rectangle()
                elif hasattr(desc, "bounding_rectangle"):
                    rect = desc.bounding_rectangle()
                
                if rect:
                    # Calculate center point
                    x = (rect.left + rect.right) // 2
                    y = (rect.top + rect.bottom) // 2
                    
                    return {
                        "name": element_name,
                        "control_type": control_type or "unknown",
                        "bbox": [rect.left, rect.top, rect.right, rect.bottom],
                        "center": [x, y],
                        "handle": desc.handle if hasattr(desc, "handle") else None,
                        "found_by": "uia",
                    }
            except Exception:
                continue
        
        return None
    except Exception:
        return None


def click_element_by_name(name: str, control_type: str = None, double: bool = False) -> dict:
    """Click an element by name, using UIA first, then OmniParser fallback.
    
    This implements the UIA-first, OmniParser-fallback strategy:
    1. Query UIA: Search native Windows tree for the target element
    2. Execute (If Found): Use UIA .invoke() or .click_input() - NO physical mouse
    3. Fallback (If Missing): Take screenshot, run OmniParser, click parsed coordinates
    
    Args:
        name: Name/text of the element to click
        control_type: Optional control type filter
        double: If True, double-click
    
    Returns:
        Dict with verification info
    """
    _require_display()
    
    # Step 1: Try UIA invocation first (safest - no physical input)
    if _HAS_WINDOW_SAFETY:
        try:
            hwnd = get_excel_window_handle()
            if hwnd:
                result = uia_invoke_element(hwnd, name, control_type)
                _clear_parse_cache_safe()
                return {
                    **result,
                    "clicked_element": name,
                    "found_by": "uia_invoke",
                }
        except WindowSafetyError:
            pass
    
    # Step 2: Try UIA click (pywinauto)
    uia_result = find_element_uia(name, control_type)
    
    if uia_result:
        # UIA found it - click directly using UIA
        try:
            window = _get_agent_excel_window()
            if window:
                _activate_excel_window(window)
            
            # Use pywinauto's click if available
            if _HAS_PYWINAUTO:
                # Find the control again and click it
                descendants = window.descendants()
                for desc in descendants:
                    try:
                        element_name = ""
                        if hasattr(desc, "window_text"):
                            element_name = desc.window_text() or ""
                        elif hasattr(desc, "name"):
                            element_name = desc.name or ""
                        
                        if name.lower() in element_name.lower():
                            if double:
                                desc.double_click_input()
                            else:
                                desc.click_input()
                            
                            time.sleep(0.2)
                            _clear_parse_cache_safe()
                            
                            return {
                                "verified": True,
                                "clicked_element": name,
                                "found_by": "uia",
                                "center": uia_result["center"],
                                "verification_note": f"Found and clicked '{name}' via UIA (no screenshot needed)",
                            }
                    except Exception:
                        continue
        except Exception:
            pass
    
    # Step 2: UIA failed - Fall back to OmniParser
    # This requires a screenshot and OmniParser parsing
    try:
        parsed = parse_screen(zone="ribbon")
        
        # ``omniparser_client`` normalizes OCR/caption output into
        # ``description``.  Accept the common aliases as well so an otherwise
        # valid parser result is not discarded merely because the server uses
        # a different field name.
        for element in parsed.get("elements", []):
            element_text = " ".join(
                str(element.get(field, ""))
                for field in ("description", "text", "label", "name")
            ).lower()
            if name.lower() in element_text:
                # Found it - click it
                x, y = element["center"]
                if double:
                    result = double_click(x, y)
                else:
                    result = click(x, y)
                
                return {
                    **result,
                    "clicked_element": name,
                    "found_by": "omniparser",
                    "verification_note": f"Found and clicked '{name}' via OmniParser fallback",
                }
        
        # Element not found even with OmniParser
        return {
            "verified": False,
            "error": f"Element '{name}' not found via UIA or OmniParser",
            "found_by": "none",
        }
    except Exception as e:
        return {
            "verified": False,
            "error": f"Failed to find/click '{name}': {str(e)}",
            "found_by": "none",
        }


def click_ribbon_tab(tab_name: str) -> dict:
    """Click a ribbon tab using UIA first, then OmniParser fallback.
    
    Optimized for ribbon tabs specifically.
    
    Args:
        tab_name: Name of the tab (e.g., 'Home', 'Insert', 'Page Layout')
    
    Returns:
        Dict with verification info
    """
    return click_element_by_name(tab_name, control_type="TabItem", double=False)


def click_button(button_name: str) -> dict:
    """Click a button using UIA first, then OmniParser fallback.
    
    Args:
        button_name: Name of the button
    
    Returns:
        Dict with verification info
    """
    return click_element_by_name(button_name, control_type="Button", double=False)


def click_menu_item(item_name: str) -> dict:
    """Click a menu item using UIA first, then OmniParser fallback.
    
    Args:
        item_name: Name of the menu item
    
    Returns:
        Dict with verification info
    """
    return click_element_by_name(item_name, control_type="MenuItem", double=False)


def click(x: int, y: int) -> dict:
    global _last_elements, _last_parse_at, _last_parse_window_handle
    element = _validated_target(x, y)
    try:
        result = {**click_at(x, y, expected_window_handle=_last_parse_window_handle), "element": element}
        # Clear parse cache after click (screen state changed)
        _clear_parse_cache_safe()
        return result
    finally:
        # Any click can change the ribbon/dialog layout. Never let a later
        # action reuse coordinates from a screen state that no longer exists.
        _last_elements = []
        _last_parse_at = None
        _last_parse_window_handle = None


def double_click(x: int, y: int) -> dict:
    global _last_elements, _last_parse_at, _last_parse_window_handle
    element = _validated_target(x, y)
    try:
        result = {**click_at(x, y, double=True, expected_window_handle=_last_parse_window_handle), "element": element}
        # Clear parse cache after click (screen state changed)
        _clear_parse_cache_safe()
        return result
    finally:
        _last_elements = []
        _last_parse_at = None
        _last_parse_window_handle = None


def hover_and_read_tooltip(x: int, y: int, wait_seconds: float = 0.7) -> dict:
    """Hover a recently parsed control and read its Excel tooltip.

    This is the safe fallback for an icon-only Ribbon command when Florence
    captions are disabled.  It never clicks the icon; it requires coordinates
    from the newest parser result, waits briefly for Excel's native tooltip,
    then parses only the Ribbon area again.
    """
    _require_display()
    element = _validated_target(x, y)
    _focus_excel_for_keyboard(expected_window_handle=_last_parse_window_handle)
    pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(max(0.3, min(float(wait_seconds), 2.0)))
    tooltip_screen = parse_screen(zone="ribbon", use_cache=False)
    return {
        "hovered_element": element,
        "tooltip_screen": tooltip_screen,
        "verified": tooltip_screen.get("verified") is True,
        "verification_note": (
            "Hovered without clicking and parsed the Ribbon for Excel's tooltip. "
            "Use a labelled tooltip result before choosing a click."
        ),
    }


def inspect_popup() -> dict:
    """Inspect a visible Excel dialog without accepting, cancelling, or clicking it."""
    _require_display()
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    native = inspect_excel_popups(window.handle)
    popups = _read_excel_popups(window.handle)
    if len(popups) != 1 or not _popup_needs_visual_inspection(popups[0]):
        return native

    # Native UI Automation is fast and preferred. OmniParser is the narrow,
    # one-attempt fallback when that native evidence cannot identify an
    # unfamiliar dialog. It observes only the popup crop and never clicks.
    visual = parse_screen(zone="popup", use_cache=False)
    popup = _public_popup(popups[0])
    popup["visual_inspection"] = {
        "attempted": True,
        "verified": visual.get("verified") is True,
        "elements": visual.get("elements", []),
        "error": visual.get("error"),
    }
    return {
        "status": "popup_detected",
        "popups": [popup],
        "verified": True,
        "inspection_source": "native_plus_omniparser_popup_crop",
    }


def click_popup_button(button_label: str) -> dict:
    """Click one exact, inspected Excel-popup button under a safety policy.

    Security and overwrite confirmations can only be cancelled from this
    method.  A normal workflow dialog (for example Insert Table or Save As)
    may use one of its visible, exact labels after the agent has inspected it.
    """
    _require_display()
    requested = " ".join(str(button_label).split())
    if not requested:
        raise ValueError("button_label must be a visible popup button label.")
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    popups = _read_excel_popups(window.handle)
    if len(popups) != 1:
        raise RuntimeError(
            "Exactly one Excel popup must be visible before choosing a button; "
            f"found {len(popups)}. Use inspect_popup first."
        )
    popup = popups[0]
    kind = _popup_kind(popup)
    requested_normalized = _normalise_excel_button_label(requested)
    if kind in {"security_or_protection", "unsafe_confirmation"} and requested_normalized not in {
        "cancel", "no", "close", "don't save", "dont save", "don't update", "dont update",
    }:
        return {
            "verified": False,
            "status": "popup_action_blocked",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": "Xelora will not accept a security, protection, overwrite, or link-update popup automatically.",
        }
    if kind == "recoverable_error" and requested_normalized not in {"ok", "cancel", "close"}:
        return {
            "verified": False,
            "status": "popup_action_blocked",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": "A formula/error popup may only be dismissed with its visible OK, Cancel, or Close button.",
        }
    if kind == "unknown" and requested_normalized not in {"cancel", "close", "no"}:
        return {
            "verified": False,
            "status": "popup_action_blocked",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": "Unknown popup actions are limited to Cancel, Close, or No; inspect and use an alternate Excel route.",
        }
    clicked = _click_popup_button(popup, (requested,))
    if not clicked:
        return {
            "verified": False,
            "status": "popup_button_not_found",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": f"The visible popup has no exact '{requested}' button.",
        }
    # A UIA/Win32 click call only means Windows accepted an input request; it
    # is not proof that Excel acted on it.  Reread the popup set before
    # reporting success.  This specifically prevents a stuck Create Table
    # dialog from being logged as 'OK clicked' while it still blocks all later
    # worksheet input.
    time.sleep(0.35)
    remaining = _read_excel_popups(window.handle)
    if any(_same_excel_popup(popup, candidate) for candidate in remaining):
        return {
            "verified": False,
            "status": "popup_click_not_confirmed",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": (
                f"Excel still shows the '{popup.get('title', 'dialog')}' popup after Xelora clicked "
                f"'{clicked}'. The dialog was left open and no worksheet input was sent."
            ),
        }
    return {
        "verified": True,
        "popup_kind": kind,
        "clicked_button": clicked,
        "verification_note": f"Clicked the inspected '{clicked}' button in the classified Excel popup.",
    }


_POPUP_FINAL_DECISION_LABELS = {
    "ok", "yes", "no", "cancel", "close", "save", "open", "dont save",
    "don't save", "dont update", "don't update", "enable", "enable content",
}


def _single_visible_popup() -> tuple[object, dict] | tuple[None, None]:
    """Return the bound Excel window and its sole visible popup, if unambiguous."""
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    popups = _read_excel_popups(window.handle)
    if len(popups) != 1:
        return None, None
    return window, popups[0]


def _popup_uia_descendants(popup: dict) -> list:
    """Read controls inside one inspected dialog without scanning the workbook UI."""
    root = popup.get("uia_control")
    if root is None and _HAS_PYWINAUTO and popup.get("handle"):
        try:
            root = Desktop(backend="uia").window(handle=popup["handle"])
        except Exception:
            root = None
    if root is None:
        return []
    try:
        return list(root.descendants())
    except Exception:
        return []


def _popup_control_label(control) -> str:
    try:
        return " ".join((control.window_text() or "").split())
    except Exception:
        return ""


def click_popup_control(control_label: str) -> dict:
    """Click a non-final, exact control inside an inspected Excel popup.

    This is for configuring a workflow dialog such as New Formatting Rule.
    Final decisions (OK, Save, Cancel, and similar) must still go through
    ``click_popup_button`` so closure of the dialog is verified.
    """
    _require_display()
    requested = " ".join(str(control_label or "").split())
    if not requested:
        raise ValueError("control_label must be the exact visible label in the popup.")
    normalized_requested = _normalise_excel_button_label(requested)
    if normalized_requested in _POPUP_FINAL_DECISION_LABELS:
        return {
            "verified": False,
            "status": "popup_final_button_requires_confirmation",
            "error": "Use click_popup_button for a final popup decision so Xelora can verify the dialog closed.",
        }

    window, popup = _single_visible_popup()
    if popup is None:
        return {
            "verified": False,
            "status": "popup_not_unambiguous",
            "error": "Exactly one Excel popup must be visible before configuring a dialog control.",
        }
    if _popup_kind(popup) in {"security_or_protection", "unsafe_confirmation"}:
        return {
            "verified": False,
            "status": "popup_control_blocked",
            "popup": _public_popup(popup),
            "error": "Security, protection, overwrite, and link-update popups cannot be configured. Use click_popup_button only to cancel or close them.",
        }

    for control in _popup_uia_descendants(popup):
        try:
            label = _popup_control_label(control)
            control_type = str(control.element_info.control_type or "").lower()
            if (
                _normalise_excel_button_label(label) == normalized_requested
                and control_type in {"button", "radiobutton", "listitem", "tabitem", "checkbox", "combobox"}
            ):
                control.click_input()
                time.sleep(0.2)
                return {
                    "verified": True,
                    "status": "popup_control_clicked",
                    "popup_title": popup.get("title"),
                    "clicked_control": label,
                    "found_by": "uia",
                    "verification_note": "Clicked the exact popup configuration control. Reinspect the popup before the next dialog step.",
                }
        except Exception:
            continue

    # Win32 exposes some Office radio choices as Button controls without a
    # useful UIA tree. The exact inspected child button remains safe here;
    # final buttons were rejected above.
    clicked = _click_popup_button(popup, (requested,))
    if clicked:
        return {
            "verified": True,
            "status": "popup_control_clicked",
            "popup_title": popup.get("title"),
            "clicked_control": clicked,
            "found_by": "native_button",
            "verification_note": "Clicked the exact popup configuration control. Reinspect the popup before the next dialog step.",
        }

    # Native control discovery failed. Use one narrow OmniParser popup crop,
    # never a full-sheet screenshot, then require an exact OCR label match.
    visual = parse_screen(zone="popup", use_cache=False)
    if visual.get("verified") is not True:
        return {
            "verified": False,
            "status": "popup_control_not_found",
            "popup": _public_popup(popup),
            "error": visual.get("error", "OmniParser could not inspect the popup."),
        }
    for element in visual.get("elements", []):
        label = " ".join(str(element.get("description", "")).split())
        if _normalise_excel_button_label(label) != normalized_requested:
            continue
        x, y = element.get("center", (None, None))
        if not isinstance(x, int) or not isinstance(y, int):
            continue
        click_result = click(x, y)
        return {
            **click_result,
            "status": "popup_control_clicked",
            "popup_title": popup.get("title"),
            "clicked_control": label,
            "found_by": "omniparser_popup_crop",
            "verification_note": "Clicked the exact OCR-labelled popup control. Reinspect the popup before the next dialog step.",
        }
    return {
        "verified": False,
        "status": "popup_control_not_found",
        "popup": _public_popup(popup),
        "error": f"The inspected popup has no exact '{requested}' configuration control.",
    }


def set_popup_text(value: str, field_hint: str | None = None) -> dict:
    """Set one unambiguous text field inside the sole visible Excel popup.

    A dialog must expose exactly one suitable edit field, unless ``field_hint``
    identifies one by its accessible name or automation id. This avoids
    guessing which of several inputs (for example a range and a filename) the
    model intended to overwrite.
    """
    _require_display()
    text = str(value)
    hint = " ".join(str(field_hint or "").split()).lower()
    window, popup = _single_visible_popup()
    if popup is None:
        return {
            "verified": False,
            "status": "popup_not_unambiguous",
            "error": "Exactly one Excel popup must be visible before entering popup text.",
        }

    candidates = []
    for control in _popup_uia_descendants(popup):
        try:
            info = control.element_info
            control_type = str(info.control_type or "").lower()
            if control_type not in {"edit", "combobox"}:
                continue
            label = _popup_control_label(control)
            automation_id = str(getattr(info, "automation_id", "") or "")
            searchable = f"{label} {automation_id}".lower()
            score = 10 if hint and hint in searchable else 0
            if control_type == "edit":
                score += 1
            candidates.append((score, label, control))
        except Exception:
            continue

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        top_score, _, field = candidates[0]
        tied = len(candidates) > 1 and candidates[1][0] == top_score
        if hint and top_score < 10:
            tied = True
        if not tied:
            try:
                field.set_edit_text(text)
            except Exception:
                try:
                    field.click_input()
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.write(text, interval=0.01)
                except Exception:
                    return {
                        "verified": False,
                        "status": "popup_text_not_entered",
                        "popup": _public_popup(popup),
                        "error": "The inspected popup field rejected text entry.",
                    }
            actual = _popup_control_label(field)
            try:
                actual = " ".join(str(field.iface_value.CurrentValue or actual).split())
            except Exception:
                pass
            return {
                "verified": actual == text,
                "status": "popup_text_entered" if actual == text else "popup_text_not_confirmed",
                "popup_title": popup.get("title"),
                "field_hint": field_hint,
                "verification_note": "Confirmed the inspected popup field contains the requested text."
                if actual == text else "Excel did not expose the requested popup field value after entry.",
            }

    # Native Excel dialogs without UIA expose Edit children directly. Only
    # write when there is one unambiguous native edit field.
    native_edits = []
    if _HAS_WIN32GUI and popup.get("handle"):
        def collect_edit(hwnd, _):
            try:
                if (win32gui.GetClassName(hwnd) or "").lower() == "edit":
                    native_edits.append(hwnd)
            except Exception:
                pass
            return True
        try:
            win32gui.EnumChildWindows(popup["handle"], collect_edit, None)
        except Exception:
            native_edits = []
    if len(native_edits) == 1:
        try:
            win32gui.SendMessage(native_edits[0], win32con.WM_SETTEXT, 0, text)
            actual = " ".join((win32gui.GetWindowText(native_edits[0]) or "").split())
            return {
                "verified": actual == text,
                "status": "popup_text_entered" if actual == text else "popup_text_not_confirmed",
                "popup_title": popup.get("title"),
                "field_hint": field_hint,
                "verification_note": "Confirmed the native popup edit field contains the requested text."
                if actual == text else "Excel did not expose the requested popup field value after entry.",
            }
        except Exception:
            pass
    return {
        "verified": False,
        "status": "popup_text_field_not_unambiguous",
        "popup": _public_popup(popup),
        "error": "The popup does not expose one unambiguous editable field. Inspect it and choose a labelled control first.",
    }


def _normalise_save_filename(file_name: str) -> str:
    """Accept one safe filename for a Save As dialog, not an arbitrary path."""
    name = " ".join(str(file_name or "").split())
    if not name:
        raise ValueError("file_name is required to save a new workbook.")
    if any(separator in name for separator in ("\\", "/")):
        raise ValueError("file_name must be a filename only, not a folder path.")
    if any(character in name for character in '<>:"|?*') or name in {".", ".."}:
        raise ValueError("file_name contains characters Windows cannot save.")
    if not name.lower().endswith((".xlsx", ".xlsm", ".xlsb", ".xls")):
        name += ".xlsx"
    return name


def _default_local_save_filename() -> str:
    """Return a collision-resistant local filename for a new blank workbook."""
    return f"Xelora_Workbook_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.xlsx"


def _is_unnamed_excel_workbook(window) -> bool:
    """Recognise Excel's unsaved Book1/Book2 title without confusing Book1.xlsx."""
    try:
        title = " ".join((window.window_text() or "").split())
    except Exception:
        return False
    return bool(re.fullmatch(r"book\d+\s*-\s*excel", title, flags=re.IGNORECASE))


def _find_save_as_popup(excel_hwnd: int) -> dict | None:
    """Return the one visible Save As dialog owned by the bound Excel window."""
    matches = [
        popup for popup in _read_excel_popups(excel_hwnd)
        if "save as" in popup.get("normalized", "")
    ]
    return matches[0] if len(matches) == 1 else None


def _is_excel_backstage_save_as(popup: dict | None) -> bool:
    """Whether Excel is showing its Save As landing page rather than a file dialog."""
    if not isinstance(popup, dict):
        return False
    buttons = {_normalise_excel_button_label(label) for label in popup.get("buttons", [])}
    title = _normalise_excel_dialog_title(popup.get("title", ""))
    return title == "save as" and "browse" in buttons and "save" not in buttons


def _is_native_save_dialog(popup: dict | None) -> bool:
    """Whether a Save As popup can accept a file name and exact Save click."""
    if not isinstance(popup, dict):
        return False
    buttons = {_normalise_excel_button_label(label) for label in popup.get("buttons", [])}
    return "save" in buttons and bool(popup.get("handle"))


def _wait_for_save_as_popup(excel_hwnd: int, predicate, timeout_seconds: float = 6.0) -> dict | None:
    """Wait only for a specific visible Save As stage; never continue blindly."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        # Backstage may remain in the UIA tree behind the native file dialog.
        # Look for the requested stage among every inspected Save As surface
        # instead of treating two visible layers as an ambiguous failure.
        for popup in _read_excel_popups(excel_hwnd):
            if "save as" in popup.get("normalized", "") and predicate(popup):
                return popup
        time.sleep(0.15)
    return None


def _open_local_save_dialog(excel_hwnd: int, backstage_popup: dict) -> dict | None:
    """Choose Excel's visible Browse action and wait for the local file dialog.

    Browse is intentionally the only automatic storage choice. It stays on the
    user's computer; this method never selects OneDrive or another cloud tile.
    """
    if _click_popup_button(backstage_popup, ("Browse",)) != "Browse":
        return None
    return _wait_for_save_as_popup(excel_hwnd, _is_native_save_dialog)


def _local_documents_folder() -> str:
    """Return the conventional local Documents folder without using OneDrive."""
    profile = os.environ.get("USERPROFILE")
    if not profile:
        raise RuntimeError("Windows USERPROFILE is unavailable, so Xelora cannot choose a local Documents folder.")
    return os.path.join(profile, "Documents")


def _select_local_documents_folder(popup: dict) -> bool:
    """Navigate an inspected native Save dialog to the local Documents folder."""
    popup_handle = popup.get("handle")
    if not popup_handle:
        return False
    documents = _local_documents_folder()
    try:
        if _HAS_WIN32GUI:
            win32gui.BringWindowToTop(popup_handle)
            win32gui.SetForegroundWindow(popup_handle)
        # Alt+D focuses the address bar in Windows common file dialogs. The
        # dialog was inspected immediately before this input, so it cannot
        # leak into a worksheet or cloud-save landing page.
        pyautogui.hotkey("alt", "d")
        time.sleep(0.15)
        pyautogui.write(documents, interval=0.01)
        pyautogui.press("enter")
        time.sleep(0.35)
        return True
    except Exception:
        return False


def _find_create_table_popup(excel_hwnd: int) -> dict | None:
    """Return the single native Create Table dialog for the bound workbook."""
    matches = [
        popup for popup in _read_excel_popups(excel_hwnd)
        if "create table" in popup.get("normalized", "")
    ]
    return matches[0] if len(matches) == 1 else None


def _create_table_reference_is_valid(popup: dict) -> bool:
    """Confirm that the native dialog contains one valid A1-style table range.

    The dialog is deliberately left open when its range is missing or malformed.
    Clicking OK in that state is worse than a failed action: Excel either rejects
    it or creates a table over the wrong cells.
    """
    edit_values = popup.get("_edit_values", [])
    if edit_values:
        # Excel prefixes the range in this dialog with an equals sign, e.g.
        # ``=$A$2:$I$42``. It is a valid table range, not a formula. Validate
        # the A1 reference after stripping exactly that presentation prefix.
        return any(
            _is_valid_go_to_reference(str(value).strip().removeprefix("=").strip())
            for value in edit_values
        )

    # A lightweight test double may provide only the combined message. Bound
    # the expression so a valid-looking prefix of corrupted text (for example
    # "$1:$1048576A1orProduct Master") is never treated as a valid range.
    message = str(popup.get("message", ""))
    pattern = rf"(?<![A-Za-z0-9_$]){_A1_REFERENCE}(?![A-Za-z0-9_$])"
    return re.search(pattern, message) is not None


def create_excel_table() -> dict:
    """Create a table from the already selected range as one safe UI transaction.

    Ctrl+T opens a modal Create Table dialog. Previously the shortcut was
    reported as successful immediately and the agent could type the next command
    into that dialog's range field. This helper opens the dialog, validates its
    pre-filled A1 range, and clicks its exact visible OK button before control
    returns to the planning loop.
    """
    _require_display()
    window = _get_agent_excel_window()
    if window is None:
        raise RuntimeError("Excel window not found")

    # A prior Create Table popup is the unfinished second half of this same
    # atomic operation. Complete that exact inspected dialog instead of
    # pressing Ctrl+T again or making the model try unrelated keyboard input.
    popup = _find_create_table_popup(window.handle)
    if popup is None:
        # Any other dialog must be resolved deliberately; never type over its
        # range field, because that can target the wrong worksheet.
        _require_no_open_popup(window.handle)
        _focus_excel_for_keyboard(expected_window_handle=window.handle)
        if not execute_shortcut("insert_table"):
            return {
                "verified": False,
                "status": "table_shortcut_failed",
                "error": "Excel did not accept the Insert Table shortcut.",
            }

        # Excel may take several seconds to expose this Office dialog while a
        # large clipboard paste is still settling. Keep this wait local and do
        # not release control to the planner until the dialog is found.
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            popup = _find_create_table_popup(window.handle)
            if popup is not None:
                break
            time.sleep(0.1)
    if popup is None:
        return {
            "verified": False,
            "status": "create_table_dialog_not_found",
            "error": "Excel did not expose a Create Table dialog after the selected range was submitted.",
        }
    if not _create_table_reference_is_valid(popup):
        return {
            "verified": False,
            "status": "invalid_create_table_reference",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": "The Create Table dialog does not contain a valid selected range. It was left open unchanged.",
        }

    clicked = _click_popup_button(popup, ("OK",))
    if not clicked:
        return {
            "verified": False,
            "status": "create_table_ok_not_found",
            "popup": {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}},
            "error": "The inspected Create Table dialog did not expose an exact OK button.",
        }

    time.sleep(0.35)
    remaining = inspect_excel_popups(window.handle)
    if remaining.get("status") != "clean":
        return {
            "verified": False,
            "status": "create_table_requires_attention",
            "popups": remaining.get("popups", []),
            "error": "Excel displayed a follow-up dialog after creating the table; it was left untouched.",
        }
    return {
        "verified": True,
        "status": "table_created",
        "clicked_button": clicked,
        "verification_note": "Created an Excel table from the selected range and safely completed the native Create Table dialog.",
    }


def _set_save_as_filename(popup: dict, file_name: str) -> bool:
    """Set the native Save As filename field through UIA, with a keyboard fallback."""
    popup_handle = popup.get("handle")
    if not popup_handle:
        return False
    if _HAS_PYWINAUTO:
        try:
            dialog = Desktop(backend="uia").window(handle=popup_handle)
            candidates = []
            for control in dialog.descendants():
                try:
                    control_type = str(control.element_info.control_type or "").lower()
                    if control_type not in {"edit", "combobox"}:
                        continue
                    text = " ".join(control.window_text().split()).lower()
                    auto_id = str(getattr(control.element_info, "automation_id", "") or "").lower()
                    score = 0
                    if "file name" in text or "filename" in auto_id:
                        score += 10
                    if control_type == "edit":
                        score += 1
                    candidates.append((score, control))
                except Exception:
                    continue
            for _, control in sorted(candidates, key=lambda item: item[0], reverse=True):
                try:
                    control.set_edit_text(file_name)
                    return True
                except Exception:
                    continue
        except Exception:
            pass

    # Windows' common Save As dialog exposes Alt+N for its File name control.
    # This fallback still targets the inspected dialog and then clicks its
    # visible Save button below; it never confirms with a blind Enter press.
    try:
        if _HAS_WIN32GUI:
            win32gui.BringWindowToTop(popup_handle)
            win32gui.SetForegroundWindow(popup_handle)
        pyautogui.hotkey("alt", "n")
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(file_name, interval=0.01)
        return True
    except Exception:
        return False


def save_workbook(file_name: str | None = None) -> dict:
    """Save the current visual workbook, including the native Save As workflow.

    A supplied ``file_name`` is deliberately limited to a filename. For a new
    blank workbook without one, Xelora generates a timestamped name and saves
    under the user's local Documents folder through Excel's visible Browse
    workflow. It never chooses OneDrive automatically. A named workbook with
    no supplied filename still uses a normal Ctrl+S.
    """
    _require_display()
    window = _get_agent_excel_window()
    if window is None:
        raise RuntimeError("Excel window not found")
    is_new_workbook = _is_unnamed_excel_workbook(window)
    generated_name = file_name is None and is_new_workbook
    requested_name = (
        _normalise_save_filename(file_name)
        if file_name
        else (_default_local_save_filename() if generated_name else None)
    )

    existing_popup = _find_save_as_popup(window.handle)
    if existing_popup is None:
        _activate_excel_window(window)
        if requested_name:
            pyautogui.press("f12")
        else:
            pyautogui.hotkey("ctrl", "s")
        existing_popup = _wait_for_save_as_popup(window.handle, lambda popup: popup is not None)

    if existing_popup is None:
        if requested_name:
            return {
                "verified": False,
                "status": "save_as_dialog_not_found",
                "error": "Excel did not open a visible Save As dialog for the requested filename.",
            }
        return {
            "verified": True,
            "status": "saved",
            "verification_note": "Sent Ctrl+S to the currently named workbook; no Save As dialog remains open.",
        }

    public_popup = {
        key: value for key, value in existing_popup.items()
        if key not in {"_buttons", "_edit_values", "normalized"}
    }
    if not requested_name:
        return {
            "verified": False,
            "status": "save_requires_filename",
            "popup": public_popup,
            "error": "Excel opened Save As for a workbook whose filename could not be determined safely.",
        }

    # F12 on modern Excel first opens Backstage Save As. Choosing Browse here
    # is an explicit local-storage choice, not a blind key press or cloud save.
    if _is_excel_backstage_save_as(existing_popup):
        existing_popup = _open_local_save_dialog(window.handle, existing_popup)
        if existing_popup is None:
            return {
                "verified": False,
                "status": "local_save_dialog_not_found",
                "popup": public_popup,
                "error": "Excel did not open the native local Save As dialog after Xelora clicked Browse.",
            }
        public_popup = {
            key: value for key, value in existing_popup.items()
            if key not in {"_buttons", "_edit_values", "normalized"}
        }

    if not _is_native_save_dialog(existing_popup):
        return {
            "verified": False,
            "status": "native_save_dialog_not_ready",
            "popup": public_popup,
            "error": "The visible Save As screen does not expose a local filename field and Save button.",
        }
    if not _select_local_documents_folder(existing_popup):
        return {
            "verified": False,
            "status": "local_documents_not_selected",
            "popup": public_popup,
            "error": "Xelora could not select the local Documents folder in the inspected Save As dialog.",
        }
    if not _set_save_as_filename(existing_popup, requested_name):
        return {
            "verified": False,
            "status": "save_filename_not_entered",
            "popup": public_popup,
            "error": "Xelora could not set the visible Save As filename field.",
        }
    clicked = _click_popup_button(existing_popup, ("Save",))
    if not clicked:
        return {
            "verified": False,
            "status": "save_button_not_found",
            "popup": public_popup,
            "error": "The visible Save As dialog did not expose an exact Save button.",
        }

    time.sleep(0.75)
    remaining = _read_excel_popups(window.handle)
    if remaining:
        pending = [
            {key: value for key, value in popup.items() if key not in {"_buttons", "_edit_values", "normalized"}}
            for popup in remaining
        ]
        return {
            "verified": False,
            "status": "save_requires_attention",
            "popups": pending,
            "error": "Excel displayed a follow-up dialog (for example overwrite confirmation); it was left untouched.",
        }
    try:
        saved_title = " ".join((_get_agent_excel_window().window_text() or "").split())
    except Exception:
        saved_title = ""
    title_verified = requested_name.lower() in saved_title.lower()
    if not title_verified:
        return {
            "verified": False,
            "status": "save_title_not_verified",
            "file_name": requested_name,
            "folder": _local_documents_folder(),
            "error": "Excel closed Save As, but the workbook title did not confirm the requested filename.",
        }
    global _bound_workbook_name
    _bound_workbook_name = requested_name
    return {
        "verified": True,
        "status": "saved",
        "file_name": requested_name,
        "folder": _local_documents_folder(),
        "generated_file_name": generated_name,
        "clicked_button": clicked,
        "verification_note": (
            f"Saved locally as '{requested_name}' in Documents through Excel's Browse workflow "
            "and verified the workbook title changed."
        ),
    }


def type_text(text: str, interval: float = 0.02) -> dict:
    _require_display()
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    _require_no_open_popup(window.handle)
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_type(text)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method
    if _activate_excel_window(window):
        pyautogui.typewrite(text, interval=interval)
    else:
        _send_text_to_excel(window, text)
    return {"typed": text, "verified": True}


def press_key(key: str) -> dict:
    _require_display()
    if str(key).strip().lower() == "f12":
        return {
            "verified": False,
            "status": "save_shortcut_blocked",
            "error": "F12 opens Save As. Use save_workbook only as the final workbook action after verification.",
        }
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    _require_no_open_popup(window.handle)
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_press(key)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method
    if _activate_excel_window(window):
        pyautogui.press(key)
    else:
        window.type_keys(_pyautogui_key_to_sendkeys(key), set_foreground=False)
    return {"pressed": key, "verified": True}


def hotkey(keys: list[str]) -> dict:
    _require_display()
    blocked = _blocked_excel_hotkey_result(keys)
    if blocked is not None:
        return blocked
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    _require_no_open_popup(window.handle)
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_hotkey(keys)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method
    if _activate_excel_window(window):
        normalized = [str(key).lower().strip() for key in keys]
        if normalized[:1] == ["alt"] and len(normalized) > 2:
            # Ribbon key tips are a sequence, not a simultaneous chord.
            pyautogui.press("alt")
            for key in normalized[1:]:
                pyautogui.press(key)
                time.sleep(0.12)
        else:
            pyautogui.hotkey(*keys)
    else:
        window.type_keys(_hotkey_to_sendkeys(keys), set_foreground=False)
    # Clear parse cache after hotkey (screen state likely changed)
    _clear_parse_cache_safe()
    return {"pressed": keys, "verified": True}


def _clear_parse_cache_safe():
    """Clear the OmniParser cache after screen-changing actions."""
    try:
        if config.OMNIPARSER_LOCAL_MODE:
            from vision.local_omniparser import clear_parse_cache
            clear_parse_cache()
    except Exception:
        pass


def _blocked_excel_hotkey_result(keys: list[str], *, allow_alt_sequence: bool = False) -> dict | None:
    """Reject unsafe or ambiguous raw key input before it reaches Excel."""
    normalized = tuple(str(key).lower().strip() for key in keys)
    blocked = {
        ("alt", "tab"): "Alt+Tab switches Windows applications and is not an Excel action.",
        ("alt", "f4"): "Alt+F4 can close the Excel application and is not allowed during a task.",
        ("ctrl", "f4"): "Ctrl+F4 can close the active workbook and is not allowed during a task.",
        ("ctrl", "shift", "esc"): "Ctrl+Shift+Esc opens Windows Task Manager and is not an Excel action.",
        (
            "ctrl", "shift", "f3"
        ): "Ctrl+Shift+F3 opens Create Names from Selection. It is not a supported table-naming action.",
    }
    if normalized not in blocked:
        # ``hotkey`` represents a simultaneous modifier chord.  A sequence
        # such as ["o", "i"] or a bare ["r"] is not a shortcut; it can type
        # into a selected cell, change an Excel menu, or act on a modal dialog.
        # Route those through their explicit, verified tools instead.
        if not normalized or not any(key in {"ctrl", "control", "alt", "shift"} for key in normalized):
            return {
                "verified": False,
                "status": "ambiguous_raw_key_input_blocked",
                "error": "Use press_key for one key, press_alt for a Ribbon KeyTip sequence, or a documented Ctrl shortcut. Raw key sequences are not allowed.",
            }
        if normalized[0] == "alt" and not allow_alt_sequence:
            return {
                "verified": False,
                "status": "ambiguous_raw_key_input_blocked",
                "error": "Use press_alt for Excel Ribbon KeyTips or execute_excel_shortcut for a documented Alt shortcut; do not send Alt sequences through hotkey.",
            }
        if normalized == ("shift", "f11"):
            return {
                "verified": False,
                "status": "ambiguous_raw_key_input_blocked",
                "error": "Use create_sheet(sheet_name) so the new worksheet is observed and named before later input is sent.",
            }
        return None
    return {
        "verified": False,
        "status": "unsafe_system_shortcut_blocked",
        "error": blocked[normalized],
    }


def _send_text_to_excel(window, text: str) -> None:
    """Type literal user data into the known Excel window without foreground focus."""
    escaped = (text.replace("{", "{{}").replace("}", "{}}").replace("+", "{+}")
                   .replace("^", "{^}").replace("%", "{%}").replace("~", "{~}")
                   .replace("(", "{(}").replace(")", "{)}").replace("\r\n", "\n")
                   .replace("\n", "{ENTER}"))
    window.type_keys(escaped, set_foreground=False)


def _pyautogui_key_to_sendkeys(key: str) -> str:
    normalized = key.lower().strip()
    special = {
        "enter": "{ENTER}", "esc": "{ESC}", "escape": "{ESC}", "tab": "{TAB}",
        "backspace": "{BACKSPACE}", "delete": "{DELETE}", "home": "{HOME}",
        "end": "{END}", "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}",
        "right": "{RIGHT}", "pageup": "{PGUP}", "pagedown": "{PGDN}",
        "insert": "{INSERT}",
    }
    if normalized in special:
        return special[normalized]
    if re.fullmatch(r"f(?:[1-9]|1[0-2])", normalized):
        return "{" + normalized.upper() + "}"
    if len(normalized) == 1 and normalized.isalnum():
        return normalized
    raise ValueError(f"Unsupported key for background Excel input: {key}")


def _hotkey_to_sendkeys(keys: list[str]) -> str:
    normalized = [str(key).lower().strip() for key in keys]
    modifiers = ""
    while normalized and normalized[0] in {"ctrl", "control", "alt", "shift"}:
        modifier = normalized.pop(0)
        modifiers += {"ctrl": "^", "control": "^", "alt": "%", "shift": "+"}[modifier]
    if len(normalized) != 1:
        raise ValueError("A background Excel hotkey must contain modifiers followed by one key.")
    return modifiers + _pyautogui_key_to_sendkeys(normalized[0])


def go_to_range(reference: str) -> dict:
    """Select a cell/range through Excel's native Go To dialog (Ctrl+G)."""
    _require_display()
    reference = reference.strip()
    if not _is_valid_go_to_reference(reference):
        raise ValueError(
            "reference must be an A1 cell/range, whole-column range, whole-row range, or defined Excel name. "
            "Quote sheet names containing spaces, for example 'Sales Data'!A:M."
        )
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    _require_no_open_popup(window.handle)
    if _activate_excel_window(window):
        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(reference, interval=0.01)
        pyautogui.press("enter")
    else:
        # Send to the known Excel window rather than sending keyboard input to
        # Xelora when Windows temporarily keeps the desktop app foreground.
        window.type_keys("^g", set_foreground=False)
        time.sleep(0.2)
        window.type_keys("^a", set_foreground=False)
        window.type_keys(reference, set_foreground=False)
        window.type_keys("{ENTER}", set_foreground=False)
    time.sleep(0.25)
    # Clear parse cache after navigation (cell selection changed)
    _clear_parse_cache_safe()
    return {"reference": reference, "verified": True,
            "verification_note": "Excel Go To accepted the requested cell, range, or defined name."}


def paste_table(headers: list[str], rows: list[list], start_cell: str = "A1") -> dict:
    """Paste a rectangular TSV table into Excel as one keyboard action."""
    _require_display()
    if not _HAS_WIN32GUI:
        raise RuntimeError("Atomic table paste requires Windows clipboard support.")
    if not headers or not all(isinstance(header, str) and header.strip() for header in headers):
        raise ValueError("headers must contain one or more non-empty strings.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows must contain at least one data row.")
    width = len(headers)
    normalized_rows = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"row {index} must contain exactly {width} values.")
        normalized_rows.append(["" if value is None else str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in row])
    go_to_range(start_cell)
    tsv = "\r\n".join(["\t".join(headers)] + ["\t".join(row) for row in normalized_rows])
    _set_clipboard_text(tsv)
    hotkey(["ctrl", "v"])
    return {
        "start_cell": start_cell,
        "rows": len(normalized_rows),
        "columns": width,
        "verified": True,
        "verification_note": "The complete rectangular table was pasted into Excel in one action.",
    }


def _set_clipboard_text(text: str) -> None:
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                return
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("Windows clipboard was busy, so the table could not be pasted safely.")


def _get_clipboard_text() -> str:
    """Read Unicode text from the clipboard, retrying past transient lock errors.

    Excel (and other apps) briefly hold the clipboard, so a single read often
    raises 'Access is denied'. Retry with backoff like _set_clipboard_text does.
    """
    import win32clipboard as _cb
    last_err: Exception | None = None
    for _ in range(10):
        try:
            _cb.OpenClipboard()
            try:
                if _cb.IsClipboardFormatAvailable(_cb.CF_UNICODETEXT):
                    return _cb.GetClipboardData(_cb.CF_UNICODETEXT) or ""
                return ""
            finally:
                _cb.CloseClipboard()
        except Exception as exc:  # noqa: BLE001 - transient lock; retry
            last_err = exc
            time.sleep(0.05)
    return ""


def fill_formula_down(start_cell: str, end_cell: str, formula: str) -> dict:
    """Enter one formula then use Excel's Fill Down shortcut for one column."""
    if not formula.startswith("="):
        raise ValueError("formula must start with '='.")
    if not re.fullmatch(r"\$?[A-Za-z]{1,3}\$?\d+", start_cell):
        raise ValueError("start_cell must be a single A1 cell reference.")
    if not re.fullmatch(r"\$?[A-Za-z]{1,3}\$?\d+", end_cell):
        raise ValueError("end_cell must be a single A1 cell reference.")
    go_to_range(start_cell)
    type_text(formula)
    press_key("enter")
    go_to_range(f"{start_cell}:{end_cell}")
    hotkey(["ctrl", "d"])
    return {"range": f"{start_cell}:{end_cell}", "formula": formula, "verified": True,
            "verification_note": "Formula was entered and filled down through the requested range."}


def format_currency(reference: str) -> dict:
    go_to_range(reference)
    hotkey(["ctrl", "shift", "4"])
    return {"range": reference, "verified": True,
            "verification_note": "Excel currency format shortcut was applied to the selected range."}


def format_bold(reference: str) -> dict:
    go_to_range(reference)
    hotkey(["ctrl", "b"])
    return {"range": reference, "verified": True,
            "verification_note": "Bold formatting was applied to the selected range."}


def autofit_columns(reference: str) -> dict:
    go_to_range(reference)
    hotkey(["alt", "h", "o", "i"])
    return {"range": reference, "verified": True,
            "verification_note": "Excel AutoFit Column Width command was sent for the selected range."}


def create_clustered_column_chart(reference: str) -> dict:
    """Create a chart only when Excel exposes a new chart object afterwards."""
    window = _get_agent_excel_window()
    count_before = _chart_count(window)
    go_to_range(reference)
    hotkey(["alt", "n", "c", "1"])
    time.sleep(1.0)
    count_after = _chart_count(window)
    if count_before is None or count_after is None or count_after <= count_before:
        return {
            "source_range": reference,
            "command_sent": True,
            "verified": False,
            "verification_note": (
                "The chart shortcut was sent, but a new chart object could not be verified. "
                "The chart must not be reported as created."
            ),
        }
    return {
        "source_range": reference,
        "chart_count_before": count_before,
        "chart_count_after": count_after,
        "verified": True,
        "verification_note": "Excel exposed a new chart object after the command.",
    }


def _chart_count(window) -> int | None:
    """Conservatively count chart controls exposed by Windows UI Automation."""
    if not _HAS_PYWINAUTO:
        return None
    try:
        count = 0
        for control in window.descendants():
            info = control.element_info
            control_type = str(getattr(info, "control_type", "")).lower()
            name = " ".join(control.window_text().split()).lower()
            if control_type == "chart" or re.fullmatch(r"chart\s*\d+", name):
                count += 1
        return count
    except Exception:
        return None


def create_pie_chart(reference: str) -> dict:
    """Create a pie chart from a two-column source range with headers.
    
    Selects the source range and uses Alt+N+C+I (Insert Pie Chart).
    Verifies a new chart object was created.
    """
    window = _get_agent_excel_window()
    count_before = _chart_count(window)
    go_to_range(reference)
    # Alt+N = Insert, C = Chart, I = Insert Pie Chart (2-D Pie)
    hotkey(["alt", "n", "c", "i"])
    time.sleep(1.0)
    count_after = _chart_count(window)
    if count_before is None or count_after is None or count_after <= count_before:
        return {
            "source_range": reference,
            "command_sent": True,
            "verified": False,
            "verification_note": (
                "The pie chart shortcut was sent, but a new chart object could not be verified. "
                "The chart must not be reported as created."
            ),
        }
    return {
        "source_range": reference,
        "chart_count_before": count_before,
        "chart_count_after": count_after,
        "verified": True,
        "verification_note": "Excel exposed a new pie chart object after the command.",
    }


def verify_task_completion(expected_sheets: list[str] = None, expected_formulas: dict = None) -> dict:
    """Cross-check that the task deliverables were actually created.
    
    Args:
        expected_sheets: List of sheet names that should exist
        expected_formulas: Dict of {sheet_name: [(cell, expected_formula_prefix), ...]}
    
    Returns:
        dict with "complete": bool, "issues": list[str], "verified_sheets": list[str]
    """
    issues = []
    verified_sheets = []
    
    # Check sheet existence
    if expected_sheets:
        existing = get_existing_sheet_names()
        for sheet in expected_sheets:
            if any(s.lower() == sheet.lower() for s in existing):
                verified_sheets.append(sheet)
            else:
                issues.append(f"Sheet '{sheet}' not found. Existing sheets: {existing}")
    
    complete = len(issues) == 0
    return {
        "verified": complete,
        "complete": complete,
        "issues": issues,
        "verified_sheets": verified_sheets,
        "all_sheets": get_existing_sheet_names(),
        "verification_note": (
            "All requested worksheet names were found."
            if complete
            else "The requested worksheet verification found missing deliverables."
        ),
    }


def activate_ribbon_tab(tab: str, fallback_keys: list[str] | None = None) -> dict:
    """Open a tab with its Excel shortcut, then verify the selected tab."""
    if not _HAS_PYWINAUTO:
        raise RuntimeError("Windows UI Automation is unavailable, so ribbon-tab selection cannot be verified.")
    _require_display()
    window = _get_agent_excel_window()
    _ensure_agent_workbook(window)
    _focus_excel_for_keyboard()
    label = tab.strip().title()
    try:
        if fallback_keys:
            pyautogui.hotkey(*fallback_keys)
            time.sleep(0.35)
        candidates = [
            control for control in window.descendants(control_type="TabItem")
            if " ".join(control.window_text().split()).lower() == tab.strip().lower()
        ]
        if not candidates:
            raise RuntimeError(f"The '{label}' ribbon tab was not found in the open workbook.")
        target = candidates[0]
        is_selected = _is_tab_selected(target)
        if not is_selected and not fallback_keys:
            # UI Automation is a fallback only when the tab has no shortcut.
            is_selected = _click_and_check_selected(target)
        if not is_selected:
            raise RuntimeError(f"Excel did not select the '{label}' ribbon tab after two attempts.")
    except Exception as exc:
        raise RuntimeError(f"Could not activate the Excel {label} tab: {exc}") from exc
    return {
        "tab": label,
        "verified": True,
        "verification_note": "Excel shortcut was sent and the named ribbon tab was confirmed selected through Windows UI Automation.",
    }


def _click_and_check_selected(target) -> bool:
    """Click a ribbon TabItem and confirm Excel actually switched to it.

    A click that doesn't throw is not proof the tab became active - Office's
    ribbon can eat a click during a repaint. Read the control's real
    selection state back instead of assuming the click worked.
    """
    target.click_input()
    try:
        target.select()
    except Exception:
        pass
    time.sleep(0.25)
    try:
        if hasattr(target, "is_selected"):
            return bool(target.is_selected())
        if hasattr(target, "get_toggle_state"):
            return bool(target.get_toggle_state())
    except Exception:
        return False
    # Neither selection API is available on this control - fall back to the
    # legacy (unverified) behavior rather than failing a host that simply
    # doesn't expose SelectionItem/Toggle patterns.
    return True


def _is_tab_selected(target) -> bool:
    """Read a ribbon TabItem selection state without clicking it."""
    try:
        if hasattr(target, "is_selected"):
            return bool(target.is_selected())
        if hasattr(target, "get_toggle_state"):
            return bool(target.get_toggle_state())
    except Exception:
        return False
    return False


def press_alt(keys: list[str]) -> dict:
    """Send an Alt-key ribbon sequence, e.g. press_alt(['h','o','i']) for Format Cells.

    Unlike a plain hotkey, this presses Alt to reveal Excel's keytips, then sends
    each following key in order (Alt+H, O, I opens the Format Cells dialog). It is
    the reliable way to reach ribbon commands that have no direct Ctrl shortcut.
    """
    _require_display()
    window = _get_agent_excel_window()
    _ensure_agent_workbook(window)
    _focus_excel_for_keyboard()
    keys = [str(k).strip().lower() for k in keys if str(k).strip()]
    if not keys:
        raise RuntimeError("press_alt requires a non-empty list of keys.")
    if keys[0] == "f":
        return {
            "verified": False,
            "status": "save_shortcut_blocked",
            "error": "Do not navigate Excel's File menu. Use save_workbook only as the final workbook action after verification.",
        }
    blocked = _blocked_excel_hotkey_result(["alt", *keys], allow_alt_sequence=True)
    if blocked is not None:
        return blocked
    # Alt first to open keytips, then each key in sequence.
    pyautogui.press("alt")
    time.sleep(0.35)
    for k in keys:
        pyautogui.press(k)
        time.sleep(0.2)
    return {
        "sent": ["alt", *keys],
        "verified": True,
        "verification_note": "Alt sequence sent. If a dialog opened, capture it with parse_screen(zone='popup').",
    }


def press_shortcut(shortcut_name: str) -> dict:
    """Perform a common Excel operation entirely via Alt-key ribbon sequences.

    This is the Alt-plus-keys task runner: no mouse, no vision, no OmniParser.
    It maps a friendly name to the exact Alt sequence Excel uses, sends it, and
    returns what dialog/state it should have opened so the agent can continue.

    Supported names (Alt sequences are Excel-stable across versions):
    - format_cells        -> Alt, H, O, I   (Format Cells dialog)
    - insert_chart        -> Alt, N, C      (Insert Chart)
    - insert_pivot        -> Alt, N, V      (Insert PivotTable)
    - insert_table        -> Alt, N, T      (Insert Table)
    - borders_all         -> Alt, H, B, A   (All borders)
    - borders_thick       -> Alt, H, B, T
    - fill_color          -> Alt, H, H      (open fill-color menu)
    - font_color          -> Alt, H, F, C   (open font-color menu)
    - bold                -> Alt, H, 1      (bold)
    - merge_center        -> Alt, H, M, C   (Merge & Center)
    - autofit_columns     -> Alt, H, O, I   (AutoFit Column Width)
    - wrap_text           -> Alt, H, W      (Wrap Text)
    - number_format       -> Alt, H, N      (open Number Format menu)
    - sum_below           -> Alt, =         (AutoSum)
    """
    _ALT_TASK_SHORTCUTS = {
        "format_cells": ["h", "o", "i"],
        "insert_chart": ["n", "c"],
        "insert_pivot": ["n", "v"],
        "insert_table": ["n", "t"],
        "borders_all": ["h", "b", "a"],
        "borders_thick": ["h", "b", "t"],
        "fill_color": ["h", "h"],
        "font_color": ["h", "f", "c"],
        "bold": ["h", "1"],
        "merge_center": ["h", "m", "c"],
        "autofit_columns": ["h", "o", "i"],
        "wrap_text": ["h", "w"],
        "number_format": ["h", "n"],
        "sum_below": ["=", "alt"],
    }
    name = shortcut_name.strip().lower()
    if name not in _ALT_TASK_SHORTCUTS:
        raise RuntimeError(
            f"Unknown Alt shortcut '{shortcut_name}'. Supported: "
            f"{', '.join(sorted(_ALT_TASK_SHORTCUTS))}"
        )
    if name == "insert_table":
        return create_excel_table()
    keys = _ALT_TASK_SHORTCUTS[name]
    # For sum_below the natural key is Alt+=, but represented generally:
    if name == "sum_below":
        _focus_excel_for_keyboard()
        pyautogui.hotkey("alt", "=")
        return {
            "sent": ["alt", "="],
            "shortcut": name,
            "verified": True,
            "verification_note": "AutoSum (Alt+=) sent. A formula was inserted; press Enter to confirm.",
        }
    result = press_alt(keys)
    result["shortcut"] = name
    return result


def find_and_click(name: str, control_type: str = None, double: bool = False) -> dict:
    """Find a UI element by name via Windows UI Automation and click it.

    UIA-first (fast, no screenshot). This is the reliable path for ribbon tabs,
    buttons, and menu items; falls back to OmniParser only via the agent loop.
    """
    _require_display()
    if not _HAS_PYWINAUTO:
        raise RuntimeError("Windows UI Automation is unavailable, so find_and_click cannot verify the target.")
    window = _get_agent_excel_window()
    _ensure_agent_workbook(window)
    _focus_excel_for_keyboard()
    target = None
    name_l = " ".join(name.strip().split()).lower()

    # Models sometimes ask to "find" the active worksheet tab. Route an exact
    # sheet-name request to the dedicated tab operation instead of searching
    # every Ribbon control and falsely reporting that a real sheet is absent.
    for sheet_name in get_existing_sheet_names():
        if sheet_name.lower() == name_l:
            sheet_result = go_to_sheet(sheet_name)
            if sheet_result.get("verified") is True:
                return {
                    "clicked_element": sheet_name,
                    "found_by": "worksheet_tab",
                    "verified": True,
                    "verification_note": f"Activated worksheet tab '{sheet_name}' through the dedicated sheet navigator.",
                }
            return sheet_result
    for control in window.descendants():
        try:
            txt = " ".join(control.window_text().split()).lower()
            if not txt or name_l not in txt:
                continue
            if control_type:
                ct = str(getattr(control.element_info, "control_type", "")).lower()
                if control_type.lower() not in ct:
                    continue
            target = control
            break
        except Exception:
            continue
    if target is None:
        raise RuntimeError(f"Could not find a UI element named '{name}' in Excel via UI Automation.")
    try:
        if double:
            target.click_input(double=True)
        else:
            target.click_input()
    except Exception as exc:
        raise RuntimeError(f"Found '{name}' but could not click it: {exc}") from exc
    time.sleep(0.3)
    return {
        "clicked_element": name,
        "found_by": "uia",
        "verified": True,
        "verification_note": f"Found and clicked '{name}' via UIA (no screenshot needed).",
    }


def scroll(clicks: int) -> dict:
    _require_display()
    _focus_excel_for_keyboard()
    pyautogui.scroll(clicks)
    return {"scrolled": clicks, "verified": True}


def list_open_windows() -> dict:
    """Used by the OS-Level Event Listener / window-focus awareness -
    Windows-only (pywinauto)."""
    if not _HAS_PYWINAUTO:
        return {"windows": [], "verified": False,
                "verification_note": "pywinauto not available - Windows-only feature."}
    windows = [w.window_text() for w in Desktop(backend="uia").windows() if w.window_text()]
    return {"windows": windows, "verified": True}


def execute_excel_shortcut(shortcut_name: str) -> dict:
    """Execute a named Excel keyboard shortcut directly (bypasses vision).
    
    This is the fastest way to perform standard Excel operations like:
    - bold, italic, underline
    - currency format, percent format
    - merge cells, auto-fit columns
    - sort, filter
    - insert charts, tables
    - etc.
    
    Args:
        shortcut_name: Name from EXCEL_SHORTCUTS (e.g., 'bold', 'currency', 'merge_center')
    
    Returns:
        Dict with verification info
    """
    _require_display()

    normalized_name = str(shortcut_name or "").strip().lower()
    # Saving a new workbook is not just a key chord: Excel opens Save As and
    # a filename plus a real Save-button click are required.  Route named Save
    # through the transactional visual helper so the agent cannot mistake a
    # blocked dialog for a completed save.
    if normalized_name == "save":
        return save_workbook()
    if normalized_name == "save_as":
        return {
            "verified": False,
            "status": "save_filename_required",
            "error": "Use save_workbook with file_name to complete the native Save As dialog safely.",
        }
    if normalized_name == "insert_table":
        return create_excel_table()
    
    resolved = resolve_shortcut(shortcut_name)
    if not resolved:
        return {
            "verified": False,
            "error": (
                f"Unknown shortcut: {shortcut_name}. Use a named shortcut, a standard chord such as "
                "'ctrl+shift+l', or press_alt for a sequential Ribbon KeyTip command."
            ),
            "available_shortcuts": list(EXCEL_SHORTCUTS.keys()),
        }
    blocked = _blocked_excel_hotkey_result(
        list(resolved[0]),
        allow_alt_sequence=bool(resolved[0] and resolved[0][0] == "alt"),
    )
    if blocked is not None:
        return blocked
    
    # Focus Excel first
    _focus_excel_for_keyboard()
    
    # Execute the shortcut
    success = execute_shortcut(shortcut_name)
    
    if success:
        return {
            "verified": True,
            "shortcut": shortcut_name,
            "keys": list(resolved[0]),
            "shortcut_kind": resolved[1],
            "verification_note": f"Executed shortcut '{shortcut_name}' directly without vision.",
        }
    else:
        return {
            "verified": False,
            "error": f"Failed to execute shortcut '{shortcut_name}'",
        }


def execute_excel_alt_sequence(keys: list[str]) -> dict:
    """Execute a raw Alt key sequence for Excel operations.
    
    This allows direct execution of any Excel keyboard shortcut,
    even if it's not in the predefined list.
    
    Args:
        keys: List of keys (e.g., ['alt', 'h', 'b', 'a'] for all borders)
    
    Returns:
        Dict with verification info
    """
    _require_display()
    blocked = _blocked_excel_hotkey_result(keys)
    if blocked is not None:
        return blocked
    _focus_excel_for_keyboard()
    
    success = execute_alt_sequence(keys)
    
    if success:
        return {
            "verified": True,
            "keys": keys,
            "verification_note": "Executed Alt key sequence directly without vision.",
        }
    else:
        return {
            "verified": False,
            "error": f"Failed to execute key sequence: {keys}",
        }


def batch_excel_operations(operations: list[dict]) -> dict:
    """Execute multiple Excel operations in sequence without pausing for verification.
    
    Args:
        operations: List of operations, each with:
            - type: 'shortcut', 'alt_sequence', 'type_text', 'press_key', 'go_to_range'
            - For shortcut: {'type': 'shortcut', 'name': 'bold'}
            - For alt_sequence: {'type': 'alt_sequence', 'keys': ['alt', 'h', 'b', 'a']}
            - For type_text: {'type': 'type_text', 'text': 'Hello'}
            - For press_key: {'type': 'press_key', 'key': 'enter'}
            - For go_to_range: {'type': 'go_to_range', 'reference': 'A1'}
    
    Returns:
        Dict with results of each operation
    """
    results = []
    
    for op in operations:
        op_type = op.get("type")
        
        if op_type == "shortcut":
            result = execute_excel_shortcut(op.get("name", ""))
        elif op_type == "alt_sequence":
            result = execute_excel_alt_sequence(op.get("keys", []))
        elif op_type == "type_text":
            result = type_text(op.get("text", ""))
        elif op_type == "press_key":
            result = press_key(op.get("key", ""))
        elif op_type == "go_to_range":
            result = go_to_range(op.get("reference", ""))
        else:
            result = {"verified": False, "error": f"Unknown operation type: {op_type}"}
        
        results.append({
            "operation": op,
            "result": result,
        })
    
    return {
        "verified": all(r["result"].get("verified", False) for r in results),
        "results": results,
        "operations_count": len(operations),
    }


def search_cached_elements(text: str, context: str = "") -> dict:
    """Search cached screen data for elements matching text.
    
    This allows finding UI elements from previous parses without
    taking a new screenshot.
    
    Args:
        text: Text to search for (case-insensitive)
        context: Optional context to filter by
    
    Returns:
        Dict with matching elements
    """
    matches = find_cached_elements(text, context)
    
    return {
        "verified": True,
        "matches": matches,
        "count": len(matches),
        "query": text,
        "context": context,
    }
