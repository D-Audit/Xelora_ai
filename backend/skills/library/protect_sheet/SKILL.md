---
name: protect_sheet
category: advanced
description: "Locks a sheet from further edits, optionally with a password."
source: migrated from skills/excel_advanced.py
---

# protect_sheet

Locks a sheet from further edits, optionally with a password.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "password": {
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
