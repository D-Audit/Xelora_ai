---
name: format_range
category: formatting
description: "Formats a cell range with font styling (bold, size, color), background color, borders, number format, and text alignment. Makes data tables and dashboards look professional."
source: new (presentation quality)
---

# format_range

Formats a cell range with font styling (bold, size, color), background color, borders, number format, and text alignment. Makes data tables and dashboards look professional.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "range": {
      "type": "string",
      "description": "Cell range like 'A1:H1' or single cell like 'A1'"
    },
    "sheet_name": {
      "type": "string",
      "description": "Sheet name (optional, uses active sheet if omitted)"
    },
    "bold": {
      "type": "boolean",
      "description": "Make text bold"
    },
    "font_size": {
      "type": "number",
      "description": "Font size in points (e.g., 12, 14)"
    },
    "font_color": {
      "type": "string",
      "description": "Font color as hex '#FF0000' or name 'red'"
    },
    "bg_color": {
      "type": "string",
      "description": "Background color as hex '#CCCCCC' or name 'lightblue'"
    },
    "number_format": {
      "type": "string",
      "description": "Number format like '$#,##0.00' for currency, '0.0%' for percent, 'mm/dd/yyyy' for dates"
    },
    "align_horizontal": {
      "type": "string",
      "description": "Horizontal alignment: 'left', 'center', 'right'"
    },
    "align_vertical": {
      "type": "string",
      "description": "Vertical alignment: 'top', 'center', 'bottom'"
    },
    "borders": {
      "type": "boolean",
      "description": "Add borders around the range"
    }
  },
  "required": ["range"]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
