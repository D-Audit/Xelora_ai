"""
skills/library/auto_fit_columns/impl.py
Auto-migrated from skills/excel_format.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    target = sheet.range(cell_range)
    target.columns.autofit()
    wb.save()
    widths = [column.column_width for column in target.columns][:50]
    verified = bool(widths) and all(isinstance(w, (int, float)) and w > 0 for w in widths)
    return {"sheet": sheet_name, "range": cell_range, "status": "autofit_applied", "verified": verified,
            "column_widths": widths,
            "verification_note": "Read back positive column widths after AutoFit." if verified
            else "Could not read back valid column widths after AutoFit."}
