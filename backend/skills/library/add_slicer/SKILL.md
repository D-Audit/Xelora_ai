---
name: add_slicer
category: analysis
description: "Adds a Slicer (interactive filter button panel) connected to an existing PivotTable field."
source: migrated from skills/excel_extended.py
---

# add_slicer

Adds a Slicer (interactive filter button panel) connected to an existing PivotTable field.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "pivot_sheet_name": {
      "type": "string"
    },
    "pivot_table_name": {
      "type": "string"
    },
    "field_name": {
      "type": "string"
    },
    "dest_sheet_name": {
      "type": "string"
    },
    "dest_cell": {
      "type": "string",
      "default": "H1"
    }
  },
  "required": [
    "pivot_sheet_name",
    "pivot_table_name",
    "field_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
