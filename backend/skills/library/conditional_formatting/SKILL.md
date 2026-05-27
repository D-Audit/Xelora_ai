---
name: conditional_formatting
category: format
description: "Highlights cells matching a condition (e.g. greater_than 100 -> red fill)."
source: migrated from skills/excel_format.py
---

# conditional_formatting

Highlights cells matching a condition (e.g. greater_than 100 -> red fill).

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
    "operator": {
      "type": "string",
      "description": "greater_than | less_than | equals"
    },
    "value": {},
    "fill_color": {
      "type": "string",
      "default": "#FFC7CE"
    }
  },
  "required": [
    "sheet_name",
    "cell_range",
    "operator",
    "value"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
