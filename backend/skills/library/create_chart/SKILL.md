---
name: create_chart
category: analysis
description: "Creates a real native Excel chart from a data range. chart_type: column, bar, line, pie, doughnut, area, scatter, radar. Waterfall and geographic heat-map charts are NOT supported (limited xlwings/COM support)."
source: migrated from skills/excel_analysis.py
---

# create_chart

Creates a real native Excel chart from a data range. chart_type: column, bar, line, pie, doughnut, area, scatter, radar. Waterfall and geographic heat-map charts are NOT supported (limited xlwings/COM support).

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "data_range": {
      "type": "string"
    },
    "chart_type": {
      "type": "string",
      "default": "column"
    },
    "chart_name": {
      "type": "string",
      "default": "Chart1"
    }
  },
  "required": [
    "sheet_name",
    "data_range"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
