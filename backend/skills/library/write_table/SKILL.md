---
name: write_table
category: write
description: "Writes a structured table: a header row + data rows, starting at start_cell. Pass table_name to also convert it into a REAL native Excel Table - required for any later formula using TableName[ColumnName] structured references. Formats the result professionally by default (styled header, number formats inferred from the headers and values, borders, column widths, frozen header row); the result's styling field lists what was applied. Pass style=none only when the user asked for unformatted data."
source: migrated from skills/excel_write.py
---

# write_table

Writes a structured table: a header row + data rows, starting at start_cell. Pass table_name to also convert it into a REAL native Excel Table - required for any later formula using TableName[ColumnName] structured references.

By default the block is formatted professionally after it is verified: a styled header row, number formats inferred from each header and its values (dates, money, counts, percentages), borders on plain ranges, fitted column widths, and a frozen header row. Pass `style: "none"` only when the user asked for unformatted data.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string"
    },
    "start_cell": {
      "type": "string"
    },
    "headers": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "rows": {
      "type": "array",
      "items": {
        "type": "array"
      }
    },
    "table_name": {
      "type": "string"
    },
    "style": {
      "type": "string",
      "enum": ["professional", "none"]
    }
  },
  "required": [
    "sheet_name",
    "start_cell",
    "headers",
    "rows"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
