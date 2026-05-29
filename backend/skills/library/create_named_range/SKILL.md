---
name: create_named_range
category: structure
description: "Creates a named range so formulas elsewhere can reference it by name instead of raw coordinates."
source: migrated from skills/excel_structure.py
---

# create_named_range

Creates a named range so formulas elsewhere can reference it by name instead of raw coordinates.

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
    "name": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "cell_range",
    "name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
