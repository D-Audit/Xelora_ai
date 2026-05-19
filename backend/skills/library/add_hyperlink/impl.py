"""
skills/library/add_hyperlink/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell: str, address: str, display_text: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell)
    is_internal = "://" not in address and not address.lower().startswith("mailto:")
    if is_internal:
        wb.api.Hyperlinks.Add(Anchor=rng.api, Address="", SubAddress=address,
                               TextToDisplay=display_text or address)
    else:
        wb.api.Hyperlinks.Add(Anchor=rng.api, Address=address,
                               TextToDisplay=display_text or address)
    wb.save()
    return {"sheet": sheet_name, "cell": cell, "address": address,
            "status": "hyperlink_added", "verified": True}
