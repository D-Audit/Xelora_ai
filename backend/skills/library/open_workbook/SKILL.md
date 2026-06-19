---
name: open_workbook
category: structure
description: "Opens an existing Excel file from disk by its full file path, making it the active workbook for subsequent skill calls in this task."
source: new (gap closure)
---

# open_workbook

Opens an existing Excel file from disk by its full file path, making it the active workbook for subsequent skill calls in this task.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string"
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
