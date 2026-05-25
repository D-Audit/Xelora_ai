---
name: clear_range
category: structure
description: "Clears the contents and/or formatting of a range without deleting the cells themselves (unlike delete_row/delete_column, nothing shifts)."
source: new (gap closure)
---

# clear_range

Clears the contents and/or formatting of a range without deleting the cells themselves (unlike delete_row/delete_column, nothing shifts).

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
    "clear_formatting": {
      "type": "boolean",
      "default": false,
      "description": "If true, also resets formatting, not just values"
    }
  },
  "required": [
    "sheet_name",
    "cell_range"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
