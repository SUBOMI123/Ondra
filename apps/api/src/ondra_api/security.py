"""Passwords, access tokens and refresh tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ondra_api.config import get_settings

_hasher = PasswordHasher()
# Verified against when the email doesn't exist, so a missing account takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "tid"]})
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return claims


def new_refresh_token(tenant_id: uuid.UUID) -> str:
    """`<tenant id>.<random>`: the tenant prefix lets refresh run inside that tenant's RLS scope."""
    return f"{tenant_id}.{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tenant_of_refresh_token(token: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(token.split(".", 1)[0])
    except (ValueError, IndexError):
        return None
