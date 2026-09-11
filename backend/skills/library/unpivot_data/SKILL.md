---
name: unpivot_data
category: transform
description: "Transforms wide Excel data into a tall, normalized table."
source: Xelora data transformation skill
---

# Unpivot Data

Transforms wide Excel data into a tall, normalized table.

Use this skill for consolidating period, region, or category columns into name-value rows while preserving identifier columns.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "data_range": {"type": "string", "description": "Source range including headers, for example A1:E10."},
    "id_columns": {"type": "array", "items": {"type": "string"}, "description": "Identifier column letters to retain."},
    "pivot_columns": {"type": "array", "items": {"type": "string"}, "description": "Wide-value column letters to turn into name/value rows."},
    "name_column_header": {"type": "string", "description": "Output header for source column names."},
    "value_column_header": {"type": "string", "description": "Output header for source values."},
    "output_sheet": {"type": "string", "description": "Optional existing destination sheet; defaults to the source sheet."},
    "output_position": {"type": "string", "description": "Optional empty top-left position, for example G1."}
  },
  "required": ["data_range", "id_columns", "pivot_columns", "name_column_header", "value_column_header"]
}
```
