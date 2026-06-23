---
name: rename_sheet
category: structure
description: "Renames an existing worksheet."
source: migrated from skills/excel_structure.py
---

# rename_sheet

Renames an existing worksheet.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "old_name": {
      "type": "string"
    },
    "new_name": {
      "type": "string"
    }
  },
  "required": [
    "old_name",
    "new_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
