---
name: find_replace
category: data
description: "Find and replace text across a sheet or within a specific range."
source: migrated from skills/excel_data.py
---

# find_replace

Find and replace text across a sheet or within a specific range.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "find_text": {
      "type": "string"
    },
    "replace_text": {
      "type": "string"
    },
    "cell_range": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "find_text",
    "replace_text"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
