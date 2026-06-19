"""
skills/library/open_workbook/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


import os
import xlwings as xw
from skills.excel_shared import bind_workbook_context


def run(file_path: str):
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}", "verified": False}
    app = xw.apps.active if len(xw.apps) > 0 else xw.App(visible=True)
    app.display_alerts = False
    wb = app.books.open(file_path)
    bind_workbook_context(wb.name)
    return {"file_path": file_path, "workbook_name": wb.name,
            "status": "workbook_opened", "verified": True}
