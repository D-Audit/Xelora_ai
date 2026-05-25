---
name: color_scale_formatting
category: format
description: "Applies a 2 or 3 color gradient scale across a range (e.g. red for low values, green for high)."
source: migrated from skills/excel_extended.py
---

# color_scale_formatting

Applies a 2 or 3 color gradient scale across a range (e.g. red for low values, green for high).

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
    "min_color": {
      "type": "string",
      "description": "Hex, e.g. '#F8696B' (red)"
    },
    "mid_color": {
      "type": "string",
      "description": "Hex, optional - omit for a 2-color scale"
    },
    "max_color": {
      "type": "string",
      "description": "Hex, e.g. '#63BE7B' (green)"
    }
  },
  "required": [
    "sheet_name",
    "cell_range",
    "min_color",
    "max_color"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
