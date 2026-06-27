---
name: set_page_layout
category: format
description: "Configures print/page setup for a sheet: orientation, margins, fit-to-page scaling, and print area. Call this before export_to_pdf if the export needs to fit on a specific number of pages or be landscape - export_to_pdf uses whatever page setup is already on the sheet."
source: new (gap closure)
---

# set_page_layout

Configures print/page setup for a sheet: orientation, margins, fit-to-page scaling, and print area. Call this before export_to_pdf if the export needs to fit on a specific number of pages or be landscape - export_to_pdf uses whatever page setup is already on the sheet.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "orientation": {
      "type": "string",
      "description": "'portrait' or 'landscape'"
    },
    "fit_to_pages_wide": {
      "type": "integer",
      "description": "e.g. 1 to fit all columns on one page wide"
    },
    "fit_to_pages_tall": {
      "type": "integer",
      "description": "e.g. 1 to fit all rows on one page tall"
    },
    "print_area": {
      "type": "string",
      "description": "e.g. 'A1:M40' - leave unset to print the whole used range"
    },
    "margins_inches": {
      "type": "number",
      "description": "Sets top/bottom/left/right margins all to this value"
    }
  },
  "required": [
    "sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
