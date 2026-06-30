"""
skills/library/unprotect_sheet/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, password: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    try:
        if password:
            sheet.api.Unprotect(Password=password)
        else:
            sheet.api.Unprotect()
    except Exception as e:
        return {"sheet_name": sheet_name, "status": "unprotect_failed", "verified": False,
                "error": str(e), "verification_note":
                "Unprotect failed - almost always means the password given doesn't match "
                "the one the sheet was actually protected with."}
    wb.save()
    return {"sheet_name": sheet_name, "status": "unprotected", "verified": True}
