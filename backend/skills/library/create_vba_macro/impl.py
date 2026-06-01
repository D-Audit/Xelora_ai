"""
skills/library/create_vba_macro/impl.py
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


def run(module_name: str, vba_code: str):
    wb = get_active_workbook()

    if not _vba_trust_enabled(wb):
        return {
            "status": "trust_not_enabled", "verified": False,
            "verification_note": (
                "Cannot create a macro: 'Trust access to the VBA project object model' "
                "is disabled in this Excel install. Ask the user to enable it manually "
                "(File > Options > Trust Center > Trust Center Settings > Macro Settings), "
                "then retry."
            ),
        }

    vb_project = wb.api.VBProject

    # Remove an existing module of the same name first so re-runs don't fail on a duplicate.
    for component in list(vb_project.VBComponents):
        if component.Name == module_name:
            vb_project.VBComponents.Remove(component)

    new_module = vb_project.VBComponents.Add(1)  # 1 = vbext_ct_StdModule
    new_module.Name = module_name
    new_module.CodeModule.AddFromString(vba_code)

    is_macro_enabled_ext = wb.name.lower().endswith((".xlsm", ".xlsb", ".xltm"))

    return {
        "module_name": module_name, "status": "module_created", "verified": True,
        "workbook_is_macro_enabled_format": is_macro_enabled_ext,
        "verification_note": (
            "Macro module created."
            if is_macro_enabled_ext else
            "Macro module created, but this workbook is NOT saved as .xlsm/.xlsb - "
            "the macro will be SILENTLY STRIPPED the next time this file is saved. "
            "Call save_as_macro_enabled before saving again."
        ),
    }
