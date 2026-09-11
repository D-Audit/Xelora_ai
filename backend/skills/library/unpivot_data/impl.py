"""Safely transform a wide Excel range into a tall table."""

from __future__ import annotations

import re

from skills.base import skill
from skills.excel_shared import get_active_workbook, normalize

_RANGE_RE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*):([A-Z]{1,3})([1-9][0-9]*)$")
_CELL_RE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")


def _column_number(column: str) -> int:
    value = 0
    for character in column:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


@skill(
    name="unpivot_data",
    description="Transform a selected wide-format range into a tall, header-preserving table without overwriting existing data.",
    input_schema={
        "type": "object",
        "properties": {
            "data_range": {"type": "string", "description": "Source range including headers, for example A1:E10."},
            "id_columns": {"type": "array", "items": {"type": "string"}, "description": "Identifier column letters to retain."},
            "pivot_columns": {"type": "array", "items": {"type": "string"}, "description": "Wide-value column letters to turn into name/value rows."},
            "name_column_header": {"type": "string", "description": "Output header for source column names."},
            "value_column_header": {"type": "string", "description": "Output header for source values."},
            "output_sheet": {"type": "string", "description": "Optional existing destination sheet; default is the source sheet."},
            "output_position": {"type": "string", "description": "Optional empty top-left output position, for example G1."},
        },
        "required": ["data_range", "id_columns", "pivot_columns", "name_column_header", "value_column_header"],
    },
    category="etl",
)
def unpivot_data(data_range: str, id_columns: list, pivot_columns: list, name_column_header: str, value_column_header: str, output_sheet: str | None = None, output_position: str | None = None) -> dict:
    match = _RANGE_RE.fullmatch(str(data_range).upper().strip())
    if match is None:
        return {"verified": False, "status": "invalid_range", "error": "data_range must be a simple A1 range such as A1:E10."}
    start_column, start_row, end_column, end_row = match.groups()
    start_column_number, end_column_number = _column_number(start_column), _column_number(end_column)
    start_row, end_row = int(start_row), int(end_row)
    if end_column_number < start_column_number or end_row <= start_row:
        return {"verified": False, "status": "invalid_range", "error": "data_range must contain a header row and at least one data row."}
    if not isinstance(id_columns, list) or not isinstance(pivot_columns, list) or not id_columns or not pivot_columns:
        return {"verified": False, "status": "invalid_columns", "error": "id_columns and pivot_columns must both be non-empty lists."}

    def column_index(column: object) -> int | None:
        value = str(column).upper().strip()
        if not re.fullmatch(r"[A-Z]{1,3}", value):
            return None
        index = _column_number(value) - start_column_number
        return index if 0 <= index <= end_column_number - start_column_number else None

    id_indices = [column_index(column) for column in id_columns]
    pivot_indices = [column_index(column) for column in pivot_columns]
    if any(index is None for index in id_indices + pivot_indices) or len(set(id_indices)) != len(id_indices) or len(set(pivot_indices)) != len(pivot_indices) or set(id_indices) & set(pivot_indices):
        return {"verified": False, "status": "invalid_columns", "error": "Columns must be unique, inside data_range, and cannot be both identifiers and pivot columns."}
    if not str(name_column_header).strip() or not str(value_column_header).strip():
        return {"verified": False, "status": "invalid_headers", "error": "Output headers must be non-empty."}

    workbook = get_active_workbook()
    source_sheet = workbook.sheets.active
    try:
        target_sheet = workbook.sheets[output_sheet] if output_sheet else source_sheet
    except Exception:
        return {"verified": False, "status": "missing_output_sheet", "error": f"Output sheet '{output_sheet}' was not found."}
    source_values = normalize(source_sheet.range(data_range).value)
    headers, data_rows = source_values[0], source_values[1:]
    output_rows = [[headers[index] for index in id_indices] + [str(name_column_header).strip(), str(value_column_header).strip()]]
    for source_row in data_rows:
        identifiers = [source_row[index] for index in id_indices]
        for pivot_index in pivot_indices:
            output_rows.append(identifiers + [headers[pivot_index], source_row[pivot_index]])

    if output_position is None:
        if target_sheet.name == source_sheet.name:
            output_column, output_row = end_column_number + 2, start_row
        else:
            output_column, output_row = 1, 1
        # Convert through an address so we use the same parser/validation path.
        column_name = ""
        remaining = output_column
        while remaining:
            remaining, remainder = divmod(remaining - 1, 26)
            column_name = chr(ord("A") + remainder) + column_name
        output_position = f"{column_name}{output_row}"
    output_match = _CELL_RE.fullmatch(str(output_position).upper().strip())
    if output_match is None:
        return {"verified": False, "status": "invalid_position", "error": "output_position must be a simple A1 reference."}
    output_column, output_row = _column_number(output_match.group(1)), int(output_match.group(2))
    output_end_column = output_column + len(output_rows[0]) - 1
    output_end_row = output_row + len(output_rows) - 1
    if target_sheet.name == source_sheet.name and not (output_end_column < start_column_number or output_column > end_column_number or output_end_row < start_row or output_row > end_row):
        return {"verified": False, "status": "overlapping_output", "error": "The output range overlaps the source data; choose another output_position or sheet."}
    target_range = target_sheet.range((output_row, output_column)).resize(len(output_rows), len(output_rows[0]))
    existing = normalize(target_range.value)
    if any(value not in (None, "") for row in existing for value in row):
        return {"verified": False, "status": "target_not_empty", "error": f"Output area at {output_position} is not empty; refusing to overwrite it."}

    target_range.value = output_rows
    header_range = target_sheet.range((output_row, output_column)).resize(1, len(output_rows[0]))
    header_range.api.Font.Bold = True
    header_range.color = "#D9EAD3"
    target_range.columns.autofit()
    workbook.save()
    written_headers = normalize(header_range.value)[0]
    verified = written_headers == output_rows[0]
    return {
        "verified": verified,
        "status": "unpivot_complete" if verified else "verification_failed",
        "source_range": data_range,
        "output_sheet": target_sheet.name,
        "output_position": output_position,
        "rows_created": len(output_rows) - 1,
        "verification_note": "The output header was read back and the source range was left intact." if verified else "The output header could not be verified after writing.",
    }


run = unpivot_data
