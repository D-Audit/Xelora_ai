---
name: create_sheets
category: structure
description: "Creates and verifies multiple empty worksheets in one Excel action."
source: native batch workbook operation
---

# create_sheets

Creates a set of named worksheets in one live workbook operation. Existing
worksheets are retained and reported as already present, making retries safe.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_names": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Two or more unique worksheet names to ensure exist."
    }
  },
  "required": ["sheet_names"]
}
```

## Implementation

See `impl.py` in this folder.
