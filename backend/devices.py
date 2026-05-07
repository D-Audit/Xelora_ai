"""devices.py - ADDITIVE ONLY. Lets a user see/revoke devices
authorised to run the desktop agent under their account. The web app
registers a "Web browser" pseudo-device on first login so the page
isn't empty; a real desktop build would call POST /devices itself on
first run with its actual OS/version."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from workspace_models import Device

router = APIRouter(prefix="/devices", tags=["devices"])


class RegisterDeviceRequest(BaseModel):
    name: str
    os: str = "windows"
    app_version: str = ""
    region: str = ""


def _serialize(d: Device) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "os": d.os,
        "appVersion": d.app_version,
        "region": d.region,
        "status": d.status,
        "isPrimary": d.is_primary,
        "authorisedAt": d.authorised_at.isoformat() if d.authorised_at else None,
        "lastActiveAt": d.last_active_at.isoformat() if d.last_active_at else None,
    }


@router.get("")
def list_devices(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    devices = db.query(Device).filter(Device.user_id == user_id, Device.status != "removed").all()
    return {"devices": [_serialize(d) for d in devices]}


@router.post("")
def register_device(req: RegisterDeviceRequest, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    existing_count = db.query(Device).filter(Device.user_id == user_id, Device.status != "removed").count()
    device = Device(
        user_id=user_id,
        name=req.name,
        os=req.os,
        app_version=req.app_version,
        region=req.region,
        status="active",
        is_primary=(existing_count == 0),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return _serialize(device)


@router.delete("/{device_id}")
def remove_device(device_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    device = db.query(Device).filter(Device.id == device_id, Device.user_id == user_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")
    device.status = "removed"
    db.commit()
    return {"removed": True}
