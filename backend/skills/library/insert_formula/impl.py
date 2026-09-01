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

_AT_COLUMN_REF_RE = re.compile(r"\[@[^\]]+\]")

_STRUCTURED_REF_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\[([^\[\]]+)\]")
_SPILL_REF_RE = re.compile(r"[A-Za-z]+\d+#")
_TABLE_AS_SHEET_REF_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)!")
_WHOLE_COLUMN_REF_RE = re.compile(
    r"(?:(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)!)?\$?[A-Z]{1,3}:\$?[A-Z]{1,3}(?!\d)"
)

MAX_HEAVY_FUNCTIONS_PER_FORMULA = 2


def _is_excel_error(value) -> bool:
    return isinstance(value, str) and value.strip().upper() in EXCEL_ERROR_VALUES


def _first_excel_error_in_range(sheet, rng):
    """Return the first displayed Excel error in a formula range, if any.

    Checking only the first and last filled cells misses bad references in the
    middle of a calculated column. A formula is not verified until every
    displayed result in the target range is error-free.
    """
    values = normalize(rng.value)
    start_row, start_column = rng.row, rng.column
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            if _is_excel_error(value):
                return {
                    "address": sheet.range((start_row + row_index, start_column + column_index)).address,
                    "value": value.strip().upper(),
                }
    return None


def _first_blank_formula_result(sheet, rng):
    """Return the first formula result Excel left blank in ``rng``.

    A stored formula is not proof that a calculation is usable.  In task 265
    the agent wrote formulas before their source cells were populated; Excel
    left the outputs blank, yet the old verifier reported success.  Blank
    results are therefore failures by default.  The rare formula deliberately
    designed to return an empty string can opt in with ``allow_blank_result``.
    """
    values = normalize(rng.value)
    start_row, start_column = rng.row, rng.column
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            if value is None or (isinstance(value, str) and value == ""):
                return {
                    "address": sheet.range((start_row + row_index, start_column + column_index)).address,
                    "value": value,
                }
    return None


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


def _validate_table_qualifiers(wb, formula: str):
    """Reject the common but invalid ``TableName!A1`` formula syntax.

    The log for task 265 used ``SalesData!$M:$M``.  ``SalesData`` is an
    Excel Table, not a worksheet, so that reference can only calculate to an
    error.  It also makes the agent look as though a formula was written when
    no usable business result exists.
    """
    for table_name in _TABLE_AS_SHEET_REF_RE.findall(formula):
        list_object = _find_table_by_name(wb, table_name)
        if list_object is None:
            continue
        try:
            actual_sheet = list_object.Parent.Name
        except Exception:
            actual_sheet = None
        correction = (
            f"Use structured references such as {table_name}[Revenue] and "
            f"{table_name}[Region]"
        )
        if actual_sheet:
            correction += f", or the worksheet reference '{actual_sheet}'!$M$2:$M$361"
        return False, (
            f"'{table_name}' is an Excel Table name, not a worksheet name, so "
            f"'{table_name}!...' is invalid. {correction}."
        )
    return True, None


def _validate_bounded_ranges(formula: str):
    """Reject full-column formula ranges that can hang desktop Excel.

    In the failing run, ``=AVERAGE(SalesData!M:M)`` ran for sixty seconds and
    forced an Excel restart.  Workbook tables or explicit used-row ranges are
    both faster and precise.
    """
    whole_columns = _WHOLE_COLUMN_REF_RE.findall(formula)
    if whole_columns:
        return False, (
            f"Whole-column reference(s) {whole_columns} are not allowed in an automated formula. "
            "Use a Table column (for example SalesData[Revenue]) or a bounded range such as "
            "'Sales Data'!$M$2:$M$361. Whole Excel columns can make calculation hang."
        )
    return True, None


