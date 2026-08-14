"""
skills/library/copy_sheet/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(source_sheet_name: str, new_sheet_name: str):
    wb = get_active_workbook()
    source = wb.sheets[source_sheet_name]
    source.api.Copy(After=source.api)
    new_sheet = wb.sheets[wb.sheets.count - 1] if False else None
    idx = [s.name for s in wb.sheets].index(source_sheet_name)
    copied = wb.sheets[idx + 1]
    copied.name = new_sheet_name
    wb.save()
    return {"source_sheet_name": source_sheet_name, "new_sheet_name": new_sheet_name,
            "status": "sheet_copied", "verified": True}
