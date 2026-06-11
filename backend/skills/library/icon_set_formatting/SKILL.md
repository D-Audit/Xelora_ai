---
name: icon_set_formatting
category: format
description: "Applies an icon set (e.g. traffic lights, arrows, stars) to a range based on relative value - style: '3TrafficLights1', '3Arrows', '5Stars', '3Symbols'."
source: migrated from skills/excel_extended.py
---

# icon_set_formatting

Applies an icon set (e.g. traffic lights, arrows, stars) to a range based on relative value - style: '3TrafficLights1', '3Arrows', '5Stars', '3Symbols'.

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
    "style": {
      "type": "string",
      "default": "3TrafficLights1"
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
