---
name: remove_duplicates
category: data
description: "Removes duplicate rows within a range, based on all columns in that range."
source: migrated from skills/excel_data.py
---

# remove_duplicates

Removes duplicate rows within a range, based on all columns in that range.

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
    }
  },
  "required": [
    "sheet_name",
    "cell_range"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
