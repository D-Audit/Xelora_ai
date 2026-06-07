---
name: fetch_live_data
category: advanced
description: "Fetches live data from an external web API (e.g. exchange rates, stock prices) and writes the result into a cell. Only use with a URL the user has explicitly named or clearly implied - never invent or guess an API URL."
source: migrated from skills/excel_advanced.py
---

# fetch_live_data

Fetches live data from an external web API (e.g. exchange rates, stock prices) and writes the result into a cell. Only use with a URL the user has explicitly named or clearly implied - never invent or guess an API URL.

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
    "url": {
      "type": "string"
    },
    "json_path": {
      "type": "string",
      "description": "Optional dot-notation path, e.g. 'rates.USD'"
    }
  },
  "required": [
    "sheet_name",
    "cell",
    "url"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
