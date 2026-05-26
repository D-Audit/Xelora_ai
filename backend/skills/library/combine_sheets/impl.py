"""
skills/library/combine_sheets/impl.py
Auto-migrated from skills/excel_structure.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_names: list, dest_sheet_name: str, dest_start_cell: str = "A1"):
    wb = get_active_workbook()
    if dest_sheet_name not in [s.name for s in wb.sheets]:
        wb.sheets.add(dest_sheet_name)
    dest = wb.sheets[dest_sheet_name]

    all_rows, header = [], None
    for name in sheet_names:
        sheet = wb.sheets[name]
        values = normalize(sheet.used_range.value)
        if not values:
            continue
        if header is None:
            header = values[0]
            all_rows.append(header)
        all_rows.extend(values[1:])

    dest.range(dest_start_cell).value = all_rows
    wb.save()
    return {"sheet_names": sheet_names, "dest_sheet_name": dest_sheet_name,
            "rows_written": len(all_rows), "status": "combined", "verified": True}
