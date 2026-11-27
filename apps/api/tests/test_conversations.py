"""The inbox API: a person can see what needs them, approve or edit Ondra's drafts, reply, take over and hand back.
Product rules hold here too: opt-outs block staff replies, VIPs stay with people and stay hidden from roles that
can't see them, and another dealer's conversations don't exist."""

import json
import uuid

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import inbound
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import Conversation, Event, Message, Policy
from sqlalchemy import select, text, update

from .conftest import login

SIG = {"x-mock-signature": "mock-secret"}
OWNER, SALES = "owner@prestigemotors.example", "daniel@prestigemotors.example"


@pytest.fixture
def outbox():
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    return channels.mock("sms").outbox


async def _customer_writes(client, monkeypatch, frm, body, reply="Thanks for your message. Let me check that for you."):
    monkeypatch.setattr(inbound, "llm_factory", lambda: ScriptedLLM([reply]))
    msg = {"id": f"conv-{uuid.uuid4().hex[:8]}", "from": frm, "to": "+12145550100", "text": body}
    await client.post("/webhooks/mock/sms", content=json.dumps(msg), headers=SIG)
    await worker.run_once()


async def _conversation_for(client, headers, name):
    items = (await client.get("/conversations", headers=headers)).json()["items"]
    return next(c for c in items if c["contact"]["name"] == name)


async def _regular_contact(tenant_id):
    async with tenant_session(tenant_id) as db:
        return (await db.execute(text("""
            SELECT c.display_name, i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id AND i.kind = 'phone'
            WHERE NOT c.is_vip AND NOT EXISTS (SELECT 1 FROM consents s WHERE s.contact_id = c.id AND s.status = 'opted_out')
              AND NOT EXISTS (SELECT 1 FROM conversations v WHERE v.contact_id = c.id)
            ORDER BY c.display_name LIMIT 1
        """))).one()


async def test_draft_shows_as_needing_you_then_edit_and_approve_sends_it(client, database, monkeypatch, outbox):
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Policy).values(draft_mode=True))
    name, phone = await _regular_contact(database["a"])
    await _customer_writes(client, monkeypatch, phone, "is the highlander still there?")
    owner = await login(client, OWNER)

    lst = (await client.get("/conversations?view=needs", headers=owner)).json()
    conv = next(c for c in lst["items"] if c["contact"]["name"] == name)
    assert conv["reason"] == "Draft to approve" and conv["last_message"]["is_draft"] is True
    assert lst["counts"]["needs"] >= 1 and outbox == []

    detail = (await client.get(f"/conversations/{conv['id']}", headers=owner)).json()
    draft = next(m for m in detail["messages"] if m["is_draft"])
    edited = "Yes, the 2021 Highlander XLE is here, listed at $33,900. Want to see it Saturday?"
    r = await client.post(f"/messages/{draft['id']}/approve", headers=owner, json={"body": edited})
    assert r.status_code == 200, r.text
    assert [m.body for m in outbox] == [edited]
    async with tenant_session(database["a"]) as db:
        m = await db.get(Message, uuid.UUID(draft["id"]))
        assert m.status == "sent" and not m.is_draft and m.author_type == "ai"
        ev = (await db.execute(select(Event).where(Event.type == "draft.edited"))).scalars().all()
        assert any(e.payload["message_id"] == draft["id"] and e.payload["after"] == edited for e in ev)
    # Approved once: approving again finds no draft.
    assert (await client.post(f"/messages/{draft['id']}/approve", headers=owner, json={})).status_code == 404
    after = await _conversation_for(client, owner, name)
    assert after["bucket"] == "ondra"


async def test_discard_and_staff_reply_supersedes_the_draft(client, database, monkeypatch, outbox):
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Policy).values(draft_mode=True))
    name, phone = await _regular_contact(database["a"])
    await _customer_writes(client, monkeypatch, phone, "do you have tacomas")
    sales = await login(client, SALES)
    conv = await _conversation_for(client, sales, name)
    draft = next(m for m in (await client.get(f"/conversations/{conv['id']}", headers=sales)).json()["messages"] if m["is_draft"])
    assert (await client.post(f"/messages/{draft['id']}/discard", headers=sales)).status_code == 204
    assert (await client.post(f"/messages/{draft['id']}/discard", headers=sales)).status_code == 404

    await _customer_writes(client, monkeypatch, phone, "hello?")
    r = await client.post(f"/conversations/{conv['id']}/reply", headers=sales, json={"body": "Hi, Daniel here. We have one Tacoma."})
    assert r.status_code == 201
    msgs = (await client.get(f"/conversations/{conv['id']}", headers=sales)).json()["messages"]
    assert not any(m["is_draft"] for m in msgs)  # the waiting draft was superseded
    assert msgs[-1]["author"] == "user" and msgs[-1]["author_name"] == "Daniel Okafor" and msgs[-1]["status"] == "sent"
    assert outbox[-1].body == "Hi, Daniel here. We have one Tacoma."


