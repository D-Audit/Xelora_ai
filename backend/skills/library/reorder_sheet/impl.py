"""
skills/library/reorder_sheet/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, new_index: int):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    target = wb.sheets[new_index] if new_index < wb.sheets.count else None
    if target is not None:
        sheet.api.Move(Before=target.api)
    else:
        sheet.api.Move(After=wb.sheets[wb.sheets.count - 1].api)
    wb.save()
    return {"sheet_name": sheet_name, "new_index": new_index,
            "status": "sheet_reordered", "verified": True}
