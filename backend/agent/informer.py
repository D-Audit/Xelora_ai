"""Read-only workbook inspection used by planning and reporting."""

from __future__ import annotations

from typing import Any


def _as_rows(value: Any) -> list[list[Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        return [[value]]
    if value and not isinstance(value[0], list):
        return [value]
    return value


def analyze_workbook() -> dict[str, Any]:
    """Return a compact overview of every worksheet without changing Excel."""
    from skills.excel_shared import get_active_workbook

    workbook = get_active_workbook()
    active_sheet = str(workbook.api.ActiveSheet.Name)
    sheets = []
    chart_count = 0
    for sheet in workbook.sheets:
        values = _as_rows(sheet.used_range.value)
        rows = len(values)
        columns = max((len(row) for row in values), default=0)
        headers = values[0] if values else []
        try:
            chart_count += len(sheet.charts)
        except Exception:
            pass
        sheets.append({
            "name": str(sheet.name), "rows": rows, "cols": columns,
            "headers": headers, "sample_data": values[1:4],
            "has_data": bool(values), "has_headers": bool(headers),
        })
    return {
        "active_sheet": active_sheet,
        "sheets": sheets,
        "total_sheets": len(sheets),
        "workbook_has_data": any(sheet["has_data"] for sheet in sheets),
        "workbook_has_charts": chart_count > 0,
        "chart_count": chart_count,
    }


def get_sheet_names_from_excel() -> list[str]:
    from skills.excel_shared import get_active_workbook

    return [str(sheet.name) for sheet in get_active_workbook().sheets]


def get_cell_data_range(range_ref: str | None = None) -> dict[str, Any]:
    """Return shape and a sample for a requested range or the active used range."""
    from skills.excel_shared import get_active_workbook

    workbook = get_active_workbook()
    sheet = workbook.sheets.active
    values = _as_rows(sheet.range(range_ref).value if range_ref else sheet.used_range.value)
    headers = values[0] if values else []
    return {
        "sheet": str(sheet.name), "range": range_ref or str(sheet.used_range.address),
        "headers": headers, "data_rows": max(len(values) - 1, 0),
        "total_cells": sum(len(row) for row in values), "col_count": max((len(row) for row in values), default=0),
        "sample_data": values[1:4],
    }
