"""
skills/library/freeze_panes/impl.py
Auto-migrated from skills/excel_format.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.activate()
    sheet.range(cell).select()
    wb.app.api.ActiveWindow.FreezePanes = True
    wb.save()
    return {"sheet": sheet_name, "cell": cell, "status": "panes_frozen", "verified": True}
