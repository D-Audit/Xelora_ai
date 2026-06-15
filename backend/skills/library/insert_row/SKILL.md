---
name: insert_row
category: structure
description: "Inserts one or more blank rows, shifting existing rows down."
source: migrated from skills/excel_structure.py
---

# insert_row

Inserts one or more blank rows, shifting existing rows down.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "row_number": {
      "type": "integer"
    },
    "count": {
      "type": "integer",
      "default": 1
    }
  },
  "required": [
    "sheet_name",
    "row_number"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
