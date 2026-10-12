"""agent_workspace.py - the desktop agent's local copy of a user's cloud files.

The web app stores uploads in the cloud; Excel and the file tools run on the
user's PC. Before each task the agent mirrors the user's files into
``STORAGE_DIR/<user_id>/`` under their real names (``Sales.xlsx``), so the
model, the file tools and Excel all see the same workbook. After the task,
spreadsheets the agent changed go back as new versions and spreadsheets it
created go up as new files, so they appear on the web Files page.

A manifest (``STORAGE_DIR/.sync/<user_id>.json``, outside the user's tool
root) remembers each local file's cloud id and the checksum both sides last
agreed on. That is enough to tell a cloud change from a local one:

    local == synced, cloud != synced  -> download
    local != synced, cloud == synced  -> upload (new version)
    both changed                      -> keep local as "name (conflict).ext", download cloud
    deleted in the cloud              -> remove local copy if unchanged, else keep it unsynced
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

SYNCED_TYPES = {".xlsx", ".xls", ".csv", ".ods", ".tsv"}  # what cloud storage accepts
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", Path(str(name)).name).strip(" .")
    return cleaned or "file"


def _skip(path: Path) -> bool:
    # Excel lock files (~$Book.xlsx), our temp files and hidden files never sync.
    return path.name.startswith(("~$", ".")) or path.name.endswith(".xelora-download")


class WorkspaceSync:
    def __init__(self, cloud, storage_dir: str | os.PathLike, user_id: int, log=print):
        self.cloud = cloud
        self.root = Path(storage_dir) / str(user_id)
        self.manifest_path = Path(storage_dir) / ".sync" / f"{user_id}.json"
        self.log = log
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest: dict[str, dict] = self._load()

    # manifest: {relative local path: {"id": str, "checksum": str, "detached": bool}}
    def _load(self) -> dict[str, dict]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.manifest, indent=1), encoding="utf-8")
        temporary.replace(self.manifest_path)

    def _local_name(self, file: dict, taken: set[str]) -> str:
        name = _safe_name(file.get("name") or f"file-{file['id']}")
        if name.lower() in taken:
            stem, suffix = os.path.splitext(name)
            name = f"{stem} ({file['id']}){suffix}"
        taken.add(name.lower())
        return name

    def pull(self) -> dict:
        """Bring cloud changes down. Returns counts for the task log."""
        counts = {"downloaded": 0, "removed": 0, "conflicts": 0, "skipped": 0}
        cloud_files = {str(file["id"]): file for file in self.cloud.list_files()}
        by_id = {entry["id"]: name for name, entry in self.manifest.items() if not entry.get("detached")}
        taken = {name.lower() for name in self.manifest}

        for file_id, file in cloud_files.items():
            name = by_id.get(file_id) or self._local_name(file, taken)
            path = self.root / name
            entry = self.manifest.get(name)
            local = _checksum(path) if path.exists() else None
            cloud = file.get("checksum")
            if local is not None and local == cloud:
                self.manifest[name] = {"id": file_id, "checksum": cloud}
                continue
            # A differing local file that sync has not agreed on yet is the user's work too.
            locally_changed = local is not None and (entry is None or local != entry["checksum"])
            if locally_changed:
                if entry and cloud == entry["checksum"]:
                    continue  # only changed here; push() uploads it
                conflict = path.with_name(f"{path.stem} (conflict){path.suffix}")
                try:
                    path.replace(conflict)
                except OSError:
                    counts["skipped"] += 1
                    self.log(f"sync: {name} is open in another program; kept the local version")
                    continue
                counts["conflicts"] += 1
            if self._download(file_id, path):
                self.manifest[name] = {"id": file_id, "checksum": cloud or _checksum(path)}
                counts["downloaded"] += 1
            else:
                counts["skipped"] += 1

        for name, entry in list(self.manifest.items()):
            if entry.get("detached") or entry["id"] in cloud_files:
                continue
            path = self.root / name
            if path.exists() and _checksum(path) != entry["checksum"]:
                entry["detached"] = True  # deleted in the cloud but edited here: keep, don't re-upload
                continue
            try:
                path.unlink(missing_ok=True)
                del self.manifest[name]
                counts["removed"] += 1
            except OSError:
                counts["skipped"] += 1
        self._save()
        return counts

    def _download(self, file_id: str, path: Path) -> bool:
        temporary = path.with_name(path.name + ".xelora-download")
        try:
            self.cloud.download_file(file_id, temporary)
            temporary.replace(path)
            return True
        except OSError as exc:  # usually: the workbook is open in Excel
            self.log(f"sync: could not update {path.name} ({exc}); keeping the local copy")
            temporary.unlink(missing_ok=True)
            return False

    def push(self) -> dict:
        """Send local spreadsheet changes and new spreadsheets up."""
        counts = {"uploaded": 0, "new": 0, "skipped": 0}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or _skip(path) or path.suffix.lower() not in SYNCED_TYPES:
                continue
            name = path.relative_to(self.root).as_posix()
            entry = self.manifest.get(name)
            if entry and entry.get("detached"):
                continue
            try:
                local = _checksum(path)
                if entry and local == entry["checksum"]:
                    continue
                stored = self.cloud.upload_file(path, file_id=entry["id"] if entry else None)
            except Exception as exc:  # locked by Excel, rejected by the cloud, network
                counts["skipped"] += 1
                self.log(f"sync: could not upload {name} ({exc})")
                continue
            self.manifest[name] = {"id": str(stored["id"]), "checksum": stored.get("checksum") or local}
            counts["uploaded" if entry else "new"] += 1
        self._save()
        return counts
