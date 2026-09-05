---
name: create_sheets
category: structure
description: "Creates and verifies multiple worksheets in the requested order in one Excel action."
source: native batch workbook operation
---

# create_sheets

Creates a set of named worksheets in one live workbook operation. Existing
worksheets are retained and reported as already present, making retries safe.
For a new Xelora-owned workbook that contains only its blank default Sheet1,
the skill renames that tab to the first requested sheet and inserts the rest
after it. This avoids an unwanted blank Sheet1 and preserves the requested
left-to-right order without deleting anything from an existing workbook.

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
