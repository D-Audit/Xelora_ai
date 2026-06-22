---
name: refresh_pivot_table
category: dashboard
description: "Refreshes an existing PivotTable so it picks up changes in its source data. Call this any time source data changes after a pivot was already built - pivots do NOT auto-refresh."
source: new (gap closure)
---

# refresh_pivot_table

Refreshes an existing PivotTable so it picks up changes in its source data. Call this any time source data changes after a pivot was already built - pivots do NOT auto-refresh.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "pivot_table_name": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "pivot_table_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
