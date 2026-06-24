---
name: reorder_sheet
category: structure
description: "Moves a sheet to a new tab position (0-indexed, left to right)."
source: new (gap closure)
---

# reorder_sheet

Moves a sheet to a new tab position (0-indexed, left to right).

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "new_index": {
      "type": "integer",
      "description": "0 = move to the very first tab"
    }
  },
  "required": [
    "sheet_name",
    "new_index"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
