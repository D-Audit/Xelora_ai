---
name: delete_vba_macro
category: vba
description: "Removes an entire VBA module (and every macro inside it) from the workbook's VBA project. Deletes the whole module, not a single Sub within a module shared by others - use create_vba_macro with the same module_name to replace a module's contents instead if you only want to change one macro."
source: new (gap closure)
---

# delete_vba_macro

Removes an entire VBA module (and every macro inside it) from the workbook's VBA project. Deletes the whole module, not a single Sub within a module shared by others - use create_vba_macro with the same module_name to replace a module's contents instead if you only want to change one macro.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "module_name": {
      "type": "string"
    }
  },
  "required": [
    "module_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
