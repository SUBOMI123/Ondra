"""Settings are real: they persist, only owners and admins change them, every change is audited, and the agent and
webhooks act on what's saved. Team management follows its rules. Each test restores what it changed."""

import json
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select, text

from ondra_api.db import tenant_session
from ondra_core.models import AuditLog, Policy, Tenant, User

from .conftest import login

OWNER, ADMIN, SALES = "owner@prestigemotors.example", "admin@prestigemotors.example", "daniel@prestigemotors.example"
SIG = {"x-mock-signature": "mock-secret"}


async def test_everyone_reads_settings_but_only_owner_and_admin_can_edit(client, database):
    sales = await login(client, SALES)
    r = await client.get("/settings", headers=sales)
    assert r.status_code == 200
    body = r.json()
    assert body["can_edit"] is False and body["business"]["name"] == "Prestige Motors"
    assert body["business"]["hours"]["sun"] is None and body["business"]["hours"]["mon"] == ["09:00", "19:00"]
    assert {c["channel"] for c in body["channels"]} == {"sms", "whatsapp", "email", "phone"}
    assert (await client.put("/settings/business", headers=sales, json=body["business"])).status_code == 403
    admin = await login(client, ADMIN)
    assert (await client.get("/settings", headers=admin)).json()["can_edit"] is True


async def test_business_hours_persist_validate_and_are_audited(client, database):
    owner = await login(client, OWNER)
    original = (await client.get("/settings", headers=owner)).json()["business"]
    changed = {**original, "name": "Prestige Motors Dallas",
               "hours": {**original["hours"], "sun": ["11:00", "16:00"]}}
    r = await client.put("/settings/business", headers=owner, json=changed)
    assert r.status_code == 200, r.text
    assert (await client.get("/settings", headers=owner)).json()["business"]["hours"]["sun"] == ["11:00", "16:00"]
    async with tenant_session(database["a"]) as db:
        t = (await db.execute(select(Tenant))).scalar_one()
        assert t.business_hours["sun"] == ["11:00", "16:00"]  # what the agent's open/closed check reads
        log = (await db.execute(select(AuditLog).where(AuditLog.action == "settings.business"))).scalars().all()
        assert log and log[-1].before["name"] == "Prestige Motors" and log[-1].after["name"] == "Prestige Motors Dallas"

    bad = {**original, "hours": {**original["hours"], "mon": ["19:00", "09:00"]}}
    assert (await client.put("/settings/business", headers=owner, json=bad)).status_code == 422
    assert (await client.put("/settings/business", headers=owner, json={**original, "timezone": "Mars/Base"})).status_code == 422
    assert (await client.put("/settings/business", headers=owner, json=original)).status_code == 200


async def test_reply_rules_persist_and_drive_the_agent(client, database):
    owner = await login(client, OWNER)
    original = (await client.get("/settings", headers=owner)).json()["replies"]
    new = {**original, "draft_mode": False, "price_disclosure": "none", "ai_disclosure": "upfront",
           "handoff_triggers": ["A discount", " A discount ", "Financing terms"]}
    r = await client.put("/settings/replies", headers=owner, json=new)
    assert r.status_code == 200 and r.json()["handoff_triggers"] == ["A discount", "Financing terms"]
    async with tenant_session(database["a"]) as db:
        p = (await db.execute(select(Policy))).scalar_one()
        t = (await db.execute(select(Tenant))).scalar_one()
        assert p.draft_mode is False and p.price_disclosure == "none" and t.settings["ai_disclosure"] == "upfront"
    assert (await client.put("/settings/replies", headers=owner, json={**new, "price_disclosure": "cheap"})).status_code == 422
    assert (await client.put("/settings/replies", headers=owner, json=original)).status_code == 200


