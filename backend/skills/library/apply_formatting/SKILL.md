---
name: apply_formatting
category: format
description: "Applies bold, a number format (e.g. '$#,##0.00'), and/or a fill color to a range."
source: migrated from skills/excel_format.py
---

# apply_formatting

Applies bold, a number format (e.g. '$#,##0.00'), and/or a fill color to a range.

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
    "bold": {
      "type": "boolean"
    },
    "number_format": {
      "type": "string"
    },
    "fill_color": {
      "type": "string",
      "description": "Hex, e.g. '#FFFF00'"
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
