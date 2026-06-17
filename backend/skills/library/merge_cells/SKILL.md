---
name: merge_cells
category: structure
description: "Merges a range of cells into one. Only the top-left cell's value is kept."
source: new (gap closure)
---

# merge_cells

Merges a range of cells into one. Only the top-left cell's value is kept.

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
    "center_text": {
      "type": "boolean",
      "default": true
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
