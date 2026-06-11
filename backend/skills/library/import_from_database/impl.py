"""
skills/library/import_from_database/impl.py
Auto-migrated from skills/excel_database.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(connection_url: str, query: str, sheet_name: str, start_cell: str = "A1"):
    from sqlalchemy import create_engine, text

    wb = get_active_workbook()
    if sheet_name not in [s.name for s in wb.sheets]:
        wb.sheets.add(sheet_name)
    sheet = wb.sheets[sheet_name]

    try:
        engine = create_engine(connection_url)
        with engine.connect() as conn:
            result = conn.execute(text(query))
            headers = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
    except Exception as e:
        return {"status": "failed", "verified": False, "error": str(e),
                "verification_note": (
                    "Could not connect or query. Common causes: missing database driver "
                    "(e.g. pyodbc/psycopg2 not installed), wrong credentials/host, or a "
                    "firewall blocking the connection from this machine."
                )}

    all_rows = [headers] + rows
    sheet.range(start_cell).value = all_rows
    wb.save()

    written_headers = sheet.range(start_cell).resize(1, len(headers)).value
    verified = (written_headers == headers) if headers else True

    return {"sheet": sheet_name, "start_cell": start_cell, "columns": headers,
            "rows_written": len(rows), "status": "imported", "verified": verified,
            "verification_note": "Confirmed column headers match the query result." if verified else
                "WARNING: written headers did not match the query result."}
