---
name: create_power_query_connection
category: advanced
description: "Connects a sheet to an external data source (database, web feed, folder of files) via Excel's Power Query / Get Data engine, using a connection string and query. Best-effort: complex M-code transformations built in the Power Query editor are not supported here - this covers a straightforward 'pull this external data in' case."
source: migrated from skills/excel_extended.py
---

# create_power_query_connection

Connects a sheet to an external data source (database, web feed, folder of files) via Excel's Power Query / Get Data engine, using a connection string and query. Best-effort: complex M-code transformations built in the Power Query editor are not supported here - this covers a straightforward 'pull this external data in' case.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "connection_name": {
      "type": "string"
    },
    "connection_string": {
      "type": "string",
      "description": "OLEDB/ODBC connection string"
    },
    "command_text": {
      "type": "string",
      "description": "SQL query or source command"
    },
    "dest_sheet_name": {
      "type": "string"
    },
    "dest_cell": {
      "type": "string",
      "default": "A1"
    }
  },
  "required": [
    "connection_name",
    "connection_string",
    "command_text",
    "dest_sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
