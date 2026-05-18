---
name: add_comment
category: format
description: "Adds a cell comment/note - a small popup annotation attached to a cell, visible on hover. Tries the modern threaded-comment API first, falls back to a legacy note if unsupported on this Excel build."
source: new (gap closure)
---

# add_comment

Adds a cell comment/note - a small popup annotation attached to a cell, visible on hover. Tries the modern threaded-comment API first, falls back to a legacy note if unsupported on this Excel build.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell": {
      "type": "string"
    },
    "text": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "cell",
    "text"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
