"""Step 2 acceptance, end to end through the HTTP webhook, Postgres (with RLS) and the mock channel adapters.

The model is a scripted double here: these tests prove the plumbing and the product rules (which never depend on the
model). Whether the model answers well is what evals/ measures, against the real model.
"""

import json
import time
import uuid

import pytest
from ondra_api import channels
from ondra_api.db import tenant_session
from ondra_api import worker
from ondra_api.services import inbound
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import (
    ChannelAddress,
    Consent,
    Contact,
    ContactIdentity,
    Event,
    Message,
    Policy,
    Task,
)
from sqlalchemy import select, text, update

DEALER = "+12145550100"
SIG = {"x-mock-signature": "mock-secret"}


@pytest.fixture
def llm(monkeypatch):
    holder = {}

    def use(script):
        holder["llm"] = ScriptedLLM(script)
        monkeypatch.setattr(inbound, "llm_factory", lambda: holder["llm"])
        return holder["llm"]

    monkeypatch.setattr(inbound, "llm_factory", lambda: holder.get("llm"))
    return use


@pytest.fixture
def outbox():
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    return channels.mock


async def set_draft_mode(tenant_id, on: bool):
    async with tenant_session(tenant_id) as db:
        await db.execute(update(Policy).values(draft_mode=on))


async def contact_named(tenant_id, name):
    async with tenant_session(tenant_id) as db:
        c = (await db.execute(select(Contact).where(Contact.display_name == name))).scalar_one()
        phone = (await db.execute(select(ContactIdentity.value).where(
            ContactIdentity.contact_id == c.id, ContactIdentity.kind == "phone"))).scalar_one()
        return c.id, phone


