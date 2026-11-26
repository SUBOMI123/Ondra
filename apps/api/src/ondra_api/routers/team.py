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

import asyncio
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from ondra_core.channels.identity import normalize_phone
from ondra_core.models import AuditLog, Session, Tenant, User
from ondra_core.permissions import Perm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.deps import Caller, require
from ondra_api.security import hash_token

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
    # The mobile Ondra rings to put a call through (VIP calls to the owner, warm transfers). "" clears it.
    phone: str | None = Field(None, max_length=40)


def clean_phone(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    try:
        return normalize_phone(raw)
    except ValueError:
        raise HTTPException(422, "That doesn't look like a phone number.") from None


def user_out(u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role, "active": u.active,
            "invited": u.password_hash is None and u.clerk_user_id is None, "phone": u.phone}


def new_invite_token(tenant_id: uuid.UUID) -> str:
    return f"{tenant_id}.{secrets.token_urlsafe(32)}"


def _issue_invite(u: User, tenant_id: uuid.UUID) -> str:
    token = new_invite_token(tenant_id)
    u.invite_token_hash = hash_token(token)
    u.invite_expires_at = datetime.now(UTC) + timedelta(days=INVITE_DAYS)
    return f"{get_settings().app_base_url.rstrip('/')}/invite?token={token}"


def _clerk() -> bool:
    return get_settings().auth_provider == "clerk"


async def _clerk_org(db: AsyncSession) -> str:
    org = (await db.execute(select(Tenant.clerk_org_id).limit(1))).scalar()
    if not org:
        raise HTTPException(409, "This dealership isn't connected to Clerk yet, so invitations can't be sent.")
    return org


async def _send_invite(db: AsyncSession, u: User, tenant_id: uuid.UUID) -> dict:
    """Local sign-in: a link to copy. Clerk: Clerk emails an Organization invitation; accepting it links them."""
    if not _clerk():
        return {"invite_link": _issue_invite(u, tenant_id), "expires_in_days": INVITE_DAYS}
    from ondra_api import clerk

    org = await _clerk_org(db)
    try:
        await asyncio.to_thread(clerk.client().invite, org, u.email, clerk.clerk_role(u.role),
                                f"{get_settings().app_base_url.rstrip('/')}/invite")
    except clerk.ClerkApiError as e:
        raise HTTPException(502, f"Clerk didn't send the invitation: {e.message}") from None
    return {"emailed": True}


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
    try:
        async with db.begin_nested():
            db.add(u)
            await db.flush()
    except IntegrityError:
        raise HTTPException(409, "That email already has an Ondra account.") from None
    sent = await _send_invite(db, u, caller.tenant_id)
    _audit(db, caller, request, "team.invite", u, None, user_out(u))
    return {"user": user_out(u), **sent}


@router.post("/{user_id}/invite")
async def resend_invite(user_id: uuid.UUID, request: Request,
                        ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_MANAGE))) -> dict:
    caller, db = ctx
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    if u.password_hash is not None or u.clerk_user_id is not None:
        raise HTTPException(409, "They've already set up their account.")
    sent = await _send_invite(db, u, caller.tenant_id)  # a new local link replaces the old one
    _audit(db, caller, request, "team.reinvite", u, None, None)
    return {"user": user_out(u), **sent}


@router.patch("/{user_id}")
async def patch_user(user_id: uuid.UUID, body: UserPatch, request: Request,
                     ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_MANAGE))) -> dict:
    caller, db = ctx
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    if u.id == caller.user_id and (body.role is not None or body.active is not None):
        raise HTTPException(403, "You can't change your own role or access. Ask another owner or admin.")
    touches_owner = u.role == "owner" or body.role == "owner"
    if touches_owner and caller.role != "owner":
        raise HTTPException(403, "Only an owner can change an owner, or make someone an owner.")
    before = user_out(u)
    if body.role is not None:
        u.role = body.role
    if body.active is not None:
        u.active = body.active
    if "phone" in body.model_fields_set:
        u.phone = clean_phone(body.phone)
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
        if _clerk() and u.clerk_user_id:
            # Also out of the Clerk Organization. Ondra already refuses them (it re-reads `active` every request).
            from ondra_api import clerk

            try:
                await asyncio.to_thread(clerk.client().remove_member, await _clerk_org(db), u.clerk_user_id)
            except clerk.ClerkApiError as e:
                if e.status != 404:
                    raise HTTPException(502, f"Deactivated in Ondra, but Clerk refused to remove them: {e.message}") from None
    elif body.active is True and _clerk() and u.clerk_user_id:
        await _send_invite(db, u, caller.tenant_id)  # back into the Clerk Organization
    after = user_out(u)
    _audit(db, caller, request, "team.update", u, before, after)
    return after
