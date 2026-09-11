"""Create a live one-variable scenario table without changing the base model."""

from __future__ import annotations

import re

from skills.base import skill
from skills.excel_shared import get_active_workbook

_CELL_RE = re.compile(r"^\$?([A-Z]{1,3})\$?([1-9][0-9]*)$")


def _column_number(column: str) -> int:
    result = 0
    for character in column:
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _parse_cell(reference: str) -> tuple[int, int] | None:
    match = _CELL_RE.fullmatch(reference.upper().strip()) if isinstance(reference, str) else None
    return (_column_number(match.group(1)), int(match.group(2))) if match else None


@skill(
    name="scenario_builder",
    description="Create a live financial scenario table from an existing one-variable Excel formula.",
    input_schema={
        "type": "object",
        "properties": {
            "scenario_name": {"type": "string", "description": "Title for the scenario analysis."},
            "output_formula_cell": {"type": "string", "description": "Existing output formula cell, for example D10."},
            "input_parameter_cell": {"type": "string", "description": "Local input cell referenced by the output formula, for example C5."},
            "base_value": {"type": "number", "description": "Baseline input value to include in the table."},
            "scenarios": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "number"}}, "required": ["name", "value"]}},
            "position": {"type": "string", "description": "Optional empty top-left position, for example F2."},
        },
        "required": ["scenario_name", "output_formula_cell", "input_parameter_cell", "base_value", "scenarios"],
    },
    category="financial",
)
def scenario_builder(scenario_name: str, output_formula_cell: str, input_parameter_cell: str, base_value: float, scenarios: list, position: str | None = None) -> dict:
    output_cell = _parse_cell(output_formula_cell)
    input_cell = _parse_cell(input_parameter_cell)
    if output_cell is None or input_cell is None:
        return {"verified": False, "status": "invalid_reference", "error": "output_formula_cell and input_parameter_cell must be simple A1 references."}
    if not isinstance(scenarios, list) or not scenarios:
        return {"verified": False, "status": "invalid_scenarios", "error": "Provide at least one named scenario."}

    workbook = get_active_workbook()
    sheet = workbook.sheets.active
    source_formula = sheet.range(output_formula_cell).formula
    if not isinstance(source_formula, str) or not source_formula.startswith("="):
        return {"verified": False, "status": "missing_output_formula", "error": f"{output_formula_cell} must contain an existing Excel formula."}

    input_column, input_row = input_cell
    input_reference = _column_name(input_column) + str(input_row)
    reference_pattern = re.compile(rf"(?<![A-Z0-9_!])\$?{re.escape(_column_name(input_column))}\$?{input_row}(?![A-Z0-9_])", re.IGNORECASE)
    if not reference_pattern.search(source_formula):
        return {
            "verified": False,
            "status": "parameter_not_referenced",
            "error": f"The formula in {output_formula_cell} does not reference local input cell {input_reference}.",
        }

    if position is None:
        start_column = max(sheet.used_range.last_cell.column + 2, 1)
        start_row = 1
        position = f"{_column_name(start_column)}{start_row}"
    else:
        parsed_position = _parse_cell(position)
        if parsed_position is None:
            return {"verified": False, "status": "invalid_position", "error": "position must be a simple A1 reference."}
        start_column, start_row = parsed_position

    rows = [{"name": "Base", "value": base_value}]
    for index, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, dict) or not str(scenario.get("name", "")).strip() or not isinstance(scenario.get("value"), (int, float)):
            return {"verified": False, "status": "invalid_scenarios", "error": f"Scenario {index} must contain a non-empty name and numeric value."}
        rows.append({"name": str(scenario["name"]).strip(), "value": scenario["value"]})

    table_height = len(rows) + 3
    target = sheet.range((start_row, start_column)).resize(table_height, 3)
    existing_values = target.value
    if existing_values not in (None, ""):
        flattened = existing_values if isinstance(existing_values, list) else [existing_values]
        if any(value not in (None, "") for value in flattened if not isinstance(value, list)) or any(
            value not in (None, "") for row in flattened if isinstance(row, list) for value in row
        ):
            return {"verified": False, "status": "target_not_empty", "error": f"Scenario output area at {position} is not empty; choose another position."}

    sheet.range((start_row, start_column)).value = scenario_name
    header = sheet.range((start_row + 2, start_column)).resize(1, 3)
    header.value = [["Scenario", "Input Value", "Output Result"]]
    sheet.range((start_row, start_column)).api.Font.Bold = True
    header.api.Font.Bold = True
    header.color = "#D9EAD3"

    for offset, scenario in enumerate(rows, start=3):
        row = start_row + offset
        sheet.range((row, start_column)).value = scenario["name"]
        input_value_cell = sheet.range((row, start_column + 1))
        input_value_cell.value = scenario["value"]
        replacement = f"${_column_name(start_column + 1)}${row}"
        result_cell = sheet.range((row, start_column + 2))
        result_cell.formula = reference_pattern.sub(replacement, source_formula)

    result_range = sheet.range((start_row + 3, start_column + 2)).resize(len(rows), 1)
    result_range.number_format = sheet.range(output_formula_cell).number_format
    sheet.range((start_row, start_column)).resize(table_height, 3).columns.autofit()
    workbook.save()

    formulas = result_range.formula
    formula_values = formulas if isinstance(formulas, list) else [formulas]
    verified = all(isinstance(value, str) and value.startswith("=") for value in formula_values)
    return {
        "verified": verified,
        "status": "scenario_table_created" if verified else "verification_failed",
        "table_position": position,
        "input_parameter_cell": input_reference,
        "output_formula_cell": output_formula_cell,
        "scenarios_created": len(rows),
        "verification_note": "Each scenario uses a copied output formula whose parameter reference points to that row's input value." if verified else "One or more scenario formulas could not be read back.",
    }


run = scenario_builder
