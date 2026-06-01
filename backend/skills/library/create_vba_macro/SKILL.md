---
name: create_vba_macro
category: vba
description: "Adds a new VBA module to the workbook's VBA project and writes a real macro into it. Requires check_vba_access to return trusted: true first, and the workbook should be .xlsm/.xlsb (use save_as_macro_enabled if it's currently .xlsx) or the macro will be silently stripped on the next save."
source: migrated from skills/excel_vba.py
---

# create_vba_macro

Adds a new VBA module to the workbook's VBA project and writes a real macro into it. Requires check_vba_access to return trusted: true first, and the workbook should be .xlsm/.xlsb (use save_as_macro_enabled if it's currently .xlsx) or the macro will be silently stripped on the next save.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "module_name": {
      "type": "string"
    },
    "vba_code": {
      "type": "string",
      "description": "Full VBA source, e.g. 'Sub MyMacro()\\n ... \\nEnd Sub'"
    }
  },
  "required": [
    "module_name",
    "vba_code"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
