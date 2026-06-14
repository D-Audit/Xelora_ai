---
name: insert_formula
category: write
description: "Writes a real, native Excel formula into a cell (e.g. '=SUM(A1:A10)'). Always use this for any calculated value - never write_cell with a precomputed number. Handles modern dynamic-array formulas (SORT, UNIQUE, FILTER) and structured Table references automatically."
source: migrated from skills/excel_write.py
---

# insert_formula

Writes a real, native Excel formula into a cell (e.g. '=SUM(A1:A10)'). Always use this for any calculated value - never write_cell with a precomputed number. Handles modern dynamic-array formulas (SORT, UNIQUE, FILTER) and structured Table references automatically.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell": {
      "type": "string"
    },
    "formula": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "cell",
    "formula"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
