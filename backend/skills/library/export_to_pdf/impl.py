"""
skills/library/export_to_pdf/impl.py
Auto-migrated from skills/excel_advanced.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

import requests


def run(sheet_name: str, output_path: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    sheet.api.ExportAsFixedFormat(0, output_path)  # 0 = xlTypePDF
    import os
    verified = os.path.exists(output_path)
    return {"sheet": sheet_name, "output_path": output_path, "status": "exported", "verified": verified}