async def test_opted_out_contacts_cannot_be_messaged_by_staff(client, database, monkeypatch, outbox):
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Policy).values(draft_mode=False))
    name, phone = await _regular_contact(database["a"])
    await _customer_writes(client, monkeypatch, phone, "is the civic there")
    await _customer_writes(client, monkeypatch, phone, "STOP")
    owner = await login(client, OWNER)
    conv = await _conversation_for(client, owner, name)
    assert (await client.get(f"/conversations/{conv['id']}", headers=owner)).json()["contact"]["opted_out"] is True
    sent_before = len(outbox)
    r = await client.post(f"/conversations/{conv['id']}/reply", headers=owner, json={"body": "Just checking in!"})
    assert r.status_code == 409 and "opted out" in r.json()["detail"]
    assert len(outbox) == sent_before
    await _customer_writes(client, monkeypatch, phone, "START")


async def test_take_over_stops_the_ai_and_hand_back_restores_it(client, database, monkeypatch, outbox):
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Policy).values(draft_mode=False))
    name, phone = await _regular_contact(database["a"])
    await _customer_writes(client, monkeypatch, phone, "highlander?")
    sales = await login(client, SALES)
    conv = await _conversation_for(client, sales, name)
    assert (await client.post(f"/conversations/{conv['id']}/takeover", headers=sales)).json()["ai_mode"] == "off"

    script = ScriptedLLM(["must not be used"])
    monkeypatch.setattr(inbound, "llm_factory", lambda: script)
    msg = {"id": f"to-{uuid.uuid4().hex[:8]}", "from": phone, "to": "+12145550100", "text": "still there?"}
    await client.post("/webhooks/mock/sms", content=json.dumps(msg), headers=SIG)
    await worker.run_once()
    assert script.requests == []  # Ondra stayed out
    assert (await _conversation_for(client, sales, name))["bucket"] == "needs"

    assert (await client.post(f"/conversations/{conv['id']}/handback", headers=sales)).json()["ai_mode"] == "auto"


async def test_vips_stay_with_people_and_are_hidden_from_sales(client, database, monkeypatch, outbox):
    async with tenant_session(database["a"]) as db:
        phone = (await db.execute(text(
            "SELECT i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id AND i.kind = 'phone' "
            "WHERE c.display_name = 'Robert Hale'"))).scalar_one()
    await _customer_writes(client, monkeypatch, phone, "call me about the range rover")
    owner, sales = await login(client, OWNER), await login(client, SALES)
    conv = await _conversation_for(client, owner, "Robert Hale")
    assert conv["reason"] == "VIP waiting for you" and conv["contact"]["is_vip"]
    detail = (await client.get(f"/conversations/{conv['id']}", headers=owner)).json()
    assert detail["brief"] is None and not any(m["author"] == "ai" for m in detail["messages"])
    assert all(c["contact"]["name"] != "Robert Hale" for c in (await client.get("/conversations", headers=sales)).json()["items"])
    assert (await client.get(f"/conversations/{conv['id']}", headers=sales)).status_code == 404
    assert (await client.post(f"/conversations/{conv['id']}/handback", headers=owner)).status_code == 409
    # The owner can still reply personally.
    assert (await client.post(f"/conversations/{conv['id']}/reply", headers=owner, json={"body": "Robert, calling you now."})).status_code == 201


async def test_another_dealers_conversations_do_not_exist(client, database):
    async with tenant_session(database["a"]) as db:
        conv_id = (await db.execute(select(Conversation.id).limit(1))).scalar_one()
    from ondra_api.security import hash_password
    from ondra_core.models import User

    async with tenant_session(database["b"]) as db:
        u = (await db.execute(select(User).where(User.email == "owner@lonestar.example"))).scalar_one()
        u.password_hash = u.password_hash or hash_password("ondra-dev-password")
    b_owner = await login(client, "owner@lonestar.example")
    assert (await client.get(f"/conversations/{conv_id}", headers=b_owner)).status_code == 404
    assert all(c["id"] != str(conv_id) for c in (await client.get("/conversations", headers=b_owner)).json()["items"])
    assert (await client.post(f"/conversations/{conv_id}/reply", headers=b_owner, json={"body": "hi"})).status_code == 404


async def test_saved_view_facts_drafts_and_after_hours_leads(client, database, monkeypatch, outbox):
    """The sidebar's saved views filter on these: drafts waiting, and leads that came in while the dealer was closed
    (in the last week only)."""
    from datetime import UTC, datetime, timedelta

    async with tenant_session(database["a"]) as db:
        await db.execute(update(Policy).values(draft_mode=True))
    name, phone = await _regular_contact(database["a"])
    await _customer_writes(client, monkeypatch, phone, "do you have any trucks under 30k?")
    owner = await login(client, OWNER)
    row = await _conversation_for(client, owner, name)
    assert row["drafts"] == 1 and row["after_hours_lead"] is False

    async with tenant_session(database["a"]) as db:
        db.add(Event(type="lead.captured", occurred_at=datetime.now(UTC) - timedelta(days=9),
                     payload={"contact_id": row["contact"]["id"], "after_hours": True}))
    assert (await _conversation_for(client, owner, name))["after_hours_lead"] is False  # too old

    async with tenant_session(database["a"]) as db:
        db.add(Event(type="lead.captured", payload={"contact_id": row["contact"]["id"], "after_hours": False}))
    assert (await _conversation_for(client, owner, name))["after_hours_lead"] is False  # came in while open

    async with tenant_session(database["a"]) as db:
        db.add(Event(type="lead.captured", payload={"contact_id": row["contact"]["id"], "after_hours": True}))
    assert (await _conversation_for(client, owner, name))["after_hours_lead"] is True
