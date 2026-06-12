---
name: import_unstructured_document
category: advanced
description: "Extracts data from a PDF, image (OCR), DOCX, or TXT/CSV file already on disk and writes it into a sheet. If the source has a detected table, writes that as rows; otherwise writes the extracted text as one line per row. Only use a file path the user has explicitly provided."
source: migrated from skills/excel_ingest.py
---

# import_unstructured_document

Extracts data from a PDF, image (OCR), DOCX, or TXT/CSV file already on disk and writes it into a sheet. If the source has a detected table, writes that as rows; otherwise writes the extracted text as one line per row. Only use a file path the user has explicitly provided.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string"
    },
    "sheet_name": {
      "type": "string"
    },
    "start_cell": {
      "type": "string",
      "default": "A1"
    },
    "table_index": {
      "type": "integer",
      "description": "Which detected table to use, if the source has more than one (0-based). Ignored if writing raw text."
    }
  },
  "required": [
    "file_path",
    "sheet_name"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
