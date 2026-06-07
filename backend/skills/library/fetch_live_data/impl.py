"""
skills/library/fetch_live_data/impl.py
Auto-migrated from skills/excel_advanced.py.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

import requests


def run(sheet_name: str, cell: str, url: str, json_path: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]

    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    value = data
    if json_path:
        for part in json_path.split("."):
            value = value[part]

    # The bug that broke B12: many public APIs (exchange rates, weather,
    # etc.) return a nested object with dozens of fields, not one plain
    # number - if json_path wasn't given (or pointed at the wrong level),
    # `value` here is still a dict/list, and writing THAT into one cell
    # crashes with a raw, unhelpful xlwings error ("must be real number,
    # not dict"). Catch it here instead, before touching Excel at all, and
    # tell the AI exactly what to pick from - so it can retry with the
    # correct json_path instead of silently giving up or hardcoding a
    # fake number.
    if isinstance(value, dict):
        return {
            "sheet": sheet_name, "cell": cell, "url": url,
            "status": "value_not_a_scalar", "verified": False,
            "verification_note": (
                f"The response at this point is a dict with keys: {list(value.keys())}. "
                f"A single cell can only hold one value - retry with json_path pointing to "
                f"one specific key (dot-notation, e.g. 'rates.KES' if 'rates' is one of the "
                f"keys above and you want the KES entry inside it)."
            ),
        }
    if isinstance(value, list):
        return {
            "sheet": sheet_name, "cell": cell, "url": url,
            "status": "value_not_a_scalar", "verified": False,
            "verification_note": (
                f"The response at this point is a list with {len(value)} items. A single "
                f"cell can only hold one value - retry with json_path pointing to a specific "
                f"index or key inside it, or use write_table if you actually want the whole "
                f"list written out as rows."
            ),
        }

    sheet.range(cell).value = value
    wb.save()

    written = sheet.range(cell).value
    verified = written == value
    return {"sheet": sheet_name, "cell": cell, "url": url, "value": written,
            "status": "fetched", "verified": verified}
