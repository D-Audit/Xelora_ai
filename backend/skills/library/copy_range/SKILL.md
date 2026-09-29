---
name: copy_range
category: structure
description: "Copies or moves a range to another place (same or different sheet): everything (values, formulas, formats), values only (paste values), or formats only; optionally transposed. Verifies the destination against the source and, for a move, that the source was cleared."
source: new (gap closure)
---

# copy_range

Copies or moves a range. Use mode "values" to paste values (freeze formulas
into numbers), "formats" to copy formatting only, or "all" for a normal copy.
Set transpose to turn rows into columns. Set move to clear the source after
the copy is verified. Source and destination must not overlap.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "source_sheet": {
      "type": "string"
    },
    "source_range": {
      "type": "string",
      "description": "Range to copy, e.g. 'A1:D20'"
    },
    "target_sheet": {
      "type": "string",
      "description": "Destination sheet (may be the same as source_sheet)"
    },
    "target_cell": {
      "type": "string",
      "description": "Top-left destination cell, e.g. 'F1'"
    },
    "mode": {
      "type": "string",
      "description": "'all' (default), 'values', or 'formats'"
    },
    "transpose": {
      "type": "boolean",
      "description": "Swap rows and columns"
    },
    "move": {
      "type": "boolean",
      "description": "Clear the source after a verified copy (cut/paste)"
    }
  },
  "required": [
    "source_sheet",
    "source_range",
    "target_sheet",
    "target_cell"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
