"""
skills/library/find_replace/impl.py
Auto-migrated from skills/excel_data.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, find_text: str, replace_text: str, cell_range: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    target = sheet.range(cell_range) if cell_range else sheet.used_range

    target.api.Replace(What=find_text, Replacement=replace_text)
    wb.save()

    values = normalize(target.value)
    still_present = any(find_text in str(cell) for row in values for cell in row if cell is not None)

    return {
        "sheet": sheet_name, "find_text": find_text, "replace_text": replace_text,
        "status": "replaced", "verified": not still_present,
        "verification_note": "Confirmed text no longer present." if not still_present else
            "WARNING: original text still found - some matches may not have been replaced.",
    }
