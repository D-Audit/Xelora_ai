---
name: filter_data
category: data
description: "Reads a range and returns only rows matching a condition on one column. operator: 'equals', 'greater_than', 'less_than', 'contains'. Read-only - does not delete non-matching rows from the sheet."
source: migrated from skills/excel_data.py
---

# filter_data

Reads a range and returns only rows matching a condition on one column. operator: 'equals', 'greater_than', 'less_than', 'contains'. Read-only - does not delete non-matching rows from the sheet.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell_range": {
      "type": "string"
    },
    "column_index": {
      "type": "integer"
    },
    "condition_value": {},
    "operator": {
      "type": "string",
      "default": "equals"
    }
  },
  "required": [
    "sheet_name",
    "cell_range",
    "column_index",
    "condition_value"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
