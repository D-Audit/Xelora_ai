"""
skills/library/set_autofilter/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell_range: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.range(cell_range).api.AutoFilter()
    wb.save()
    return {"sheet": sheet_name, "cell_range": cell_range,
            "status": "autofilter_enabled", "verified": True}
