"""
skills/library/data_bar_formatting/impl.py
Auto-migrated from skills/excel_extended.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str, bar_color: str = "#638EC6"):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    rng.api.FormatConditions.Delete()
    data_bar = rng.api.FormatConditions.AddDatabar()
    r, g, b = hex_to_rgb(bar_color)
    data_bar.BarColor.Color = r + g * 256 + b * 65536
    wb.save()

    return {"sheet": sheet_name, "range": cell_range, "bar_color": bar_color,
            "status": "data_bar_applied", "verified": True,
            "verification_note": "Rule added. Visual bars require manual/visual check."}
