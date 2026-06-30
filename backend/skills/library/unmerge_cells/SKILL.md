---
name: unmerge_cells
category: structure
description: "Undoes a previous merge on a range of cells."
source: new (gap closure)
---

# unmerge_cells

Undoes a previous merge on a range of cells.

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
