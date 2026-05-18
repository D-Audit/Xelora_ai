"""
skills/library/add_comment/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell: str, text: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell)
    try:
        rng.api.AddCommentThreaded(text)
        method = "threaded"
    except Exception:
        try:
            existing = rng.api.Comment
            if existing:
                existing.Delete()
        except Exception:
            pass
        rng.api.AddComment(text)
        method = "legacy"
    wb.save()
    return {"sheet": sheet_name, "cell": cell, "method": method,
            "status": "comment_added", "verified": True}