def run(
    sheet_name: str,
    cell: str,
    formula: str,
    fill_to: str | None = None,
    allow_blank_result: bool = False,
):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell)

    fill_range = None
    fill_end = None
    if fill_to:
        try:
            fill_end = sheet.range(fill_to)
        except Exception as exc:
            return {
                "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
                "status": "invalid_fill_target", "verified": False,
                "verification_note": f"Could not resolve fill_to '{fill_to}': {exc}",
            }
        if fill_end.column != rng.column or fill_end.row < rng.row:
            return {
                "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
                "status": "invalid_fill_target", "verified": False,
                "verification_note": (
                    "fill_to must be in the same column as cell and at or below it. "
                    f"Received {cell} through {fill_to}."
                ),
            }
        fill_range = sheet.range(cell, fill_to)

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

    complexity_ok, complexity_error = _check_complexity(formula)
    if not complexity_ok:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "formula_too_complex", "verified": False,
            "verification_note": complexity_error,
        }

    refs_ok, ref_error = _validate_structured_references(wb, formula)
    if not refs_ok:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "invalid_structured_reference", "verified": False,
            "verification_note": ref_error,
        }

    table_qualifiers_ok, table_qualifier_error = _validate_table_qualifiers(wb, formula)
    if not table_qualifiers_ok:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "table_name_used_as_sheet_reference", "verified": False,
            "verification_note": table_qualifier_error,
        }

    bounded_ranges_ok, bounded_range_error = _validate_bounded_ranges(formula)
    if not bounded_ranges_ok:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "status": "whole_column_reference_blocked", "verified": False,
            "verification_note": bounded_range_error,
        }

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
    # Formula2 avoids Excel's legacy implicit-intersection behaviour for
    # dynamic-array formulas.  Use it first whenever the formula can spill
    # or uses a modern function, then retain a legacy fallback for older
    # installs and ordinary formulas.
    prefers_formula2 = _formula_may_spill(formula) or any(
        fn in upper_formula for fn in _DYNAMIC_ARRAY_ONLY_FUNCTIONS
    )
    write_methods = (
        (("formula2", "formula"), "activate+formula2")
        if prefers_formula2 else (("formula", "formula2"), "activate+formula2")
    )
    set_calculation_mode(wb.app, "manual")
    try:
        written = False
        for attribute in write_methods[0]:
            try:
                setattr(rng, attribute, formula)
                attempts.append(attribute)
                written = True
                break
            except Exception:
                continue
        if not written:
            try:
                sheet.activate()
                rng.select()
                rng.formula2 = formula
                attempts.append(write_methods[1])
                written = True
            except Exception as e:
                return {
                    "sheet": sheet_name, "cell": cell, "formula": formula,
                    "status": "write_failed", "verified": False, "attempts": attempts,
                    "error": str(e),
                    "verification_note": "Formula could not be written via .formula, .formula2, or activate+.formula2.",
                }

        if fill_range is not None and fill_end.row > rng.row:
            try:
                fill_range.api.FillDown()
            except Exception as exc:
                return {
                    "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
                    "status": "fill_down_failed", "verified": False, "attempts": attempts,
                    "error": str(exc),
                    "verification_note": (
                        "The starting formula was written, but Excel could not fill it down "
                        f"through {fill_to}."
                    ),
                }

        try:
            if _formula_may_spill(formula):
                wb.app.calculate()
            else:
                (fill_range if fill_range is not None else rng).api.Calculate()
        except Exception:
            pass

        calculated_value = rng.value
        fill_end_value = fill_end.value if fill_end is not None else None
        try:
            stored_formula = rng.formula2 if prefers_formula2 else rng.formula
        except Exception:
            stored_formula = None
        try:
            fill_end_formula = (
                fill_end.formula2 if prefers_formula2 else fill_end.formula
            ) if fill_end is not None else None
        except Exception:
            fill_end_formula = None
    finally:
        set_calculation_mode(wb.app, "automatic")

    checked_range = fill_range if fill_range is not None else rng
    range_error = _first_excel_error_in_range(sheet, checked_range)
    if range_error:
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
            "calculated_value": calculated_value, "fill_end_value": fill_end_value,
            "formula_error_cell": range_error["address"],
            "formula_error_value": range_error["value"],
            "status": "formula_error",
            "attempts": attempts, "verified": False,
            "verification_note": (
                "Formula was stored but calculates to an Excel error at "
                f"{range_error['address']} ({range_error['value']}). Fix the formula itself."
            ),
        }

    if not allow_blank_result:
        blank_result = _first_blank_formula_result(sheet, checked_range)
        if blank_result:
            return {
                "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
                "calculated_value": calculated_value, "fill_end_value": fill_end_value,
                "formula_blank_cell": blank_result["address"],
                "status": "formula_blank_result",
                "attempts": attempts, "verified": False,
                "verification_note": (
                    "Formula was stored but Excel returned a blank result at "
                    f"{blank_result['address']}. Populate or repair its source data before "
                    "continuing with dependent worksheet changes. If an empty result is truly "
                    "intended, retry with allow_blank_result=true."
                ),
            }

    def _normalise_formula(value):
        return re.sub(r"\\s+", "", str(value or "")).upper()

    if _normalise_formula(stored_formula) != _normalise_formula(formula):
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula,
            "stored_formula": stored_formula, "calculated_value": calculated_value,
            "status": "formula_not_preserved", "attempts": attempts, "verified": False,
            "verification_note": (
                "Excel accepted the write but the stored formula differs from the requested formula; "
                "the agent will not treat that as a completed formula change."
            ),
        }

    if fill_end is not None and not (
        isinstance(fill_end_formula, str) and fill_end_formula.startswith("=")
    ):
        return {
            "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
            "stored_formula": stored_formula, "fill_end_formula": fill_end_formula,
            "calculated_value": calculated_value, "fill_end_value": fill_end_value,
            "status": "fill_down_not_preserved", "attempts": attempts, "verified": False,
            "verification_note": (
                f"Excel did not preserve a formula at the final fill target {fill_to}; "
                "the calculated column cannot be treated as complete."
            ),
        }

    wb.save()

    return {
        "sheet": sheet_name, "cell": cell, "formula": formula, "fill_to": fill_to,
        "allow_blank_result": allow_blank_result,
        "calculated_value": calculated_value, "fill_end_value": fill_end_value,
        "status": "formula_written",
        "attempts": attempts, "verified": True,
        "stored_formula": stored_formula, "fill_end_formula": fill_end_formula,
        "verification_note": (
            "Confirmed the requested formula is stored and calculates without an Excel error."
            if fill_end is None else
            f"Confirmed the formula is stored at {cell}, filled through {fill_to}, and both endpoints calculate without an Excel error."
        ),
    }
