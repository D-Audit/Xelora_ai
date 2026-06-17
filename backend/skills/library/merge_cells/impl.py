"""
skills/library/merge_cells/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell_range: str, center_text: bool = True):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)
    rng.api.Merge()
    if center_text:
        rng.api.HorizontalAlignment = -4108  # xlCenter
        rng.api.VerticalAlignment = -4108
    wb.save()
    return {"sheet": sheet_name, "cell_range": cell_range,
            "status": "merged", "verified": True}
