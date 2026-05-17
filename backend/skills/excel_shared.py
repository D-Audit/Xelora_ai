"""
skills/excel_shared.py
Helpers shared by every skill and by codegen.
"""

import contextvars
import os
import subprocess
import time
import xlwings as xw

_CURRENT_WORKBOOK_NAME = contextvars.ContextVar("current_workbook_name", default=None)
_RESTART_COUNT = contextvars.ContextVar("excel_restart_count", default=0)

_LAST_KNOWN_WORKBOOK_PATH = None
_LAST_KNOWN_APP_PID = None

MAX_RESTARTS_PER_TASK = 2
RESPONSIVENESS_TIMEOUT_SECONDS = 20
RESPONSIVENESS_POLL_INTERVAL = 1

_DYNAMIC_ARRAY_SUPPORT_CACHE = {}  # keyed by app.pid - avoids re-probing every single call


def bind_workbook_context(workbook_name: str | None):
    """Called once per task. Also resets the restart counter, so a
    restart cap is per-task, not a permanent global limit."""
    _CURRENT_WORKBOOK_NAME.set(workbook_name)
    _RESTART_COUNT.set(0)


def _harden_app(app):
    app.display_alerts = False
    try:
        app.api.AutomationSecurity = 3
    except Exception:
        pass
    try:
        app.api.AskToUpdateLinks = False
    except Exception:
        pass
    try:
        app.api.AlertBeforeOverwriting = False
    except Exception:
        pass
    try:
        app.screen_updating = False
    except Exception:
        pass


def restore_screen_updating(app):
    try:
        app.screen_updating = True
    except Exception:
        pass


def set_calculation_mode(app, mode: str):
    """mode is 'manual' or 'automatic'. Always pair a 'manual' call with a
    guaranteed 'automatic' call afterward via try/finally at the call site."""
    try:
        app.calculation = mode
    except Exception:
        pass


def supports_dynamic_arrays(app) -> bool:
    """Excel's own Application.Version reports '16.0' for 2016, 2019, AND
    365 alike - it CANNOT distinguish them. The only reliable way to know
    if UNIQUE/SORT/FILTER/XLOOKUP/LET/SEQUENCE actually work on THIS
    specific user's Excel is to literally try one and see if Excel
    recognizes it - this runs fresh against whatever Excel is actually
    open, so it automatically adapts per user/machine rather than
    assuming any one version. Result is cached per Excel process so this
    only costs one extra call per session, not one per formula."""
    if app.pid in _DYNAMIC_ARRAY_SUPPORT_CACHE:
        return _DYNAMIC_ARRAY_SUPPORT_CACHE[app.pid]

    wb = app.books.active
    sheet = wb.sheets.active
    probe_cell = sheet.range("XFD1048576")  # farthest, almost-never-used corner cell

    try:
        original_value = probe_cell.value
        probe_cell.formula2 = "=SEQUENCE(1)"
        result = probe_cell.value
        supported = result is not None and str(result).strip().upper() != "#NAME?"
    except Exception:
        supported = False
    finally:
        try:
            probe_cell.value = original_value
        except Exception:
            pass

    _DYNAMIC_ARRAY_SUPPORT_CACHE[app.pid] = supported
    return supported


def _ensure_workbook_has_path(wb):
    if os.path.dirname(wb.fullname):
        return
    default_dir = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(default_dir, exist_ok=True)
    base_name = os.path.splitext(wb.name)[0] or "workbook"
    candidate = os.path.join(default_dir, f"{base_name}.xlsx")
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(default_dir, f"{base_name}_{counter}.xlsx")
        counter += 1
    wb.save(candidate)


def save_active_workbook_best_effort():
    """Called by agent/core.py after any skill call that completed without
    timing out - makes 'everything before a recovery is saved' actually
    true, rather than depending on individual skills remembering to save."""
    try:
        wb = get_active_workbook()
        wb.save()
    except Exception:
        pass


def _wait_until_responsive(app, timeout=RESPONSIVENESS_TIMEOUT_SECONDS) -> bool:
    """Polls a cheap, harmless COM call until the relaunched Excel process
    genuinely answers, instead of a blind sleep and hoping - this is what
    stops 'restart produces another immediately-hung instance' from
    happening silently."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _ = app.books.count
            return True
        except Exception:
            time.sleep(RESPONSIVENESS_POLL_INTERVAL)
    return False


def force_restart_excel_and_reopen():
    """
    Called automatically when a skill call times out. Kills ONLY the
    specific tracked PID - never by image name. Capped at
    MAX_RESTARTS_PER_TASK per task; once hit, raises instead of looping.
    """
    global _LAST_KNOWN_WORKBOOK_PATH, _LAST_KNOWN_APP_PID

    restart_count = _RESTART_COUNT.get()
    if restart_count >= MAX_RESTARTS_PER_TASK:
        raise RuntimeError(
            f"Already attempted {restart_count} Excel restart(s) in this task, all of "
            f"which were followed by another hang - this is not recovering. Stopping "
            f"auto-restarts. Please close every Excel window manually, reopen your file, "
            f"and start a new task."
        )
    _RESTART_COUNT.set(restart_count + 1)

    killed_note = "no tracked Excel process ID - did not force-kill anything."
    if _LAST_KNOWN_APP_PID:
        subprocess.run(["taskkill", "/F", "/PID", str(_LAST_KNOWN_APP_PID)], capture_output=True)
        killed_note = f"killed Excel process PID {_LAST_KNOWN_APP_PID} (only that one process)."
        time.sleep(1)

    app = xw.App(visible=True)

    if not _wait_until_responsive(app):
        raise RuntimeError(
            f"Relaunched Excel (after {killed_note}) but it did not become responsive "
            f"within {RESPONSIVENESS_TIMEOUT_SECONDS}s. Please check Excel manually."
        )

    _harden_app(app)
    _LAST_KNOWN_APP_PID = app.pid
    _DYNAMIC_ARRAY_SUPPORT_CACHE.pop(app.pid, None)  # fresh process - re-probe if/when needed

    if _LAST_KNOWN_WORKBOOK_PATH and os.path.exists(_LAST_KNOWN_WORKBOOK_PATH):
        wb = app.books.open(_LAST_KNOWN_WORKBOOK_PATH)
    else:
        wb = app.books.add()
        _ensure_workbook_has_path(wb)
        _LAST_KNOWN_WORKBOOK_PATH = wb.fullname

    restore_screen_updating(app)
    return wb, killed_note


def get_active_workbook():
    global _LAST_KNOWN_WORKBOOK_PATH, _LAST_KNOWN_APP_PID
    pinned_name = _CURRENT_WORKBOOK_NAME.get()

    if pinned_name:
        for app in xw.apps:
            for book in app.books:
                if book.name == pinned_name:
                    _harden_app(app)
                    _ensure_workbook_has_path(book)
                    restore_screen_updating(app)
                    _LAST_KNOWN_WORKBOOK_PATH = book.fullname
                    _LAST_KNOWN_APP_PID = app.pid
                    return book

    if len(xw.apps) == 0:
        app = xw.App(visible=True)
        _harden_app(app)
        wb = app.books.add()
    else:
        app = xw.apps.active
        _harden_app(app)
        wb = app.books.active

    _ensure_workbook_has_path(wb)
    restore_screen_updating(app)
    _LAST_KNOWN_WORKBOOK_PATH = wb.fullname
    _LAST_KNOWN_APP_PID = app.pid
    return wb


def normalize(values):
    if not isinstance(values, list):
        values = [[values]]
    elif values and not isinstance(values[0], list):
        values = [values]
    return values


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
