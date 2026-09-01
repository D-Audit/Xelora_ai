"""
skills/library/create_new_workbook/impl.py
"""

import os
import xlwings as xw
from skills.excel_shared import (
    bind_workbook_context,
    get_active_workbook,
    mark_task_bootstrap_workbook_used,
    normalize_workbook_path,
    retain_owned_excel_app,
    _active_or_new_workbook,
    use_task_bootstrap_workbook,
)


def run(file_path: str):
    try:
        file_path = normalize_workbook_path(file_path)
    except ValueError as exc:
        return {"error": str(exc), "verified": False, "status": "invalid_path"}
    if not file_path.lower().endswith((".xlsx", ".xlsm")):
        file_path += ".xlsx"
    parent_directory = os.path.dirname(file_path)
    if not os.path.isdir(parent_directory):
        return {
            "error": f"The destination folder does not exist: {parent_directory}",
            "file_path": file_path,
            "verified": False,
            "status": "destination_folder_not_found",
        }

    # New-workbook tasks already receive one dedicated startup workbook before
    # planning.  Save that workbook under the requested name instead of adding
    # Book2 beside it.  This is the normal path for a natural-language request
    # such as "create a workbook named Report.xlsx".
    reuse_startup_workbook = use_task_bootstrap_workbook()
    try:
        if reuse_startup_workbook:
            wb = get_active_workbook()
            app = wb.app
        else:
            created_app = len(xw.apps) == 0
            app = xw.apps.active if not created_app else xw.App(visible=True)
            if created_app:
                retain_owned_excel_app(app)
            # A new Excel instance commonly already contains Book1. Reusing
            # it prevents Xelora from showing a second blank Excel window.
            wb = _active_or_new_workbook(app) if created_app else app.books.add()
        app.display_alerts = False
        app.visible = True
        wb.save(file_path)
    except Exception as exc:
        return {
            "error": str(exc), "file_path": file_path,
            "verified": False, "status": "workbook_create_failed",
        }

    verified = os.path.isfile(file_path)
    bind_workbook_context(wb.name, wb.app.pid)
    if reuse_startup_workbook:
        mark_task_bootstrap_workbook_used()
    return {"file_path": file_path, "workbook_name": wb.name,
            "excel_app_pid": wb.app.pid,
            "status": "workbook_created", "verified": verified,
            "verification_note": (
                "Confirmed the workbook was saved at the requested absolute path."
                if verified else "Excel created the workbook but the requested file was not found on disk."
            )}
