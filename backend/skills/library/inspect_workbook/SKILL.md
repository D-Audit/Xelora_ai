---
name: inspect_workbook
category: read
description: "Builds a semantic map of a sheet: used range, header guess, existing tables/charts/named ranges/pivot tables, and any cells that contain formulas (with their dependency references). Always call this before acting on a sheet you haven't inspected yet - don't guess at structure."
source: migrated from skills/excel_read.py
---

# inspect_workbook

Builds a semantic map of a sheet: used range, header guess, existing tables/charts/named ranges/pivot tables, and any cells that contain formulas (with their dependency references). Always call this before acting on a sheet you haven't inspected yet - don't guess at structure.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
