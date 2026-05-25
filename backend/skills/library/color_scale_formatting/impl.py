"""
skills/library/color_scale_formatting/impl.py
Auto-migrated from skills/excel_extended.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str, min_color: str, max_color: str, mid_color: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    rng.api.FormatConditions.Delete()
    color_scale_type = 3 if mid_color else 2   # xlColorScale gradient type (2 or 3 stop)
    cs = rng.api.FormatConditions.AddColorScale(ColorScaleType=color_scale_type)

    def _to_bgr(hex_color):
        r, g, b = hex_to_rgb(hex_color)
        return r + g * 256 + b * 65536

    cs.ColorScaleCriteria(1).FormatColor.Color = _to_bgr(min_color)
    if mid_color:
        cs.ColorScaleCriteria(2).FormatColor.Color = _to_bgr(mid_color)
    cs.ColorScaleCriteria(color_scale_type).FormatColor.Color = _to_bgr(max_color)
    wb.save()

    return {"sheet": sheet_name, "range": cell_range, "min_color": min_color, "mid_color": mid_color,
            "max_color": max_color, "status": "color_scale_applied", "verified": True,
            "verification_note": "Rule added. Visual gradient requires manual/visual check."}
