---
name: write_cell
category: write
description: "Writes a single literal value into a single cell (text/labels/raw input only - never a calculated value, use insert_formula for that)."
source: migrated from skills/excel_write.py
---

# write_cell

Writes a single literal value into a single cell (text/labels/raw input only - never a calculated value, use insert_formula for that).

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
    "value": {}
  },
  "required": [
    "sheet_name",
    "cell",
    "value"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
