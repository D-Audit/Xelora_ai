---
name: add_shape
category: dashboard
description: "Draws a freeform shape (rectangle, oval, rounded rectangle, arrow) on a sheet - useful for dashboard section dividers, callout boxes, or visual accents. For a clickable button wired to a macro, use add_macro_button instead."
source: new (gap closure)
---

# add_shape

Draws a freeform shape (rectangle, oval, rounded rectangle, arrow) on a sheet - useful for dashboard section dividers, callout boxes, or visual accents. For a clickable button wired to a macro, use add_macro_button instead.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "shape_type": {
      "type": "string",
      "description": "One of: rectangle, rounded_rectangle, oval, right_arrow"
    },
    "cell": {
      "type": "string"
    },
    "width": {
      "type": "number",
      "default": 100
    },
    "height": {
      "type": "number",
      "default": 60
    },
    "fill_color": {
      "type": "string"
    },
    "text": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "shape_type",
    "cell"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
