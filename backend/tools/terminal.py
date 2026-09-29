"""Constrained local terminal inspection for authenticated Xelora tasks.

This deliberately does not run a shell. It permits a small read-only command
set, passes argv directly to subprocess, anchors paths to one configured root,
and caps runtime/output. Mutating commands remain unavailable unless the
administrator explicitly extends the policy with TERMINAL_WRITE_TOOLS.

The allowlist is intentionally argv-shape based, not free-form: every accepted
invocation is enumerated here and reviewed in tests. `git push`, package
installation, file deletion, and chained/shell-interpreted input never pass.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.mcp_client import scrubbed_environment

import logging

_LOGGER = logging.getLogger(__name__)

_MAX_TIMEOUT = 120
_MAX_OUTPUT = 20_000
_MAX_ARGV = 64
_MAX_ARG_LENGTH = 4_000

# Windows resolves `git` to git.exe / git.cmd and `python` to python.exe, and
# its `where`/`dir` differ from POSIX `which`/`ls`. Resolution is delegated to
# subprocess with shell=False, which handles PATHEXT correctly on Windows; the
# policy below matches executable *names* only, never paths, so both platforms
# behave the same.
_WINDOWS_EXE_SUFFIXES = (".exe", ".cmd", ".bat")
# Commands answered in-process so they behave identically on Windows, where
# `pwd`/`ls` do not exist and `dir` is a cmd.exe builtin.
_IN_PROCESS = {"pwd", "ls", "dir"}
# Batch files run through cmd.exe even with shell=False, which re-parses
# arguments; only plain tokens may reach one.
_BATCH_SAFE_ARG = re.compile(r"^[A-Za-z0-9._/\\:=-]*$")


def _versionish(args: list[str]) -> bool:
    return args == ["--version"] or args == ["-V"]


def _workspace_root() -> Path:
    configured = os.getenv("XELORA_TERMINAL_ROOT", "").strip()
    if not configured:
        raise PermissionError("Terminal tools require XELORA_TERMINAL_ROOT to be configured by the administrator.")
    root = Path(configured).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise PermissionError("XELORA_TERMINAL_ROOT must point to a directory.")
    return root


def _write_tools_enabled() -> bool:
    if os.getenv("TERMINAL_WRITE_TOOLS", "").strip().lower() in {"1", "true", "yes"}:
        return True
    try:
        import config
        return bool(config.TERMINAL_WRITE_TOOLS)
    except Exception:
        return False


def _default_timeout() -> int:
    try:
        import config
        return int(config.TERMINAL_TIMEOUT_SECONDS)
    except Exception:
        return 30


def _exe_name(argv0: str) -> str:
    """Return the bare, lower-case executable name with any Windows suffix removed."""
    name = Path(argv0).name.lower()
    for suffix in _WINDOWS_EXE_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


def _command_policy(argv: list[str], root: Path) -> tuple[bool, str, str]:
    """Decide whether argv is allowed. Returns (allowed, reason, risk)."""
    if not argv:
        return False, "Provide a command.", "read"
    if len(argv) > _MAX_ARGV or any(len(arg) > _MAX_ARG_LENGTH for arg in argv):
        return False, "Command is too large for the terminal policy.", "read"
    if "/" in argv[0] or "\\" in argv[0]:
        # The allowlist names programs, never paths: `/tmp/x/git` is not git.
        return False, "Give the program name only (e.g. git), not a path.", "read"
    if any("\x00" in arg for arg in argv):
        return False, "Arguments may not contain NUL bytes.", "read"

    exe = _exe_name(argv[0])
    args = argv[1:]

    if exe in {"pwd", "whoami"}:
        if not args:
            return True, "", "read"
        return False, "This command takes no arguments.", "read"

    if exe in {"python", "python3", "node", "npm", "pytest", "pip", "pip3"}:
        if _versionish(args):
            return True, "", "read"
        if exe in {"pip", "pip3"} and len(args) == 2 and args[0] == "show" and args[1].replace("-", "").replace("_", "").isalnum():
            return True, "", "read"
    if exe == "git":
        if _versionish(args):
            return True, "", "read"
        if args in (["status"], ["status", "--short"], ["diff", "--stat"], ["branch", "--show-current"]):
            return True, "", "read"
        if len(args) >= 1 and args[0] == "log" and all(
            a in {"--oneline", "--decorate"} or a.startswith("-n") or a.isdigit() for a in args[1:]
        ):
            return True, "", "read"
        if len(args) == 2 and args[0] == "diff" and not args[1].startswith("-"):
            candidate = (root / args[1]).resolve()
            try:
                candidate.relative_to(root)
                return True, "", "read"
            except ValueError:
                return False, "Git diff path must stay inside the configured workspace.", "read"
    if exe in {"ls", "dir"} and len(args) <= 2 and all(not a.startswith("-") or a in {"-a", "-l", "-la", "-al"} for a in args):
        paths = [arg for arg in args if not arg.startswith("-")]
        if paths:
            candidate = (root / paths[0]).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                return False, "Directory path must stay inside the configured workspace.", "read"
        return True, "", "read"

    # Administrator-extended, still bounded write commands (e.g. project setup).
    if _write_tools_enabled():
        decision = _write_command_policy(exe, args, root)
        if decision is not None:
            return decision

    return False, "Command is outside the read-only terminal allowlist. Mutating or arbitrary commands are blocked.", "read"


def _write_command_policy(exe: str, args: list[str], root: Path) -> tuple[bool, str, str] | None:
    """Bounded, opt-in write commands for project setup inside the workspace root.

    Returns None when the command is not covered, so the read-only verdict
    applies. Every entry here requires TERMINAL_WRITE_TOOLS=true *and* stays
    anchored to the workspace root.
    """
    if exe in {"pip", "pip3"} and len(args) >= 2 and args[0] == "install":
        for flag in ("-r", "--requirement"):
            if flag in args[1:]:
                requirement = args[args.index(flag) + 1] if args.index(flag) + 1 < len(args) else ""
                candidate = (root / requirement).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    return False, "Requirements file must stay inside the configured workspace.", "write"
        if any(arg.startswith("-e") for arg in args[1:]):
            return False, "Editable installs are not permitted by the terminal policy.", "write"
        return True, "", "write"
    if exe == "python" and len(args) >= 2 and args[0] == "-m" and args[1] == "pip" and len(args) >= 4 and args[2] == "install":
        return True, "", "write"
    if exe == "pytest" and args and all(not a.startswith("-") for a in args):
        candidate = (root / args[0]).resolve()
        try:
            candidate.relative_to(root)
            return True, "", "write"
        except ValueError:
            return False, "Test path must stay inside the configured workspace.", "write"
    return None


def _resolve_executable(argv0: str) -> tuple[str | None, str]:
    """Resolve an allowlisted program name on PATH (PATHEXT-aware on Windows)."""
    resolved = shutil.which(_exe_name(argv0))
    if resolved is None:
        return None, f"'{_exe_name(argv0)}' is not installed or not on PATH."
    return resolved, ""


def _in_process(exe: str, args: list[str], workdir: Path, root: Path) -> dict[str, Any]:
    if exe == "pwd":
        stdout = str(workdir) + "\n"
    else:
        paths = [arg for arg in args if not arg.startswith("-")]
        target = (workdir / paths[0]).resolve() if paths else workdir
        try:
            target.relative_to(root)
        except ValueError:
            return {"status": "permission_denied", "verified": False, "error": "Directory path must stay inside the configured workspace."}
        if not target.is_dir():
            return {"status": "command_failed", "verified": True, "succeeded": False, "exit_code": 1,
                    "stdout": "", "stderr": f"{target.name}: not a directory", "verification_note": "Command exited non-zero (1); treat this as a failure."}
        show_hidden = any(flag in {"-a", "-la", "-al"} for flag in args)
        names = sorted(
            (item.name + ("/" if item.is_dir() else "") for item in target.iterdir()
             if show_hidden or not item.name.startswith(".")),
            key=str.lower,
        )
        stdout = "\n".join(names[:2000]) + ("\n" if names else "")
    return {"status": "success", "verified": True, "succeeded": True, "exit_code": 0, "cwd": str(workdir),
            "stdout": stdout[-_MAX_OUTPUT:], "stderr": "", "truncated": len(stdout) > _MAX_OUTPUT,
            "risk": "read", "verification_note": "Answered in-process by Xelora (portable across Windows/macOS/Linux)."}


def run_terminal(argv: list[str] | str, cwd: str = ".", timeout_seconds: int | None = None) -> dict[str, Any]:
    """Run one allowlisted, policy-checked command without shell interpretation."""
    if isinstance(argv, str):
        try:
            argv = shlex.split(argv, posix=os.name != "nt")
        except ValueError as exc:
            return {"status": "invalid_arguments", "verified": False, "error": str(exc)}
    if not isinstance(argv, list) or not all(isinstance(item, str) and item for item in argv):
        return {"status": "invalid_arguments", "verified": False, "error": "argv must be a list of non-empty strings."}
    try:
        root = _workspace_root()
    except (OSError, PermissionError) as exc:
        return {"status": "workspace_not_configured", "verified": False, "error": str(exc)}
    allowed, reason, risk = _command_policy(argv, root)
    if not allowed:
        return {"status": "permission_denied", "verified": False, "risk": risk, "error": reason}
    try:
        workdir = (root / cwd).resolve(strict=True)
        workdir.relative_to(root)
        if not workdir.is_dir():
            raise NotADirectoryError(cwd)
    except (OSError, ValueError, PermissionError) as exc:
        return {"status": "invalid_working_directory", "verified": False, "error": str(exc)}

    exe = _exe_name(argv[0])
    if exe in _IN_PROCESS:
        return _in_process(exe, argv[1:], workdir, root)
    executable, missing = _resolve_executable(argv[0])
    if executable is None:
        return {"status": "execution_error", "verified": False, "error": missing}
    if executable.lower().endswith((".bat", ".cmd")) and not all(_BATCH_SAFE_ARG.match(arg) for arg in argv[1:]):
        return {"status": "permission_denied", "verified": False,
                "error": "This program is a batch script; its arguments may only contain letters, digits, and . _ / \\ : = -."}

    try:
        limit = max(1, min(int(timeout_seconds if timeout_seconds is not None else _default_timeout()), _MAX_TIMEOUT))
    except (TypeError, ValueError):
        limit = _default_timeout()
    started = time.monotonic()
    audit_argv = " ".join(argv)[:300]
    try:
        completed = subprocess.run(
            [executable, *argv[1:]], cwd=workdir, shell=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=limit, check=False, stdin=subprocess.DEVNULL,
            # Provider keys, database URLs and tokens never reach a child process.
            env=scrubbed_environment({"GIT_TERMINAL_PROMPT": "0", "PIP_NO_INPUT": "1", "PYTHONUNBUFFERED": "1"}),
        )
    except subprocess.TimeoutExpired as exc:
        _LOGGER.info("terminal timeout argv=%s after %ss", audit_argv, limit)
        def _text(value: Any) -> str:
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")
        return {"status": "timeout", "verified": False, "timed_out": True, "risk": risk,
                "stdout": _text(exc.stdout)[-_MAX_OUTPUT:], "stderr": _text(exc.stderr)[-_MAX_OUTPUT:],
                "duration_seconds": round(time.monotonic() - started, 3), "error": f"Command exceeded {limit} seconds."}
    except OSError as exc:
        return {"status": "execution_error", "verified": False, "error": str(exc)}

    stdout, stderr = completed.stdout or "", completed.stderr or ""
    exit_code = completed.returncode
    _LOGGER.info("terminal ran argv=%s exit=%s risk=%s", audit_argv, exit_code, risk)
    return {
        "status": "success" if exit_code == 0 else "command_failed",
        # The observation (exit code + output) is sound either way; whether the
        # command succeeded is `succeeded`, never implied by `verified`.
        "verified": True,
        "succeeded": exit_code == 0,
        "argv": argv,
        "cwd": str(workdir),
        "exit_code": exit_code,
        "stdout": stdout[-_MAX_OUTPUT:],
        "stderr": stderr[-_MAX_OUTPUT:],
        "truncated": len(stdout) > _MAX_OUTPUT or len(stderr) > _MAX_OUTPUT,
        "duration_seconds": round(time.monotonic() - started, 3),
        "risk": risk,
        "verification_note": (
            f"Exit code {exit_code} captured. Confirm any expected artifact with the file tools."
            if exit_code == 0 else f"Command exited non-zero ({exit_code}); treat this as a failure."
        ),
    }
