"""
skills/library/rename_sheet/impl.py
Auto-migrated from skills/excel_structure.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(old_name: str, new_name: str):
    wb = get_active_workbook()
    sheet = wb.sheets[old_name]
    sheet.name = new_name
    wb.save()
    names = [s.name for s in wb.sheets]
    verified = new_name in names and old_name not in names
    return {"old_name": old_name, "new_name": new_name, "status": "sheet_renamed", "verified": verified}
