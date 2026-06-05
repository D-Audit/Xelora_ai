"""
skills/library/delete_sheet/impl.py
Auto-migrated from skills/excel_structure.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str):
    wb = get_active_workbook()
    if len(wb.sheets) <= 1:
        return {"sheet_name": sheet_name, "status": "refused", "verified": False,
                "verification_note": "Cannot delete the only remaining sheet in the workbook."}
    wb.sheets[sheet_name].delete()
    wb.save()
    verified = sheet_name not in [s.name for s in wb.sheets]
    return {"sheet_name": sheet_name, "status": "sheet_deleted", "verified": verified}
