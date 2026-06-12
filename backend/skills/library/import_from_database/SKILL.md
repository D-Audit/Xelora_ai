---
name: import_from_database
category: advanced
description: "Runs a SQL query against an external database and writes the results into a sheet as a table. connection_url is a standard SQLAlchemy URL, e.g. 'postgresql://user:pass@host:5432/dbname' or 'mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server'. Only use a connection URL the user has explicitly provided - never invent one."
source: migrated from skills/excel_database.py
---

# import_from_database

Runs a SQL query against an external database and writes the results into a sheet as a table. connection_url is a standard SQLAlchemy URL, e.g. 'postgresql://user:pass@host:5432/dbname' or 'mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server'. Only use a connection URL the user has explicitly provided - never invent one.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "connection_url": {
      "type": "string"
    },
    "query": {
      "type": "string"
    },
    "sheet_name": {
      "type": "string"
    },
    "start_cell": {
      "type": "string",
      "default": "A1"
    }
  },
  "required": [
    "connection_url",
    "query",
    "sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
