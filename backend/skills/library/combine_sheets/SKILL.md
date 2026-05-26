---
name: combine_sheets
category: structure
description: "Combines data from multiple sheets sharing the same column structure into one destination sheet, stacked vertically."
source: migrated from skills/excel_structure.py
---

# combine_sheets

Combines data from multiple sheets sharing the same column structure into one destination sheet, stacked vertically.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "dest_sheet_name": {
      "type": "string"
    },
    "dest_start_cell": {
      "type": "string",
      "default": "A1"
    }
  },
  "required": [
    "sheet_names",
    "dest_sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
