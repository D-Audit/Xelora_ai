---
name: data_validation
category: advanced
description: "Restricts a range of cells to only accept values from a dropdown list."
source: migrated from skills/excel_advanced.py
---

# data_validation

Restricts a range of cells to only accept values from a dropdown list.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell_range": {
      "type": "string"
    },
    "allowed_values": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "sheet_name",
    "cell_range",
    "allowed_values"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
