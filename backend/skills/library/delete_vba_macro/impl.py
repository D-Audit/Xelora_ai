"""
skills/library/delete_vba_macro/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(module_name: str):
    wb = get_active_workbook()
    try:
        vb_project = wb.api.VBProject
        _ = vb_project.VBComponents.Count
    except Exception:
        return {"status": "trust_not_enabled", "verified": False,
                "verification_note": "VBA project object model access is not trusted - "
                "cannot delete a macro module. See check_vba_access."}

    for component in list(vb_project.VBComponents):
        if component.Name == module_name:
            vb_project.VBComponents.Remove(component)
            wb.save()
            return {"module_name": module_name, "status": "module_deleted", "verified": True}

    return {"module_name": module_name, "status": "not_found", "verified": False,
            "verification_note": f"No VBA module named '{module_name}' exists in this workbook."}
