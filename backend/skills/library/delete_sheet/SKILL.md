---
name: delete_sheet
category: structure
description: "Deletes a worksheet. Refuses if it's the only sheet in the workbook."
source: migrated from skills/excel_structure.py
---

# delete_sheet

Deletes a worksheet. Refuses if it's the only sheet in the workbook.

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
