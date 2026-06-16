---
name: list_vba_macros
category: vba
description: "Lists every macro currently defined in the workbook's VBA project, so the AI can check what already exists before deciding to create a new one or reuse/edit an existing one. Requires check_vba_access to report trusted: true first."
source: new (gap closure)
---

# list_vba_macros

Lists every macro currently defined in the workbook's VBA project, so the AI can check what already exists before deciding to create a new one or reuse/edit an existing one. Requires check_vba_access to report trusted: true first.

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
