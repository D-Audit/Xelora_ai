---
name: modify_chart
category: dashboard
description: "Changes an existing chart's type, title, or data range without deleting and recreating it."
source: new (gap closure)
---

# modify_chart

Changes an existing chart's type, title, or data range without deleting and recreating it.

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
    },
    "chart_type": {
      "type": "string",
      "description": "One of: column, bar, line, pie, scatter, area"
    },
    "title": {
      "type": "string"
    },
    "title_formula": {
      "type": "string",
      "description": "e.g. '=Sheet1!A1' for a dynamic title"
    },
    "data_range": {
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
