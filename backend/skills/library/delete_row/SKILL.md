---
name: delete_row
category: structure
description: "Deletes one or more entire rows from a sheet, shifting rows below upward."
source: new (gap closure)
---

# delete_row

Deletes one or more entire rows from a sheet, shifting rows below upward.

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
