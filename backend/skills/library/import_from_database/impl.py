"""
skills/library/import_from_database/impl.py
Auto-migrated from skills/excel_database.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



_MAX_IMPORT_ROWS = 100_000
_READ_ONLY_START = ("select", "with")
_MUTATING_WORDS = ("insert", "update", "delete", "drop", "alter", "create", "truncate",
                   "merge", "grant", "revoke", "exec", "execute", "call", "attach", "pragma",
                   "copy", "replace", "vacuum")


def _read_only_query_error(query: str):
    """This skill imports data; it must never change the source database."""
    import re
    text_only = re.sub(r"--[^\n]*|/\*.*?\*/", " ", query or "", flags=re.S)
    text_only = re.sub(r"'(?:[^']|'')*'", "''", text_only)
    statement = text_only.strip().rstrip(";").strip()
    if not statement:
        return "Provide a SELECT query."
    if ";" in statement:
        return "Only one SQL statement is allowed."
    lowered = statement.lower()
    if not lowered.startswith(_READ_ONLY_START):
        return "Only read-only SELECT (or WITH ... SELECT) queries can be imported."
    words = set(re.findall(r"[a-z_]+", lowered))
    blocked = sorted(words & set(_MUTATING_WORDS))
    if blocked:
        return f"The query contains data-changing keywords ({', '.join(blocked)}); only reads are allowed."
    return None


def run(connection_url: str, query: str, sheet_name: str, start_cell: str = "A1"):
    from sqlalchemy import create_engine, text

    refusal = _read_only_query_error(query)
    if refusal:
        return {"status": "query_not_read_only", "verified": False, "error": refusal}

    wb = get_active_workbook()
    if sheet_name not in [s.name for s in wb.sheets]:
        wb.sheets.add(sheet_name)
    sheet = wb.sheets[sheet_name]

    try:
        engine = create_engine(connection_url)
        with engine.connect() as conn:
            result = conn.execute(text(query))
            headers = list(result.keys())
            rows = [list(row) for row in result.fetchmany(_MAX_IMPORT_ROWS + 1)]
            conn.rollback()
        engine.dispose()
    except Exception as e:
        return {"status": "failed", "verified": False, "error": str(e),
                "verification_note": (
                    "Could not connect or query. Common causes: missing database driver "
                    "(e.g. pyodbc/psycopg2 not installed), wrong credentials/host, or a "
                    "firewall blocking the connection from this machine."
                )}

    truncated = len(rows) > _MAX_IMPORT_ROWS
    rows = rows[:_MAX_IMPORT_ROWS]
    all_rows = [headers] + rows
    sheet.range(start_cell).value = all_rows
    wb.save()

    written_headers = sheet.range(start_cell).resize(1, len(headers)).value
    verified = (written_headers == headers) if headers else True

    return {"sheet": sheet_name, "start_cell": start_cell, "columns": headers,
            "rows_written": len(rows), "truncated": truncated, "status": "imported", "verified": verified,
            "verification_note": "Confirmed column headers match the query result." if verified else
                "WARNING: written headers did not match the query result."}
