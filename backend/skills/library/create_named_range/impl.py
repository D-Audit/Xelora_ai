"""
skills/library/create_named_range/impl.py
Auto-migrated from skills/excel_structure.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str, name: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    full_address = f"{sheet_name}!{sheet.range(cell_range).address}"
    wb.names.add(name, f"={full_address}")
    wb.save()
    verified = name in [n.name for n in wb.names]
    return {"sheet": sheet_name, "range": cell_range, "name": name,
            "status": "named_range_created", "verified": verified}
