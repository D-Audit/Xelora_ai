---
name: data_bar_formatting
category: format
description: "Applies in-cell data bars (a horizontal bar showing each value's size relative to the range) - like a mini bar chart inside the cells."
source: migrated from skills/excel_extended.py
---

# data_bar_formatting

Applies in-cell data bars (a horizontal bar showing each value's size relative to the range) - like a mini bar chart inside the cells.

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
    "bar_color": {
      "type": "string",
      "default": "#638EC6"
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
