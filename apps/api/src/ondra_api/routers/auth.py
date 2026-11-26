"""Sign in, refresh and sign out.

Access tokens are short-lived JWTs sent as a Bearer header. Refresh tokens live in an httpOnly cookie scoped to
/auth, are stored only as a hash, and rotate on every use.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from ondra_core.models import AuditLog, Session, Tenant, User
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.deps import Caller, get_db
from ondra_api.schemas import MeOut
from ondra_api.security import (
    create_access_token,
    hash_token,
    new_refresh_token,
    tenant_of_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "ondra_refresh"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE, token, max_age=s.refresh_token_days * 86400, httponly=True, secure=s.cookie_secure,
        samesite="lax", path="/auth",
    )


async def _start_session(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID, request: Request) -> str:
    token = new_refresh_token(tenant_id)
    db.add(
        Session(
            tenant_id=tenant_id, user_id=user_id, token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
            user_agent=request.headers.get("user-agent", "")[:300],
            ip=request.client.host if request.client else None,
        )
    )
    return token


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response) -> TokenOut:
    async with no_tenant_session() as db:
        row = (await db.execute(text("SELECT * FROM auth_find_user(:e)"), {"e": body.email})).mappings().first()
    ok = verify_password(body.password, row["password_hash"] if row else None)
    if not row or not ok or not row["active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password don't match an account.")
    async with tenant_session(row["tenant_id"]) as db:
        refresh = await _start_session(db, row["id"], row["tenant_id"], request)
        db.add(AuditLog(tenant_id=row["tenant_id"], actor_type="user", actor_user_id=row["id"], action="auth.login",
                        resource=f"user:{row['id']}", ip=request.client.host if request.client else None))
    _set_cookie(response, refresh)
    return TokenOut(access_token=create_access_token(row["id"], row["tenant_id"], row["role"]),
                    expires_in=get_settings().access_token_minutes * 60)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, ondra_refresh: str | None = Cookie(default=None)) -> TokenOut:
    tenant_id = tenant_of_refresh_token(ondra_refresh or "")
    if tenant_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    async with tenant_session(tenant_id) as db:
        sess = (await db.execute(select(Session).where(Session.token_hash == hash_token(ondra_refresh or "")))).scalar_one_or_none()
        if sess is None or sess.revoked_at is not None or sess.expires_at < datetime.now(UTC):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session expired. Sign in again.")
        user = (await db.execute(select(User).where(User.id == sess.user_id))).scalar_one()
        if not user.active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is no longer active.")
        sess.revoked_at = datetime.now(UTC)  # rotate: each refresh token works once
        new = await _start_session(db, user.id, tenant_id, request)
    _set_cookie(response, new)
    return TokenOut(access_token=create_access_token(user.id, tenant_id, user.role),
                    expires_in=get_settings().access_token_minutes * 60)


@router.post("/logout", status_code=204)
async def logout(response: Response, ondra_refresh: str | None = Cookie(default=None)) -> Response:
    tenant_id = tenant_of_refresh_token(ondra_refresh or "")
    if tenant_id is not None:
        async with tenant_session(tenant_id) as db:
            await db.execute(update(Session).where(Session.token_hash == hash_token(ondra_refresh or ""))
                             .values(revoked_at=datetime.now(UTC)))
    response.delete_cookie(COOKIE, path="/auth")
    response.status_code = 204
    return response


me_router = APIRouter(tags=["auth"])


@me_router.get("/me", response_model=MeOut)
async def me(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> MeOut:
    caller, db = ctx
    user = (await db.execute(select(User).where(User.id == caller.user_id))).scalar_one()
    tenant = (await db.execute(select(Tenant))).scalar_one()
    return MeOut(id=user.id, email=user.email, name=user.name, role=user.role,
                 tenant_id=tenant.id, tenant_name=tenant.name)
