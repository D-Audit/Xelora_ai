"""
skills/library/inspect_workbook/impl.py
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


def run(sheet_name: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]

    used = sheet.used_range
    used_address = used.address if used else None

    header_guess = False
    formula_map = {}
    if used:
        first_row = normalize(used.rows[0].value)[0]
        header_guess = all(isinstance(v, str) for v in first_row if v is not None)

        # AST-lite formula scan: record every non-empty formula cell in the
        # used range, plus a naive extraction of the ranges it references,
        # so the agent has a dependency hint before it edits a formula it
        # didn't write ("AST Analysis" capability, simplified).
        try:
            formulas = used.formula
            formulas = normalize(formulas)
            for r_idx, row in enumerate(formulas):
                for c_idx, cell_formula in enumerate(row):
                    if isinstance(cell_formula, str) and cell_formula.startswith("="):
                        addr = used.offset(r_idx, c_idx).address
                        formula_map[addr] = {
                            "formula": cell_formula,
                            "referenced_ranges": _extract_range_refs(cell_formula),
                        }
        except Exception:
            pass  # formula scan is best-effort, never blocks the read

    existing_tables = [t.name for t in sheet.tables] if hasattr(sheet, "tables") else []
    existing_charts = [c.name for c in sheet.charts] if hasattr(sheet, "charts") else []
    named_ranges = [n.name for n in wb.names if sheet_name in n.name or n.refers_to.startswith(f"={sheet_name}")]

    try:
        pivot_tables = [pt.Name for pt in sheet.api.PivotTables()]
    except Exception:
        pivot_tables = []

    other_sheets = [s.name for s in wb.sheets if s.name != sheet_name]

    return {
        "sheet": sheet_name,
        "used_range": used_address,
        "likely_has_header_row": header_guess,
        "existing_tables": existing_tables,
        "existing_charts": existing_charts,
        "existing_pivot_tables": pivot_tables,
        "named_ranges_touching_this_sheet": named_ranges,
        "formulas_found": formula_map,
        "other_sheets_in_workbook": other_sheets,
        "verified": True,
    }
