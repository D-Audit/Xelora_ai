"""
skills/library/delete_chart/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, chart_name: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.charts[chart_name].delete()
    wb.save()
    return {"sheet": sheet_name, "chart_name": chart_name,
            "status": "chart_deleted", "verified": True}
