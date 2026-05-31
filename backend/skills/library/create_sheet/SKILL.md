---
name: create_sheet
category: structure
description: "Creates a new, empty worksheet."
source: migrated from skills/excel_structure.py
---

# create_sheet

Creates a new, empty worksheet.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
