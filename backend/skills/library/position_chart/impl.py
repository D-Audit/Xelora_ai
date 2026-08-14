"""
skills/library/position_chart/impl.py
Positions and sizes a chart at a specific location.
"""
from skills.excel_shared import get_active_workbook


def run(
    chart_index: int,
    sheet_name: str,
    top_left_cell: str,
    width: int = 400,
    height: int = 250,
    title: str = None,
) -> dict:
    """
    Positions and sizes an existing chart.
    """
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    
    try:
        chart = sheet.charts[chart_index - 1]
    except IndexError:
        return {
            "status": "error",
            "error": f"Chart {chart_index} not found on sheet '{sheet_name}'",
            "verified": False
        }
    
    cell = sheet.range(top_left_cell)
    
    chart.left = cell.left
    chart.top = cell.top
    chart.width = width
    chart.height = height
    
    if title:
        try:
            chart.api.SetElement(2)  # msoElementChartTitleAboveChart
            chart.api.ChartTitle.Text = title
        except Exception as e:
            pass
    
    wb.save()
    
    return {
        "chart_index": chart_index,
        "sheet": sheet_name,
        "position": top_left_cell,
        "width": width,
        "height": height,
        "title": title if title else "not_set",
        "status": "positioned",
        "verified": True
    }