async def post(client, channel, frm, body, msg_id=None, to=DEALER):
    payload = {"id": msg_id or f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": to, "text": body}
    r = await client.post(f"/webhooks/mock/{channel}", content=json.dumps(payload), headers=SIG)
    await worker.run_once()  # the production path: the webhook queues the AI turn, the worker runs it
    return r


async def messages_for(tenant_id, contact_id):
    async with tenant_session(tenant_id) as db:
        return (await db.execute(text("""
            SELECT m.direction, m.author_type, m.body, m.is_draft, m.status FROM messages m
            JOIN conversations c ON c.id = m.conversation_id WHERE c.contact_id = :c ORDER BY m.created_at
        """), {"c": contact_id})).all()


SEARCH_THEN_REPLY = [
    [("search_inventory", {"query": "highlander"})],
    "We don't have a Highlander right now. Want me to look for another 3-row SUV?",
]


async def test_whatsapp_message_gets_an_ai_reply_fast(client, database, llm, outbox):
    t = database["a"]
    await set_draft_mode(t, False)
    cid, phone = await _any_regular_contact(t)
    script = llm(list(SEARCH_THEN_REPLY))
    started = time.monotonic()
    r = await post(client, "whatsapp", phone, "is the highlander still available?")
    elapsed = time.monotonic() - started
    assert r.status_code == 200 and r.json()["stored"] == 1
    assert elapsed < 5, elapsed  # plumbing budget; real-model latency is measured by the eval runner
    [sent] = outbox("whatsapp").outbox
    assert sent.to_address == phone and sent.from_address == DEALER and "Highlander" in sent.body
    rows = await messages_for(t, cid)
    assert [(d, a, s) for d, a, _, _, s in rows][-2:] == [("inbound", "customer", "received"), ("outbound", "ai", "sent")]
    assert len(script.requests) == 2


async def _any_regular_contact(t):
    async with tenant_session(t) as db:
        row = (await db.execute(text("""
            SELECT c.id, i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id AND i.kind = 'phone'
            WHERE NOT c.is_vip AND NOT EXISTS (SELECT 1 FROM consents s WHERE s.contact_id = c.id AND s.status = 'opted_out')
            ORDER BY c.display_name LIMIT 1
        """))).one()
        return row.id, row.value


async def test_duplicate_webhooks_are_processed_once(client, database, llm, outbox):
    t = database["a"]
    await set_draft_mode(t, False)
    cid, phone = await _any_regular_contact(t)
    llm(list(SEARCH_THEN_REPLY))
    first = await post(client, "sms", phone, "highlander?", msg_id="dup-1")
    again = await post(client, "sms", phone, "highlander?", msg_id="dup-1")
    assert first.json() == {"stored": 1, "duplicates": 0} and again.json() == {"stored": 0, "duplicates": 1}
    assert len(outbox("sms").outbox) == 1


async def test_vip_gets_no_ai_and_the_owner_is_alerted(client, database, llm, outbox):
    t = database["a"]
    await set_draft_mode(t, False)
    cid, phone = await contact_named(t, "Robert Hale")
    script = llm(["this must never be used"])
    r = await post(client, "sms", phone, "Sam, call me about the Range Rover")
    assert r.status_code == 200
    assert script.requests == []  # the model was never called
    assert outbox("sms").outbox == []
    rows = await messages_for(t, cid)
    assert not any(author == "ai" for _, author, *_ in rows)  # no AI reply, no AI draft (people may reply)
    async with tenant_session(t) as db:
        task = (await db.execute(select(Task).where(Task.contact_id == cid).order_by(Task.created_at.desc()))).scalars().first()
        owner = (await db.execute(text("SELECT id FROM users WHERE role = 'owner'"))).scalar_one()
        vip_owner = (await db.get(Contact, cid)).vip_owner_user_id
        alerts = (await db.execute(select(Event).where(Event.type == "alert.created"))).scalars().all()
    assert task.urgency == "high" and task.source == "rule" and task.assignee_user_id in (vip_owner, owner)
    assert any(a.payload["contact_id"] == str(cid) and a.payload["to"] == "owner" for a in alerts)


async def test_draft_mode_stores_a_draft_and_sends_nothing(client, database, llm, outbox):
    t = database["a"]
    await set_draft_mode(t, True)
    cid, phone = await _any_regular_contact(t)
    llm(list(SEARCH_THEN_REPLY))
    await post(client, "sms", phone, "any highlanders?")
    assert outbox("sms").outbox == []
    *_, last = await messages_for(t, cid)
    assert last.direction == "outbound" and last.author_type == "ai" and last.is_draft and last.status == "queued"
    await set_draft_mode(t, False)


async def test_stop_opts_out_on_every_channel_and_blocks_later_ai(client, database, llm, outbox):
    t = database["a"]
    await set_draft_mode(t, False)
    cid, phone = await _any_regular_contact(t)
    script = llm(["never used"])
    await post(client, "sms", phone, "STOP")
    async with tenant_session(t) as db:
        statuses = (await db.execute(select(Consent.channel, Consent.status).where(
            Consent.contact_id == cid, Consent.source == "keyword:sms"))).all()
    assert {c for c, s in statuses if s == "opted_out"} == {"sms", "whatsapp", "email", "phone"}
    # Writing again on WhatsApp: still no AI and nothing sent, but a person is told.
    await post(client, "whatsapp", phone, "actually is the civic still there")
    assert script.requests == [] and outbox("sms").outbox == [] and outbox("whatsapp").outbox == []
    async with tenant_session(t) as db:
        tasks = (await db.execute(select(Task).where(Task.contact_id == cid, Task.source == "rule"))).scalars().all()
        assert tasks
    # Opt back in, so later tests can use this contact.
    await post(client, "sms", phone, "START")
    async with tenant_session(t) as db:
        assert not await inbound.contact_opted_out(db, cid)


async def test_new_number_creates_a_contact(client, database, llm, outbox):
    t = database["a"]
    await set_draft_mode(t, False)
    llm(list(SEARCH_THEN_REPLY))
    await post(client, "sms", "(469) 555-0199", "hi do u have highlanders")
    async with tenant_session(t) as db:
        ident = (await db.execute(select(ContactIdentity).where(ContactIdentity.value == "+14695550199"))).scalar_one()
        assert ident.kind == "phone"
        await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": ident.contact_id})  # keep seed counts exact
    assert len(outbox("sms").outbox) == 1


async def test_bad_signature_and_unknown_address(client, database, llm, outbox):
    r = await client.post("/webhooks/mock/sms", content=b'{"id":"x","from":"+1","to":"+1","text":"hi"}',
                          headers={"x-mock-signature": "wrong"})
    assert r.status_code == 403
    script = llm(["never used"])
    r = await post(client, "sms", "+12145550101", "hi", to="+19995550000")
    assert r.status_code == 200 and r.json()["stored"] == 0 and script.requests == []


async def test_inbound_lands_only_in_the_dealer_that_owns_the_number(client, database, llm, outbox):
    a, b = database["a"], database["b"]
    async with tenant_session(b) as db:
        if not (await db.execute(select(ChannelAddress))).first():
            db.add(ChannelAddress(channel="sms", address="+19725550100", provider="mock"))
    await set_draft_mode(b, False)
    script = llm([[("search_inventory", {})], "Yes, the Telluride is here."])
    await post(client, "sms", "+12145559876", "telluride?", to="+19725550100")
    # Tenant B's inventory tool returned tenant B's stock only.
    tool_output = script.requests[1]["messages"][-1]["content"][0]["content"]
    assert "Telluride" in tool_output and "Highlander" not in tool_output and "Silverado" not in tool_output
    async with tenant_session(b) as db:
        ident = (await db.execute(select(ContactIdentity).where(ContactIdentity.value == "+12145559876"))).scalar_one()
        await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": ident.contact_id})
    async with tenant_session(a) as db:
        assert (await db.execute(select(ContactIdentity).where(ContactIdentity.value == "+12145559876"))).first() is None


async def test_tools_in_tenant_a_never_see_tenant_b_stock(database):
    from ondra_api.services.agent_tools import DbToolBackend

    async with tenant_session(database["a"]) as db:
        contact = (await db.execute(select(Contact).limit(1))).scalar_one()
        backend = DbToolBackend(db, contact=contact, conversation=None, price_disclosure="listed", open_now=False)
        assert await backend.search_inventory(make="Kia", model="Telluride") == []
        hits = await backend.search_knowledge("opening hours on sunday")  # the mock embedder matches words, not meaning
        assert hits and hits[0]["title"] == "Opening hours"


async def test_price_policy_none_hides_prices_from_the_model(database):
    from ondra_api.services.agent_tools import DbToolBackend

    async with tenant_session(database["a"]) as db:
        contact = (await db.execute(select(Contact).limit(1))).scalar_one()
        backend = DbToolBackend(db, contact=contact, conversation=None, price_disclosure="none", open_now=False)
        cars = await backend.search_inventory()
        assert cars and all("price" not in c for c in cars)


async def test_messages_table_is_unchanged_in_shape(database):
    # Guard: inbound messages from the webhook are stored with the provider's id for idempotency.
    async with tenant_session(database["a"]) as db:
        ids = (await db.execute(select(Message.provider_message_id).where(Message.direction == "inbound"))).scalars().all()
        assert ids and len(ids) == len(set(ids))


async def test_knowledge_search_is_semantic_scoped_and_admits_ignorance(database):
    """With the local mock embedder: answers were embedded at seed time, unrelated questions return nothing
    (so the AI hands off), and another dealer's answers are invisible."""
    from ondra_api.services import knowledge

    async with tenant_session(database["a"]) as db:
        spaces = (await db.execute(text("SELECT DISTINCT embedding_space FROM knowledge_docs"))).scalars().all()
        assert spaces == ["hash-v1"]
        assert (await knowledge.search(db, "what are your opening hours on sunday"))[0]["title"] == "Opening hours"
        assert await knowledge.search(db, "do you install lift kits") == []
    async with tenant_session(database["b"]) as db:
        assert await knowledge.search(db, "what are your opening hours") == []


async def test_knowledge_search_falls_back_to_full_text_when_embeddings_fail(database):
    from ondra_api.services import knowledge

    class Down:
        space = "voyage-4"

        async def embed(self, texts, input_type):
            raise ConnectionError("voyage unreachable")

    async with tenant_session(database["a"]) as db:
        hits = await knowledge.search(db, "parking", emb=Down())
        assert hits and hits[0]["title"] == "Location and parking"
