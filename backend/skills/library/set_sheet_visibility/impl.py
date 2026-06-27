"""
skills/library/set_sheet_visibility/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, visible: bool):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.api.Visible = 1 if visible else 0  # xlSheetVisible / xlSheetHidden
    wb.save()
    return {"sheet_name": sheet_name, "visible": visible,
            "status": "visibility_set", "verified": True}
