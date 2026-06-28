"""
skills/library/sort_range/impl.py
Auto-migrated from skills/excel_data.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell_range: str, sort_columns: list):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    # Get total columns inside the selected boundaries to prevent out-of-range crashes
    total_range_columns = rng.columns.count

    sort_obj = sheet.api.Sort
    sort_obj.SortFields.Clear()
    
    for level in sort_columns:
        # Cast to int to prevent "Indices must be integers" crash
        raw_index = int(level["column_index"])
        
        # FIX 1: Automatically shift 1-indexed numbers (like 7 for column G) 
        # to 0-indexed positions (6) used by Python range slicing
        col_idx = raw_index - 1 if raw_index >= 1 else raw_index
        
        # Guardrail check against boundaries to prevent unhandled background errors
        if col_idx < 0 or col_idx >= total_range_columns:
            return {
                "sheet": sheet_name, "range": cell_range, "sort_columns": sort_columns,
                "status": "sort_failed", "verified": False,
                "verification_note": (
                    f"CRITICAL INDEX ERROR: You provided column_index {raw_index} for a selection range "
                    f"that is only {total_range_columns} columns wide. Remember that column_index must map "
                    f"within the selected target range bounding box (Column 1 is the first column of the selection)."
                )
            }

        column_range = rng.columns[col_idx].api
        order = 1 if level.get("ascending", True) else 2
        sort_obj.SortFields.Add(Key=column_range, Order=order)

    sort_obj.SetRange(rng.api)
    
    # FIX 2: Dynamically detect if row 1 is included to handle headers properly.
    # If sorting from row 2 (e.g., A2:G4), there is no header row inside this specific range selection.
    if rng.row == 1:
        sort_obj.Header = 1  # 1 = xlYes
    else:
        sort_obj.Header = 2  # 2 = xlNo (treat all selected rows as data to prevent skipping row 2)

    try:
        sort_obj.Apply()
        wb.save()
    except Exception as e:
        return {
            "sheet": sheet_name, "range": cell_range, "sort_columns": sort_columns,
            "status": "execution_failed", "verified": False,
            "verification_note": f"Excel COM interface rejected sort layout configuration. Error: {str(e)}"
        }

    return {
        "sheet": sheet_name, "range": cell_range, "sort_columns": sort_columns,
        "status": "sorted", "verified": True,
        "verification_note": "Sort successfully configured and applied via Excel's native Sort feature.",
    }
