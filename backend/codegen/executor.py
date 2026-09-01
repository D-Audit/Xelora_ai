"""
codegen/executor.py
The second execution layer: when no skill in the library covers what
the user asked, the AI writes real xlwings Python instead of
being limited to a fixed function list. This module is what makes that
safe enough to actually run.

Two safety layers:
1. AST allow-list check - rejects imports/calls outside an approved
   set BEFORE anything executes (no os, subprocess, sys, shutil, socket,
   eval/exec, __import__, open() outside read-only use, etc).
2. Subprocess isolation with a hard timeout - generated code runs in a
   separate process, not this one, and gets killed if it hangs.

This is not a full security sandbox (nothing short of a VM/container
truly is) - it's a pragmatic barrier against accidents and obviously
malicious generated code. Treat it as a seatbelt, not a cage.

Formulas (including dynamic-array formulas like SORT/UNIQUE/FILTER) must
go through the insert_formula skill, not raw generated code - that skill
now handles the .formula / .formula2 / sheet-activation logic properly
(see skills/excel_write.py). A previous version of this file tried to
auto-rewrite .formula/.formula2 in generated code to sneak past the AST
check below - that never actually worked (the AST check still caught the
rewritten form) and has been removed entirely.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


# Generated code controls the live Excel instance through xlwings.  openpyxl
# intentionally is not allowed here: it operates on a separate file object,
# which is how a model can accidentally verify one workbook while changing
# another.  Skills may still use openpyxl utilities internally where needed.
ALLOWED_IMPORTS = {"xlwings", "datetime", "math", "random", "re", "json", "statistics"}

DISALLOWED_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
}

DISALLOWED_MODULES_ANYWHERE = {"os", "sys", "subprocess", "shutil", "socket", "ctypes", "pathlib", "importlib"}
DISALLOWED_EXCEL_FORMULA_ATTRS = {"formula", "formula2"}


class CodeRejected(Exception):
    """Raised when generated code fails the static safety check."""


def _attribute_path(node) -> str | None:
    """Return a dotted attribute path for simple names such as xw.books.active."""
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _formula_literal(node: ast.AST) -> bool:
    """Whether a value assignment is trying to smuggle an Excel formula."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.lstrip().startswith("=")
    if isinstance(node, ast.JoinedStr):
        first_text = next(
            (
                value.value
                for value in node.values
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            ),
            "",
        )
        return first_text.lstrip().startswith("=")
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return any(_formula_literal(item) for item in node.elts)
    return False


def _literal_sheet_name(node: ast.Subscript) -> str | None:
    """Return a literal ``wb.sheets['Name']`` target when one is present."""
    if not isinstance(node.value, ast.Attribute) or node.value.attr != "sheets":
        return None
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return None


def _check_ast(code: str):
    tree = ast.parse(code)
    referenced_sheets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            sheet_name = _literal_sheet_name(node)
            if sheet_name:
                referenced_sheets.add(sheet_name)
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DISALLOWED_MODULES_ANYWHERE:
                    raise CodeRejected(f"Import of '{alias.name}' is not allowed.")
                if root not in ALLOWED_IMPORTS:
                    raise CodeRejected(f"Import of '{alias.name}' is not in the allowed list {sorted(ALLOWED_IMPORTS)}.")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in DISALLOWED_MODULES_ANYWHERE:
                raise CodeRejected(f"Import from '{node.module}' is not allowed.")
            if root not in ALLOWED_IMPORTS:
                raise CodeRejected(f"Import from '{node.module}' is not in the allowed list {sorted(ALLOWED_IMPORTS)}.")
        elif isinstance(node, ast.Name) and node.id in DISALLOWED_NAMES:
            raise CodeRejected(f"Use of '{node.id}' is not allowed in generated code.")
        elif isinstance(node, ast.Name) and node.id == "default_api":
            raise CodeRejected(
                "'default_api' is not available in generated code. Use get_task_workbook() "
                "and the registered Excel skills instead."
            )
        elif isinstance(node, ast.Attribute) and node.attr in DISALLOWED_NAMES:
            raise CodeRejected(f"Use of '.{node.attr}' is not allowed in generated code.")
        elif _attribute_path(node) in {"xw.books.active", "xlwings.books.active", "xw.apps.active"}:
            raise CodeRejected(
                "Do not select an active xlwings workbook. Use get_task_workbook() "
                "so generated code stays bound to this task's verified workbook."
            )
        elif _attribute_path(node) == "wb.sheetnames":
            raise CodeRejected(
                "get_task_workbook() returns an xlwings Book, not an openpyxl Workbook. "
                "Use wb.sheet_names for names or wb.sheets for worksheets."
            )
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and node.attr.lower() in DISALLOWED_EXCEL_FORMULA_ATTRS
        ):
            raise CodeRejected(
                f"Direct Excel formula assignment via '.{node.attr}' is not allowed in generated code. "
                f"Use the insert_formula skill so formulas go through verification and timeout handling."
            )
        elif (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute) and target.attr.lower() == "value"
                for target in node.targets
            )
            and _formula_literal(node.value)
        ):
            raise CodeRejected(
                "Writing a formula-looking string through '.value' is not allowed in generated code. "
                "Use the insert_formula skill so Excel writes and verifies the formula."
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.lower() == "save"
        ):
            raise CodeRejected(
                "Generated code must not save or rename the workbook. Use save_workbook only after "
                "the final workbook inspection succeeds."
            )

    if len(referenced_sheets) > 1:
        raise CodeRejected(
            "Generated code must have one atomic worksheet target, not a multi-sheet workbook build. "
            "Use create_sheets and the dedicated Excel skills for workbook structure, formulas, "
            "tables, charts, and final saving."
        )


