"""
codegen/executor.py
The second execution layer: when no skill in the library covers what
the user asked, the AI writes real xlwings/openpyxl Python instead of
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


ALLOWED_IMPORTS = {"xlwings", "openpyxl", "datetime", "math", "random", "re", "json", "statistics"}

DISALLOWED_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
}

DISALLOWED_MODULES_ANYWHERE = {"os", "sys", "subprocess", "shutil", "socket", "ctypes", "pathlib", "importlib"}
DISALLOWED_EXCEL_FORMULA_ATTRS = {"formula", "formula2"}


class CodeRejected(Exception):
    """Raised when generated code fails the static safety check."""


def _check_ast(code: str):
    tree = ast.parse(code)
    for node in ast.walk(tree):
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
        elif isinstance(node, ast.Attribute) and node.attr in DISALLOWED_NAMES:
            raise CodeRejected(f"Use of '.{node.attr}' is not allowed in generated code.")
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and node.attr.lower() in DISALLOWED_EXCEL_FORMULA_ATTRS
        ):
            raise CodeRejected(
                f"Direct Excel formula assignment via '.{node.attr}' is not allowed in generated code. "
                f"Use the insert_formula skill so formulas go through verification and timeout handling."
            )


_RUNNER_TEMPLATE = """
import json
import sys
from skills.excel_shared import bind_workbook_context, get_active_workbook  # noqa: F401

WORKBOOK_NAME = {workbook_name}
if WORKBOOK_NAME:
    bind_workbook_context(WORKBOOK_NAME)
result = None

{user_code}

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
    return env


def run_generated_code(
    code: str,
    project_root: str,
    timeout_seconds: int = 100,
    workbook_name: str | None = None,
) -> dict:
    """
    Validates and runs AI-generated Excel automation code in a
    subprocess. The generated code is expected to:
      - call get_active_workbook() to get the live workbook (already
        imported into its namespace)
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