async def test_channels_add_route_messages_and_can_be_switched_off(client, database):
    owner = await login(client, OWNER)
    r = await client.post("/settings/channels", headers=owner, json={"channel": "sms", "address": "(214) 555-0177"})
    assert r.status_code == 201, r.text
    ch = r.json()
    assert ch["address"] == "+12145550177" and ch["provider"] == "mock" and ch["live"] is False

    # Another dealer can't claim the same number.
    from ondra_api.security import hash_password
    async with tenant_session(database["b"]) as db:
        u = (await db.execute(select(User).where(User.email == "owner@lonestar.example"))).scalar_one()
        u.password_hash = u.password_hash or hash_password("ondra-dev-password")
    b_owner = await login(client, "owner@lonestar.example")
    clash = await client.post("/settings/channels", headers=b_owner, json={"channel": "sms", "address": "+12145550177"})
    assert clash.status_code == 409

    # A message to the new number reaches this dealer; once switched off, it's not accepted.
    msg = {"id": "ch-test-1", "from": "+12145559000", "to": "+12145550177", "text": "STOP"}
    assert (await client.post("/webhooks/mock/sms", content=json.dumps(msg), headers=SIG)).json()["stored"] == 1
    assert (await client.patch(f"/settings/channels/{ch['id']}", headers=owner, json={"active": False})).json()["active"] is False
    msg2 = {**msg, "id": "ch-test-2"}
    assert (await client.post("/webhooks/mock/sms", content=json.dumps(msg2), headers=SIG)).json()["stored"] == 0

    assert (await client.delete(f"/settings/channels/{ch['id']}", headers=owner)).status_code == 204
    async with tenant_session(database["a"]) as db:
        await db.execute(text("DELETE FROM contacts WHERE display_name = '+12145559000'"))


async def test_invite_accept_and_sign_in(client, database):
    admin = await login(client, ADMIN)
    r = await client.post("/users/invite", headers=admin, json={"name": "Tom Reyes", "email": "tom@prestigemotors.example",
                                                               "role": "sales"})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["invited"] is True
    token = parse_qs(urlparse(r.json()["invite_link"]).query)["token"][0]

    # Can't sign in before accepting; short passwords refused; the link works once.
    assert (await client.post("/auth/login", json={"email": "tom@prestigemotors.example", "password": "x" * 12})).status_code == 401
    assert (await client.post("/auth/accept-invite", json={"token": token, "password": "short"})).status_code == 422
    assert (await client.post("/auth/accept-invite", json={"token": token, "password": "a-good-long-password"})).status_code == 204
    assert (await client.post("/auth/accept-invite", json={"token": token, "password": "a-good-long-password"})).status_code == 400
    await login(client, "tom@prestigemotors.example", "a-good-long-password")

    # Same email again: refused.
    again = await client.post("/users/invite", headers=admin, json={"name": "T", "email": "TOM@prestigemotors.example",
                                                                   "role": "sales"})
    assert again.status_code == 409
    # People are deactivated, never deleted (the audit log keeps pointing at them).
    tom = next(u for u in (await client.get("/users", headers=admin)).json()["items"] if u["email"].startswith("tom@"))
    assert (await client.patch(f"/users/{tom['id']}", headers=admin, json={"active": False})).status_code == 200


