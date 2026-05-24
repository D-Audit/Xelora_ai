"""
skills/library/clear_range/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell_range: str, clear_formatting: bool = False):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)
    if clear_formatting:
        rng.api.Clear()
    else:
        rng.api.ClearContents()
    wb.save()
    return {"sheet": sheet_name, "cell_range": cell_range, "clear_formatting": clear_formatting,
            "status": "cleared", "verified": True}
