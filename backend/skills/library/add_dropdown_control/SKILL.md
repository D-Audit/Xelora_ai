---
name: add_dropdown_control
category: dashboard
description: "Adds a Form-Control dropdown (combo box) or checkbox to a sheet, letting a user pick from a list or toggle a value - useful for dashboard filters not driven by a slicer. For a real Table/PivotTable slicer, use add_slicer instead."
source: new (gap closure)
---

# add_dropdown_control

Adds a Form-Control dropdown (combo box) or checkbox to a sheet, letting a user pick from a list or toggle a value - useful for dashboard filters not driven by a slicer. For a real Table/PivotTable slicer, use add_slicer instead.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "control_type": {
      "type": "string",
      "description": "One of: dropdown, checkbox"
    },
    "cell": {
      "type": "string"
    },
    "options": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "linked_cell": {
      "type": "string"
    },
    "label": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "control_type",
    "cell"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
