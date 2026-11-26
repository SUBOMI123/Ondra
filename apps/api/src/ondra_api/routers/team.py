"""Team management: invite teammates, change roles, deactivate. Owners and admins only (Perm.USERS_MANAGE).

Rules, enforced here and tested:
- Only an owner can make someone an owner, or change or deactivate an owner.
- Nobody changes their own role or deactivates themselves (so you can't lock yourself out by accident).
- A dealership always keeps at least one active owner.
- Deactivating someone signs them out everywhere at once.

Invites: the new teammate gets a one-time link (`<tenant>.<random>`, stored as a hash, valid 7 days) to set their
password. Until Postmark sends email for us, the link is shown once to the person who sent the invite.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.deps import Caller, require
from ondra_api.security import hash_token
from ondra_core.models import AuditLog, Session, User
from ondra_core.permissions import Perm

router = APIRouter(prefix="/users", tags=["team"])

Role = Literal["owner", "admin", "manager", "sales", "service", "ops", "viewer"]
INVITE_DAYS = 7


class InviteIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: Role


class UserPatch(BaseModel):
    role: Role | None = None
    active: bool | None = None


def user_out(u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role, "active": u.active,
            "invited": u.password_hash is None}


def new_invite_token(tenant_id: uuid.UUID) -> str:
    return f"{tenant_id}.{secrets.token_urlsafe(32)}"


def _issue_invite(u: User, tenant_id: uuid.UUID) -> str:
    token = new_invite_token(tenant_id)
    u.invite_token_hash = hash_token(token)
    u.invite_expires_at = datetime.now(UTC) + timedelta(days=INVITE_DAYS)
    return f"{get_settings().app_base_url.rstrip('/')}/invite?token={token}"


def _audit(db: AsyncSession, caller: Caller, request: Request, action: str, u: User, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource=f"user:{u.id}",
                    before=before, after=after, ip=request.client.host if request.client else None))


@router.post("/invite", status_code=201)
async def invite(body: InviteIn, request: Request,
                 ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_MANAGE))) -> dict:
    caller, db = ctx
    if body.role == "owner" and caller.role != "owner":
        raise HTTPException(403, "Only an owner can add another owner.")
    u = User(email=body.email.lower(), name=body.name.strip(), role=body.role, password_hash=None, active=True)
    link = _issue_invite(u, caller.tenant_id)
    try:
        async with db.begin_nested():
            db.add(u)
            await db.flush()
    except IntegrityError:
        raise HTTPException(409, "That email already has an Ondra account.") from None
    _audit(db, caller, request, "team.invite", u, None, user_out(u))
    return {"user": user_out(u), "invite_link": link, "expires_in_days": INVITE_DAYS}


@router.post("/{user_id}/invite")
async def resend_invite(user_id: uuid.UUID, request: Request,
                        ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_MANAGE))) -> dict:
    caller, db = ctx
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    if u.password_hash is not None:
        raise HTTPException(409, "They've already set up their account.")
    link = _issue_invite(u, caller.tenant_id)  # the old link stops working
    _audit(db, caller, request, "team.reinvite", u, None, None)
    return {"user": user_out(u), "invite_link": link, "expires_in_days": INVITE_DAYS}


@router.patch("/{user_id}")
async def patch_user(user_id: uuid.UUID, body: UserPatch, request: Request,
                     ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_MANAGE))) -> dict:
    caller, db = ctx
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    if u.id == caller.user_id:
        raise HTTPException(403, "You can't change your own role or access. Ask another owner or admin.")
    touches_owner = u.role == "owner" or body.role == "owner"
    if touches_owner and caller.role != "owner":
        raise HTTPException(403, "Only an owner can change an owner, or make someone an owner.")
    before = user_out(u)
    if body.role is not None:
        u.role = body.role
    if body.active is not None:
        u.active = body.active
    await db.flush()
    owners = (await db.execute(
        select(func.count()).select_from(User).where(User.role == "owner", User.active.is_(True))
    )).scalar_one()
    if owners == 0:
        raise HTTPException(409, "The dealership needs at least one active owner.")
    if body.active is False:
        # Signed out everywhere: refresh sessions die now; any access token expires within its 15 minutes and is
        # refused sooner, because every request re-reads `active` from the database.
        await db.execute(update(Session).where(Session.user_id == u.id, Session.revoked_at.is_(None))
                         .values(revoked_at=func.now()))
    after = user_out(u)
    _audit(db, caller, request, "team.update", u, before, after)
    return after
