"""
skills/library/open_workbook/impl.py
"""

import os
import xlwings as xw
from skills.excel_shared import bind_workbook_context, normalize_workbook_path, _close_startup_books


def run(file_path: str):
    try:
        file_path = normalize_workbook_path(file_path)
    except ValueError as exc:
        return {"error": str(exc), "verified": False, "status": "invalid_path"}
    if not os.path.isfile(file_path):
        return {"error": f"File not found: {file_path}", "verified": False, "status": "file_not_found"}

    normalized_target = os.path.normcase(os.path.abspath(file_path))
    for existing_app in xw.apps:
        for existing_book in existing_app.books:
            try:
                if os.path.normcase(os.path.abspath(existing_book.fullname)) == normalized_target:
                    existing_app.visible = True
                    existing_book.activate()
                    bind_workbook_context(existing_book.name)
                    return {
                        "file_path": file_path, "workbook_name": existing_book.name,
                        "status": "workbook_already_open", "verified": True,
                        "verification_note": "Confirmed the requested workbook was already open and activated.",
                    }
            except Exception:
                continue

    created_app = len(xw.apps) == 0
    app = xw.apps.active if not created_app else xw.App(visible=True)
    app.display_alerts = False
    app.visible = True
    try:
        if created_app:
            # The app was launched solely to open this file, so Book1 cannot
            # contain user work and must not remain as a duplicate window.
            _close_startup_books(app)
        wb = app.books.open(file_path)
    except Exception as exc:
        return {
            "error": str(exc), "file_path": file_path,
            "verified": False, "status": "workbook_open_failed",
        }
    bind_workbook_context(wb.name)
    return {"file_path": file_path, "workbook_name": wb.name,
            "status": "workbook_opened", "verified": True,
            "verification_note": "Confirmed Excel opened and activated the requested workbook."}
