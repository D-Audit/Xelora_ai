---
name: insert_column
category: structure
description: "Inserts one or more blank columns, shifting existing columns right."
source: migrated from skills/excel_structure.py
---

# insert_column

Inserts one or more blank columns, shifting existing columns right.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "column_letter": {
      "type": "string"
    },
    "count": {
      "type": "integer",
      "default": 1
    }
  },
  "required": [
    "sheet_name",
    "column_letter"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
