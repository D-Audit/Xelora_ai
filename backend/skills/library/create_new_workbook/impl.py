"""
skills/library/create_new_workbook/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


import os
import xlwings as xw
from skills.excel_shared import bind_workbook_context


def run(file_path: str):
    if not file_path.lower().endswith((".xlsx", ".xlsm")):
        file_path += ".xlsx"
    app = xw.apps.active if len(xw.apps) > 0 else xw.App(visible=True)
    app.display_alerts = False
    wb = app.books.add()
    wb.save(file_path)
    bind_workbook_context(wb.name)
    return {"file_path": file_path, "workbook_name": wb.name,
            "status": "workbook_created", "verified": os.path.exists(file_path)}
