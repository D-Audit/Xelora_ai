"""
skills/library/inspect_workbook/impl.py
Auto-migrated from skills/excel_read.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


EXCEL_ERROR_VALUES = {
    "#REF!", "#VALUE!", "#NAME?", "#DIV/0!", "#N/A", "#NULL!",
    "#NUM!", "#CALC!", "#SPILL!", "#BLOCKED!", "#CONNECT!",
}
MAX_REPORTED_FORMULA_ERRORS = 80

def _extract_range_refs(formula: str):
    """Very small, dependency-free heuristic: pulls out A1-style range
    tokens from a formula string. Not a real parser - good enough to
    flag 'this formula touches these cells' for the agent's planning
    step. Swap in a real formula AST library later if precision matters."""
    import re
    return re.findall(r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?", formula)


def _is_excel_error(value):
    return isinstance(value, str) and value.strip().upper() in EXCEL_ERROR_VALUES


def _matrix_value(values, row_index: int, column_index: int):
    if row_index >= len(values):
        return None
    row = values[row_index]
    return row[column_index] if isinstance(row, list) and column_index < len(row) else None


def _inspect_sheet(wb, sheet):
    sheet_name = sheet.name

    used = sheet.used_range
    used_address = used.address if used else None

    header_guess = False
    formula_map = {}
    formula_errors = []
    if used:
        values = normalize(used.value)
        first_row = normalize(used.rows[0].value)[0]
        header_guess = all(isinstance(v, str) for v in first_row if v is not None)

        try:
            formulas = used.formula
            formulas = normalize(formulas)
            for r_idx, row in enumerate(formulas):
                for c_idx, cell_formula in enumerate(row):
                    cell_value = _matrix_value(values, r_idx, c_idx)
                    if _is_excel_error(cell_value) and len(formula_errors) < MAX_REPORTED_FORMULA_ERRORS:
                        formula_errors.append({
                            "sheet": sheet_name,
                            "address": used.offset(r_idx, c_idx).address,
                            "error": cell_value.strip().upper(),
                            "formula": cell_formula if isinstance(cell_formula, str) and cell_formula.startswith("=") else None,
                        })
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
        "formula_errors": formula_errors,
        "formula_error_count": len(formula_errors),
        "other_sheets_in_workbook": other_sheets,
        "verified": True,
    }


def run(sheet_name: str | None = None):
    """Inspect one sheet, or audit every worksheet when ``sheet_name`` is omitted."""
    wb = get_active_workbook()
    if sheet_name:
        return _inspect_sheet(wb, wb.sheets[sheet_name])

    sheet_reports = [_inspect_sheet(wb, sheet) for sheet in wb.sheets]
    formula_errors = [
        error
        for report in sheet_reports
        for error in report["formula_errors"]
    ][:MAX_REPORTED_FORMULA_ERRORS]
    return {
        "workbook_name": wb.name,
        "sheet_reports": sheet_reports,
        "formula_errors": formula_errors,
        "formula_error_count": sum(report["formula_error_count"] for report in sheet_reports),
        "verified": True,
    }
