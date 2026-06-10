"""
skills/library/group_rows_columns/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def _col_index_to_letter(idx: int) -> str:
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def run(sheet_name: str, orientation: str, start: int, end: int):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    if orientation.lower() == "rows":
        sheet.api.Rows(f"{start}:{end}").Group()
    else:
        start_letter = _col_index_to_letter(start)
        end_letter = _col_index_to_letter(end)
        sheet.api.Columns(f"{start_letter}:{end_letter}").Group()
    wb.save()
    return {"sheet": sheet_name, "orientation": orientation, "start": start, "end": end,
            "status": "grouped", "verified": True}