async def test_team_rules(client, database):
    owner, admin = await login(client, OWNER), await login(client, ADMIN)
    users = {u["email"]: u for u in (await client.get("/users", headers=owner)).json()["items"]}
    owner_id, admin_id, sales_id = (users[e]["id"] for e in (OWNER, ADMIN, SALES))

    # One top role: "owner" isn't a role any more; admins manage each other; nobody changes themselves.
    assert (await client.post("/users/invite", headers=admin, json={"name": "X", "email": "x@prestigemotors.example",
                                                                   "role": "owner"})).status_code == 422
    assert (await client.patch(f"/users/{owner_id}", headers=owner, json={"role": "sales"})).status_code == 403
    assert (await client.patch(f"/users/{owner_id}", headers=admin, json={"role": "manager"})).json()["role"] == "manager"
    assert (await client.patch(f"/users/{owner_id}", headers=admin, json={"role": "admin"})).json()["role"] == "admin"
    # Sales can't manage the team at all.
    sales = await login(client, SALES)
    assert (await client.patch(f"/users/{admin_id}", headers=sales, json={"active": False})).status_code == 403

    # Change a role, then deactivate: they're signed out and can't sign in.
    assert (await client.patch(f"/users/{sales_id}", headers=admin, json={"role": "manager"})).json()["role"] == "manager"
    assert (await client.patch(f"/users/{sales_id}", headers=admin, json={"active": False})).json()["active"] is False
    assert (await client.get("/me", headers=sales)).status_code == 401  # existing token refused at once
    assert (await client.post("/auth/login", json={"email": SALES, "password": "ondra-dev-password"})).status_code == 401
    async with tenant_session(database["a"]) as db:
        live = (await db.execute(text(
            "SELECT count(*) FROM sessions s JOIN users u ON u.id = s.user_id WHERE u.email = :e AND s.revoked_at IS NULL"
        ), {"e": SALES})).scalar()
        assert live == 0

    # Restore.
    assert (await client.patch(f"/users/{sales_id}", headers=admin, json={"active": True, "role": "sales"})).status_code == 200


async def test_mobiles_for_putting_calls_through(client, database):
    owner, admin, sales = await login(client, OWNER), await login(client, ADMIN), await login(client, SALES)
    users = {u["email"]: u for u in (await client.get("/users", headers=admin)).json()["items"]}
    sales_id = users[SALES]["id"]
    # An admin records a salesperson's mobile; it's stored in E.164.
    r = await client.patch(f"/users/{sales_id}", headers=admin, json={"phone": "(469) 555-0188"})
    assert r.status_code == 200 and r.json()["phone"] == "+14695550188" and r.json()["role"] == "sales"
    listed = {u["email"]: u for u in (await client.get("/users", headers=admin)).json()["items"]}
    assert listed[SALES]["phone"] == "+14695550188" and listed[OWNER]["phone"]  # the team list shows them
    assert (await client.patch(f"/users/{sales_id}", headers=admin, json={"phone": "call me"})).status_code == 422
    # Anyone sets their own; nobody changes their own role through it.
    original = (await client.get("/me", headers=owner)).json()["phone"]
    assert (await client.patch("/me", headers=sales, json={"phone": "+1 214 555 0199"})).json()["phone"] == "+12145550199"
    assert (await client.patch(f"/users/{users[OWNER]['id']}", headers=owner, json={"role": "sales"})).status_code == 403
    assert (await client.patch("/me", headers=owner, json={"phone": original})).status_code == 200


async def test_the_team_list_searches_filters_and_pages(client, database):
    admin = await login(client, ADMIN)
    everyone = (await client.get("/users", headers=admin)).json()
    assert everyone["counts"]["status"]["active"] >= 5 and everyone["counts"]["role"]["sales"] >= 1
    found = (await client.get("/users?q=daniel", headers=admin)).json()
    assert [u["email"] for u in found["items"]] == [SALES] and found["total"] == 1
    phone = next(u for u in everyone["items"] if u["email"] == SALES)["phone"]  # E.164, e.g. +12145550199
    formatted = f"({phone[2:5]}) {phone[5:8]}-{phone[8:]}"
    assert [u["email"] for u in (await client.get("/users", headers=admin, params={"q": formatted})).json()["items"]] == [SALES]
    sales_only = (await client.get("/users?role=sales", headers=admin)).json()
    assert sales_only["items"] and all(u["role"] == "sales" for u in sales_only["items"])
    page1 = (await client.get("/users?limit=2&offset=0", headers=admin)).json()
    page2 = (await client.get("/users?limit=2&offset=2", headers=admin)).json()
    assert len(page1["items"]) == 2 and page1["total"] == everyone["total"]
    assert not {u["id"] for u in page1["items"]} & {u["id"] for u in page2["items"]}
    assert (await client.get("/users?status=deactivated", headers=admin)).json()["counts"] == everyone["counts"]
