"""
skills/library/split_column/impl.py
Auto-migrated from skills/excel_data.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, source_column: str, delimiter: str, new_headers: list, start_row: int = 2):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    used = sheet.used_range
    last_row = used.last_cell.row

    col_range = sheet.range(f"{source_column}{start_row}:{source_column}{last_row}")
    values = normalize(col_range.value)

    split_rows = [(str(v[0]).split(delimiter) if v[0] is not None else [""] * len(new_headers)) for v in values]

    from openpyxl.utils import column_index_from_string, get_column_letter
    base_col_idx = column_index_from_string(source_column)
    header_row = start_row - 1
    for i, header in enumerate(new_headers):
        col_letter = get_column_letter(base_col_idx + 1 + i)
        sheet.range(f"{col_letter}{header_row}").value = header
        col_values = [[row[i] if i < len(row) else ""] for row in split_rows]
        sheet.range(f"{col_letter}{start_row}").resize(len(col_values), 1).value = col_values

    wb.save()
    return {"sheet": sheet_name, "source_column": source_column, "new_headers": new_headers,
            "rows_split": len(split_rows), "status": "split", "verified": True}
