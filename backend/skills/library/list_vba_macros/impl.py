"""
skills/library/list_vba_macros/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run():
    wb = get_active_workbook()
    try:
        vb_project = wb.api.VBProject
        _ = vb_project.VBComponents.Count
    except Exception:
        return {"trusted": False, "macros": [], "verified": True,
                "verification_note": "VBA project object model access is not trusted - "
                "cannot list macros. See check_vba_access."}

    macros = []
    for component in vb_project.VBComponents:
        code_module = component.CodeModule
        seen_in_module = set()
        line = 1
        total_lines = code_module.CountOfLines
        # ProcOfLine(line, 0) returns the Sub/Function name that line belongs to.
        # Walk line-by-line (cheap for typical macro sizes) and dedupe by name.
        while line <= total_lines:
            try:
                proc_name = code_module.ProcOfLine(line, 0)
            except Exception:
                proc_name = None
            if proc_name and proc_name not in seen_in_module:
                seen_in_module.add(proc_name)
                macros.append({"name": proc_name, "module": component.Name})
            line += 1

    return {"macros": macros, "count": len(macros), "verified": True}
