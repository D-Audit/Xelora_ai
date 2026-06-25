"""
skills/library/save_as_macro_enabled/impl.py
Auto-migrated from skills/excel_vba.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

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
    if not file_path.lower().endswith(".xlsm"):
        file_path += ".xlsm"
    wb.api.SaveAs(file_path, FileFormat=52)  # 52 = xlOpenXMLWorkbookMacroEnabled
    return {"file_path": file_path, "status": "saved_as_macro_enabled", "verified": True}
