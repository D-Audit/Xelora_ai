"""Desktop agent's local mirror of the user's cloud files (agent_workspace.py)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from agent_workspace import WorkspaceSync

USER = 5


def _sum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeCloud:
    """In-memory stand-in for the /agent-link/files endpoints."""

    def __init__(self):
        self.files: dict[str, dict] = {}
        self.next_id = 1
        self.uploads: list[tuple[str, str | None]] = []

    def add(self, name: str, data: bytes) -> str:
        file_id = str(self.next_id)
        self.next_id += 1
        self.files[file_id] = {"id": file_id, "name": name, "data": data}
        return file_id

    def list_files(self):
        return [{"id": f["id"], "name": f["name"], "checksum": _sum(f["data"])} for f in self.files.values()]

    def download_file(self, file_id, destination):
        Path(destination).write_bytes(self.files[file_id]["data"])

    def upload_file(self, path, file_id=None):
        data = Path(path).read_bytes()
        self.uploads.append((Path(path).name, file_id))
        if file_id is None:
            file_id = self.add(Path(path).name, data)
        else:
            self.files[file_id]["data"] = data
        return {"id": file_id, "checksum": _sum(data)}


class WorkspaceSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cloud = FakeCloud()
        self.logs: list[str] = []

    def sync(self) -> WorkspaceSync:
        return WorkspaceSync(self.cloud, self._tmp.name, USER, log=self.logs.append)

    @property
    def root(self) -> Path:
        return Path(self._tmp.name) / str(USER)

    def test_cloud_files_arrive_under_their_real_names(self):
        self.cloud.add("Sales Q3.xlsx", b"v1")
        counts = self.sync().pull()
        self.assertEqual(1, counts["downloaded"])
        self.assertEqual(b"v1", (self.root / "Sales Q3.xlsx").read_bytes())

    def test_duplicate_names_stay_distinct(self):
        self.cloud.add("Report.csv", b"a")
        second = self.cloud.add("Report.csv", b"b")
        self.sync().pull()
        self.assertEqual(b"b", (self.root / f"Report ({second}).csv").read_bytes())

    def test_unchanged_files_are_not_downloaded_again(self):
        self.cloud.add("Budget.xlsx", b"v1")
        self.sync().pull()
        self.assertEqual(0, self.sync().pull()["downloaded"])

    def test_cloud_update_replaces_an_unchanged_local_copy(self):
        file_id = self.cloud.add("Budget.xlsx", b"v1")
        self.sync().pull()
        self.cloud.files[file_id]["data"] = b"v2"
        self.sync().pull()
        self.assertEqual(b"v2", (self.root / "Budget.xlsx").read_bytes())

    def test_local_edit_goes_up_as_a_new_version(self):
        file_id = self.cloud.add("Budget.xlsx", b"v1")
        workspace = self.sync()
        workspace.pull()
        (self.root / "Budget.xlsx").write_bytes(b"edited by Excel")
        self.assertEqual(0, workspace.pull()["downloaded"])  # the local edit is not overwritten
        counts = workspace.push()
        self.assertEqual(1, counts["uploaded"])
        self.assertEqual([("Budget.xlsx", file_id)], self.cloud.uploads)
        self.assertEqual(b"edited by Excel", self.cloud.files[file_id]["data"])
        self.assertEqual(0, sum(self.sync().push().values()))  # now in agreement

    def test_new_spreadsheet_goes_up_as_a_new_file(self):
        workspace = self.sync()
        workspace.pull()
        (self.root / "Forecast.xlsx").write_bytes(b"new")
        (self.root / "notes.md").write_text("not a spreadsheet")
        (self.root / "~$Forecast.xlsx").write_bytes(b"excel lock file")
        counts = workspace.push()
        self.assertEqual(1, counts["new"])
        self.assertEqual([("Forecast.xlsx", None)], self.cloud.uploads)

    def test_both_sides_changed_keeps_the_local_work(self):
        file_id = self.cloud.add("Plan.xlsx", b"v1")
        self.sync().pull()
        (self.root / "Plan.xlsx").write_bytes(b"local edit")
        self.cloud.files[file_id]["data"] = b"cloud edit"
        counts = self.sync().pull()
        self.assertEqual(1, counts["conflicts"])
        self.assertEqual(b"cloud edit", (self.root / "Plan.xlsx").read_bytes())
        self.assertEqual(b"local edit", (self.root / "Plan (conflict).xlsx").read_bytes())

    def test_unsynced_local_file_with_a_cloud_name_is_not_overwritten(self):
        self.root.mkdir(parents=True)
        (self.root / "Sales.xlsx").write_bytes(b"made on this PC")
        self.cloud.add("Sales.xlsx", b"from the web")
        self.sync().pull()
        self.assertEqual(b"made on this PC", (self.root / "Sales (conflict).xlsx").read_bytes())
        self.assertEqual(b"from the web", (self.root / "Sales.xlsx").read_bytes())

    def test_cloud_deletion_removes_only_unchanged_copies(self):
        keep = self.cloud.add("Edited.xlsx", b"v1")
        drop = self.cloud.add("Untouched.xlsx", b"v1")
        workspace = self.sync()
        workspace.pull()
        (self.root / "Edited.xlsx").write_bytes(b"local work")
        del self.cloud.files[keep], self.cloud.files[drop]
        counts = workspace.pull()
        self.assertEqual(1, counts["removed"])
        self.assertFalse((self.root / "Untouched.xlsx").exists())
        self.assertTrue((self.root / "Edited.xlsx").exists())
        self.assertEqual(0, sum(workspace.push().values()))  # deleted on the web: not resurrected

    def test_manifest_lives_outside_the_file_tools_root(self):
        self.cloud.add("A.csv", b"x")
        self.sync().pull()
        self.assertEqual(["A.csv"], sorted(path.name for path in self.root.iterdir()))


if __name__ == "__main__":
    unittest.main()
