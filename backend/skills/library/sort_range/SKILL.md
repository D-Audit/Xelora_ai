---
name: sort_range
category: data
description: "Sorts a range by one or more columns using Excel's own native Sort feature - matches the Data > Sort dialog exactly, including multi-level sorts. sort_columns: list of {'column_index': int, 'ascending': bool}, first item is primary sort key. Assumes row 1 of the range is a header."
source: migrated from skills/excel_data.py
---

# sort_range

Sorts a range by one or more columns using Excel's own native Sort feature - matches the Data > Sort dialog exactly, including multi-level sorts. sort_columns: list of {'column_index': int, 'ascending': bool}, first item is primary sort key. Assumes row 1 of the range is a header.

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
    "sort_columns": {
      "type": "array",
      "items": {
        "type": "object"
      }
    }
  },
  "required": [
    "sheet_name",
    "cell_range",
    "sort_columns"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
