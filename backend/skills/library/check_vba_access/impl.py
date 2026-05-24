"""
skills/library/check_vba_access/impl.py
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


def run():
    wb = get_active_workbook()
    trusted = _vba_trust_enabled(wb)
    return {
        "trusted": trusted,
        "verified": True,
        "verification_note": (
            "VBA project object model access is enabled - macros can be created."
            if trusted else
            "VBA project object model access is NOT trusted. Ask the user to enable it: "
            "File > Options > Trust Center > Trust Center Settings > Macro Settings > "
            "check 'Trust access to the VBA project object model', then retry."
        ),
    }
