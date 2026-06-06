---
name: export_to_pdf
category: advanced
description: "Exports a sheet as a PDF file to a given file path."
source: migrated from skills/excel_advanced.py
---

# export_to_pdf

Exports a sheet as a PDF file to a given file path.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "output_path"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
