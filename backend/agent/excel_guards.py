"""Pre-execution argument guards for Excel skills.

Skills keep their own validation; these checks run earlier, at the policy
boundary, so the model gets a precise, correctable error before Excel is
touched, and so risky arguments are refused even if a skill would accept them:

* file paths: only the file types each skill is meant to handle, never hidden
  or credential locations (a prompt-injected page must not be able to make
  Xelora import ~/.ssh/id_rsa into a sheet);
* database imports: one read-only SELECT;
* write_table: every row the same width as the headers (names the bad row),
  no formulas smuggled into data rows, and a payload size that fits a tool
  call (larger data belongs in import_workspace_file_to_sheet or codegen);
* insert_formula: the formula must be a formula.
"""
from __future__ import annotations

import re
from pathlib import PureWindowsPath, PurePosixPath
from typing import Any

# skill -> (path argument, allowed extensions, required?)
_PATH_RULES: dict[str, tuple[str, frozenset[str], bool]] = {
    "open_workbook": ("file_path", frozenset({".xlsx", ".xlsm", ".xls", ".xlsb", ".csv", ".tsv", ".ods"}), True),
    "create_new_workbook": ("file_path", frozenset({".xlsx", ".xlsm"}), False),
    "save_as_macro_enabled": ("file_path", frozenset({".xlsm"}), True),
    "export_to_pdf": ("output_path", frozenset({".pdf"}), False),
    "insert_picture": ("image_path", frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp"}), True),
    "import_unstructured_document": (
        "file_path",
        frozenset({".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".docx", ".txt", ".csv", ".tsv", ".md"}),
        True,
    ),
}
_SENSITIVE_PARTS = {
    "appdata", "application data", "library", "windows", "system32", "program files",
    "program files (x86)", "programdata", "etc", "proc", "sys",
}
MAX_WRITE_TABLE_CELLS = 20_000
_MUTATING_SQL = (
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "merge", "grant",
    "revoke", "exec", "execute", "call", "attach", "pragma", "copy", "replace", "vacuum",
)


def _path_error(skill: str, value: Any) -> str | None:
    argument, extensions, required = _PATH_RULES[skill]
    if value in (None, ""):
        return f"{skill} needs '{argument}'." if required else None
    if not isinstance(value, str):
        return f"'{argument}' must be a file path string."
    windows, posix = PureWindowsPath(value), PurePosixPath(value.replace("\\", "/"))
    parts = [part for part in (windows.parts if "\\" in value or windows.drive else posix.parts)]
    suffix = (windows.suffix or posix.suffix).lower()
    if suffix not in extensions:
        return f"{skill} only accepts {', '.join(sorted(extensions))} files for '{argument}', not '{suffix or 'no extension'}'."
    for part in parts[:-1]:
        cleaned = part.strip("\\/").lower()
        if cleaned.startswith(".") and cleaned not in {".", ".."}:
            return f"'{argument}' points inside a hidden folder ('{part}'); use a normal documents folder."
        if cleaned in _SENSITIVE_PARTS and skill != "open_workbook":
            # Workbooks legitimately open from AppData (e.g. Outlook attachments);
            # their type allowlist already limits what can be read.
            return f"'{argument}' points into a system or application-data folder ('{part}'); use the user's documents instead."
    if value.startswith("\\\\?\\") or value.startswith("//?/"):
        return f"'{argument}' uses an unsupported device path."
    return None


def read_only_sql_error(query: Any) -> str | None:
    if not isinstance(query, str) or not query.strip():
        return "Provide a SELECT query."
    text = re.sub(r"--[^\n]*|/\*.*?\*/", " ", query, flags=re.S)
    text = re.sub(r"'(?:[^']|'')*'", "''", text)
    statement = text.strip().rstrip(";").strip()
    if ";" in statement:
        return "Only one SQL statement is allowed."
    lowered = statement.lower()
    if not lowered.startswith(("select", "with")):
        return "Only read-only SELECT (or WITH ... SELECT) queries can be imported."
    blocked = sorted(set(re.findall(r"[a-z_]+", lowered)) & set(_MUTATING_SQL))
    if blocked:
        return f"The query contains data-changing keywords ({', '.join(blocked)}); only reads are allowed."
    return None


def _write_table_error(tool_input: dict[str, Any]) -> str | None:
    headers, rows = tool_input.get("headers"), tool_input.get("rows")
    if not isinstance(headers, list) or not headers:
        return "write_table needs a non-empty 'headers' list."
    if not isinstance(rows, list):
        return "write_table 'rows' must be a list of row lists (use [] to convert existing data into a Table)."
    width = len(headers)
    for index, row in enumerate(rows):
        if not isinstance(row, list):
            return f"write_table row {index + 1} is not a list."
        if len(row) != width:
            return (f"write_table row {index + 1} has {len(row)} values but there are {width} headers "
                    f"({headers}). Fix that row; one bad row fails the whole write.")
        for value in row:
            if isinstance(value, str) and value.lstrip().startswith("="):
                return (f"write_table row {index + 1} contains a formula ({value[:60]!r}). Write raw data with "
                        "write_table, then add calculated columns with insert_formula (fill_to for the column).")
    if width * (len(rows) + 1) > MAX_WRITE_TABLE_CELLS:
        return (f"write_table payload has {width * (len(rows) + 1)} cells (limit {MAX_WRITE_TABLE_CELLS}). "
                "For an uploaded file use import_workspace_file_to_sheet; for generated data use run_excel_code, "
                "then write_table with rows=[] to convert the range into a Table.")
    return None


def excel_argument_error(skill: str, tool_input: dict[str, Any]) -> str | None:
    """Return a correctable error message, or None when the arguments are acceptable."""
    if skill in _PATH_RULES:
        argument = _PATH_RULES[skill][0]
        return _path_error(skill, tool_input.get(argument))
    if skill == "import_from_database":
        return read_only_sql_error(tool_input.get("query"))
    if skill == "write_table":
        return _write_table_error(tool_input)
    if skill == "insert_formula":
        formula = tool_input.get("formula")
        if not isinstance(formula, str) or not formula.lstrip().startswith("="):
            return "insert_formula needs 'formula' starting with '=' (e.g. '=SUM(B2:B10)'). Use write_cell for plain values."
    return None
