"""
skills/library/remove_duplicates/impl.py
Auto-migrated from skills/excel_data.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    values = normalize(sheet.range(cell_range).value)

    seen, unique_rows, removed = set(), [], 0
    for row in values:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)
        else:
            removed += 1

    start_cell = cell_range.split(":")[0]
    sheet.range(cell_range).clear_contents()
    sheet.range(start_cell).value = unique_rows
    wb.save()

    recheck = normalize(sheet.range(start_cell).resize(
        len(unique_rows), len(unique_rows[0]) if unique_rows else 1).value)
    recheck_keys = [tuple(row) for row in recheck]
    verified = len(recheck_keys) == len(set(recheck_keys))

    return {
        "sheet": sheet_name, "range": cell_range, "duplicates_removed": removed,
        "status": "cleaned", "verified": verified,
        "verification_note": "Confirmed no duplicates remain." if verified else
            "WARNING: duplicates may still be present - please double check.",
    }
