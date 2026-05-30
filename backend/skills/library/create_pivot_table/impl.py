"""
skills/library/create_pivot_table/impl.py
Auto-migrated from skills/excel_analysis.py.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def _resolve_source_range(wb, sheet, source_range: str):
    """The bug that broke the whole downstream Dashboard: passing an Excel
    Table's NAME (e.g. 'SalesTable') straight into sheet.range() is
    unreliable across xlwings versions - it can silently return only the
    table's DATA rows, excluding the header row. A PivotCache built from
    a headerless range has no real field names at all (Excel invents
    'Column1', 'Column2'...), so PivotFields('Country') then fails with
    exactly the vague COM error we saw. Fix: if source_range matches a
    real Table name, use that table's .Range directly (guaranteed to
    include headers) instead of guessing via sheet.range()."""
    for candidate_sheet in wb.sheets:
        try:
            for list_object in candidate_sheet.api.ListObjects:
                if list_object.Name == source_range:
                    return list_object.Range
        except Exception:
            continue
    return sheet.range(source_range).api


def run(sheet_name: str, source_range: str, row_field: str, value_field: str,
        agg_function: str = "sum", dest_sheet_name: str = None, dest_cell: str = "A1"):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]

    if not dest_sheet_name:
        dest_sheet_name = "PivotSheet"
        if dest_sheet_name not in [s.name for s in wb.sheets]:
            wb.sheets.add(dest_sheet_name, after=sheet)
    dest_sheet = wb.sheets[dest_sheet_name]

    source_api_range = _resolve_source_range(wb, sheet, source_range)

    # Confirm the fields the AI asked for actually exist in the source
    # BEFORE creating anything - avoids leaving a half-built pivot object
    # behind (which is what blocked write_cell/insert_formula on
    # unrelated cells afterward: "We can't change this part of the
    # PivotTable.").
    try:
        header_values = [cell.Value for cell in source_api_range.Rows(1).Columns]
    except Exception:
        header_values = None

    if header_values is not None:
        missing = [f for f in (row_field, value_field) if f not in header_values]
        if missing:
            return {
                "source_sheet": sheet_name, "source_range": source_range,
                "status": "field_not_found", "verified": False,
                "verification_note": (
                    f"{missing} not found in the source data's actual headers: "
                    f"{header_values}. Use one of those exact names for row_field/value_field."
                ),
            }

    pivot_cache = None
    pivot_table = None
    try:
        pivot_cache = wb.api.PivotCaches().Create(SourceType=1, SourceData=source_api_range)
        pivot_table = pivot_cache.CreatePivotTable(
            TableDestination=dest_sheet.range(dest_cell).api,
            TableName="Pivot_" + value_field.replace(" ", "_"),
        )

        agg_map = {"sum": -4157, "average": -4106, "count": -4112, "max": -4136, "min": -4139}
        xl_function = agg_map.get(agg_function, -4157)

        pivot_table.PivotFields(row_field).Orientation = 1
        data_field = pivot_table.PivotFields(value_field)
        pivot_table.AddDataField(data_field, f"{agg_function.title()} of {value_field}", xl_function)

    except Exception as e:
        # Clean up any partially-created pivot object instead of leaving
        # it sitting on the sheet blocking unrelated future actions -
        # this is the specific fix for the cascade failure seen before.
        try:
            if pivot_table is not None:
                pivot_table.TableRange2.Clear()
        except Exception:
            pass
        return {
            "source_sheet": sheet_name, "source_range": source_range,
            "status": "pivot_creation_failed", "verified": False,
            "error": str(e),
            "verification_note": (
                "PivotTable creation failed partway through and any partial object was "
                "cleaned up - the sheet should be clean, not blocked. Check that row_field "
                "and value_field exactly match the source data's column headers."
            ),
        }

    wb.save()

    verified = pivot_table.Name in [pt.Name for pt in dest_sheet.api.PivotTables()]
    return {"source_sheet": sheet_name, "source_range": source_range, "dest_sheet": dest_sheet_name,
            "row_field": row_field, "value_field": value_field, "agg_function": agg_function,
            "status": "pivot_table_created", "verified": verified}
