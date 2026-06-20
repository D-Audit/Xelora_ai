---
name: position_chart
category: charts
description: "Positions and sizes an existing chart at a specific cell location. Use this to organize dashboard layouts and prevent overlapping charts."
source: new (presentation quality)
---

# position_chart

Positions and sizes an existing chart at a specific cell location. Use this to organize dashboard layouts and prevent overlapping charts.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "chart_index": {
      "type": "number",
      "description": "Chart index (1-based) on the sheet. The first chart created is 1, second is 2, etc."
    },
    "sheet_name": {
      "type": "string",
      "description": "Sheet name where the chart exists"
    },
    "top_left_cell": {
      "type": "string",
      "description": "Cell where the chart's top-left corner should be positioned (e.g., 'A15', 'K5')"
    },
    "width": {
      "type": "number",
      "description": "Chart width in points (optional, default 400). About 50 points per column."
    },
    "height": {
      "type": "number",
      "description": "Chart height in points (optional, default 250). About 17 points per row."
    },
    "title": {
      "type": "string",
      "description": "Chart title to set (optional)"
    }
  },
  "required": ["chart_index", "sheet_name", "top_left_cell"]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
