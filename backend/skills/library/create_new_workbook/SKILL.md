---
name: create_new_workbook
category: structure
description: "Creates a brand-new, blank workbook and saves it at the given file path, making it the active workbook for subsequent skill calls in this task."
source: new (gap closure)
---

# create_new_workbook

Creates a brand-new, blank workbook and saves it at the given file path, making it the active workbook for subsequent skill calls in this task.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Full path, with or without .xlsx extension"
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
