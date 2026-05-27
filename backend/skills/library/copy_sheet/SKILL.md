---
name: copy_sheet
category: structure
description: "Duplicates an existing sheet under a new name, keeping all its content and formatting."
source: new (gap closure)
---

# copy_sheet

Duplicates an existing sheet under a new name, keeping all its content and formatting.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "source_sheet_name": {
      "type": "string"
    },
    "new_sheet_name": {
      "type": "string"
    }
  },
  "required": [
    "source_sheet_name",
    "new_sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
