---
name: get_excel_version
category: read
description: "Detects the real Excel version and build on the user's machine, and reports whether it supports dynamic-array functions (UNIQUE, SORT, FILTER, XLOOKUP, LET). Call this once at the very start of a task before writing any formulas."
source: new
---

# get_excel_version

Detects the real Excel version and build on the user's machine, and
reports whether it supports dynamic-array functions (UNIQUE, SORT,
FILTER, XLOOKUP, LET). Call this once at the very start of a task
before writing any formulas.

## Input schema

```json
{
  "type": "object",
  "properties": {}
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run()`
matching the input schema above.