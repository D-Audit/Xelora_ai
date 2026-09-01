"""
skills/excel_shared.py
Helpers shared by every skill and by codegen.
"""

import contextvars
import os
import subprocess
import time
import xlwings as xw
import config

_CURRENT_WORKBOOK_NAME = contextvars.ContextVar("current_workbook_name", default=None)
_CURRENT_EXCEL_PID = contextvars.ContextVar("current_excel_pid", default=None)
_TASK_BOOTSTRAP_WORKBOOK = contextvars.ContextVar("task_bootstrap_workbook", default=False)
_RESTART_COUNT = contextvars.ContextVar("excel_restart_count", default=0)

_LAST_KNOWN_WORKBOOK_PATH = None
_LAST_KNOWN_APP_PID = None
# Keep a strong reference to every Excel instance Xelora starts through
# xlwings.  On Windows, dropping the last ``xw.App`` wrapper can release the
# final COM reference and make Excel exit after the first inspection.  A PID
# alone is not enough to keep that process alive.
_OWNED_EXCEL_APPS = {}

MAX_RESTARTS_PER_TASK = 2
RESPONSIVENESS_TIMEOUT_SECONDS = 20
RESPONSIVENESS_POLL_INTERVAL = 1

_DYNAMIC_ARRAY_SUPPORT_CACHE = {}  # keyed by app.pid - avoids re-probing every single call
_EXCEL_CAPABILITY_CACHE = {}  # keyed by app.pid; safe to reuse for one Excel process


def bind_workbook_context(workbook_name: str | None, excel_app_pid: int | None = None):
    """Bind all automation in this task to one workbook *and* Excel process.

    A workbook name alone is not a safe identity: Excel can have several
    unsaved ``Book1`` workbooks open, including in separate processes.  The
    process ID is therefore retained whenever it is known.  Legacy callers
    that only know a name preserve an already-bound PID for that same task.
    """
    _CURRENT_WORKBOOK_NAME.set(workbook_name)
    if workbook_name is None:
        _CURRENT_EXCEL_PID.set(None)
        _TASK_BOOTSTRAP_WORKBOOK.set(False)
    elif excel_app_pid is not None:
        _CURRENT_EXCEL_PID.set(int(excel_app_pid))
    _RESTART_COUNT.set(0)


def _app_pid(app) -> int | None:
    """Return an xlwings application's PID without making routing fail."""
    try:
        return int(app.pid)
    except Exception:
        return None


def retain_owned_excel_app(app) -> int | None:
    """Keep an Xelora-created Excel process alive for the server lifetime."""
    app_pid = _app_pid(app)
    if app_pid is not None:
        _OWNED_EXCEL_APPS[app_pid] = app
    return app_pid


def _forget_owned_excel_app(app_pid: int | None) -> None:
    if app_pid is not None:
        _OWNED_EXCEL_APPS.pop(int(app_pid), None)


def _bind_resolved_workbook(book) -> None:
    """Record the exact workbook process after a successful live lookup."""
    global _LAST_KNOWN_WORKBOOK_PATH, _LAST_KNOWN_APP_PID
    app_pid = _app_pid(book.app)
    _CURRENT_WORKBOOK_NAME.set(book.name)
    _CURRENT_EXCEL_PID.set(app_pid)
    _LAST_KNOWN_WORKBOOK_PATH = book.fullname
    _LAST_KNOWN_APP_PID = app_pid


def start_task_workbook():
    """Start exactly one dedicated, visible workbook for a new-workbook task.

    This intentionally does not use ``xw.apps.active``.  Attaching a new task
    to the user's active Excel process, then later creating a second workbook,
    was the source of the stray Book1/Book2 windows.  A task that requested a
    new workbook owns this one process and one startup workbook; existing
    user workbooks are left untouched.
    """
    app = xw.App(visible=True)
    retain_owned_excel_app(app)
    _harden_app(app)
    workbook = _active_or_new_workbook(app)
    _ensure_workbook_has_path(workbook)
    restore_screen_updating(app)
    _bind_resolved_workbook(workbook)
    _TASK_BOOTSTRAP_WORKBOOK.set(True)
    return workbook


def use_task_bootstrap_workbook() -> bool:
    """Whether this task has an untouched startup workbook to save as output."""
    return bool(_TASK_BOOTSTRAP_WORKBOOK.get())


def mark_task_bootstrap_workbook_used() -> None:
    _TASK_BOOTSTRAP_WORKBOOK.set(False)


