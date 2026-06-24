---
name: run_macro
category: advanced
description: "Runs an existing VBA macro already present in the workbook (recorded or hand-written), by name, with optional positional arguments. Cannot write NEW VBA code into the workbook - only executes macros that already exist there."
source: migrated from skills/excel_extended.py
---

# run_macro

Runs an existing VBA macro already present in the workbook (recorded or hand-written), by name, with optional positional arguments. Cannot write NEW VBA code into the workbook - only executes macros that already exist there.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "macro_name": {
      "type": "string"
    },
    "args": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "macro_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