_RUNNER_TEMPLATE = """
import json
import sys
from skills.excel_shared import bind_workbook_context, get_active_workbook  # noqa: F401

WORKBOOK_NAME = {workbook_name}
EXCEL_APP_PID = {excel_app_pid}
if WORKBOOK_NAME:
    bind_workbook_context(WORKBOOK_NAME, EXCEL_APP_PID)

def get_task_workbook():
    # Resolve the workbook pinned to this task, never Excel's global active book.
    return get_active_workbook()

result = None

{user_code}

# A Save As operation can change the workbook's visible name.  Return the live
# identity from the same COM session so the parent task never remains pinned to
# the stale Book1 name after a successful generated operation.
if isinstance(result, dict):
    try:
        # Generated workbook code conventionally keeps its bound Book in
        # ``wb``. Reuse that exact COM object after Save As rather than
        # resolving the old name again. Never open/attach to Excel merely to
        # enrich a data-only code result that did not use a task workbook.
        _result_workbook = globals().get("wb")
        if _result_workbook is None and WORKBOOK_NAME:
            _result_workbook = get_task_workbook()
        if _result_workbook is not None:
            result.setdefault("workbook_name", _result_workbook.name)
            result.setdefault("excel_app_pid", _result_workbook.app.pid)
    except Exception:
        pass

print("___RESULT_START___")
print(json.dumps(result if result is not None else {{"_runner_error": "code ran but did not set `result`"}}, default=str))
print("___RESULT_END___")
"""


def _subprocess_env(project_root: str) -> dict:
    """Bug fix: Python puts the SCRIPT'S OWN directory on sys.path when you
    run `python script.py` - not the current working directory. Since the
    generated code is written to a temp file (e.g. C:\\Users\\...\\Temp\\
    tmpXXXX.py), 'import skills' failed with ModuleNotFoundError every
    single time, because project_root was never actually on sys.path from
    there. This was breaking the entire code-generation layer, not just
    some calls - setting PYTHONPATH explicitly is what fixes it."""
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    # The generated worker only needs skills.excel_shared. Avoid paying the
    # import cost of the complete signed skill catalogue on every fallback.
    env["XELORA_SKIP_SKILL_REGISTRY"] = "1"
    return env


def run_generated_code(
    code: str,
    project_root: str,
    timeout_seconds: int = 100,
    workbook_name: str | None = None,
    excel_app_pid: int | None = None,
) -> dict:
    """
    Validates and runs AI-generated Excel automation code in a
    subprocess. The generated code is expected to:
      - call ``get_task_workbook()`` to get the live workbook pinned to this
        task; never use ``xw.books.active`` or ``xw.apps.active``
      - assign a JSON-serializable dict to a variable named `result`, including
        `verified: true` only after it has checked the intended workbook effect

    Returns a dict always containing at least {"verified": bool}.
    """
    if not isinstance(code, str) or not code.strip():
        return {
            "error": "Generated code must be a non-empty Python string.",
            "verified": False,
            "status": "invalid_code",
        }
    try:
        _check_ast(code)
    except (CodeRejected, SyntaxError) as e:
        return {"error": str(e), "verified": False, "status": "rejected_by_sandbox"}

    wrapped = _RUNNER_TEMPLATE.format(
        user_code=textwrap.indent(code, ""),
        # This is Python source, not JSON.  ``json.dumps(None)`` produces
        # ``null``, which crashes the subprocess before user code runs.
        workbook_name=repr(workbook_name),
        excel_app_pid=repr(excel_app_pid),
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(wrapped)
        script_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_subprocess_env(project_root),
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Generated code timed out after {timeout_seconds}s.", "verified": False, "status": "timeout"}
    finally:
        Path(script_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        return {"error": proc.stderr.strip()[-2000:], "verified": False, "status": "exception", "stdout": proc.stdout}

    stdout = proc.stdout
    if "___RESULT_START___" not in stdout:
        return {"error": "Generated code did not produce a result.", "verified": False,
                "status": "no_result", "stdout": stdout}

    marker_start = stdout.rfind("___RESULT_START___")
    marker_end = stdout.find("___RESULT_END___", marker_start)
    if marker_start < 0 or marker_end < 0:
        return {"error": "Generated code did not produce a complete result marker.", "verified": False,
                "status": "no_result", "stdout": stdout}
    payload = stdout[marker_start + len("___RESULT_START___"):marker_end].strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {"error": "Result was not valid JSON.", "verified": False, "raw": payload}

    if not isinstance(parsed, dict):
        return {
            "error": "Generated code must set `result` to a JSON object with verification evidence.",
            "verified": False,
            "status": "invalid_result_shape",
            "raw_result": parsed,
        }
    if "_runner_error" in parsed:
        return {"error": parsed["_runner_error"], "verified": False, "status": "no_result"}
    if parsed.get("verified") is not True:
        parsed["verified"] = False
        parsed.setdefault("status", "unverified_result")
        parsed.setdefault(
            "verification_note",
            "Generated code must return verified: true and describe the live workbook state it checked.",
        )
    elif not isinstance(parsed.get("verification_note"), str) or not parsed["verification_note"].strip():
        parsed["verified"] = False
        parsed["status"] = "verification_evidence_missing"
        parsed["verification_note"] = (
            "Generated code set verified: true without a non-empty verification_note describing "
            "the workbook value, range, chart, or object it read back."
        )
    return parsed
