"""Build a verified budget-versus-actual variance analysis."""

from __future__ import annotations

import re

from skills.base import skill
from skills.excel_shared import get_active_workbook

_COLUMN_RE = re.compile(r"^[A-Z]{1,3}$")


def _column_number(column: str) -> int:
    value = 0
    for character in column:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _column_name(number: int) -> str:
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(ord("A") + remainder) + value
    return value


@skill(
    name="variance_analysis",
    description="Create budget-versus-actual variance dollars, percentage, and status columns with threshold highlighting.",
    input_schema={
        "type": "object",
        "properties": {
            "budget_column": {"type": "string", "description": "Budget column letter, for example B."},
            "actual_column": {"type": "string", "description": "Actual column letter, for example C."},
            "data_start_row": {"type": "integer", "description": "First data row; defaults to 2."},
            "data_end_row": {"type": "integer", "description": "Last data row to analyze."},
            "variance_threshold_percent": {"type": "number", "description": "Flag absolute percentage variances above this value; defaults to 10."},
        },
        "required": ["budget_column", "actual_column", "data_end_row"],
    },
    category="financial",
)
def variance_analysis(budget_column: str, actual_column: str, data_end_row: int, data_start_row: int = 2, variance_threshold_percent: float = 10) -> dict:
    budget_column = str(budget_column).upper().strip()
    actual_column = str(actual_column).upper().strip()
    if not _COLUMN_RE.fullmatch(budget_column) or not _COLUMN_RE.fullmatch(actual_column):
        return {"verified": False, "status": "invalid_column", "error": "budget_column and actual_column must be A1-style column letters."}
    if not isinstance(data_start_row, int) or not isinstance(data_end_row, int) or data_start_row < 2 or data_end_row < data_start_row:
        return {"verified": False, "status": "invalid_rows", "error": "data_start_row must be at least 2 and data_end_row must not precede it."}
    if not isinstance(variance_threshold_percent, (int, float)) or variance_threshold_percent < 0:
        return {"verified": False, "status": "invalid_threshold", "error": "variance_threshold_percent must be a non-negative number."}

    workbook = get_active_workbook()
    sheet = workbook.sheets.active
    variance_column = _column_name(_column_number(actual_column) + 1)
    variance_pct_column = _column_name(_column_number(actual_column) + 2)
    status_column = _column_name(_column_number(actual_column) + 3)
    headers = ["Variance ($)", "Variance (%)", "Status"]
    header_range = sheet.range(f"{variance_column}1:{status_column}1")
    existing_headers = header_range.value
    existing_flat = existing_headers if isinstance(existing_headers, list) else [existing_headers]
    if any(value not in (None, "", expected) for value, expected in zip(existing_flat, headers)):
        return {"verified": False, "status": "target_not_empty", "error": f"Columns {variance_column}:{status_column} already contain different headers; refusing to overwrite them."}

    header_range.value = [headers]
    header_range.api.Font.Bold = True
    header_range.color = "#FFF2CC"
    threshold = f"{float(variance_threshold_percent):g}%"
    for row in range(data_start_row, data_end_row + 1):
        sheet.range(f"{variance_column}{row}").formula = f"={actual_column}{row}-{budget_column}{row}"
        sheet.range(f"{variance_pct_column}{row}").formula = f"=IFERROR({variance_column}{row}/{budget_column}{row},0)"
        sheet.range(f"{status_column}{row}").formula = f'=IF(ABS({variance_pct_column}{row})>{threshold},"FLAGGED","OK")'

    sheet.range(f"{variance_column}{data_start_row}:{variance_column}{data_end_row}").number_format = "$#,##0.00"
    sheet.range(f"{variance_pct_column}{data_start_row}:{variance_pct_column}{data_end_row}").number_format = "0.00%"
    conditional_formatting_applied = False
    try:
        conditions = sheet.range(f"{status_column}{data_start_row}:{status_column}{data_end_row}").api.FormatConditions
        condition = conditions.Add(1, 3, '="FLAGGED"')
        condition.Interior.Color = 13421823
        conditional_formatting_applied = True
    except Exception:
        pass
    sheet.range(f"{variance_column}1:{status_column}{data_end_row}").columns.autofit()
    workbook.save()

    formulas = sheet.range(f"{variance_column}{data_start_row}:{status_column}{data_end_row}").formula
    formula_rows = formulas if isinstance(formulas, list) and formulas and isinstance(formulas[0], list) else [formulas]
    verified = all(isinstance(cell, str) and cell.startswith("=") for row in formula_rows for cell in (row if isinstance(row, list) else [row]))
    return {
        "verified": verified,
        "status": "variance_analysis_created" if verified else "verification_failed",
        "budget_column": budget_column,
        "actual_column": actual_column,
        "variance_column": variance_column,
        "variance_pct_column": variance_pct_column,
        "status_column": status_column,
        "rows_analyzed": data_end_row - data_start_row + 1,
        "variance_threshold_percent": variance_threshold_percent,
        "conditional_formatting_applied": conditional_formatting_applied,
    }


run = variance_analysis
