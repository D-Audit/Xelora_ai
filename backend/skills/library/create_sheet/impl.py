"""
skills/library/create_sheet/impl.py
Auto-migrated from skills/excel_structure.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str):
    wb = get_active_workbook()
    if sheet_name in [s.name for s in wb.sheets]:
        # Creating a named sheet is idempotent. A retry or a previous action
        # may already have made it, and that live sheet satisfies this
        # deliverable just as well as a newly-created one.
        return {"sheet_name": sheet_name, "status": "already_exists", "verified": True,
                "verification_note": f"Confirmed that the required sheet '{sheet_name}' already exists."}
    wb.sheets.add(sheet_name)
    wb.save()
    verified = sheet_name in [s.name for s in wb.sheets]
    return {"sheet_name": sheet_name, "status": "sheet_created", "verified": verified}
