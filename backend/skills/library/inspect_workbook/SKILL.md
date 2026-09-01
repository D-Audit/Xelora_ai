---
name: inspect_workbook
category: read
description: "Builds a semantic map of one sheet, or audits the entire workbook when sheet_name is omitted. Reports used ranges, tables/charts/pivots, formulas, and every detected Excel formula error such as #REF! or #VALUE!. Always use the workbook-wide audit before reporting completion."
source: migrated from skills/excel_read.py
---

# inspect_workbook

Builds a semantic map of a sheet: used range, header guess, existing tables/charts/named ranges/pivot tables, and any cells that contain formulas (with their dependency references). Always call this before acting on a sheet you haven't inspected yet - don't guess at structure.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "sheet_name": {
      "type": "string",
      "description": "Optional sheet to inspect. Omit this field to inspect every worksheet and audit formula errors workbook-wide."
    }
  }
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
