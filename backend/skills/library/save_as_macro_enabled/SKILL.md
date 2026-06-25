---
name: save_as_macro_enabled
category: vba
description: "Saves the current workbook as a .xlsm (macro-enabled) file at the given path. Call this before create_vba_macro if the workbook is currently .xlsx, or Excel will silently discard any VBA code on save."
source: migrated from skills/excel_vba.py
---

# save_as_macro_enabled

Saves the current workbook as a .xlsm (macro-enabled) file at the given path. Call this before create_vba_macro if the workbook is currently .xlsx, or Excel will silently discard any VBA code on save.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Full path, with or without the .xlsm extension"
    }
  },
  "required": [
    "file_path"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
