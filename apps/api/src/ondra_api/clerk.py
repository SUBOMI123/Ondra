"""Clerk: who someone is (sign-in, MFA, invitations). What they may do stays in Ondra (roles, VIP rules, RLS).

Session tokens (docs: clerk.com/docs/guides/sessions/session-tokens, manual-jwt-verification; version 2 claims):
    sub   the Clerk user           o.id  the active Organization (= an Ondra dealership)
    fva   [minutes since first factor, minutes since second factor]; -1 = no second factor verified
    azp   the origin the token was made for; checked against CLERK_AUTHORIZED_PARTIES
    sts   "pending" while the user still has a sign-in task to finish (for example setting up MFA)
Tokens are RS256. The public key comes from CLERK_JWT_KEY (PEM, networkless) or the Backend API's JWKS, cached.

Backend API calls (api.clerk.com/v1) go through `ClerkClient`, which tests replace with a fake.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
import jwt

from ondra_api.config import get_settings


class ClerkTokenError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ClerkSession:
    user_id: str
    org_id: str | None
    second_factor: bool  # a second factor was verified in this session


class _Keys:
    """Public keys by key id, from CLERK_JWT_KEY or the JWKS endpoint, refreshed hourly or on an unknown key id."""

    def __init__(self) -> None:
        self._keys: dict[str | None, object] = {}
        self._loaded = 0.0

    def _load(self) -> None:
        s = get_settings()
        if s.clerk_jwt_key:
            from cryptography.hazmat.primitives.serialization import load_pem_public_key

            self._keys = {None: load_pem_public_key(s.clerk_jwt_key.replace("\\n", "\n").encode())}
        else:
            r = httpx.get(f"{s.clerk_api_base}/v1/jwks", headers={"Authorization": f"Bearer {s.clerk_secret_key}"}, timeout=10)
            r.raise_for_status()
            self._keys = {k["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k)) for k in r.json()["keys"]}
        self._loaded = time.monotonic()

    def get(self, kid: str | None):
        if not self._keys or time.monotonic() - self._loaded > 3600 or (kid not in self._keys and None not in self._keys):
            self._load()
        return self._keys.get(kid) or self._keys.get(None)

    def reset(self) -> None:
        self._keys, self._loaded = {}, 0.0


keys = _Keys()


def verify_session_token(token: str) -> ClerkSession:
    s = get_settings()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = keys.get(kid)
        if key is None:
            raise ClerkTokenError("Sign in to continue.")
        claims = jwt.decode(token, key=key, algorithms=["RS256"], leeway=5, options={"require": ["exp", "iat", "sub"]})
    except jwt.ExpiredSignatureError:
        raise ClerkTokenError("Your session expired. Sign in again.") from None
    except (jwt.InvalidTokenError, httpx.HTTPError):
        raise ClerkTokenError("Sign in to continue.") from None
    parties = [p.strip() for p in s.clerk_authorized_parties.split(",") if p.strip()]
    if parties and claims.get("azp") and claims["azp"] not in parties:
        raise ClerkTokenError("Sign in to continue.")
    if claims.get("sts") == "pending":
        raise ClerkTokenError("Finish signing in to continue.")
    org = claims.get("o") or {}
    fva = claims.get("fva") or [0, -1]
    return ClerkSession(user_id=claims["sub"], org_id=org.get("id") if isinstance(org, dict) else None,
                        second_factor=len(fva) > 1 and fva[1] is not None and fva[1] >= 0)


class ClerkClient:
    """The few Backend API calls Ondra makes. Docs: clerk.com/docs/reference/backend (Organizations, Users)."""

    def __init__(self) -> None:
        s = get_settings()
        self.base = f"{s.clerk_api_base}/v1"
        self.headers = {"Authorization": f"Bearer {s.clerk_secret_key}"}

    def _call(self, method: str, path: str, **kw) -> dict:
        r = httpx.request(method, f"{self.base}{path}", headers=self.headers, timeout=15, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json()["errors"][0].get("long_message") or r.json()["errors"][0]["message"]
            except (ValueError, KeyError, IndexError):
                msg = r.text[:200]
            raise ClerkApiError(r.status_code, msg)
        return r.json() if r.content else {}

    def primary_email(self, user_id: str) -> str | None:
        u = self._call("GET", f"/users/{user_id}")
        primary = u.get("primary_email_address_id")
        return next((e["email_address"] for e in u.get("email_addresses", []) if e["id"] == primary), None)

    def two_factor_enabled(self, user_id: str) -> bool:
        return bool(self._call("GET", f"/users/{user_id}").get("two_factor_enabled"))

    def create_organization(self, name: str) -> str:
        return self._call("POST", "/organizations", json={"name": name})["id"]

    def invite(self, org_id: str, email: str, role: str, redirect_url: str) -> str:
        return self._call("POST", f"/organizations/{org_id}/invitations",
                          json={"email_address": email, "role": role, "redirect_url": redirect_url})["id"]

    def set_role(self, org_id: str, user_id: str, role: str) -> None:
        self._call("PATCH", f"/organizations/{org_id}/memberships/{user_id}", json={"role": role})

    def remove_member(self, org_id: str, user_id: str) -> None:
        self._call("DELETE", f"/organizations/{org_id}/memberships/{user_id}")


class ClerkApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status, self.message = status, message


_client: ClerkClient | None = None


def client() -> ClerkClient:
    global _client
    if _client is None:
        _client = ClerkClient()
    return _client


def set_client(c) -> None:
    """Tests swap in a fake."""
    global _client
    _client = c
    _mfa_cache.clear()


_mfa_cache: dict[str, tuple[bool, float]] = {}


def has_mfa_set_up(user_id: str) -> bool:
    """Whether the person has two-step sign-in set up on their Clerk account (an authenticator app, passkey or
    backup codes). The session token can't tell: Clerk's new-device email code also counts as a verified second
    factor in `fva`, so `fva` alone would let an owner in who never set up MFA (found in the end-to-end test).
    Cached for a minute per person."""
    hit = _mfa_cache.get(user_id)
    if hit and time.monotonic() - hit[1] < 60:
        return hit[0]
    value = client().two_factor_enabled(user_id)
    _mfa_cache[user_id] = (value, time.monotonic())
    return value


# Clerk Organization roles mirror Ondra's for Clerk's own screens; Ondra's database is what's enforced.
def clerk_role(role: str) -> str:
    return "org:admin" if role == "admin" else "org:member"
