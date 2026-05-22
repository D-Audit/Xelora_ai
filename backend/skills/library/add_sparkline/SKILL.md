---
name: add_sparkline
category: dashboard
description: "Adds an in-cell sparkline (small trend chart) driven by a data range - common in dashboard rows to show a per-row trend next to the numbers."
source: new (gap closure)
---

# add_sparkline

Adds an in-cell sparkline (small trend chart) driven by a data range - common in dashboard rows to show a per-row trend next to the numbers.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell": {
      "type": "string"
    },
    "data_range": {
      "type": "string"
    },
    "sparkline_type": {
      "type": "string",
      "default": "line",
      "description": "One of: line, column, win_loss"
    }
  },
  "required": [
    "sheet_name",
    "cell",
    "data_range"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
