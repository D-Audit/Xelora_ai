"""
files.py
ADDITIVE ONLY. File upload/list/download/delete for a user's
spreadsheets. Storage is local disk under ./storage/{user_id}/ by
default (STORAGE_DIR env var to change it) - fine for a single-server
deployment; swap for S3/GCS later without touching the frontend, since
the frontend only ever talks to /files, never to disk paths directly.
"""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from workspace_models import FileAsset

STORAGE_DIR = os.getenv("STORAGE_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "100"))

router = APIRouter(prefix="/files", tags=["files"])


def _user_dir(user_id: int) -> str:
    path = os.path.join(STORAGE_DIR, str(user_id))
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not create storage folder at {path} ({e.strerror or e}). Check STORAGE_DIR permissions.",
        )
    return path


def _serialize(f: FileAsset) -> dict:
    return {
        "id": str(f.id),
        "name": f.name,
        "type": f.file_type,
        "sizeMB": round(f.size_mb, 3),
        "status": f.status,
        "rowCount": f.row_count,
        "columnCount": f.column_count,
        "tags": f.tags or [],
        "uploadedAt": f.uploaded_at.isoformat() if f.uploaded_at else None,
        "lastModifiedAt": f.last_modified_at.isoformat() if f.last_modified_at else None,
    }


@router.get("")
def list_files(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    files = db.query(FileAsset).filter(FileAsset.user_id == user_id).order_by(FileAsset.uploaded_at.desc()).all()
    return {"files": [_serialize(f) for f in files]}


@router.post("")
async def upload_file(
    upload: UploadFile = FastAPIFile(...),
    user_id: int = Depends(get_current_user_id),
    db: Session | None = Depends(get_db_or_503),
):
    db = _require_db(db)

    ext = (upload.filename or "").rsplit(".", 1)[-1].lower() if "." in (upload.filename or "") else "xlsx"
    if ext not in ("xlsx", "xls", "csv", "ods", "tsv"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    contents = await upload.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_MB}MB upload limit.")

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(_user_dir(user_id), stored_name)
    try:
        with open(dest, "wb") as out:
            out.write(contents)
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save the file to disk ({e.strerror or e}). Check that {STORAGE_DIR} is writable.",
        )

    record = FileAsset(
        user_id=user_id,
        name=upload.filename or stored_name,
        file_type=ext,
        size_mb=size_mb,
        status="ready",
        storage_path=dest,
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=500, detail="Could not save file metadata. The upload was not completed.")
    db.refresh(record)
    return _serialize(record)


@router.get("/{file_id}/download")
def download_file(file_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    f = db.query(FileAsset).filter(FileAsset.id == file_id, FileAsset.user_id == user_id).first()
    if not f or not os.path.exists(f.storage_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(f.storage_path, filename=f.name)


@router.delete("/{file_id}")
def delete_file(file_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    f = db.query(FileAsset).filter(FileAsset.id == file_id, FileAsset.user_id == user_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found.")
    if os.path.exists(f.storage_path):
        try:
            os.remove(f.storage_path)
        except OSError:
            pass
    db.delete(f)
    db.commit()
    return {"deleted": True}
