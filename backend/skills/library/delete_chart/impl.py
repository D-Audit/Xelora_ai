"""
skills/library/delete_chart/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, chart_name: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    existing = [chart.name for chart in sheet.charts]
    if chart_name not in existing:
        return {"sheet": sheet_name, "chart_name": chart_name, "status": "chart_not_found",
                "verified": False, "available_charts": existing,
                "error": f"No chart named '{chart_name}' on '{sheet_name}'. Available: {existing}."}
    sheet.charts[chart_name].delete()
    wb.save()
    remaining = [chart.name for chart in sheet.charts]
    verified = chart_name not in remaining
    return {"sheet": sheet_name, "chart_name": chart_name,
            "status": "chart_deleted" if verified else "chart_still_present", "verified": verified,
            "remaining_charts": remaining,
            "verification_note": "Re-listed the sheet's charts; the chart is gone." if verified
            else "The chart is still listed after delete."}
