---
name: unprotect_sheet
category: structure
description: "Removes protection from a sheet that was locked with protect_sheet. Requires the same password it was protected with, if one was set."
source: new (gap closure)
---

# unprotect_sheet

Removes protection from a sheet that was locked with protect_sheet. Requires the same password it was protected with, if one was set.

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
