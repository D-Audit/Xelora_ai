---
name: split_column
category: data
description: "Splits one column of text into multiple columns on a delimiter (e.g. 'Full Name' -> 'First Name', 'Last Name')."
source: migrated from skills/excel_data.py
---

# split_column

Splits one column of text into multiple columns on a delimiter (e.g. 'Full Name' -> 'First Name', 'Last Name').

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "source_column": {
      "type": "string"
    },
    "delimiter": {
      "type": "string"
    },
    "new_headers": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "start_row": {
      "type": "integer",
      "default": 2
    }
  },
  "required": [
    "sheet_name",
    "source_column",
    "delimiter",
    "new_headers"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
