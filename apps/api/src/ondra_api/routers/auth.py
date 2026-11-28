"""Sign in, refresh and sign out.

Access tokens are short-lived JWTs sent as a Bearer header. Refresh tokens live in an httpOnly cookie scoped to
/auth, are stored only as a hash, and rotate on every use.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from ondra_core.models import AuditLog, Session, Tenant, User
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.deps import Caller, get_db
from ondra_api.schemas import MeOut
from ondra_api.security import (
    client_ip,
    create_access_token,
    hash_token,
    new_refresh_token,
    tenant_of_refresh_token,
    verify_password,
)


def _local_sign_in_only() -> None:
    """With Clerk on, Ondra's own passwords don't sign anyone in (they'd skip Clerk's MFA)."""
    if get_settings().auth_provider == "clerk":
        raise HTTPException(404, "Sign in with your dealership's Clerk account.")


router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(_local_sign_in_only)])
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
            ip=client_ip(request),
        )
    )
    return token


# Password guessing: after 5 wrong passwords for one email, or 30 from one address, in 15 minutes, sign-in waits.
# Counted for unknown emails too, so the answer never says whether an account exists.
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_MAX_PER_EMAIL = 5
LOGIN_MAX_PER_IP = 30


async def _too_many_attempts(db: AsyncSession, email: str, ip: str | None) -> bool:
    since = datetime.now(UTC) - LOGIN_WINDOW
    row = (await db.execute(text("""
        SELECT count(*) FILTER (WHERE email = :e), count(*) FILTER (WHERE ip = :ip)
        FROM login_attempts WHERE at > :since AND (email = :e OR ip = :ip)"""),
        {"e": email, "ip": ip, "since": since})).one()
    return row[0] >= LOGIN_MAX_PER_EMAIL or (ip is not None and row[1] >= LOGIN_MAX_PER_IP)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response) -> TokenOut:
    ip = client_ip(request)
    async with no_tenant_session() as db:
        if await _too_many_attempts(db, body.email, ip):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Too many attempts. Wait 15 minutes and try again, or ask an admin to reset your password.")
        row = (await db.execute(text("SELECT * FROM auth_find_user(:e)"), {"e": body.email})).mappings().first()
    ok = verify_password(body.password, row["password_hash"] if row else None)
    if not row or not ok or not row["active"]:
        async with no_tenant_session() as db:
            await db.execute(text("INSERT INTO login_attempts (email, ip) VALUES (:e, :ip)"), {"e": body.email, "ip": ip})
            await db.execute(text("DELETE FROM login_attempts WHERE at < now() - interval '1 day'"))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password don't match an account.")
    async with no_tenant_session() as db:
        await db.execute(text("DELETE FROM login_attempts WHERE email = :e"), {"e": body.email})
    async with tenant_session(row["tenant_id"]) as db:
        refresh = await _start_session(db, row["id"], row["tenant_id"], request)
        db.add(AuditLog(tenant_id=row["tenant_id"], actor_type="user", actor_user_id=row["id"], action="auth.login",
                        resource=f"user:{row['id']}", ip=client_ip(request)))
    _set_cookie(response, refresh)
    return TokenOut(access_token=create_access_token(row["id"], row["tenant_id"], row["role"]),
                    expires_in=get_settings().access_token_minutes * 60)


# Two tabs refreshing at the same moment both present the same token; only a reuse after this long is treated as theft.
REUSE_GRACE = timedelta(seconds=30)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, ondra_refresh: str | None = Cookie(default=None)) -> TokenOut:
    tenant_id = tenant_of_refresh_token(ondra_refresh or "")
    if tenant_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    now = datetime.now(UTC)
    token_hash = hash_token(ondra_refresh or "")
    async with tenant_session(tenant_id) as db:
        # Rotate atomically: each refresh token works once, even when two requests race with the same one.
        claimed = (await db.execute(
            update(Session).where(Session.token_hash == token_hash, Session.revoked_at.is_(None), Session.expires_at > now)
            .values(revoked_at=now).returning(Session.user_id)
        )).scalar_one_or_none()
        if claimed is None:
            old = (await db.execute(select(Session).where(Session.token_hash == token_hash))).scalar_one_or_none()
            if old is not None and old.revoked_at is not None and now - old.revoked_at > REUSE_GRACE:
                # A used token came back: someone else has a copy. End every session of that person, so whoever
                # holds a stolen token loses it too, and leave a trace.
                await db.execute(update(Session).where(Session.user_id == old.user_id, Session.revoked_at.is_(None))
                                 .values(revoked_at=now))
                db.add(AuditLog(tenant_id=tenant_id, actor_type="system", action="auth.refresh_reused",
                                resource=f"user:{old.user_id}", ip=client_ip(request)))
        else:
            user = (await db.execute(select(User).where(User.id == claimed))).scalar_one()
            new = await _start_session(db, user.id, tenant_id, request) if user.active else None
    # Raised outside the transaction, so a revocation above is committed, not rolled back with the error.
    if claimed is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session expired. Sign in again.")
    if new is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is no longer active.")
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


class AcceptInviteIn(BaseModel):
    token: str
    password: str


@router.post("/accept-invite", status_code=204)
async def accept_invite(body: AcceptInviteIn, request: Request) -> None:
    """A new teammate sets their password from their invite link. The link works once."""
    from ondra_api.security import hash_password

    if len(body.password) < 12:
        raise HTTPException(422, "Use at least 12 characters.")
    tenant_id = tenant_of_refresh_token(body.token)
    bad = HTTPException(400, "This invite link has expired or was already used. Ask for a new one.")
    if tenant_id is None:
        raise bad
    async with tenant_session(tenant_id) as db:
        u = (await db.execute(select(User).where(User.invite_token_hash == hash_token(body.token)))).scalar_one_or_none()
        if u is None or not u.active or u.invite_expires_at is None or u.invite_expires_at < datetime.now(UTC):
            raise bad
        u.password_hash = hash_password(body.password)
        u.invite_token_hash = None
        u.invite_expires_at = None
        db.add(AuditLog(actor_type="user", actor_user_id=u.id, action="auth.accept_invite", resource=f"user:{u.id}",
                        ip=client_ip(request)))


me_router = APIRouter(tags=["auth"])


@me_router.get("/me", response_model=MeOut)
async def me(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> MeOut:
    caller, db = ctx
    user = (await db.execute(select(User).where(User.id == caller.user_id))).scalar_one()
    tenant = (await db.execute(select(Tenant))).scalar_one()
    return MeOut(id=user.id, email=user.email, name=user.name, role=user.role,
                 tenant_id=tenant.id, tenant_name=tenant.name, timezone=(tenant.timezones or ["America/Chicago"])[0], phone=user.phone,
                 mfa_required=caller.mfa_missing)


class MePatch(BaseModel):
    phone: str | None = Field(None, max_length=40)


@me_router.patch("/me", response_model=MeOut)
async def update_me(body: MePatch, ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> MeOut:
    """Anyone can set their own mobile: it's the number Ondra rings to put a call through to them."""
    from ondra_api.routers.team import clean_phone

    caller, db = ctx
    user = (await db.execute(select(User).where(User.id == caller.user_id))).scalar_one()
    user.phone = clean_phone(body.phone)
    db.add(AuditLog(actor_type="user", actor_user_id=user.id, action="team.phone", resource=f"user:{user.id}"))
    return await me(ctx)
