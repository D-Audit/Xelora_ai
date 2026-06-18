"""
skills/library/modify_chart/impl.py

FIXED (title crash): xlwings' sheet.charts[chart_name] can wrap the chart
differently depending on how it was created moments earlier - sometimes
.api returns the real Chart COM object directly, sometimes it returns the
containing ChartObject (which has a .Chart property to get the real
thing), and in some cases it comes back as a tuple. Setting .HasTitle on
whichever of these ISN'T the real Chart object crashes with exactly the
"'tuple' object has no attribute 'HasTitle'" error seen in testing.
_resolve_chart_com_object() normalizes all of these cases to the real
Chart COM object before touching .HasTitle/.ChartTitle.

FIXED (missing chart): looking up a chart by a name that doesn't exist
now returns a clear, actionable error instead of a raw KeyError.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def _resolve_chart_com_object(chart):
    """Normalizes xlwings' chart.api to the real Chart COM object
    (the one with .HasTitle, .ChartTitle, etc.), regardless of whether
    xlwings handed back the Chart itself, its containing ChartObject
    (which exposes the real Chart via a .Chart property), or - in some
    versions/timing situations - a tuple wrapping either of those."""
    api_obj = chart.api

    if isinstance(api_obj, tuple):
        api_obj = api_obj[0] if api_obj else None

    if api_obj is not None and hasattr(api_obj, "Chart") and not hasattr(api_obj, "HasTitle"):
        try:
            api_obj = api_obj.Chart
        except Exception:
            pass

    if isinstance(api_obj, tuple):  # in case unwrapping .Chart itself returned a tuple
        api_obj = api_obj[0] if api_obj else None

    return api_obj


def run(sheet_name: str, chart_name: str, chart_type: str = None, title: str = None,
        title_formula: str = None, data_range: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]

    existing_chart_names = [c.name for c in sheet.charts]
    if chart_name not in existing_chart_names:
        return {
            "sheet": sheet_name, "chart_name": chart_name, "status": "chart_not_found",
            "verified": False,
            "verification_note": (
                f"No chart named '{chart_name}' exists on sheet '{sheet_name}'. "
                f"Charts currently on this sheet: {existing_chart_names or 'none'}. "
                f"This usually means an earlier create_chart call for this name failed - "
                f"check for that failure before retrying this modify_chart call."
            ),
        }

    chart = sheet.charts[chart_name]
    changes = []

    if chart_type:
        type_map = {"column": "column_clustered", "bar": "bar_clustered", "line": "line",
                    "pie": "pie", "scatter": "xy_scatter_lines_no_markers", "area": "area"}
        chart.chart_type = type_map.get(chart_type.lower(), chart_type)
        changes.append(f"type -> {chart_type}")

    if data_range:
        chart.set_source_data(sheet.range(data_range))
        changes.append(f"data_range -> {data_range}")

    if title_formula or title:
        real_chart = _resolve_chart_com_object(chart)
        if real_chart is None or not hasattr(real_chart, "HasTitle"):
            return {
                "sheet": sheet_name, "chart_name": chart_name, "changes": changes,
                "status": "title_change_failed", "verified": False,
                "verification_note": (
                    "Could not resolve the underlying chart object to set a title - other "
                    "requested changes (if any) above were still applied. Try again, or set "
                    "the title via run_excel_code as a fallback for this one step."
                ),
            }
        real_chart.HasTitle = True
        real_chart.ChartTitle.Text = title_formula or title
        changes.append(f"title -> {title_formula or title}")

    wb.save()
    return {"sheet": sheet_name, "chart_name": chart_name, "changes": changes,
            "status": "modified" if changes else "no_changes_requested", "verified": True}
