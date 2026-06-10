---
name: group_rows_columns
category: structure
description: "Groups a range of rows or columns into a collapsible outline section (the little +/- expand/collapse controls in the margin)."
source: new (gap closure)
---

# group_rows_columns

Groups a range of rows or columns into a collapsible outline section (the little +/- expand/collapse controls in the margin).

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "orientation": {
      "type": "string",
      "description": "'rows' or 'columns'"
    },
    "start": {
      "type": "integer",
      "description": "Start row/column number (1-indexed)"
    },
    "end": {
      "type": "integer",
      "description": "End row/column number (1-indexed)"
    }
  },
  "required": [
    "sheet_name",
    "orientation",
    "start",
    "end"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
