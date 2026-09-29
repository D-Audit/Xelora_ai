"""Per-user workspace files for Xelora agent tasks.

This is separate from the upload API: uploads own persistence and metadata,
while these functions provide a strictly bounded agent view of that user's
stored artifacts under ``STORAGE_DIR/<user_id>`` (the same root the upload
API uses). Reads, search, metadata, create-without-overwrite, and atomic
update of bounded text files are supported. No absolute path, traversal,
symlink escape, move, or delete is permitted here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import logging

_LOGGER = logging.getLogger(__name__)

_MAX_READ_BYTES = 1_000_000
_MAX_LIST_FILES = 200
_TEXT_EXTENSIONS = {".csv", ".tsv", ".txt", ".json", ".md", ".py", ".log", ".xml", ".html"}


def _storage_root() -> Path:
    # Reuse the upload API's configured storage root. Maintaining a second
    # environment variable here would make uploaded assets invisible to the
    # agent whenever STORAGE_DIR is customized.
    try:
        from files import STORAGE_DIR
        configured = STORAGE_DIR
    except Exception:
        configured = os.getenv("STORAGE_DIR") or str(Path(__file__).resolve().parents[1] / "storage")
    return Path(configured).resolve()


def _user_root(user_id: int | None) -> Path:
    if user_id is None:
        raise PermissionError("File tools require an authenticated Xelora user.")
    root = (_storage_root() / str(user_id)).resolve()
    try:
        root.relative_to(_storage_root())
    except ValueError as exc:
        raise PermissionError("The requested user file root is invalid.") from exc
    return root


def _resolve_user_path(user_id: int | None, path: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty relative path.")
    root = _user_root(user_id)
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Path escapes this user's Xelora storage.") from exc
    return candidate


def _upload_display_names(user_id: int | None) -> dict[str, str]:
    """Map stored upload file names (UUIDs) to the names the user uploaded.

    Best effort: without a database the listing still works, just without
    friendly names.
    """
    try:
        from database import SessionLocal
        from workspace_models import FileAsset
        if SessionLocal is None:
            return {}
        db = SessionLocal()
        try:
            rows = db.query(FileAsset.storage_path, FileAsset.name).filter(FileAsset.user_id == user_id).limit(1000).all()
        finally:
            db.close()
        return {Path(str(storage_path)).name: str(name) for storage_path, name in rows if storage_path}
    except Exception:
        return {}


def list_workspace_files(user_id: int | None, path: str = ".") -> dict[str, Any]:
    """List a bounded directory within the current user's Xelora storage."""
    target = _resolve_user_path(user_id, path)
    if not target.exists() and target == _user_root(user_id):
        return {"path": ".", "entries": [], "truncated": False, "verified": True,
                "note": "This user has no stored files yet. Upload a file in Xelora first."}
    if not target.exists():
        return {"verified": False, "error": "Directory does not exist."}
    if not target.is_dir():
        return {"verified": False, "error": "path is not a directory."}
    root = _user_root(user_id)
    display_names = _upload_display_names(user_id)
    entries = []
    for item in sorted(target.iterdir(), key=lambda entry: entry.name.lower())[:_MAX_LIST_FILES]:
        if item.is_symlink() or item.name.endswith((".uploading", ".xelora.tmp")):
            continue
        entry = {
            "path": str(item.relative_to(root)),
            "type": "directory" if item.is_dir() else "file",
            "size_bytes": item.stat().st_size if item.is_file() else None,
        }
        if item.name in display_names:
            entry["uploaded_as"] = display_names[item.name]
        entries.append(entry)
    return {
        "path": str(target.relative_to(root)) or ".",
        "entries": entries,
        "truncated": len(list(target.iterdir())) > _MAX_LIST_FILES,
        "verified": True,
    }


def read_workspace_file(user_id: int | None, path: str, max_chars: int = 20_000) -> dict[str, Any]:
    """Read bounded text from one file in the current user's Xelora storage."""
    target = _resolve_user_path(user_id, path)
    if target.is_symlink() or not target.is_file():
        return {"verified": False, "error": "path is not a readable regular file."}
    if target.suffix.lower() not in _TEXT_EXTENSIONS:
        return {"verified": False, "error": "This file type is not readable as text by the agent."}
    if target.stat().st_size > _MAX_READ_BYTES:
        return {"verified": False, "error": "File exceeds the 1 MB agent read limit."}
    cap = max(1, min(int(max_chars), 100_000)) if isinstance(max_chars, int) else 20_000
    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(target.relative_to(_user_root(user_id))),
        "text": text[:cap],
        "truncated": len(text) > cap,
        "verified": True,
    }


_MAX_SEARCH_FILES = 500
_MAX_SEARCH_MATCHES = 200


