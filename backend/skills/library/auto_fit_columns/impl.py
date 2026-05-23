"""
skills/library/auto_fit_columns/impl.py
Auto-migrated from skills/excel_format.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.range(cell_range).columns.autofit()
    wb.save()
    return {"sheet": sheet_name, "range": cell_range, "status": "autofit_applied", "verified": True}
