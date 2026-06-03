---
name: delete_chart
category: dashboard
description: "Deletes an existing chart from a sheet by name."
source: new (gap closure)
---

# delete_chart

Deletes an existing chart from a sheet by name.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "chart_name": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "chart_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
