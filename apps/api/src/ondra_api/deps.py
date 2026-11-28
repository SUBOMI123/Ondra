"""Request dependencies: who is calling, and a database session scoped to their tenant."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from ondra_core.models import AuditLog, User
from ondra_core.permissions import Perm, has_perm
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.security import decode_access_token


@dataclass(frozen=True)
class Caller:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    mfa_missing: bool = False  # signed in with Clerk without the second factor their role requires


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


MFA_REQUIRED = "Set up two-step sign-in to continue. Owners and admins need it."
# Paths a person without required MFA may still call, so the dashboard can show them how to set it up.
_MFA_EXEMPT = {"/me"}


async def authenticate(request: Request) -> tuple[Caller, AsyncSession]:
    """Who is calling, from Ondra's own token (local) or a Clerk session token. Returns an open tenant session the
    caller must close. The role always comes from Ondra's database, so a change applies at once."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise _unauthorized("Sign in to continue.")
    token = header[7:]
    if get_settings().auth_provider == "clerk":
        return await _clerk_caller(token)
    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Your session expired. Sign in again.") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Sign in to continue.") from None
    cm = tenant_session(uuid.UUID(claims["tid"]))
    session = await cm.__aenter__()
    try:
        user = (await session.execute(select(User).where(User.id == uuid.UUID(claims["sub"])))).scalar_one_or_none()
        if user is None or not user.active:
            raise _unauthorized("This account is no longer active.")
    except BaseException:
        await cm.__aexit__(None, None, None)
        raise
    session.info["cm"] = cm
    return Caller(user.id, user.tenant_id, user.role), session


async def _clerk_caller(token: str) -> tuple[Caller, AsyncSession]:
    from ondra_api import clerk

    try:
        cs = await asyncio.to_thread(clerk.verify_session_token, token)
    except clerk.ClerkTokenError as e:
        raise _unauthorized(e.message) from None
    if not cs.org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choose your dealership to continue.")
    async with no_tenant_session() as db:
        tenant_id = (await db.execute(text("SELECT tenant_for_clerk_org(:o)"), {"o": cs.org_id})).scalar()
    if tenant_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This organization isn't connected to a dealership in Ondra.")
    cm = tenant_session(tenant_id)
    session = await cm.__aenter__()
    try:
        user = (await session.execute(select(User).where(User.clerk_user_id == cs.user_id))).scalar_one_or_none()
        if user is None:
            # First sign-in after accepting an invitation: link the invited person by their verified email.
            email = await asyncio.to_thread(clerk.client().primary_email, cs.user_id)
            user = (await session.execute(select(User).where(User.email == email, User.clerk_user_id.is_(None))
                                          )).scalar_one_or_none() if email else None
            if user is not None:
                user.clerk_user_id = cs.user_id
                user.invite_token_hash, user.invite_expires_at = None, None
                session.add(AuditLog(actor_type="user", actor_user_id=user.id, action="auth.clerk_linked",
                                     resource=f"user:{user.id}"))
                await session.flush()
        if user is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "You're not on this dealership's team in Ondra. Ask an owner or admin to invite you.")
        if not user.active:
            raise _unauthorized("This account is no longer active.")
    except BaseException:
        await cm.__aexit__(None, None, None)
        raise
    session.info["cm"] = cm
    needs_mfa = user.role in {r.strip() for r in get_settings().clerk_mfa_roles.split(",")}
    # Both: MFA set up on their account, and a second factor used in this session (see clerk.has_mfa_set_up).
    mfa_missing = needs_mfa and (not cs.second_factor or not await asyncio.to_thread(clerk.has_mfa_set_up, cs.user_id))
    return Caller(user.id, user.tenant_id, user.role, mfa_missing=mfa_missing), session


async def get_db(request: Request) -> AsyncIterator[tuple[Caller, AsyncSession]]:
    caller, session = await authenticate(request)
    cm = session.info.pop("cm")
    try:
        if caller.mfa_missing and request.url.path not in _MFA_EXEMPT:
            raise HTTPException(status.HTTP_403_FORBIDDEN, MFA_REQUIRED, headers={"X-Ondra-Reason": "mfa_required"})
        yield caller, session
    except BaseException as e:
        await cm.__aexit__(type(e), e, e.__traceback__)
        raise
    else:
        await cm.__aexit__(None, None, None)


def require(perm: Perm):
    async def dep(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> tuple[Caller, AsyncSession]:
        caller, _ = ctx
        if not has_perm(caller.role, perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow this.")
        return ctx

    return dep
