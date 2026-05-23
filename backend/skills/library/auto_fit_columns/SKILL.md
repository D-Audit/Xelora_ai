---
name: auto_fit_columns
category: format
description: "Auto-fits column widths in a range so content isn't cut off."
source: migrated from skills/excel_format.py
---

# auto_fit_columns

Auto-fits column widths in a range so content isn't cut off.

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
