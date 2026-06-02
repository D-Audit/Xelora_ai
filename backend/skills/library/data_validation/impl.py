"""
skills/library/data_validation/impl.py
Auto-migrated from skills/excel_advanced.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

import requests


def run(sheet_name: str, cell_range: str, allowed_values: list):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    formula = ",".join(allowed_values)
    rng.api.Validation.Delete()
    rng.api.Validation.Add(Type=3, AlertStyle=1, Formula1=formula)  # xlValidateList
    wb.save()
    return {"sheet": sheet_name, "range": cell_range, "allowed_values": allowed_values,
            "status": "validation_applied", "verified": True}
