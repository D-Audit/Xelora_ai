---
name: add_macro_button
category: vba
description: "Draws a clickable Form-Control button on a sheet and wires it to run an existing macro by name. Create the macro first with create_vba_macro."
source: migrated from skills/excel_vba.py
---

# add_macro_button

Draws a clickable Form-Control button on a sheet and wires it to run an existing macro by name. Create the macro first with create_vba_macro.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell": {
      "type": "string",
      "description": "Anchor cell for the button's position, e.g. 'K2'"
    },
    "label": {
      "type": "string"
    },
    "macro_name": {
      "type": "string",
      "description": "Must match an existing Sub name, e.g. 'GenerateIncidentReport'"
    },
    "background_color": {
      "type": "string",
      "description": "Hex color, e.g. '#E74C3C'"
    },
    "width": {
      "type": "number",
      "default": 160
    },
    "height": {
      "type": "number",
      "default": 30
    }
  },
  "required": [
    "sheet_name",
    "cell",
    "label",
    "macro_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
