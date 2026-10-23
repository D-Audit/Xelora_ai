"""
skills/library/create_chart/impl.py
Auto-migrated from skills/excel_analysis.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.

FIXED: multi-area Table structured references (e.g. two non-adjacent
columns for a chart) require a comma between each TableName[[Col]] piece.
Rather than relying on the AI to always remember the comma, this now
detects the pattern and inserts it automatically if missing.
"""

import re
from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def _fix_multi_area_table_reference(data_range: str) -> str:
    """
    Detects two or more 'TableName[[Column]]' pieces glued together with
    no separator (a common, easy mistake) and inserts commas between them.
    Leaves anything that isn't this exact pattern completely untouched.
    """
    pattern = r"([A-Za-z_][A-Za-z0-9_]*\[\[[^\]]+\]\])"
    pieces = re.findall(pattern, data_range)

    if len(pieces) < 2:
        return data_range  # not this pattern - leave it alone

    rejoined = ",".join(pieces)
    if data_range.replace(",", "") == "".join(pieces):
        return rejoined
    return data_range


def run(sheet_name: str, data_range: str, chart_type: str = "column", chart_name: str = "Chart1"):
    chart_type_map = {
        "column": "column_clustered", "bar": "bar_clustered", "line": "line",
        "pie": "pie", "doughnut": "doughnut", "area": "area",
        "scatter": "xy_scatter", "radar": "radar",
    }
    chart_type = str(chart_type).strip().lower()
    if chart_type not in chart_type_map:
        return {"status": "unsupported_chart_type", "verified": False,
                "error": f"Unsupported chart type: {chart_type}",
                "supported_types": list(chart_type_map)}
    xl_type = chart_type_map[chart_type]
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    if chart_name in [c.name for c in sheet.charts]:
        return {"status": "chart_already_exists", "verified": False,
                "error": f"Chart '{chart_name}' already exists. Use modify_chart or choose a new name."}
    data_range = _fix_multi_area_table_reference(data_range)

    chart = None
    try:
        source = sheet.range(data_range)
        chart = sheet.charts.add()
        chart.set_source_data(source)
        chart.chart_type = xl_type
        chart.name = chart_name
        wb.save()
    except Exception as e:
        cleanup_error = None
        if chart is not None:
            try:
                chart.delete()
            except Exception as cleanup_exc:
                cleanup_error = str(cleanup_exc)
        return {
            "sheet": sheet_name, "data_range": data_range, "chart_type": chart_type,
            "chart_name": chart_name, "status": "chart_creation_failed", "verified": False,
            "error": str(e),
            "cleanup_error": cleanup_error,
            "verification_note": (
                f"Could not create chart from data_range '{data_range}'. If this range "
                f"references two or more non-adjacent Table columns, each piece must be "
                f"joined with a comma, e.g. TableName[[ColA]],TableName[[ColB]] - and if "
                f"they're adjacent columns, a single combined range like TableName[[ColA]:[ColB]] "
                f"is usually more reliable than separate structured references."
            ),
        }

    verified = chart_name in [c.name for c in sheet.charts] and chart.chart_type == xl_type
    return {"sheet": sheet_name, "data_range": data_range, "chart_type": chart_type,
            "chart_name": chart_name, "status": "chart_created" if verified else "chart_verification_failed", "verified": verified}
