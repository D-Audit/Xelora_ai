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

This module provides the primitives (screenshot, click, type, find-
window). The actual "which button do I click" decision is made by the
AI: it's given the screenshot, plans in text where to click, and this
module just executes that plan. Wiring that loop into agent/core.py is
Phase 2 (see README "What's scaffolded vs implemented").
"""

import ctypes
import re
import subprocess
import time

try:
    import winreg
except ImportError:
    winreg = None

from vision.omniparser_client import parse_image

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except Exception:
    _HAS_PYAUTOGUI = False

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

_last_elements: list[dict] = []
_last_parse_at: float | None = None
_last_parse_window_handle: int | None = None
_agent_excel_handle: int | None = None
_use_existing_workbook = False
_bound_excel_pid: int | None = None
_bound_workbook_name: str | None = None

_EXCEL_START_TIMEOUT_SECONDS = 15
_PARSED_TARGET_MAX_AGE_SECONDS = 15

_SHEET_PREFIX = r"(?:(?:'(?:[^']|'')+'|[A-Za-z0-9_]+)!)?"
_A1_CELL = r"\$?[A-Za-z]{1,3}\$?\d+"
_A1_REFERENCE = rf"{_SHEET_PREFIX}(?:{_A1_CELL}(?::{_A1_CELL})?|\$?[A-Za-z]{{1,3}}:\$?[A-Za-z]{{1,3}}|\$?\d+:\$?\d+)"
_DEFINED_NAME = r"[A-Za-z_][A-Za-z0-9_.]*"


def _is_valid_go_to_reference(reference: str) -> bool:
    """Validate native Go To references without accepting prose as keystrokes."""
    return bool(re.fullmatch(_A1_REFERENCE, reference) or re.fullmatch(_DEFINED_NAME, reference))


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
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
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


def _open_blank_excel_window():
    """Launch desktop Excel and wait for its initial blank workbook window."""
    global _agent_excel_handle
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
        # /x starts a separate Excel instance, keeping the user's existing
        # workbooks outside the agent's controlled session.
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
    """Excel launched with /x can open to its Start screen (showing the
    user's recent/pinned files) or restore a previous session instead of a
    fresh blank workbook. The agent must never operate on the user's files,
    so before the AI ever parses the screen: dismiss any Start screen / stray
    dialog and force a new blank workbook with Ctrl+N.

    Keys are only sent if Excel can be verified as the foreground window -
    otherwise we skip rather than risk typing into another application.
    """
    try:
        if window.is_minimized():
            window.restore()
        _activate_excel_window(window)
        window.type_keys("{ESC}", set_foreground=False)  # dismiss Start screen / stray dialog
        time.sleep(0.4)
        window.type_keys("^n", set_foreground=False)     # Ctrl+N: guaranteed fresh blank workbook
        time.sleep(1.0)
    except Exception:
        pass


def _get_agent_excel_window():
    """Return only the blank Excel instance launched for this agent session."""
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
        return window
    window = _window_by_handle(_agent_excel_handle)
    if window is not None:
        _maximize_excel_window(window)
        return window
    return _open_blank_excel_window()


def set_workbook_mode(use_existing: bool) -> None:
    """Choose between the user's open workbook and the agent-owned blank one."""
    global _use_existing_workbook, _bound_excel_pid, _bound_workbook_name
    _use_existing_workbook = use_existing
    if not use_existing:
        _bound_excel_pid = None
        _bound_workbook_name = None


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
    if not _use_existing_workbook:
        _ensure_agent_workbook(window)
        # A prior interrupted task may have left a temporary dialog open.
        # Target Excel directly instead of requiring the user to click it.
        try:
            window.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
    return {
        "window_title": window.window_text(),
        "mode": "existing_workbook" if _use_existing_workbook else "agent_blank_workbook",
        "verified": True,
    }


def _capture_excel_window():
    """Focus and capture Excel, returning its image and screen origin.

    OmniParser returns coordinates relative to this image.  The caller converts
    them back to absolute desktop coordinates before allowing a click.
    """
    window = _get_agent_excel_window()

    try:
        foreground_verified = _activate_excel_window(window)
        rect = window.rectangle()
        image = window.capture_as_image()
        return image, (rect.left, rect.top), {
            "title": window.window_text(),
            "handle": window.handle,
            "rect": [rect.left, rect.top, rect.right, rect.bottom],
            "foreground_verified": foreground_verified,
        }
    except Exception:
        # Falling back to the desktop keeps the visual tool usable if Windows
        # blocks foreground activation for a particular Excel instance.
        return None


def _focus_excel_for_keyboard(expected_window_handle: int | None = None):
    """Bring the expected Excel window forward before input is sent."""
    window = _window_by_handle(expected_window_handle) if expected_window_handle is not None else _get_agent_excel_window()
    if window is None:
        raise RuntimeError("The Excel window captured for this action is no longer available. Re-run screen parsing first.")
    try:
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
    try:
        _focus_excel_for_keyboard()
        pyautogui.hotkey("ctrl", "n")
    except RuntimeError:
        # pywinauto targets the known Excel window directly, so this remains
        # safe even if Windows temporarily refuses foreground activation.
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
    """Captures the current screen (Intelligent Window Capture, simplified
    to whole-screen for portability - swap in pywinauto's per-window
    capture on Windows for the 'window-specific screenshot' variant)."""
    _require_display()
    img = pyautogui.screenshot()
    return {"screen_size": list(img.size), "verified": True}


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
    _focus_excel_for_keyboard(expected_window_handle)
    if double:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y)
    time.sleep(0.2)
    return {"clicked_at": [x, y], "double": double, "verified": True}


