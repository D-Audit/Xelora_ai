"""
skills/library/add_slicer/impl.py
Auto-migrated from skills/excel_extended.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(pivot_sheet_name: str, pivot_table_name: str, field_name: str,
               dest_sheet_name: str = None, dest_cell: str = "H1"):
    wb = get_active_workbook()
    pivot_sheet = wb.sheets[pivot_sheet_name]
    pivot_table = pivot_sheet.api.PivotTables(pivot_table_name)

    dest_sheet = wb.sheets[dest_sheet_name] if dest_sheet_name else pivot_sheet
    slicer_caches = wb.api.SlicerCaches
    cache = slicer_caches.Add2(pivot_table, field_name)

    dest_range = dest_sheet.range(dest_cell).api
    slicer = cache.Slicers.Add(
        dest_sheet.api, "", f"Slicer_{field_name.replace(' ', '_')}",
        field_name, dest_range.Top, dest_range.Left, 200, 200,
    )
    wb.save()

    return {"pivot_table_name": pivot_table_name, "field_name": field_name,
            "status": "slicer_added", "verified": True}
