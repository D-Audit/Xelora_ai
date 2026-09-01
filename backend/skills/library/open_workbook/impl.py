"""
skills/library/open_workbook/impl.py
"""

import os
import xlwings as xw
from skills.excel_shared import (
    bind_workbook_context,
    get_active_workbook,
    mark_task_bootstrap_workbook_used,
    normalize_workbook_path,
    retain_owned_excel_app,
    _close_startup_books,
    use_task_bootstrap_workbook,
)


def run(file_path: str):
    try:
        file_path = normalize_workbook_path(file_path)
    except ValueError as exc:
        return {"error": str(exc), "verified": False, "status": "invalid_path"}
    if not os.path.isfile(file_path):
        return {"error": f"File not found: {file_path}", "verified": False, "status": "file_not_found"}

    normalized_target = os.path.normcase(os.path.abspath(file_path))
    bootstrap_book = None
    if use_task_bootstrap_workbook():
        try:
            bootstrap_book = get_active_workbook()
        except Exception:
            # The normal open path below returns a clear error if Excel itself
            # is unavailable. Do not hide it behind bootstrap cleanup.
            bootstrap_book = None

    for existing_app in xw.apps:
        for existing_book in existing_app.books:
            try:
                if os.path.normcase(os.path.abspath(existing_book.fullname)) == normalized_target:
                    bootstrap_is_target = False
                    if bootstrap_book is not None:
                        try:
                            bootstrap_is_target = (
                                os.path.normcase(os.path.abspath(bootstrap_book.fullname))
                                == normalized_target
                            )
                        except Exception:
                            pass
                    if bootstrap_book is not None and not bootstrap_is_target:
                        # This temporary blank workbook belongs solely to this
                        # task. Closing it avoids a stray Book1 window; it
                        # never closes an existing user workbook.
                        bootstrap_book.close(save=False)
                    existing_app.visible = True
                    existing_book.activate()
                    bind_workbook_context(existing_book.name, existing_app.pid)
                    mark_task_bootstrap_workbook_used()
                    return {
                        "file_path": file_path, "workbook_name": existing_book.name,
                        "excel_app_pid": existing_app.pid,
                        "status": "workbook_already_open", "verified": True,
                        "verification_note": "Confirmed the requested workbook was already open and activated.",
                    }
            except Exception:
                continue

    created_app = len(xw.apps) == 0
    # Replace the task's disposable startup Book1 in its own process. This
    # avoids opening a requested workbook beside a blank Book1 window.
    if bootstrap_book is not None:
        app = bootstrap_book.app
    else:
        app = xw.apps.active if not created_app else xw.App(visible=True)
        if created_app:
            retain_owned_excel_app(app)
    app.display_alerts = False
    app.visible = True
    try:
        if bootstrap_book is not None:
            bootstrap_book.close(save=False)
        elif created_app:
            # The app was launched solely to open this file, so Book1 cannot
            # contain user work and must not remain as a duplicate window.
            _close_startup_books(app)
        wb = app.books.open(file_path)
    except Exception as exc:
        return {
            "error": str(exc), "file_path": file_path,
            "verified": False, "status": "workbook_open_failed",
        }
    bind_workbook_context(wb.name, wb.app.pid)
    mark_task_bootstrap_workbook_used()
    return {"file_path": file_path, "workbook_name": wb.name,
            "excel_app_pid": wb.app.pid,
            "status": "workbook_opened", "verified": True,
            "verification_note": "Confirmed Excel opened and activated the requested workbook."}
