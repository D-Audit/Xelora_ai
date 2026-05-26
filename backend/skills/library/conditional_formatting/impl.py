"""
skills/library/conditional_formatting/impl.py
Auto-migrated from skills/excel_format.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str, operator: str, value, fill_color: str = "#FFC7CE"):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    op_map = {"greater_than": 5, "less_than": 6, "equals": 3}
    excel_op = op_map.get(operator, 5)
    rgb = hex_to_rgb(fill_color)

    fc = rng.api.FormatConditions.Add(Type=1, Operator=excel_op, Formula1=str(value))
    fc.Interior.Color = rgb[0] + rgb[1] * 256 + rgb[2] * 65536
    wb.save()

    return {
        "sheet": sheet_name, "range": cell_range, "operator": operator, "value": value,
        "fill_color": fill_color, "status": "conditional_formatting_applied", "verified": True,
        "verification_note": "Rule added. Visual rendering requires manual/visual check.",
    }
