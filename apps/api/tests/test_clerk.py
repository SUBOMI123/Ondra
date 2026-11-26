"""Clerk sign-in: Clerk proves who someone is; Ondra decides what they may do. Real RS256 tokens signed with a test
key, verified the way production verifies them; Clerk's Backend API is a fake that records calls."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, update

from ondra_api import clerk
from ondra_api.config import get_settings
from ondra_api.db import tenant_session
from ondra_core.models import AuditLog, Tenant, User

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
ORG_A, ORG_B, APP = "org_prestige", "org_lonestar", "https://app.ondra.example"


class FakeClerk:
    def __init__(self) -> None:
        self.emails: dict[str, str] = {}
        self.calls: list[tuple] = []

    def primary_email(self, user_id):
        self.calls.append(("email", user_id))
        return self.emails.get(user_id)

    def invite(self, org_id, email, role, redirect_url):
        self.calls.append(("invite", org_id, email, role, redirect_url))
        return "orginv_1"

    def remove_member(self, org_id, user_id):
        self.calls.append(("remove", org_id, user_id))


def token(sub, org=ORG_A, fva=(3, -1), key=KEY, exp_in=60, azp=APP, **extra):
    now = int(time.time())
    claims = {"sub": sub, "iat": now, "nbf": now, "exp": now + exp_in, "azp": azp, "fva": list(fva), "v": 2,
              "sid": "sess_1", **extra}
    if org:
        claims["o"] = {"id": org, "rol": "admin", "slg": "x"}
    return {"Authorization": "Bearer " + jwt.encode(claims, key, algorithm="RS256")}


@pytest.fixture
async def clerk_mode(database, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "auth_provider", "clerk")
    monkeypatch.setattr(s, "clerk_jwt_key", PEM)
    monkeypatch.setattr(s, "clerk_authorized_parties", APP)
    clerk.keys.reset()
    fake = FakeClerk()
    clerk.set_client(fake)
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Tenant).values(clerk_org_id=ORG_A))
        owner = (await db.execute(select(User).where(User.role == "owner"))).scalar_one()
        owner.clerk_user_id = "user_owner"
        sales = (await db.execute(select(User).where(User.email == "daniel@prestigemotors.example"))).scalar_one()
        sales.clerk_user_id = "user_daniel"
    async with tenant_session(database["b"]) as db:
        await db.execute(update(Tenant).values(clerk_org_id=ORG_B))
    yield fake
    clerk.keys.reset()
    clerk.set_client(None)
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Tenant).values(clerk_org_id=None))
        await db.execute(update(User).values(clerk_user_id=None))
    async with tenant_session(database["b"]) as db:
        await db.execute(update(Tenant).values(clerk_org_id=None))


async def test_a_clerk_session_reaches_only_its_own_dealership(client, clerk_mode):
    r = await client.get("/conversations", headers=token("user_daniel"))
    assert r.status_code == 200 and r.json()["items"]
    me = (await client.get("/me", headers=token("user_daniel"))).json()
    assert me["tenant_name"] == "Prestige Motors" and me["role"] == "sales" and me["mfa_required"] is False
    # The same Clerk user with another dealership's organization active isn't on that team.
    assert (await client.get("/conversations", headers=token("user_daniel", org=ORG_B))).status_code == 403
    # No active organization, or one Ondra doesn't know: refused.
    assert (await client.get("/conversations", headers=token("user_daniel", org=None))).status_code == 403
    assert (await client.get("/conversations", headers=token("user_daniel", org="org_unknown"))).status_code == 403


async def test_bad_tokens_are_refused(client, clerk_mode):
    for headers in (token("user_daniel", key=OTHER_KEY), token("user_daniel", exp_in=-60),
                    token("user_daniel", azp="https://evil.example"), token("user_daniel", sts="pending"),
                    {"Authorization": "Bearer not-a-token"}, {}):
        assert (await client.get("/conversations", headers=headers)).status_code == 401
    # Ondra's own password sign-in is off, so it can't be used to skip Clerk's MFA.
    r = await client.post("/auth/login", json={"email": "owner@prestigemotors.example", "password": "ondra-dev-password"})
    assert r.status_code == 404


async def test_owners_and_admins_need_two_step_sign_in(client, clerk_mode):
    no_mfa = token("user_owner", fva=(2, -1))
    r = await client.get("/conversations", headers=no_mfa)
    assert r.status_code == 403 and r.headers["x-ondra-reason"] == "mfa_required"
    assert (await client.get("/me", headers=no_mfa)).json()["mfa_required"] is True  # so the screen can explain
    assert (await client.get("/live", headers=no_mfa)).status_code == 403
    assert (await client.get("/conversations", headers=token("user_owner", fva=(2, 0)))).status_code == 200
    # Sales doesn't need it.
    assert (await client.get("/conversations", headers=token("user_daniel", fva=(2, -1)))).status_code == 200


async def test_an_invited_person_is_linked_on_first_sign_in(client, clerk_mode, database):
    owner = token("user_owner", fva=(1, 1))
    r = await client.post("/users/invite", headers=owner, json={"name": "Ada Obi", "email": "ada@prestigemotors.example",
                                                                "role": "admin"})
    assert r.status_code == 201 and r.json()["emailed"] is True and "invite_link" not in r.json()
    assert clerk_mode.calls[-1] == ("invite", ORG_A, "ada@prestigemotors.example", "org:admin", "http://localhost:3001/invite")
    # Before accepting, a stranger with no invitation is refused.
    clerk_mode.emails["user_stranger"] = "stranger@example.com"
    assert (await client.get("/me", headers=token("user_stranger"))).status_code == 403
    # Ada accepts in Clerk and signs in: linked by her verified email, once.
    clerk_mode.emails["user_ada"] = "ada@prestigemotors.example"
    me = (await client.get("/me", headers=token("user_ada", fva=(1, 0)))).json()
    assert me["email"] == "ada@prestigemotors.example" and me["role"] == "admin"
    async with tenant_session(database["a"]) as db:
        ada = (await db.execute(select(User).where(User.email == "ada@prestigemotors.example"))).scalar_one()
        assert ada.clerk_user_id == "user_ada"
        assert (await db.execute(select(AuditLog).where(AuditLog.action == "auth.clerk_linked",
                                                        AuditLog.resource == f"user:{ada.id}"))).scalar_one()
    team = {u["email"]: u for u in (await client.get("/users", headers=owner)).json()["items"]}
    assert team["ada@prestigemotors.example"]["invited"] is False

    # Deactivating removes her from the Clerk organization, and Ondra refuses her at once.
    r = await client.patch(f"/users/{ada.id}", headers=owner, json={"active": False})
    assert r.status_code == 200 and clerk_mode.calls[-1] == ("remove", ORG_A, "user_ada")
    assert (await client.get("/me", headers=token("user_ada", fva=(1, 0)))).status_code == 401
    async with tenant_session(database["a"]) as db:
        await db.execute(update(User).where(User.id == ada.id).values(email=f"gone-{uuid.uuid4().hex}@x.example"))
