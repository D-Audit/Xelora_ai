"""
skills/library/insert_formula/impl.py
"""

import re

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb, set_calculation_mode, supports_dynamic_arrays  # noqa: F401

EXCEL_ERROR_VALUES = {
    "#REF!", "#VALUE!", "#NAME?", "#DIV/0!", "#N/A",
    "#NULL!", "#NUM!", "#CALC!", "#SPILL!", "#BLOCKED!", "#CONNECT!",
}

_SPILLING_FUNCTIONS = ("SORT(", "UNIQUE(", "FILTER(", "SEQUENCE(", "RANDARRAY(")

_HEAVY_FUNCTIONS = ("SUMIFS(", "XLOOKUP(", "SORT(", "UNIQUE(", "FILTER(",
                    "HSTACK(", "VSTACK(", "LET(", "SUMPRODUCT(")

_DYNAMIC_ARRAY_ONLY_FUNCTIONS = ("UNIQUE(", "SORT(", "FILTER(", "SEQUENCE(", "RANDARRAY(",
                                  "XLOOKUP(", "LET(")

# [@ColumnName] "current row" structured self-references - proven, repeat
# hang trigger across multiple runs, even though the syntax itself is
# valid and old (Excel 2007+). A plain cell reference (=E2*F2) has always
# worked in every case we've seen, so this is blocked outright rather
# than risked.
_AT_COLUMN_REF_RE = re.compile(r"\[@[^\]]+\]")

_STRUCTURED_REF_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\[([^\[\]]+)\]")
_SPILL_REF_RE = re.compile(r"[A-Za-z]+\d+#")

MAX_HEAVY_FUNCTIONS_PER_FORMULA = 1


def _is_excel_error(value) -> bool:
    return isinstance(value, str) and value.strip().upper() in EXCEL_ERROR_VALUES


def _formula_may_spill(formula: str) -> bool:
    upper = formula.upper()
    return any(fn in upper for fn in _SPILLING_FUNCTIONS)


def _check_complexity(formula: str):
    upper = formula.upper()
    heavy_count = sum(upper.count(fn) for fn in _HEAVY_FUNCTIONS)
    spill_ref_count = len(_SPILL_REF_RE.findall(formula))

    if heavy_count > MAX_HEAVY_FUNCTIONS_PER_FORMULA:
        found = [fn.rstrip("(") for fn in _HEAVY_FUNCTIONS if fn in upper]
        return False, (
            f"This formula combines {heavy_count} array/lookup-heavy functions in one cell "
            f"({', '.join(found)}), which is the specific pattern that has repeatedly hung "
            f"Excel's calculation engine. Split this into separate helper cells instead - "
            f"write ONE of these functions per cell, then reference that cell's result in the "
            f"next formula. Do not combine them into one nested formula, even across "
            f"multiple retries."
        )

    if heavy_count >= 1 and spill_ref_count >= 1:
        return False, (
            f"This formula feeds a spilled range reference ({_SPILL_REF_RE.findall(formula)}) "
            f"into an array/lookup-heavy function, forcing per-element array broadcasting - a "
            f"common hang cause even with only one heavy function. Write against a single, "
            f"non-spilled value or a plain fixed range instead, or split across helper cells."
        )

    return True, None


def _check_spill_area_is_clear(sheet, cell: str, check_rows: int = 30, check_cols: int = 10):
    anchor = sheet.range(cell)
    start_row = anchor.row
    start_col = anchor.column
    block = sheet.range((start_row, start_col), (start_row + check_rows, start_col + check_cols))
    values = block.value
    if values is None:
        return True, None
    rows = normalize(values)
    for r_idx, row in enumerate(rows):
        for c_idx, v in enumerate(row):
            if r_idx == 0 and c_idx == 0:
                continue
            if v is not None and v != "":
                blocking_cell = sheet.range((start_row + r_idx, start_col + c_idx)).address
                return False, blocking_cell
    return True, None


def _find_table_by_name(wb, table_name: str):
    for sheet in wb.sheets:
        try:
            for list_object in sheet.api.ListObjects:
                if list_object.Name == table_name:
                    return list_object
        except Exception:
            continue
    return None


def _validate_structured_references(wb, formula: str):
    for table_name, column_name in _STRUCTURED_REF_RE.findall(formula):
        list_object = _find_table_by_name(wb, table_name)
        if list_object is None:
            continue
        try:
            header_row = list_object.HeaderRowRange
            actual_columns = [str(c.Value) for c in header_row]
        except Exception:
            continue
        if column_name not in actual_columns:
            return False, (
                f"Table '{table_name}' has no column named '{column_name}'. "
                f"Its actual columns are: {actual_columns}."
            )
    return True, None


