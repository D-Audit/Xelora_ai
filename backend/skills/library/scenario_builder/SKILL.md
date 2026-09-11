---
name: scenario_builder
category: analysis
description: "Creates formula-based what-if scenario tables for financial planning and sensitivity analysis."
source: Xelora financial modeling skill
---

# Scenario Builder

Creates formula-based what-if scenario tables for financial planning and sensitivity analysis.

Use this skill when the user requests conservative, base, aggressive, or parameter-sweep scenarios. Keep assumptions editable and link projected outputs to workbook cells with formulas.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "scenario_name": {"type": "string", "description": "Title for the scenario analysis."},
    "output_formula_cell": {"type": "string", "description": "Existing output formula cell, for example D10."},
    "input_parameter_cell": {"type": "string", "description": "Local input cell referenced by the output formula, for example C5."},
    "base_value": {"type": "number", "description": "Baseline input value to include."},
    "scenarios": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "number"}}, "required": ["name", "value"]}},
    "position": {"type": "string", "description": "Optional empty top-left position, for example F2."}
  },
  "required": ["scenario_name", "output_formula_cell", "input_parameter_cell", "base_value", "scenarios"]
}
```
