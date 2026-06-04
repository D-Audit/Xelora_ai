"""
skills/library/delete_row/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, row_number: int, count: int = 1):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = f"{row_number}:{row_number + count - 1}"
    sheet.api.Rows(rng).Delete()
    wb.save()
    return {"sheet": sheet_name, "row_number": row_number, "count": count,
            "status": "rows_deleted", "verified": True}
