---
name: freeze_panes
category: format
description: "Freezes rows/columns above and to the left of a cell (e.g. 'A2' freezes just the header row)."
source: migrated from skills/excel_format.py
---

# freeze_panes

Freezes rows/columns above and to the left of a cell (e.g. 'A2' freezes just the header row).

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
    }
  },
  "required": [
    "sheet_name",
    "cell"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
