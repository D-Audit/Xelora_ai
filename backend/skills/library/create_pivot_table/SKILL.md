---
name: create_pivot_table
category: analysis
description: "Creates a real native Excel PivotTable summarizing source_range. agg_function: sum, average, count, max, min."
source: migrated from skills/excel_analysis.py
---

# create_pivot_table

Creates a real native Excel PivotTable summarizing source_range. agg_function: sum, average, count, max, min.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "source_range": {
      "type": "string"
    },
    "row_field": {
      "type": "string"
    },
    "value_field": {
      "type": "string"
    },
    "agg_function": {
      "type": "string",
      "default": "sum"
    },
    "dest_sheet_name": {
      "type": "string"
    },
    "dest_cell": {
      "type": "string",
      "default": "A1"
    }
  },
  "required": [
    "sheet_name",
    "source_range",
    "row_field",
    "value_field"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
