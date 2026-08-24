"""
skills/library/write_table/impl.py
Auto-migrated from skills/excel_write.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

EXCEL_ERROR_VALUES = {"#NAME?", "#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NULL!", "#NUM!", "#SPILL!", "#CALC!"}
def _is_excel_error(value) -> bool:
    return isinstance(value, str) and value.strip() in EXCEL_ERROR_VALUES


def _values_equivalent(expected_value, actual_value) -> bool:
    """Compare a value with Excel's normal type coercions accounted for.

    A tool payload is JSON, so a model often sends ``"2025-01-15"`` and
    ``"1200"``. Excel may read those exact cells back as a ``datetime`` and
    a numeric value. Exact Python equality calls that a failed write even when
    Excel stored the intended date or number correctly.
    """
    if expected_value in (None, "") and actual_value in (None, ""):
        return True
    if expected_value == actual_value:
        return True

    if isinstance(expected_value, str) and isinstance(actual_value, (datetime, date)):
        try:
            parsed = datetime.fromisoformat(expected_value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(expected_value), datetime.min.time())
            except ValueError:
                parsed = None
        if parsed is not None:
            if len(expected_value) == 10:
                actual_date = actual_value.date() if isinstance(actual_value, datetime) else actual_value
                return parsed.date() == actual_date
            return parsed == actual_value

    try:
        # Decimal avoids the false negatives caused by binary float rendering
        # while still rejecting genuinely different numeric values.
        expected_number = Decimal(str(expected_value).strip())
        actual_number = Decimal(str(actual_value).strip())
        return abs(expected_number - actual_number) <= Decimal("0.000000001")
    except (InvalidOperation, ValueError, TypeError):
        return False


def _table_values_match(expected, actual) -> bool:
    """Excel reports blank text cells as None and may coerce dates/numbers."""
    if len(expected) != len(actual):
        return False
    for expected_row, actual_row in zip(expected, actual):
        if len(expected_row) != len(actual_row):
            return False
        for expected_value, actual_value in zip(expected_row, actual_row):
            if not _values_equivalent(expected_value, actual_value):
                return False
    return True


def run(sheet_name: str, start_cell: str, headers: list, rows: list, table_name: str = None):
    if not isinstance(headers, list) or not headers or any(not isinstance(header, str) or not header.strip() for header in headers):
        return {
            "error": "headers must be a non-empty list of non-blank strings.",
            "verified": False, "status": "invalid_headers",
        }
    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
        return {
            "error": "Every data row must be a list with exactly the same number of values as headers.",
            "verified": False, "status": "invalid_row_shape",
        }

    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]

    sheet.activate()

    start = sheet.range(start_cell)
    start.value = headers
    data_start = start.offset(1, 0)
    existing_data_rows = 0
    if rows:
        data_start.value = rows
    else:
        # Code generation may have already populated a rectangular data set
        # and then call this skill only to turn it into a real Excel Table.
        # The old implementation created a one-row Table over just the
        # headers in that case, leaving every data row outside the Table and
        # breaking formulas, pivots, and charts downstream.
        try:
            if data_start.value not in (None, ""):
                existing_last_row = sheet.used_range.last_cell.row
                existing_data_rows = max(existing_last_row - data_start.row + 1, 0)
        except Exception:
            existing_data_rows = 0
    wb.save()

    written_headers = normalize(start.resize(1, len(headers)).value)[0]
    actual_values = []
    if rows:
        actual_values = normalize(data_start.resize(len(rows), len(headers)).value)

    headers_match = _table_values_match([headers], [written_headers])
    rows_match = _table_values_match(rows, actual_values)
    verified = headers_match and rows_match
    result = {
        "sheet": sheet_name, "start_cell": start_cell, "headers": headers,
        "rows_written": len(rows), "status": "table_created", "verified": verified,
        "verification_note": "Confirmed every header and data value matches the requested table." if verified else
            "The written table does not exactly match the requested headers and data values.",
    }

    if table_name:
        table_row_count = len(rows) if rows else existing_data_rows
        full_range = start.resize(1 + table_row_count, len(headers))
        existing_tables = {t.name: t for t in sheet.tables}

        if table_name in existing_tables:
            result["table_name"] = table_name
            existing_table = existing_tables[table_name]
            try:
                existing_table.api.Resize(full_range.api)
                wb.save()
                result["table_status"] = "table_resized_to_existing_data"
            except Exception as e:
                result["table_status"] = "table_resize_failed"
                result["error"] = str(e)
                result["verified"] = False
                result["verification_note"] = (
                    f"The existing Table '{table_name}' could not be expanded to include "
                    f"the {table_row_count} existing data row(s): {e}"
                )
        else:
            try:
                sheet.tables.add(source=full_range, name=table_name)
                wb.save()
                result["table_name"] = table_name
                result["table_status"] = "table_created"
            except Exception as e:
                result["table_name"] = table_name
                result["table_status"] = "table_creation_failed"
                result["error"] = str(e)
                result["verified"] = False
                result["verification_note"] = (
                    f"Data was written, but converting it into a real Table named "
                    f"'{table_name}' failed ({e}). Structured references to it will fail."
                )

    if not rows and existing_data_rows:
        result["existing_rows_included"] = existing_data_rows
        result["verification_note"] = (
            f"Confirmed the headers and included {existing_data_rows} existing data row(s) "
            "in the native Excel Table."
        )

    return result
