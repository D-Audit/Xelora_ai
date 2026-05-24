---
name: check_vba_access
category: vba
description: "Checks whether 'Trust access to the VBA project object model' is enabled in this Excel install. ALWAYS call this before create_vba_macro or add_macro_button - if it returns trusted: false, tell the user to enable it manually (File > Options > Trust Center > Trust Center Settings > Macro Settings > check 'Trust access to the VBA project object model') since this is a security setting the agent will not change on its own."
source: migrated from skills/excel_vba.py
---

# check_vba_access

Checks whether 'Trust access to the VBA project object model' is enabled in this Excel install. ALWAYS call this before create_vba_macro or add_macro_button - if it returns trusted: false, tell the user to enable it manually (File > Options > Trust Center > Trust Center Settings > Macro Settings > check 'Trust access to the VBA project object model') since this is a security setting the agent will not change on its own.

## Input schema

```json
{
  "type": "object",
  "properties": {}
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