def run(sheet_name: str, cell: str, formula: str):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell)

    # 1. [@Column] "current row" self-references - blocked outright, proven repeat hang trigger.
    if _AT_COLUMN_REF_RE.search(formula):
        found = _AT_COLUMN_REF_RE.findall(formula)
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "at_column_reference_blocked", "verified": False,
            "verification_note": (
                f"'{found}' uses [@ColumnName] 'current row' structured self-reference "
                f"syntax, which has repeatedly hung Excel via COM automation even though it's "
                f"valid syntax. Use a plain cell reference instead (e.g. '=E2*F2' instead of "
                f"'=[@Quantity]*[@Unit_Price]') - this has been proven to work reliably."
            ),
        }

    # 2. Functions that only exist in Excel 365/2021+ - tested live against
    # THIS user's actual Excel, not assumed from a version number (which
    # Excel itself can't reliably report - 2016/2019/365 all say "16.0").
    upper_formula = formula.upper()
    if any(fn in upper_formula for fn in _DYNAMIC_ARRAY_ONLY_FUNCTIONS) and not supports_dynamic_arrays(wb.app):
        used = [fn.rstrip("(") for fn in _DYNAMIC_ARRAY_ONLY_FUNCTIONS if fn in upper_formula]
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "function_not_available_this_excel_version", "verified": False,
            "verification_note": (
                f"{used} require Excel 365 or 2021+ - this Excel installation does not "
                f"support them (confirmed by direct test, not just a version guess). Use a "
                f"legacy equivalent instead: XLOOKUP -> INDEX/MATCH, UNIQUE/SORT/FILTER -> a "
                f"manual helper-column approach (write out categories with write_table, or "
                f"use SUMIFS/COUNTIFS against the raw table directly without an intermediate "
                f"unique-list step), LET -> just use several separate helper cells."
            ),
        }

    # 3. Complexity limit - too many heavy functions combined in one cell.
    complexity_ok, complexity_error = _check_complexity(formula)
    if not complexity_ok:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "formula_too_complex", "verified": False,
            "verification_note": complexity_error,
        }

    # 4. Structured references to columns that don't actually exist.
    refs_ok, ref_error = _validate_structured_references(wb, formula)
    if not refs_ok:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "invalid_structured_reference", "verified": False,
            "verification_note": ref_error,
        }

    # 5. Spill area overlap check.
    if _formula_may_spill(formula):
        is_clear, blocking_cell = _check_spill_area_is_clear(sheet, cell)
        if not is_clear:
            return {
                "sheet": sheet_name, "cell": cell, "formula": formula,
                "status": "spill_area_blocked", "verified": False,
                "verification_note": (
                    f"Cell {blocking_cell} already has content in the area this formula "
                    f"would spill into. Clear that area first, or place this formula "
                    f"somewhere with clear room, before retrying."
                ),
            }

    attempts = []
    set_calculation_mode(wb.app, "manual")
    try:
        try:
            rng.formula = formula
            attempts.append("formula")
        except Exception:
            try:
                rng.formula2 = formula
                attempts.append("formula2")
            except Exception:
                try:
                    sheet.activate()
                    rng.select()
                    rng.formula2 = formula
                    attempts.append("activate+formula2")
                except Exception as e:
                    return {
                        "sheet": sheet_name, "cell": cell, "formula": formula,
                        "status": "write_failed", "verified": False, "attempts": attempts,
                        "error": str(e),
                        "verification_note": "Formula could not be written via .formula, .formula2, or activate+.formula2.",
                    }

        try:
            if _formula_may_spill(formula):
                wb.app.calculate()
            else:
                rng.api.Calculate()
        except Exception:
            pass

        calculated_value = rng.value
    finally:
        set_calculation_mode(wb.app, "automatic")

    if _is_excel_error(calculated_value):
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "calculated_value": calculated_value, "status": "formula_error",
            "attempts": attempts, "verified": False,
            "verification_note": f"Formula was stored but calculates to {calculated_value}. Fix the formula itself.",
        }

    wb.save()

    return {
        "sheet": sheet_name, "cell": cell, "formula": formula,
        "calculated_value": calculated_value, "status": "formula_written",
        "attempts": attempts, "verified": True,
        "verification_note": "Confirmed formula stored AND calculates without an Excel error.",
    }
