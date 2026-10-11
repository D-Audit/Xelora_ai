"""Live, disposable repro for Excel sheet-tab UI Automation overflow.

Run from ``backend`` on the Windows desktop where Excel is installed:

    .\\venv\\Scripts\\python.exe repro_sheet_tab_overflow.py

The script launches its own unsaved Excel instance, adds 24 worksheets with
the same Shift+F11 primitive used by ``create_sheet``, then records every UIA
``TabItem`` visible in the Excel window. It never saves or closes a workbook.
The Excel window deliberately stays open afterward so the tab strip can be
compared with the printed raw UIA evidence.
"""

import json
import subprocess
import sys
import time
import traceback

from vision import ui_control


SHEET_INSERTIONS = 24
UIA_READ_TIMEOUT_SECONDS = 6


def _read_tabitems_in_disposable_child(window_handle: int) -> dict:
    """Bound a potentially hung UIA descendants() call without touching Excel."""
    child_code = """
import json
import sys
from pywinauto import Desktop

window = Desktop(backend='uia').window(handle=int(sys.argv[1]))
tab_items = []
for control in window.descendants():
    if str(control.element_info.control_type or '') == 'TabItem':
        tab_items.append(control.window_text() or '')
print(json.dumps({'tab_items': tab_items}))
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", child_code, str(window_handle)],
            capture_output=True,
            text=True,
            timeout=UIA_READ_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "timeout_seconds": UIA_READ_TIMEOUT_SECONDS,
            "error": "UIA window.descendants() did not return before the hard timeout.",
        }
    if completed.returncode != 0:
        return {
            "status": "child_error",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    try:
        return {"status": "ok", **json.loads(completed.stdout)}
    except json.JSONDecodeError:
        return {"status": "invalid_child_output", "stdout": completed.stdout, "stderr": completed.stderr}


def main() -> None:
    if not ui_control._HAS_PYAUTOGUI or not ui_control._HAS_PYWINAUTO:
        raise RuntimeError("This repro requires a local Windows desktop with pyautogui and pywinauto.")

    # A new interpreter has no bound window. This opens a separate /x Excel
    # process, never adopts a user's open workbook, and leaves the generated
    # workbook unsaved for visual inspection.
    ui_control.set_workbook_mode(False)
    ui_control.prepare_agent_workbook()
    window = ui_control._get_agent_excel_window()
    before = ui_control._sheet_tab_uia_snapshot(window, "overflow_repro_before")
    print(json.dumps({"stage": "before_insertions", "snapshot": before}, default=str), flush=True)

    ui_control._focus_excel_for_keyboard(expected_window_handle=window.handle)
    insertion_events = []
    for insertion in range(1, SHEET_INSERTIONS + 1):
        if not ui_control._activate_excel_window(window):
            raise RuntimeError("The dedicated Excel repro window could not be activated.")
        print(json.dumps({"stage": "before_insert", "insertion": insertion}), flush=True)
        ui_control.pyautogui.hotkey("shift", "f11")
        print(json.dumps({"stage": "after_insert_sent", "insertion": insertion}), flush=True)
        time.sleep(0.12)
        is_visible = bool(ui_control.win32gui.IsWindowVisible(window.handle)) if ui_control._HAS_WIN32GUI else None
        insertion_events.append({"insertion": insertion, "window_visible": is_visible})
        print(json.dumps({"stage": "after_insert", "insertion": insertion, "window_visible": is_visible}), flush=True)
        if is_visible is False:
            break

    # Give Excel time to publish its overflow controls and UIA descendants.
    time.sleep(1.5)
    after = _read_tabitems_in_disposable_child(window.handle)

    print(json.dumps({
        "insertions_sent": SHEET_INSERTIONS,
        "before": before,
        "insertion_events": insertion_events,
        "after": after,
        "notes": (
            "The unsaved Excel repro workbook remains open. Compare its visible tab strip with "
            "after.tab_items; do not save it."
        ),
    }, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        print(json.dumps({
            "stage": "repro_exception",
            "type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }), flush=True)
        raise
