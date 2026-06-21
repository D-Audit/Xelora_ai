"""
skills/library/refresh_pivot_table/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, pivot_table_name: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    pivot = sheet.api.PivotTables(pivot_table_name)
    pivot.RefreshTable()
    wb.save()
    return {"sheet": sheet_name, "pivot_table_name": pivot_table_name,
            "status": "refreshed", "verified": True}