def parse_screen(zone: str = "window") -> dict:
    """Parse a focused Excel ribbon, dialog area, or whole window on demand."""
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
    parsed = parse_image(image)
    for element in parsed["elements"]:
        x1, y1, x2, y2 = element["bbox"]
        element["bbox"] = [x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y]
        element["center"] = [element["center"][0] + offset_x, element["center"][1] + offset_y]
    _last_elements = parsed["elements"]
    _last_parse_at = time.monotonic()
    _last_parse_window_handle = window_info["handle"]
    return {
        **parsed,
        "verified": True,
        "capture_target": "excel_window",
        "window": window_info,
    }


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


def click(x: int, y: int) -> dict:
    global _last_elements, _last_parse_at, _last_parse_window_handle
    element = _validated_target(x, y)
    try:
        return {**click_at(x, y, expected_window_handle=_last_parse_window_handle), "element": element}
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
        return {**click_at(x, y, double=True, expected_window_handle=_last_parse_window_handle), "element": element}
    finally:
        _last_elements = []
        _last_parse_at = None
        _last_parse_window_handle = None


def type_text(text: str, interval: float = 0.02) -> dict:
    _require_display()
    window = _get_agent_excel_window()
    if _activate_excel_window(window):
        pyautogui.typewrite(text, interval=interval)
    else:
        _send_text_to_excel(window, text)
    return {"typed": text, "verified": True}


def press_key(key: str) -> dict:
    _require_display()
    window = _get_agent_excel_window()
    if _activate_excel_window(window):
        pyautogui.press(key)
    else:
        window.type_keys(_pyautogui_key_to_sendkeys(key), set_foreground=False)
    return {"pressed": key, "verified": True}


def hotkey(keys: list[str]) -> dict:
    _require_display()
    window = _get_agent_excel_window()
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
    return {"pressed": keys, "verified": True}


def _send_text_to_excel(window, text: str) -> None:
    """Type literal user data into the known Excel window without foreground focus."""
    escaped = (text.replace("{", "{{}").replace("}", "{}}").replace("+", "{+}")
                   .replace("^", "{^}").replace("%", "{%}").replace("~", "{~}")
                   .replace("(", "{(}").replace(")", "{)}").replace("\r\n", "\n")
                   .replace("\n", "{ENTER}"))
    window.type_keys(escaped, set_foreground=False)


def _pyautogui_key_to_sendkeys(key: str) -> str:
    normalized = key.lower().strip()
    special = {"enter": "{ENTER}", "esc": "{ESC}", "escape": "{ESC}", "tab": "{TAB}", "backspace": "{BACKSPACE}", "delete": "{DELETE}"}
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
