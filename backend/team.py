"""team.py - ADDITIVE ONLY. Single-owner-team model: the logged-in
user is the "owner", and can invite members by email. If an invitee
later registers with that exact email, they're auto-linked
(member_user_id set) - see auth.py's register() hook below, which
this module does NOT modify (the link-on-register check lives in
auth.py's register endpoint would require editing auth.py again; to
avoid coupling, linking instead happens lazily the next time this
router's list_team endpoint runs, by matching on email)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import get_current_user_id, get_db_or_503, _require_db
from models import User
from workspace_models import TeamMember
from plan_catalog import get_plan
from auth_billing_models import Subscription

router = APIRouter(prefix="/team", tags=["team"])

0
class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"
    name: str | None = None


class UpdateRoleRequest(BaseModel):
    role: str


def _serialize(m: TeamMember) -> dict:
    return {
        "id": str(m.id),
        "email": m.email,
        "name": m.name,
        "role": m.role,
        "status": m.status,
        "invitedAt": m.invited_at.isoformat() if m.invited_at else None,
        "joinedAt": m.joined_at.isoformat() if m.joined_at else None,
        "lastActiveAt": m.last_active_at.isoformat() if m.last_active_at else None,
    }


def _relink_pending_members(db: Session, owner_id: int) -> None:
    """Lazily link any invited-but-unlinked members whose email now
    matches a registered user - runs on every list call, cheap at this
    scale."""
    pending = (
        db.query(TeamMember)
        .filter(TeamMember.owner_user_id == owner_id, TeamMember.member_user_id.is_(None), TeamMember.status == "invited")
        .all()
    )
    if not pending:
        return
    changed = False
    for member in pending:
        matched = db.query(User).filter(User.email.ilike(member.email)).first()
        if matched:
            member.member_user_id = matched.id
            member.status = "active"
            member.joined_at = datetime.now(timezone.utc)
            changed = True
    if changed:
        db.commit()


@router.get("")
def list_team(user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    _relink_pending_members(db, user_id)
    members = db.query(TeamMember).filter(TeamMember.owner_user_id == user_id).order_by(TeamMember.invited_at.desc()).all()
    return {"members": [_serialize(m) for m in members]}


@router.post("/invite")
def invite_member(req: InviteRequest, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)

    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    plan = get_plan(sub.plan_tier) if sub else get_plan("trial")
    seat_limit = plan["team_members"]
    if seat_limit is not None:
        current_count = db.query(TeamMember).filter(
            TeamMember.owner_user_id == user_id, TeamMember.status.in_(["active", "invited"])
        ).count()
        if current_count >= seat_limit:
            raise HTTPException(
                status_code=402,
                detail=f"Your {plan['name']} plan includes {seat_limit} team seat(s). Upgrade to invite more.",
            )

    existing = db.query(TeamMember).filter(TeamMember.owner_user_id == user_id, TeamMember.email.ilike(req.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="This person has already been invited.")

    matched_user = db.query(User).filter(User.email.ilike(req.email)).first()
    member = TeamMember(
        owner_user_id=user_id,
        member_user_id=matched_user.id if matched_user else None,
        email=req.email,
        name=req.name or (matched_user.name if matched_user else None),
        role=req.role,
        status="active" if matched_user else "invited",
        joined_at=datetime.now(timezone.utc) if matched_user else None,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return _serialize(member)


@router.patch("/{member_id}")
def update_member_role(member_id: int, req: UpdateRoleRequest, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.owner_user_id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found.")
    member.role = req.role
    db.commit()
    return _serialize(member)


@router.delete("/{member_id}")
def remove_member(member_id: int, user_id: int = Depends(get_current_user_id), db: Session | None = Depends(get_db_or_503)):
    db = _require_db(db)
    member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.owner_user_id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found.")
    db.delete(member)
    db.commit()
    return {"removed": True}
