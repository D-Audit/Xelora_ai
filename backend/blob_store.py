"""Durable storage for uploaded file contents (files.py).

files.py always works with a local path under ``STORAGE_DIR/<user_id>/``
(parsing, downloads). On hosts whose disk is wiped on restart (Render's free
tier), that disk is only a cache: every stored file is also saved to a
durable backend chosen by ``FILE_STORAGE``, and brought back on demand.

- ``local``    the disk is the store (single PC, paid host with a disk)
- ``database`` file bytes in Postgres, in 1 MB chunks (no extra service)
- ``s3``       an S3-compatible bucket: AWS S3, Cloudflare R2, Backblaze, ...

Objects are keyed ``<user_id>/<stored name>``, the last two parts of the
local path, so the key does not depend on where STORAGE_DIR points.
"""
from __future__ import annotations

import logging
import os
from contextlib import suppress
from pathlib import Path

from sqlalchemy import Column, Integer, LargeBinary, String, UniqueConstraint

import config
import database
from database import Base

logger = logging.getLogger(__name__)
CHUNK_BYTES = 1024 * 1024


class FileBlobChunk(Base):
    __tablename__ = "file_blob_chunks"
    __table_args__ = (UniqueConstraint("key", "seq", name="uq_file_blob_chunk"),)

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)


class BlobStoreError(RuntimeError):
    pass


def backend() -> str:
    name = config.FILE_STORAGE
    if name == "database" and database.SessionLocal is None:
        logger.warning("FILE_STORAGE=database needs DATABASE_URL; keeping files on local disk only")
        return "local"
    if name == "s3" and not config.S3_BUCKET:
        logger.warning("FILE_STORAGE=s3 needs S3_BUCKET; keeping files on local disk only")
        return "local"
    return name if name in {"database", "s3"} else "local"


def key_for(path: str | os.PathLike) -> str:
    parts = Path(path).parts
    return "/".join(parts[-2:])


# ── database backend ────────────────────────────────────────────────────────

def _db_save(key: str, path: str) -> None:
    db = database.SessionLocal()
    try:
        db.query(FileBlobChunk).filter(FileBlobChunk.key == key).delete(synchronize_session=False)
        with open(path, "rb") as source:
            seq = 0
            while chunk := source.read(CHUNK_BYTES):
                db.add(FileBlobChunk(key=key, seq=seq, data=chunk))
                db.flush()  # one chunk in memory at a time
                db.expunge_all()
                seq += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _db_load(key: str, destination: str) -> bool:
    db = database.SessionLocal()
    try:
        seqs = [seq for (seq,) in db.query(FileBlobChunk.seq).filter(FileBlobChunk.key == key).order_by(FileBlobChunk.seq)]
        if not seqs:
            return False
        with open(destination, "wb") as target:
            for seq in seqs:
                (data,) = db.query(FileBlobChunk.data).filter(FileBlobChunk.key == key, FileBlobChunk.seq == seq).one()
                target.write(data)
        return True
    finally:
        db.close()


def _db_delete(key: str) -> None:
    db = database.SessionLocal()
    try:
        db.query(FileBlobChunk).filter(FileBlobChunk.key == key).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ── S3 backend ──────────────────────────────────────────────────────────────

_s3_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        try:
            import boto3
        except ImportError as error:
            raise BlobStoreError("FILE_STORAGE=s3 needs the boto3 package (pip install boto3).") from error
        _s3_client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT_URL or None,
            region_name=config.S3_REGION or None,
            aws_access_key_id=config.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=config.S3_SECRET_ACCESS_KEY or None,
        )
    return _s3_client


def _s3_key(key: str) -> str:
    return f"{config.S3_PREFIX}{key}"


def _s3_load(key: str, destination: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        _s3().download_file(config.S3_BUCKET, _s3_key(key), destination)
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


# ── public API ──────────────────────────────────────────────────────────────

def save(path: str) -> None:
    """Persist a file that was just written at ``path``. Raises BlobStoreError on failure."""
    kind = backend()
    if kind == "local":
        return
    try:
        if kind == "database":
            _db_save(key_for(path), path)
        else:
            _s3().upload_file(path, config.S3_BUCKET, _s3_key(key_for(path)))
    except BlobStoreError:
        raise
    except Exception as error:
        logger.exception("blob_save_failed backend=%s key=%s", kind, key_for(path))
        raise BlobStoreError(f"Could not save the file to {kind} storage.") from error


def ensure_local(path: str) -> bool:
    """Make sure ``path`` exists on local disk, restoring it from the durable store if needed."""
    if os.path.exists(path):
        return True
    kind = backend()
    if kind == "local":
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.restoring"
    try:
        found = _db_load(key_for(path), temporary) if kind == "database" else _s3_load(key_for(path), temporary)
        if found:
            os.replace(temporary, path)
            return True
        return False
    except Exception:
        logger.exception("blob_restore_failed backend=%s key=%s", kind, key_for(path))
        return False
    finally:
        with suppress(OSError):
            os.remove(temporary)


def delete(path: str) -> None:
    """Remove the local copy and the durable object. Never raises."""
    with suppress(OSError):
        os.remove(path)
    kind = backend()
    try:
        if kind == "database":
            _db_delete(key_for(path))
        elif kind == "s3":
            _s3().delete_object(Bucket=config.S3_BUCKET, Key=_s3_key(key_for(path)))
    except Exception:
        logger.exception("blob_delete_failed backend=%s key=%s", kind, key_for(path))
