"""
skills/library/save_as_macro_enabled/impl.py
Auto-migrated from skills/excel_vba.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

import os

from skills.excel_shared import get_active_workbook, normalize_workbook_path

def _vba_trust_enabled(wb) -> bool:
    """Touching VBProject raises a COM error if trust access isn't granted -
    cheapest reliable way to test it."""
    try:
        _ = wb.api.VBProject.VBComponents.Count
        return True
    except Exception:
        return False


def run(file_path: str):
    wb = get_active_workbook()
    try:
        file_path = normalize_workbook_path(file_path)
    except ValueError as exc:
        return {"error": str(exc), "verified": False, "status": "invalid_path"}
    if not file_path.lower().endswith(".xlsm"):
        file_path += ".xlsm"
    if not os.path.isdir(os.path.dirname(file_path)):
        return {
            "error": f"The destination folder does not exist: {os.path.dirname(file_path)}",
            "file_path": file_path, "verified": False,
            "status": "destination_folder_not_found",
        }
    try:
        wb.api.SaveAs(file_path, FileFormat=52)  # 52 = xlOpenXMLWorkbookMacroEnabled
    except Exception as exc:
        return {
            "error": str(exc), "file_path": file_path,
            "verified": False, "status": "save_as_failed",
        }

    verified = os.path.isfile(file_path) and wb.name.lower().endswith(".xlsm")
    return {
        "file_path": file_path, "workbook_name": wb.name,
        "status": "saved_as_macro_enabled", "verified": verified,
        "verification_note": (
            "Confirmed an .xlsm workbook exists at the requested path."
            if verified else "Excel returned from SaveAs but the expected .xlsm file was not verified."
        ),
    }
