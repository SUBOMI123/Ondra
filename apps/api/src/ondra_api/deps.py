"""Request dependencies: who is calling, and a database session scoped to their tenant."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.db import tenant_session
from ondra_api.security import decode_access_token
from ondra_core.models import User
from ondra_core.permissions import Perm, has_perm


@dataclass(frozen=True)
class Caller:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def get_db(request: Request) -> AsyncIterator[tuple[Caller, AsyncSession]]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise _unauthorized("Sign in to continue.")
    try:
        claims = decode_access_token(header[7:])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Your session expired. Sign in again.")
    except jwt.InvalidTokenError:
        raise _unauthorized("Sign in to continue.")
    tenant_id = uuid.UUID(claims["tid"])
    async with tenant_session(tenant_id) as session:
        # The role comes from the database, not the token, so a role change or deactivation applies at once.
        user = (await session.execute(select(User).where(User.id == uuid.UUID(claims["sub"])))).scalar_one_or_none()
        if user is None or not user.active:
            raise _unauthorized("This account is no longer active.")
        yield Caller(user.id, user.tenant_id, user.role), session


def require(perm: Perm):
    async def dep(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> tuple[Caller, AsyncSession]:
        caller, _ = ctx
        if not has_perm(caller.role, perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow this.")
        return ctx

    return dep
