"""
skills/library/format_range/impl.py
Formats a cell range with styling.
"""
from skills.excel_shared import get_active_workbook


def run(
    range: str,
    sheet_name: str = None,
    bold: bool = None,
    font_size: int = None,
    font_color: str = None,
    bg_color: str = None,
    number_format: str = None,
    align_horizontal: str = None,
    align_vertical: str = None,
    borders: bool = None,
) -> dict:
    """
    Formats a cell range with font styling, colors, borders, number format, and alignment.
    """
    wb = get_active_workbook()
    
    if sheet_name:
        sheet = wb.sheets[sheet_name]
    else:
        sheet = wb.sheets.active
    
    cell_range = sheet.range(range)
    
    if bold is not None:
        cell_range.font.bold = bold
    
    if font_size is not None:
        cell_range.font.size = font_size
    
    if font_color:
        cell_range.font.color = _parse_color(font_color)
    
    if bg_color:
        cell_range.color = _parse_color(bg_color)
    
    if number_format:
        cell_range.number_format = number_format
    
    alignment_map_h = {
        'left': -4131,
        'center': -4108,
        'right': -4152
    }
    alignment_map_v = {
        'top': -4160,
        'center': -4108,
        'bottom': -4107
    }
    
    if align_horizontal and align_horizontal.lower() in alignment_map_h:
        cell_range.api.HorizontalAlignment = alignment_map_h[align_horizontal.lower()]
    
    if align_vertical and align_vertical.lower() in alignment_map_v:
        cell_range.api.VerticalAlignment = alignment_map_v[align_vertical.lower()]
    
    if borders:
        for edge in [7, 8, 9, 10]:  # xlEdgeLeft, xlEdgeTop, xlEdgeBottom, xlEdgeRight
            cell_range.api.Borders(edge).LineStyle = 1
            cell_range.api.Borders(edge).Weight = 2
    
    wb.save()
    
    return {
        "range": range,
        "sheet": sheet_name or sheet.name,
        "status": "formatted",
        "verified": True
    }


def _parse_color(color: str):
    """Parse color string to RGB tuple or hex value."""
    color_map = {
        'red': (255, 0, 0),
        'blue': (0, 0, 255),
        'green': (0, 255, 0),
        'yellow': (255, 255, 0),
        'orange': (255, 165, 0),
        'purple': (128, 0, 128),
        'lightblue': (173, 216, 230),
        'lightgray': (211, 211, 211),
        'lightgrey': (211, 211, 211),
        'white': (255, 255, 255),
        'black': (0, 0, 0),
    }
    
    color_lower = color.lower()
    if color_lower in color_map:
        return color_map[color_lower]
    
    if color.startswith('#'):
        hex_color = color[1:]
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
    
    return (0, 0, 0)
