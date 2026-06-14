"""
skills/library/insert_picture/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


import os


def run(sheet_name: str, image_path: str, anchor_cell: str, width: float = None, height: float = None):
    if not os.path.exists(image_path):
        return {"error": f"Image file not found at {image_path}", "verified": False}
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    anchor = sheet.range(anchor_cell)
    sheet.pictures.add(image_path, left=anchor.left, top=anchor.top, width=width, height=height)
    wb.save()
    return {"sheet": sheet_name, "anchor_cell": anchor_cell, "image_path": image_path,
            "status": "picture_inserted", "verified": True}
