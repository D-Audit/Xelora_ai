---
name: set_sheet_visibility
category: structure
description: "Hides or unhides a sheet (it still exists and can be referenced by formulas, just not shown in the tab bar)."
source: new (gap closure)
---

# set_sheet_visibility

Hides or unhides a sheet (it still exists and can be referenced by formulas, just not shown in the tab bar).

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "visible": {
      "type": "boolean"
    }
  },
  "required": [
    "sheet_name",
    "visible"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
