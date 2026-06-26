---
name: set_autofilter
category: data
description: "Turns on Excel's native AutoFilter dropdown arrows for a range's header row - the actual in-sheet filter UI, distinct from filter_data (which computes a filtered result without adding the interactive dropdowns)."
source: new (gap closure)
---

# set_autofilter

Turns on Excel's native AutoFilter dropdown arrows for a range's header row - the actual in-sheet filter UI, distinct from filter_data (which computes a filtered result without adding the interactive dropdowns).

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
