"""Follow-up sequences and quiet hours, through the real send path, job runner and Postgres. Includes the Step 6
acceptance check: STOP on SMS blocks all outbound to that contact, on every channel, follow-ups included."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import follow_ups, inbound
from ondra_api.services.outbound import Blocked, deliver
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import (
    Consent,
    Contact,
    Conversation,
    FollowUp,
    FollowUpSequence,
    Job,
    Message,
    Policy,
    Task,
)
from sqlalchemy import delete, select, text, update

from tests.conftest import login

DEALER = "+12145550100"
SIG = {"x-mock-signature": "mock-secret"}
# Noon in Chicago today: outside the default quiet hours (9 pm to 8 am), whenever the tests run.
NOON = datetime.now(UTC).replace(hour=18, minute=0, second=0, microsecond=0)
NIGHT = NOON.replace(hour=5)  # 11 pm in Chicago
TWO_STEPS = [{"after_hours": 24, "write": "ondra", "text": "", "require_approval": True},
             {"after_hours": 72, "write": "text", "text": "Hi {first_name}, {dealership} here. Still looking?", "require_approval": False}]


@pytest.fixture
async def desk(client, database, monkeypatch):
    """Tenant A sending for real (draft mode off), with one follow-up sequence. Put back afterwards."""
    t = database["a"]
    holder = {}
    monkeypatch.setattr(inbound, "llm_factory", lambda: holder.get("llm"))
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    started = datetime.now(UTC)
    created: list[str] = []
    async with tenant_session(t) as db:
        draft_before = (await db.execute(select(Policy.draft_mode))).scalar_one()
        quiet_before = (await db.execute(select(Policy.quiet_hours))).scalar_one()
        await db.execute(update(Policy).values(draft_mode=False, quiet_hours={}))
        seq = FollowUpSequence(name="Quiet buyers", steps=TWO_STEPS, topics=[])
        db.add(seq)
        await db.flush()
        seq_id = seq.id

    class Desk:
        tenant = t
        sequence_id = seq_id

        def script(self, *steps):
            holder["llm"] = ScriptedLLM(list(steps))
            return holder["llm"]

        async def writes(self, body, *, channel="sms", frm=None, reply="Yes, the Highlander is here. Want to come see it?"):
            """A customer writes and Ondra replies (scripted). Returns their number."""
            if frm is None:
                frm = f"+1972555{uuid.uuid4().int % 9000 + 1000}"
                created.append(frm)
            if reply is not None:
                self.script(reply)
            r = await client.post(f"/webhooks/mock/{channel}", headers=SIG,
                                  content=json.dumps({"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": DEALER, "text": body}))
            assert r.status_code == 200, r.text
            await worker.run_once()
            return frm

        async def contact(self, frm) -> uuid.UUID:
            async with tenant_session(t) as db:
                return (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = :v LIMIT 1"), {"v": frm})).scalar_one()

        async def consent(self, frm, channel="sms"):
            async with tenant_session(t) as db:
                db.add(Consent(contact_id=await self.contact(frm), channel=channel, purpose="transactional", status="opted_in", source="test"))

        async def follow_ups(self, frm) -> list[FollowUp]:
            async with tenant_session(t) as db:
                return list((await db.execute(select(FollowUp).where(FollowUp.contact_id == await self.contact(frm))
                                              .order_by(FollowUp.created_at, FollowUp.step))).scalars())

        async def due(self, frm, now=NOON) -> str:
            fu = next(f for f in await self.follow_ups(frm) if f.status == "scheduled")
            return await follow_ups.run(t, {"follow_up_id": str(fu.id)}, now=now)

        async def thread(self, frm):
            async with tenant_session(t) as db:
                return (await db.execute(text("""SELECT m.direction, m.author_type, m.body, m.is_draft, m.status, m.id FROM messages m
                    JOIN conversations c ON c.id = m.conversation_id WHERE c.contact_id = :c ORDER BY m.created_at"""),
                                         {"c": await self.contact(frm)})).all()

    yield Desk()
    async with tenant_session(t) as db:
        await db.execute(delete(FollowUpSequence))  # their follow-ups cascade
        invented = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = ANY(:v)"), {"v": created})).scalars().all()
        await db.execute(delete(Task).where(Task.contact_id.in_(invented)))
        await db.execute(delete(Task).where(Task.created_at > started, Task.source == "rule"))
        await db.execute(delete(Contact).where(Contact.id.in_(invented)))
        await db.execute(delete(Job).where(Job.kind == "follow_up"))
        await db.execute(update(Policy).values(draft_mode=draft_before, quiet_hours=quiet_before))


async def test_a_quiet_customer_gets_a_draft_to_approve_then_the_next_step(client, desk):
    frm = await desk.writes("Is the Highlander still available?")
    await desk.consent(frm)
    [first] = await desk.follow_ups(frm)
    assert (first.step, first.status) == (0, "scheduled")
    assert timedelta(hours=23) < first.due_at - datetime.now(UTC) < timedelta(hours=36)  # 24 h, pushed past quiet hours
    async with tenant_session(desk.tenant) as db:
        job = (await db.execute(select(Job).where(Job.kind == "follow_up", Job.payload["follow_up_id"].astext == str(first.id)))).scalar_one()
        assert job.run_at == first.due_at

    llm = desk.script("Hi, it's Prestige Motors. The Highlander you asked about is still here. Would Saturday suit you to come see it?")
    assert await desk.due(frm) == "drafted"
    assert "went quiet" in llm.requests[0]["system"][0]["text"] and llm.requests[0]["tools"] == []
    *_, draft = await desk.thread(frm)
    assert (draft.author_type, draft.is_draft) == ("ai", True) and channels.mock("sms").outbox[1:] == []  # only the first reply went out
    assert (await desk.follow_ups(frm))[0].status == "awaiting_approval"

    owner = await login(client, "owner@prestigemotors.example")
    r = await client.post(f"/messages/{draft.id}/approve", json={}, headers=owner)
    assert r.status_code == 200, r.text
    assert "Highlander" in channels.mock("sms").outbox[-1].body
    one, two = await desk.follow_ups(frm)
    assert (one.status, two.step, two.status) == ("sent", 1, "scheduled")
    assert timedelta(hours=71) < two.due_at - datetime.now(UTC) < timedelta(hours=84)

    # Step 2 is a fixed message that needs no approval: it goes straight out, with their name filled in.
    assert await desk.due(frm) == "sent"
    assert channels.mock("sms").outbox[-1].body == "Hi there, Prestige Motors here. Still looking?"  # no name on file
    assert [f.status for f in await desk.follow_ups(frm)] == ["sent", "sent"]  # the sequence is finished


async def test_a_reply_from_the_customer_stops_the_sequence_and_drops_a_waiting_draft(desk):
    frm = await desk.writes("Do you have any F-150s?")
    await desk.consent(frm)
    desk.script("Still thinking about an F-150? We have a few on the lot.")
    assert await desk.due(frm) == "drafted"
    await desk.writes("Sorry, was busy. Yes still interested", frm=frm, reply="Good to hear. Want to come by this week?")
    first, fresh = await desk.follow_ups(frm)
    assert (first.status, first.reason) == ("cancelled", "replied")
    assert (fresh.step, fresh.status) == (0, "scheduled")  # the clock restarted from Ondra's new reply
    assert not any(m.is_draft for m in await desk.thread(frm))  # the stale follow-up draft is gone


async def test_stop_on_sms_blocks_all_outbound_on_every_channel(client, desk):
    """Step 6 acceptance."""
    async with tenant_session(desk.tenant) as db:
        cid, phone = (await db.execute(text("""SELECT c.id, i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id
            AND i.kind = 'phone' WHERE NOT c.is_vip AND c.preferred_channel = 'whatsapp' AND NOT EXISTS (SELECT 1 FROM consents s
            WHERE s.contact_id = c.id AND s.status = 'opted_out') ORDER BY c.display_name LIMIT 1"""))).one()
    await desk.writes("Is the Camry still for sale?", frm=phone, channel="sms")
    await desk.writes("Also asking here", frm=phone, channel="whatsapp", reply="Yes, on WhatsApp too.")
    live = [f for f in await desk.follow_ups(phone) if f.status == "scheduled"]
    assert len(live) == 1  # one follow-up per customer, on the channel they wrote on last, not one per channel
    sent_before = {ch: len(channels.mock(ch).outbox) for ch in channels.CHANNELS}

    llm = desk.script("must not be used")
    await desk.writes("STOP", frm=phone, channel="sms", reply=None)
    assert llm.requests == []
    assert all(f.status == "cancelled" for f in await desk.follow_ups(phone))
    assert await follow_ups.run(desk.tenant, {"follow_up_id": str(live[0].id)}, now=NOON) == "skipped: not scheduled"
    async with tenant_session(desk.tenant) as db:
        latest = (await db.execute(text("""SELECT DISTINCT ON (channel) channel, status FROM consents WHERE contact_id = :c
                                            ORDER BY channel, captured_at DESC, created_at DESC"""), {"c": cid})).all()
        assert {ch: st for ch, st in latest} == {"sms": "opted_out", "whatsapp": "opted_out", "email": "opted_out", "phone": "opted_out"}
        convs = {c.channel: c.id for c in (await db.execute(select(Conversation).where(Conversation.contact_id == cid))).scalars()}

    # A person can't message them either, on any channel; nor can a reminder or a late follow-up.
    owner = await login(client, "owner@prestigemotors.example")
    for channel in ("sms", "whatsapp"):
        r = await client.post(f"/conversations/{convs[channel]}/reply", json={"body": "Just one more thing"}, headers=owner)
        assert r.status_code == 409 and "opted out" in r.json()["detail"]
    async with tenant_session(desk.tenant) as db:
        m = Message(conversation_id=convs["whatsapp"], direction="outbound", author_type="system", body="Reminder", status="queued")
        db.add(m)
        await db.flush()
        mid = m.id
    with pytest.raises(Blocked):
        await deliver(desk.tenant, mid)
    # A later message from them gets no AI reply; a person is told.
    await desk.writes("Actually is it still there?", frm=phone, channel="whatsapp", reply=None)
    assert llm.requests == []
    assert {ch: len(channels.mock(ch).outbox) for ch in channels.CHANNELS} == sent_before  # nothing left the building

    async with tenant_session(desk.tenant) as db:  # put the seeded contact back as they were
        await db.execute(text("DELETE FROM consents WHERE contact_id = :c AND source LIKE 'keyword:%'"), {"c": cid})
        await db.execute(text("DELETE FROM tasks WHERE contact_id = :c AND created_at > now() - interval '5 minutes'"), {"c": cid})
        await db.execute(text("DELETE FROM messages WHERE conversation_id = ANY(:ids) AND created_at > now() - interval '5 minutes'"),
                         {"ids": list(convs.values())})


async def test_no_recorded_consent_means_a_person_follows_up_not_ondra(desk):
    frm = await desk.writes("How much is the Tahoe?")  # a new number: nothing on file says we may text them first
    llm = desk.script("must not be used")
    assert (await desk.due(frm)).startswith("needs_person: no recorded consent")
    assert llm.requests == [] and len(channels.mock("sms").outbox) == 1  # only the original reply
    async with tenant_session(desk.tenant) as db:
        task = (await db.execute(select(Task).where(Task.contact_id == await desk.contact(frm)).order_by(Task.created_at.desc()).limit(1))).scalar_one()
    assert "follow up" in task.title and "no recorded consent" in task.brief and task.urgency == "low"
    assert [f.status for f in await desk.follow_ups(frm)] == ["needs_person"]


async def test_nothing_is_sent_in_quiet_hours(client, desk):
    frm = await desk.writes("Any Accords in stock?")
    await desk.consent(frm)
    assert await desk.due(frm, now=NIGHT) == "deferred: quiet hours"
    [fu] = await desk.follow_ups(frm)
    assert fu.status == "scheduled" and fu.due_at == NIGHT.replace(hour=14)  # 8 am Chicago, when quiet hours end
    # The dealer's own quiet hours apply once set.
    owner = await login(client, "owner@prestigemotors.example")
    r = await client.put("/follow-ups/quiet-hours", json={"start": "11:00", "end": "13:00"}, headers=owner)
    assert r.status_code == 200
    assert await desk.due(frm, now=NOON) == "deferred: quiet hours"  # noon is now inside them
    assert len(channels.mock("sms").outbox) == 1


async def test_a_vip_is_never_enrolled_and_a_person_taking_over_stops_it(client, desk):
    async with tenant_session(desk.tenant) as db:
        vip_conv = (await db.execute(text("""SELECT cv.id FROM conversations cv JOIN contacts c ON c.id = cv.contact_id
                                              WHERE c.is_vip AND cv.channel <> 'phone' LIMIT 1"""))).scalar_one()
    owner = await login(client, "owner@prestigemotors.example")
    r = await client.post(f"/conversations/{vip_conv}/reply", json={"body": "I'll call you at 3."}, headers=owner)
    assert r.status_code == 201, r.text
    async with tenant_session(desk.tenant) as db:
        assert (await db.execute(select(FollowUp).where(FollowUp.conversation_id == vip_conv))).scalars().all() == []
        await db.execute(text("DELETE FROM messages WHERE conversation_id = :c AND body = 'I''ll call you at 3.'"), {"c": vip_conv})

    frm = await desk.writes("Is the Silverado available?")
    await desk.consent(frm)
    async with tenant_session(desk.tenant) as db:
        conv = (await db.execute(select(Conversation.id).where(Conversation.contact_id == await desk.contact(frm)))).scalar_one()
    assert (await client.post(f"/conversations/{conv}/takeover", headers=owner)).status_code == 200
    assert await desk.due(frm) == "cancelled: person_handling"


async def test_ondras_follow_up_is_checked_and_can_decline_to_write(desk):
    # It tries to offer money off: the draft is thrown away. Step 1 has no fixed text to fall back on, so nothing is sent.
    frm = await desk.writes("What's your best price on the Camry?", reply="I've passed that to our sales team.")
    await desk.consent(frm)
    desk.script("Good news, we can take $500 off the Camry if you come in this week!")
    assert await desk.due(frm) == "cancelled: nothing_to_say"
    # Ondra judges there's nothing to follow up on.
    other = await desk.writes("Thanks, I bought one elsewhere", reply="Congratulations, enjoy it.")
    await desk.consent(other)
    desk.script("SKIP")
    assert await desk.due(other) == "cancelled: nothing_to_say"
    assert len(channels.mock("sms").outbox) == 2  # the two original replies, no follow-ups


async def test_whatsapp_follow_ups_need_the_24_hour_window(desk):
    frm = await desk.writes("Hola, tienen camionetas?", channel="whatsapp", reply="Si, tenemos varias.")
    await desk.consent(frm, "whatsapp")
    async with tenant_session(desk.tenant) as db:
        await db.execute(update(Conversation).where(Conversation.contact_id == await desk.contact(frm))
                         .values(last_inbound_at=NOON - timedelta(hours=30)))
    assert "24-hour window" in await desk.due(frm)
    assert len(channels.mock("whatsapp").outbox) == 1


async def test_sequences_api_permissions_validation_and_isolation(client, database, desk):
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    got = (await client.get("/follow-ups", headers=sales)).json()
    assert [s["name"] for s in got["sequences"]] == ["Quiet buyers"] and got["can_edit"] is False
    assert got["quiet_hours"] == {"start": "21:00", "end": "08:00"}  # the default until the dealer sets their own
    body = {"name": "Service check-in", "topics": ["service"], "steps": [{"after_hours": 48, "write": "text", "text": "Hi {first_name}"}]}
    assert (await client.post("/follow-ups", json=body, headers=sales)).status_code == 403
    made = (await client.post("/follow-ups", json=body, headers=owner)).json()
    assert made["steps"][0]["require_approval"] is True  # approval is the default
    bad = await client.post("/follow-ups", json={**body, "steps": [{"after_hours": 48, "write": "text", "text": " "}]}, headers=owner)
    assert bad.status_code == 422 and "write the message" in bad.json()["detail"]
    assert (await client.post("/follow-ups", json={**body, "steps": []}, headers=owner)).status_code == 422
    assert (await client.put("/follow-ups/quiet-hours", json={"start": "9pm", "end": "08:00"}, headers=owner)).status_code == 422
    off = (await client.put(f"/follow-ups/{made['id']}", json={**body, "active": False}, headers=owner)).json()
    assert off["active"] is False
    assert (await client.delete(f"/follow-ups/{made['id']}", headers=owner)).status_code == 204
    other = await login(client, "owner@lonestar.example")
    assert (await client.get("/follow-ups", headers=other)).json()["sequences"] == []  # never another dealer's
    async with tenant_session(database["b"]) as db:
        assert (await db.execute(select(FollowUp))).scalars().all() == []
