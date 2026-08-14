"""
skills/library/write_table/impl.py
Auto-migrated from skills/excel_write.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

EXCEL_ERROR_VALUES = {"#NAME?", "#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NULL!", "#NUM!", "#SPILL!", "#CALC!"}
def _is_excel_error(value) -> bool:
    return isinstance(value, str) and value.strip() in EXCEL_ERROR_VALUES


def run(sheet_name: str, start_cell: str, headers: list, rows: list, table_name: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]

    sheet.activate()

    start = sheet.range(start_cell)
    start.value = headers
    data_start = start.offset(1, 0)
    if rows:
        data_start.value = rows
    wb.save()

    written_headers = normalize(start.resize(1, len(headers)).value)[0]
    actual_row_count = 0
    if rows:
        actual_values = normalize(data_start.resize(len(rows), len(headers)).value)
        actual_row_count = len(actual_values)

    verified = (written_headers == headers) and (actual_row_count == len(rows))
    result = {
        "sheet": sheet_name, "start_cell": start_cell, "headers": headers,
        "rows_written": len(rows), "status": "table_created", "verified": verified,
        "verification_note": "Confirmed headers and row count match." if verified else
            f"WARNING: expected {len(rows)} rows, found {actual_row_count}.",
    }

    if table_name:
        full_range = start.resize(1 + len(rows), len(headers))
        existing_table_names = [t.name for t in sheet.tables]

        if table_name in existing_table_names:
            result["table_name"] = table_name
            result["table_status"] = "table_already_existed"
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

    return result
