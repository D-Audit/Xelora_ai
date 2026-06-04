---
name: delete_column
category: structure
description: "Deletes one or more entire columns from a sheet, shifting columns to the right leftward."
source: new (gap closure)
---

# delete_column

Deletes one or more entire columns from a sheet, shifting columns to the right leftward.

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
