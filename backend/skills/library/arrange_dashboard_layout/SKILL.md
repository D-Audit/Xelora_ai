---
name: arrange_dashboard_layout
category: dashboard
description: "Audits every visible floating object on a worksheet (charts, pictures, shapes, slicers, and controls) for overlap, or reflows them into a spaced grid and verifies the result. Use after creating a dashboard or report with visual objects."
source: presentation-quality layout guard
---

# arrange_dashboard_layout

Audits or arranges all visible floating objects on a worksheet. It reads the
Excel Shapes collection, so charts, pictures, controls, slicers, and ordinary
shapes are checked together rather than in isolation.

Use `mode: "reflow"` after completing a dashboard or report. The skill keeps
each object's current size, arranges the objects in a clear grid, saves the
workbook, reads the final bounds back, and only returns `verified: true` when
no objects overlap. Use `mode: "audit"` when positions must not be changed.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string",
      "description": "The dashboard or report worksheet to check."
    },
    "mode": {
      "type": "string",
      "enum": ["reflow", "audit"],
      "default": "reflow",
      "description": "reflow arranges every visible floating object; audit only reports overlaps."
    },
    "start_cell": {
      "type": "string",
      "default": "B2",
      "description": "Cell at the top-left of the reflow grid."
    },
    "columns": {
      "type": "integer",
      "default": 2,
      "description": "Number of objects per row in the reflow grid."
    },
    "horizontal_gap": {
      "type": "number",
      "default": 18,
      "description": "Horizontal spacing in points between objects."
    },
    "vertical_gap": {
      "type": "number",
      "default": 18,
      "description": "Vertical spacing in points between objects."
    }
  },
  "required": ["sheet_name"]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