def _safe_existing_path(user_id: int | None, path: str) -> tuple[Path, Path]:
    """Resolve an existing user file while rejecting absolute paths and symlinks."""
    from pathlib import PureWindowsPath

    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty relative path.")
    normalized = path.replace("\\", "/")
    if Path(normalized).is_absolute() or PureWindowsPath(path).is_absolute() or PureWindowsPath(path).drive:
        raise PermissionError("Only relative paths inside this user's storage are allowed.")
    root = _user_root(user_id)
    lexical = root.joinpath(*[part for part in normalized.split("/") if part not in {"", "."}])
    cursor = root
    for part in lexical.relative_to(root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PermissionError("Symlink paths are not available to agent file tools.")
    target = lexical.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Path escapes this user's Xelora storage.") from exc
    return root, target


def search_workspace_files(user_id: int | None, query: str, path: str = ".", max_results: int = 50) -> dict[str, Any]:
    """Search bounded text files within the authenticated user's storage."""
    if not isinstance(query, str) or not query.strip():
        return {"verified": False, "error": "query must be a non-empty string."}
    root, base = _safe_existing_path(user_id, path)
    if not base.is_dir():
        return {"verified": False, "error": "path is not a directory."}
    cap = max(1, min(int(max_results), _MAX_SEARCH_MATCHES))
    matches = []
    files_scanned = 0
    for candidate in base.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower() not in _TEXT_EXTENSIONS:
            continue
        files_scanned += 1
        if files_scanned > _MAX_SEARCH_FILES:
            break
        if candidate.stat().st_size > _MAX_READ_BYTES:
            continue
        try:
            with candidate.open("r", encoding="utf-8", errors="replace") as source:
                for line_number, line in enumerate(source, 1):
                    if query.casefold() in line.casefold():
                        matches.append({"path": str(candidate.relative_to(root)), "line": line_number, "text": line.strip()[:500]})
                        if len(matches) >= cap:
                            return {"query": query, "matches": matches, "files_scanned": files_scanned, "truncated": True, "verified": True}
        except OSError:
            continue
    return {"query": query, "matches": matches, "files_scanned": files_scanned, "truncated": files_scanned > _MAX_SEARCH_FILES, "verified": True}


def get_workspace_file_metadata(user_id: int | None, path: str) -> dict[str, Any]:
    """Return metadata for one file contained in the authenticated user's storage."""
    root, target = _safe_existing_path(user_id, path)
    if not target.is_file():
        return {"verified": False, "error": "path is not a regular file."}
    stat = target.stat()
    return {"path": str(target.relative_to(root)), "size_bytes": stat.st_size, "modified_time": stat.st_mtime, "extension": target.suffix.lower(), "verified": True}


def create_workspace_file(user_id: int | None, path: str, content: str) -> dict[str, Any]:
    """Create a new bounded text file; existing files are never overwritten."""
    if not isinstance(content, str):
        return {"verified": False, "error": "content must be text."}
    if len(content.encode("utf-8")) > _MAX_READ_BYTES:
        return {"verified": False, "error": "File exceeds the 1 MB agent write limit."}
    from pathlib import PureWindowsPath
    normalized = path.replace("\\", "/") if isinstance(path, str) else ""
    if not normalized or Path(normalized).is_absolute() or PureWindowsPath(str(path)).is_absolute() or PureWindowsPath(str(path)).drive:
        raise PermissionError("Only relative paths inside this user's storage are allowed.")
    if ".." in normalized.split("/"):
        raise PermissionError("Path escapes this user's Xelora storage.")
    if Path(normalized).suffix.lower() not in _TEXT_EXTENSIONS:
        return {"verified": False, "error": "This file type is not writable as text by the agent."}
    root = _user_root(user_id)
    target = root.joinpath(*[part for part in normalized.split("/") if part not in {"", "."}])
    try:
        target.resolve().relative_to(root)
    except ValueError as exc:
        raise PermissionError("Path escapes this user's Xelora storage.") from exc
    parent = target.parent
    cursor = root
    for part in parent.relative_to(root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PermissionError("Symlink paths are not available to agent file tools.")
    parent.resolve().relative_to(root)
    parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8", newline="") as destination:
            destination.write(content)
    except FileExistsError:
        return {"verified": False, "error": "File already exists; create will not overwrite it."}
    except OSError as exc:
        return {"verified": False, "error": f"Could not create file: {exc}"}
    actual = target.read_text(encoding="utf-8", errors="replace")
    verified = actual == content
    _LOGGER.info("Agent created user file user_id=%s path=%s bytes=%s", user_id, target.relative_to(root), target.stat().st_size)
    return {"path": str(target.relative_to(root)), "bytes_written": target.stat().st_size, "verified": verified, "verification_note": "Read back newly created file content." if verified else "Read-back content differs."}


def update_workspace_file(user_id: int | None, path: str, content: str) -> dict[str, Any]:
    """Replace a bounded existing text file inside the user's storage."""
    if not isinstance(content, str):
        return {"verified": False, "error": "content must be text."}
    if len(content.encode("utf-8")) > _MAX_READ_BYTES:
        return {"verified": False, "error": "File exceeds the 1 MB agent write limit."}
    root, target = _safe_existing_path(user_id, path)
    if not target.is_file() or target.suffix.lower() not in _TEXT_EXTENSIONS:
        return {"verified": False, "error": "path is not a supported text file."}
    if target.stat().st_size > _MAX_READ_BYTES:
        return {"verified": False, "error": "Existing file exceeds the 1 MB update limit."}
    temporary = target.with_name(f".{target.name}.xelora.tmp")
    try:
        if temporary.is_symlink():
            raise PermissionError("Symlink paths are not available to agent file tools.")
        # A stale temp file can only come from an interrupted earlier update
        # by this same tool; it never holds user data, so replace it.
        temporary.unlink(missing_ok=True)
        with temporary.open("x", encoding="utf-8", newline="") as destination:
            destination.write(content)
        os.replace(temporary, target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        return {"verified": False, "error": f"Could not update file: {exc}"}
    actual = target.read_text(encoding="utf-8", errors="replace")
    verified = actual == content
    _LOGGER.info("Agent updated user file user_id=%s path=%s bytes=%s", user_id, target.relative_to(root), target.stat().st_size)
    return {"path": str(target.relative_to(root)), "bytes_written": target.stat().st_size, "verified": verified, "verification_note": "Read back updated file content." if verified else "Read-back content differs."}
