"""
skills/library/insert_row/impl.py
Auto-migrated from skills/excel_structure.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, row_number: int, count: int = 1):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    for _ in range(count):
        sheet.range(f"{row_number}:{row_number}").api.Insert()
    wb.save()
    return {"sheet": sheet_name, "row_number": row_number, "count": count, "status": "rows_inserted", "verified": True}