def normalize_workbook_path(file_path: str) -> str:
    """Return a real absolute workbook path without creating directories.

    Agents often use the familiar ``~/Desktop/report.xlsx`` spelling.  On
    Windows that is especially error-prone because a redirected OneDrive
    Desktop is usually *not* ``C:\\Users\\<user>\\Desktop``.  Excel does not
    expand ``~`` itself, so passing it through makes Excel interpret it as a
    folder relative to the backend.  Resolve that shorthand here, before any
    COM call, and leave missing directories as an explicit, safe failure for
    the caller to report.
    """
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path must be a non-empty string")

    raw_path = file_path.strip().strip('"').strip("'")
    expanded = os.path.expandvars(raw_path)
    if expanded.startswith(("~/", "~\\")):
        relative_parts = [part for part in expanded[2:].replace("/", os.sep).split(os.sep) if part]
        home = os.path.expanduser("~")
        if relative_parts and relative_parts[0].lower() == "desktop":
            # OneDrive Desktop redirection is the default on many current
            # Windows setups. Prefer it only when it really exists.
            one_drive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
            redirected_desktop = os.path.join(one_drive, "Desktop") if one_drive else None
            standard_desktop = os.path.join(home, "Desktop")
            desktop = (
                redirected_desktop
                if redirected_desktop and os.path.isdir(redirected_desktop)
                else standard_desktop
            )
            expanded = os.path.join(desktop, *relative_parts[1:])
        else:
            expanded = os.path.join(home, *relative_parts)
    else:
        expanded = os.path.expanduser(expanded)

    return os.path.abspath(os.path.normpath(expanded))


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


def _active_or_new_workbook(app):
    """Use Excel's startup workbook when it already supplied one.

    On Windows, ``xw.App(visible=True)`` frequently opens Book1 by itself.
    Calling ``books.add()`` immediately afterward creates Book2 in a second
    Excel window. Reuse Book1 when it exists; only add a workbook when Excel
    is still on its start screen with no documents.
    """
    try:
        if len(app.books) > 0:
            return app.books.active
    except Exception:
        pass
    return app.books.add()


def _close_startup_books(app) -> None:
    """Close unsaved documents in a freshly-created, agent-owned app only."""
    try:
        books = list(app.books)
    except Exception:
        return
    for book in books:
        try:
            book.close(save=False)
        except Exception:
            pass


def restore_screen_updating(app):
    try:
        app.screen_updating = True
    except Exception:
        pass


def _maximize_excel_window(app) -> dict:
    """Maximize the live Excel application and read its state back.

    xlwings' ``visible`` flag only makes the window appear; it deliberately
    preserves whatever small/restored size Excel last used.  Excel's COM
    ``WindowState`` is the native, monitor-aware way to maximize it without
    sending a mouse click or stealing keyboard focus.
    """
    if not config.MAXIMIZE_EXCEL_WINDOW:
        return {"requested": False, "verified": False, "status": "disabled"}

    # Excel's documented XlWindowState value for xlMaximized.
    xl_maximized = -4137
    try:
        app.api.WindowState = xl_maximized
        current_state = int(app.api.WindowState)
        return {
            "requested": True,
            "verified": current_state == xl_maximized,
            "status": "maximized" if current_state == xl_maximized else "state_not_maximized",
            "window_state": current_state,
        }
    except Exception as exc:
        # Window size must not make a verified workbook edit fail.  The caller
        # logs this as an observable UX limitation while preserving Excel work.
        return {
            "requested": True,
            "verified": False,
            "status": "maximize_unavailable",
            "error": str(exc),
        }


def keep_workbook_visible(wb=None) -> dict:
    """Keep the workbook on the user's desktop while automation runs.

    Skills still use Excel's object model for reliable edits, but they should
    never make the work feel hidden.  This helper restores redraw, ensures the
    Excel instance is visible, and asks Excel to activate the target workbook.
    It maximizes Excel through its native COM window state but deliberately
    does not force-focus it, so it cannot steal a keystroke from the Xelora
    chat while a task is running.
    """
    wb = wb or get_active_workbook()
    app = wb.app
    try:
        app.visible = True
    except Exception:
        pass
    restore_screen_updating(app)
    window = _maximize_excel_window(app)
    try:
        wb.activate()
    except Exception:
        pass
    return {
        "workbook": wb.name,
        "visible": True,
        "screen_updating": True,
        "maximized": window["verified"],
        "maximize_status": window["status"],
    }


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

    original_value = None
    original_formula = None
    try:
        # Preserve the formula rather than only the calculated value.  The
        # previous probe could silently replace a rare existing formula in
        # this far-corner cell with its result.
        original_value = probe_cell.value
        original_formula = probe_cell.formula
        probe_cell.formula2 = "=SEQUENCE(1)"
        result = probe_cell.value
        supported = result is not None and str(result).strip().upper() != "#NAME?"
    except Exception:
        supported = False
    finally:
        try:
            if isinstance(original_formula, str) and original_formula.startswith("="):
                probe_cell.formula = original_formula
            else:
                probe_cell.value = original_value
        except Exception:
            pass

    _DYNAMIC_ARRAY_SUPPORT_CACHE[app.pid] = supported
    return supported


