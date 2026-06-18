---
name: merge_columns
category: data
description: "Merges multiple columns of text into one (e.g. 'First Name' + 'Last Name' -> 'Full Name')."
source: migrated from skills/excel_data.py
---

# merge_columns

Merges multiple columns of text into one (e.g. 'First Name' + 'Last Name' -> 'Full Name').

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "source_columns": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "new_header": {
      "type": "string"
    },
    "separator": {
      "type": "string",
      "default": " "
    },
    "start_row": {
      "type": "integer",
      "default": 2
    }
  },
  "required": [
    "sheet_name",
    "source_columns",
    "new_header"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
