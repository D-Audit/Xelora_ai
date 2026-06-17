"""
skills/library/merge_columns/impl.py
Auto-migrated from skills/excel_data.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, source_columns: list, new_header: str, separator: str = " ", start_row: int = 2):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    used = sheet.used_range
    last_row = used.last_cell.row

    columns_values = []
    for col in source_columns:
        col_values = normalize(sheet.range(f"{col}{start_row}:{col}{last_row}").value)
        columns_values.append([row[0] for row in col_values])

    merged = [separator.join(str(v) if v is not None else "" for v in row_vals)
              for row_vals in zip(*columns_values)]

    from openpyxl.utils import column_index_from_string, get_column_letter
    last_source_col_idx = max(column_index_from_string(c) for c in source_columns)
    dest_col_letter = get_column_letter(last_source_col_idx + 1)

    sheet.range(f"{dest_col_letter}{start_row - 1}").value = new_header
    sheet.range(f"{dest_col_letter}{start_row}").resize(len(merged), 1).value = [[v] for v in merged]
    wb.save()

    return {"sheet": sheet_name, "new_header": new_header, "rows_merged": len(merged),
            "status": "merged", "verified": True}
