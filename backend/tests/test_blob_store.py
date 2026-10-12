"""Durable upload storage (blob_store.py) and the /files routes on top of it."""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("LOCAL_API_KEY", "test-api-key")

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
import blob_store  # noqa: E402
import config  # noqa: E402
import database  # noqa: E402
import files  # noqa: E402
import server  # noqa: E402
from auth import create_token  # noqa: E402

USER = 51


def _sqlite_sessions():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class BlobCase(unittest.TestCase):
    backend = "database"

    def setUp(self):
        self.Session = _sqlite_sessions()
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.storage = os.path.join(self._dir.name, "storage")
        for item in (patch.object(config, "FILE_STORAGE", self.backend),
                     patch.object(config, "S3_BUCKET", "bucket"),
                     patch.object(database, "SessionLocal", self.Session),
                     patch.object(auth, "SessionLocal", self.Session),
                     patch.object(files, "SessionLocal", self.Session),
                     patch.object(files, "STORAGE_DIR", self.storage)):
            item.start()
            self.addCleanup(item.stop)

    def write(self, name: str, data: bytes) -> str:
        path = os.path.join(self.storage, str(USER), name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        return path


class DatabaseBackendTests(BlobCase):
    def test_file_is_restored_after_local_disk_is_wiped(self):
        data = os.urandom(blob_store.CHUNK_BYTES * 2 + 123)  # spans three chunks
        path = self.write("abc.xlsx", data)
        blob_store.save(path)
        os.remove(path)
        self.assertTrue(blob_store.ensure_local(path))
        with open(path, "rb") as handle:
            self.assertEqual(data, handle.read())

    def test_saving_again_replaces_the_stored_copy(self):
        path = self.write("a.csv", b"old,data\n" * 1000)
        blob_store.save(path)
        self.write("a.csv", b"new\n")
        blob_store.save(path)
        os.remove(path)
        blob_store.ensure_local(path)
        with open(path, "rb") as handle:
            self.assertEqual(b"new\n", handle.read())

    def test_delete_removes_both_copies(self):
        path = self.write("gone.csv", b"x\n")
        blob_store.save(path)
        blob_store.delete(path)
        self.assertFalse(os.path.exists(path))
        self.assertFalse(blob_store.ensure_local(path))

    def test_key_does_not_depend_on_storage_dir(self):
        self.assertEqual("51/f.xlsx", blob_store.key_for("/tmp/a/51/f.xlsx"))
        self.assertEqual("51/f.xlsx", blob_store.key_for("/var/data/xelora/51/f.xlsx"))

    def test_database_backend_without_a_database_falls_back_to_local(self):
        with patch.object(database, "SessionLocal", None):
            self.assertEqual("local", blob_store.backend())


class FilesRouteTests(BlobCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(server.app)
        self.headers = {"Authorization": f"Bearer {create_token(USER)[0]}"}

    def test_upload_survives_a_restart_and_downloads(self):
        uploaded = self.client.post("/files", files={"upload": ("Sales.csv", b"region,total\nNorth,10\n")},
                                    headers=self.headers)
        self.assertEqual(200, uploaded.status_code, uploaded.text)
        shutil.rmtree(self.storage)  # the host restarted with an empty disk
        download = self.client.get(f"/files/{uploaded.json()['id']}/download", headers=self.headers)
        self.assertEqual(200, download.status_code, download.text)
        self.assertEqual(b"region,total\nNorth,10\n", download.content)

    def test_missing_file_is_a_clear_404(self):
        with patch.object(config, "FILE_STORAGE", "local"):
            uploaded = self.client.post("/files", files={"upload": ("A.csv", b"a\n1\n")}, headers=self.headers).json()
            shutil.rmtree(self.storage)
            response = self.client.get(f"/files/{uploaded['id']}/download", headers=self.headers)
        self.assertEqual(404, response.status_code)
        self.assertIn("Upload it again", response.json()["detail"])

    def test_storage_failure_rejects_the_upload(self):
        with patch.object(blob_store, "_db_save", side_effect=RuntimeError("db down")):
            response = self.client.post("/files", files={"upload": ("A.csv", b"a\n1\n")}, headers=self.headers)
        self.assertEqual(503, response.status_code)
        self.assertEqual([], self.client.get("/files", headers=self.headers).json()["files"])
        self.assertEqual([], os.listdir(os.path.join(self.storage, str(USER))))


class S3BackendTests(BlobCase):
    backend = "s3"

    def test_s3_calls_use_the_prefixed_key(self):
        client = MagicMock()
        with patch.object(blob_store, "_s3", return_value=client), patch.object(config, "S3_PREFIX", "xelora/"):
            path = self.write("f.xlsx", b"data")
            blob_store.save(path)
            blob_store.delete(path)
        client.upload_file.assert_called_once_with(path, "bucket", f"xelora/{USER}/f.xlsx")
        client.delete_object.assert_called_once_with(Bucket="bucket", Key=f"xelora/{USER}/f.xlsx")


if __name__ == "__main__":
    unittest.main()
