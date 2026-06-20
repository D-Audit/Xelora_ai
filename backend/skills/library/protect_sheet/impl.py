"""
skills/library/protect_sheet/impl.py
Auto-migrated from skills/excel_advanced.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

import requests


def run(sheet_name: str, password: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    if password:
        sheet.api.Protect(Password=password)
    else:
        sheet.api.Protect()
    wb.save()
    return {"sheet": sheet_name, "status": "sheet_protected", "verified": True}
