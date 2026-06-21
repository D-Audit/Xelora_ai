"""
skills/library/read_range/impl.py
Auto-migrated from skills/excel_read.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

def _extract_range_refs(formula: str):
    """Very small, dependency-free heuristic: pulls out A1-style range
    tokens from a formula string. Not a real parser - good enough to
    flag 'this formula touches these cells' for the agent's planning
    step. Swap in a real formula AST library later if precision matters."""
    import re
    return re.findall(r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?", formula)


def run(sheet_name: str, cell_range: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    values = normalize(sheet.range(cell_range).value)
    return {"sheet": sheet_name, "range": cell_range, "values": values, "verified": True}
