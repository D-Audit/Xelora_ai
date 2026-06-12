"""
skills/library/import_unstructured_document/impl.py
Auto-migrated from skills/excel_ingest.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(file_path: str, sheet_name: str, start_cell: str = "A1", table_index: int = 0):
    from ingestion.document_ingest import extract_document, UnsupportedFileType

    try:
        extracted = extract_document(file_path)
    except (UnsupportedFileType, FileNotFoundError) as e:
        return {"status": "failed", "verified": False, "error": str(e)}

    wb = get_active_workbook()
    if sheet_name not in [s.name for s in wb.sheets]:
        wb.sheets.add(sheet_name)
    sheet = wb.sheets[sheet_name]

    tables = extracted.get("tables", [])
    if tables and len(tables) > table_index:
        rows = tables[table_index]
        sheet.range(start_cell).value = rows
        wb.save()
        written = normalize(sheet.range(start_cell).resize(len(rows), len(rows[0]) if rows else 1).value)
        verified = len(written) == len(rows)
        return {"source_type": extracted["source_type"], "wrote": "table", "table_index": table_index,
                "rows_written": len(rows), "status": "imported", "verified": verified,
                "verification_note": "Confirmed row count matches the detected table." if verified else
                    "WARNING: written row count did not match extracted table."}

    text = extracted.get("text", "")
    lines = [[line] for line in text.splitlines() if line.strip()]
    if not lines:
        return {"source_type": extracted["source_type"], "status": "no_data_found", "verified": False,
                "verification_note": "No table or readable text was extracted from this file - "
                    "for scanned/handwritten sources this usually means OCR couldn't read it clearly."}

    sheet.range(start_cell).value = lines
    wb.save()
    return {"source_type": extracted["source_type"], "wrote": "text_lines",
            "lines_written": len(lines), "status": "imported", "verified": True}
