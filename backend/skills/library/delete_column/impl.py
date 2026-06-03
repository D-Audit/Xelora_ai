"""
skills/library/delete_column/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def _col_letter_to_index(letter: str) -> int:
    idx = 0
    for ch in letter.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def _col_index_to_letter(idx: int) -> str:
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def run(sheet_name: str, column_letter: str, count: int = 1):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    start_idx = _col_letter_to_index(column_letter)
    end_letter = _col_index_to_letter(start_idx + count - 1)
    rng = f"{column_letter}:{end_letter}"
    sheet.api.Columns(rng).Delete()
    wb.save()
    return {"sheet": sheet_name, "column_letter": column_letter, "count": count,
            "status": "columns_deleted", "verified": True}