def get_excel_capabilities(wb=None, *, probe_dynamic_arrays: bool = True) -> dict:
    """Return a capability profile for the *running* Excel instance.

    ``Application.Version`` alone is deliberately not treated as an edition:
    Excel 2016, 2019, 2021 and Microsoft 365 can all report 16.0.  We retain
    that diagnostic value, but use a live formula probe for feature decisions.
    The profile is cached per process and can be passed to the planner.
    """
    wb = wb or get_active_workbook()
    app = wb.app
    if probe_dynamic_arrays and app.pid in _EXCEL_CAPABILITY_CACHE:
        return _EXCEL_CAPABILITY_CACHE[app.pid]

    def _read_api(name):
        try:
            return str(getattr(app.api, name))
        except Exception:
            return None

    # Writing a probe formula during task startup can block on a slow Excel
    # calculation/UI state. Start safely with legacy-compatible formulas;
    # deeper capability probing is only needed when a later feature requires
    # it. This also avoids touching the user's worksheet before the task has
    # made any requested change.
    dynamic_arrays = supports_dynamic_arrays(app) if probe_dynamic_arrays else False
    profile = {
        "application_version": _read_api("Version"),
        "application_build": _read_api("Build"),
        "dynamic_arrays": dynamic_arrays,
        "xlookup": dynamic_arrays,
        "let": dynamic_arrays,
        "modern_formula_support": dynamic_arrays,
        "formula_mode": "Formula2" if dynamic_arrays else "legacy Formula",
        "planning_rule": (
            "Modern dynamic-array functions are supported."
            if dynamic_arrays else
            "Use legacy-compatible formulas only: INDEX/MATCH, helper columns, "
            "SUMIFS/COUNTIFS, and ordinary ranges. Do not use XLOOKUP, LET, "
            "FILTER, UNIQUE, SORT, SEQUENCE, RANDARRAY, HSTACK, or VSTACK."
        ),
        "dynamic_array_probe": "completed" if probe_dynamic_arrays else "deferred",
    }
    if probe_dynamic_arrays:
        _EXCEL_CAPABILITY_CACHE[app.pid] = profile
    return profile


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
        _forget_owned_excel_app(_LAST_KNOWN_APP_PID)
        subprocess.run(["taskkill", "/F", "/PID", str(_LAST_KNOWN_APP_PID)], capture_output=True)
        killed_note = f"killed Excel process PID {_LAST_KNOWN_APP_PID} (only that one process)."
        time.sleep(1)

    app = xw.App(visible=True)
    retain_owned_excel_app(app)

    if not _wait_until_responsive(app):
        raise RuntimeError(
            f"Relaunched Excel (after {killed_note}) but it did not become responsive "
            f"within {RESPONSIVENESS_TIMEOUT_SECONDS}s. Please check Excel manually."
        )

    _harden_app(app)
    _LAST_KNOWN_APP_PID = app.pid
    _DYNAMIC_ARRAY_SUPPORT_CACHE.pop(app.pid, None)  # fresh process - re-probe if/when needed

    if _LAST_KNOWN_WORKBOOK_PATH and os.path.exists(_LAST_KNOWN_WORKBOOK_PATH):
        # This app was created above and contains no user work. Remove the
        # default Book1 before reopening the task workbook.
        _close_startup_books(app)
        wb = app.books.open(_LAST_KNOWN_WORKBOOK_PATH)
    else:
        wb = _active_or_new_workbook(app)
        _ensure_workbook_has_path(wb)
        _LAST_KNOWN_WORKBOOK_PATH = wb.fullname

    restore_screen_updating(app)
    _maximize_excel_window(app)
    # Preserve the per-task restart count; rebinding after recovery must not
    # make a repeatedly hung Excel instance eligible for unlimited restarts.
    _CURRENT_WORKBOOK_NAME.set(wb.name)
    _CURRENT_EXCEL_PID.set(_app_pid(app))
    return wb, killed_note


def get_active_workbook():
    global _LAST_KNOWN_WORKBOOK_PATH, _LAST_KNOWN_APP_PID
    pinned_name = _CURRENT_WORKBOOK_NAME.get()
    pinned_pid = _CURRENT_EXCEL_PID.get()

    if pinned_name:
        for app in xw.apps:
            app_pid = _app_pid(app)
            if pinned_pid is not None and app_pid != pinned_pid:
                continue
            for book in app.books:
                if book.name == pinned_name:
                    _harden_app(app)
                    _ensure_workbook_has_path(book)
                    restore_screen_updating(app)
                    _bind_resolved_workbook(book)
                    return book

        # A pinned task must never fall through to an unrelated active
        # workbook.  It is safer to stop and ask the user to reopen the named
        # file than to make a correct-looking change to the wrong workbook.
        identity = (
            f" in Excel process {pinned_pid}"
            if pinned_pid is not None else ""
        )
        raise RuntimeError(
            f"The task's target workbook '{pinned_name}'{identity} is not open in Excel. "
            "Reopen that workbook and retry the action."
        )

    if len(xw.apps) == 0:
        app = xw.App(visible=True)
        retain_owned_excel_app(app)
        _harden_app(app)
        wb = _active_or_new_workbook(app)
    else:
        app = xw.apps.active
        _harden_app(app)
        wb = app.books.active

    _ensure_workbook_has_path(wb)
    restore_screen_updating(app)
    _bind_resolved_workbook(wb)
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
