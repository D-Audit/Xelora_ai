---
name: add_hyperlink
category: format
description: "Adds a clickable hyperlink to a cell - either a web URL or a link to another cell/sheet in this workbook."
source: new (gap closure)
---

# add_hyperlink

Adds a clickable hyperlink to a cell - either a web URL or a link to another cell/sheet in this workbook.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell": {
      "type": "string"
    },
    "address": {
      "type": "string",
      "description": "URL, or 'SheetName!A1' for an internal link"
    },
    "display_text": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "cell",
    "address"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
