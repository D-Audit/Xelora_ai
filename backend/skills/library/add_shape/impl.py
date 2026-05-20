"""
skills/library/add_shape/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, shape_type: str, cell: str, width: float = 100, height: float = 60,
        fill_color: str = None, text: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    anchor = sheet.range(cell)
    type_map = {"rectangle": 1, "rounded_rectangle": 5, "oval": 9, "right_arrow": 33}
    shape_code = type_map.get(shape_type.lower(), 1)
    shape = sheet.api.Shapes.AddShape(shape_code, anchor.left, anchor.top, width, height)
    if fill_color:
        r, g, b = hex_to_rgb(fill_color)
        shape.Fill.ForeColor.RGB = r + (g * 256) + (b * 65536)
    if text:
        shape.TextFrame.Characters().Text = text
    wb.save()
    return {"sheet": sheet_name, "shape_type": shape_type, "cell": cell,
            "status": "shape_added", "verified": True}
