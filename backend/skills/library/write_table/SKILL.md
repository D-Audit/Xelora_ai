---
name: write_table
category: write
description: "Writes a structured table: a header row + data rows, starting at start_cell. Pass table_name to also convert it into a REAL native Excel Table - required for any later formula using TableName[ColumnName] structured references."
source: migrated from skills/excel_write.py
---

# write_table

Writes a structured table: a header row + data rows, starting at start_cell. Pass table_name to also convert it into a REAL native Excel Table - required for any later formula using TableName[ColumnName] structured references.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "start_cell": {
      "type": "string"
    },
    "headers": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "rows": {
      "type": "array",
      "items": {
        "type": "array"
      }
    },
    "table_name": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "start_cell",
    "headers",
    "rows"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
