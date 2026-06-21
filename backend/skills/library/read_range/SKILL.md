---
name: read_range
category: read
description: "Reads values from a cell range so the agent can 'see' the data."
source: migrated from skills/excel_read.py
---

# read_range

Reads values from a cell range so the agent can 'see' the data.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "cell_range": {
      "type": "string"
    }
  },
  "required": [
    "sheet_name",
    "cell_range"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
