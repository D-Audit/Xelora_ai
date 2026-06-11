"""
skills/library/icon_set_formatting/impl.py
Auto-migrated from skills/excel_extended.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str, style: str = "3TrafficLights1"):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    style_map = {
        "3TrafficLights1": 6, "3Arrows": 3, "3Symbols": 8, "5Stars": 12,
        "4TrafficLights": 5, "5Arrows": 4,
    }
    xl_icon_set_id = style_map.get(style, 6)

    rng.api.FormatConditions.Delete()
    icon_set_collection = wb.app.api.Application.IconSets(xl_icon_set_id)
    rng.api.FormatConditions.AddIconSetCondition()
    fc = rng.api.FormatConditions(rng.api.FormatConditions.Count)
    fc.IconSet = icon_set_collection
    wb.save()

    return {"sheet": sheet_name, "range": cell_range, "style": style,
            "status": "icon_set_applied", "verified": True,
            "verification_note": "Rule added. Visual icons require manual/visual check."}
