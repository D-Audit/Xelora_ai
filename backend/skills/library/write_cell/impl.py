"""
skills/library/write_cell/impl.py
Auto-migrated from skills/excel_write.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

EXCEL_ERROR_VALUES = {"#NAME?", "#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NULL!", "#NUM!", "#SPILL!", "#CALC!"}
def _is_excel_error(value) -> bool:
    return isinstance(value, str) and value.strip() in EXCEL_ERROR_VALUES


def run(sheet_name: str, cell: str, value):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.range(cell).value = value
    wb.save()

    written_value = sheet.range(cell).value
    verified = written_value == value

    return {
        "sheet": sheet_name, "cell": cell, "value": written_value,
        "status": "written", "verified": verified,
        "verification_note": "Confirmed value matches." if verified else
            f"WARNING: expected {value!r}, found {written_value!r}.",
    }
