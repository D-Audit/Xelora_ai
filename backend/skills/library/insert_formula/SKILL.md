---
name: insert_formula
category: write
description: "Writes a real, native Excel formula into a cell (e.g. '=SUM(A1:A10)'). Always use this for any calculated value - never write_cell with a precomputed number. Pass fill_to to safely fill one formula down a column and verify the full result range. Rejects blank results by default, invalid TableName! references, and whole-column ranges that can hang Excel."
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
    },
    "fill_to": {
      "type": "string",
      "description": "Optional final cell in the same column. The formula is filled from cell through this cell using Excel's native FillDown."
    },
    "allow_blank_result": {
      "type": "boolean",
      "description": "Default false. Set true only when the requested formula is intentionally designed to return blank cells; otherwise a blank result stops dependent work for repair."
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
