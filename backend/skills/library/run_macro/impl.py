"""
skills/library/run_macro/impl.py
Auto-migrated from skills/excel_extended.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(macro_name: str, args: list = None):
    wb = get_active_workbook()
    macro = wb.app.macro(macro_name)
    result = macro(*(args or []))
    return {"macro_name": macro_name, "args": args or [], "macro_return_value": result,
            "status": "macro_executed", "verified": True,
            "verification_note": "Macro ran without raising an error. It does not "
            "confirm the macro's own internal logic succeeded - check its effects manually."}
