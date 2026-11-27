"""Step 8: the owner's WhatsApp line. Includes both acceptance checks: the briefing arrives at the configured local
time with correct counts; a voice note updates the right client and creates a task."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import briefing, inbound, owner_assistant
from ondra_api.services.owner import deliver_alert, send_to_owner
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import (
    Appointment,
    AppointmentType,
    AssistantMessage,
    Contact,
    Conversation,
    Deal,
    Job,
    Message,
    Task,
    Tenant,
    User,
)
from sqlalchemy import delete, select, text, update

DEALER = "+12145550100"
OWNER = "+12145559000"  # the owner's own mobile, as set in Settings > Team
SIG = {"x-mock-signature": "mock-secret"}
CHI = ZoneInfo("America/Chicago")


@pytest.fixture
async def line(client, database, monkeypatch):
    t = database["a"]
    holder = {}
    monkeypatch.setattr(owner_assistant, "llm_factory", lambda: holder.get("llm"))
    monkeypatch.setattr(inbound, "llm_factory", lambda: holder.get("customer_llm"))
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    started = datetime.now(UTC)
    async with tenant_session(t) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        settings_before = dict(tenant.settings or {})
        owner = (await db.execute(select(User).where(User.role == "owner"))).scalar_one()
        phone_before, owner_id = owner.phone, owner.id
        owner.phone = OWNER
        await db.execute(delete(Job).where(Job.kind.in_(("owner_alert", "owner_briefing", "assistant_turn"))))

    class Line:
        tenant = t
        owner = owner_id

        def script(self, *steps):
            holder["llm"] = ScriptedLLM(list(steps))
            return holder["llm"]

        async def owner_sends(self, text_="", *, voice=None, button=None, frm=OWNER, channel="whatsapp"):
            payload = {"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": DEALER, "text": text_}
            if voice:
                payload["voice"] = voice
            if button:
                payload["button"] = button
            r = await client.post(f"/webhooks/mock/{channel}", headers=SIG, content=json.dumps(payload))
            assert r.status_code == 200, r.text
            await worker.run_once()
            return r.json()

        def to_owner(self):
            return [m for m in channels.mock("whatsapp").outbox if m.to_address == OWNER]

        async def thread(self):
            async with tenant_session(t) as db:
                return list((await db.execute(select(AssistantMessage).where(AssistantMessage.user_id == owner_id, AssistantMessage.created_at >= started)
                                              .order_by(AssistantMessage.created_at))).scalars())

        async def client_named(self, name) -> Contact:
            async with tenant_session(t) as db:
                return (await db.execute(select(Contact).where(Contact.display_name == name))).scalar_one()

    yield Line()
    async with tenant_session(t) as db:
        await db.execute(delete(AssistantMessage))
        await db.execute(delete(Job).where(Job.kind.in_(("owner_alert", "owner_briefing", "assistant_turn"))))
        await db.execute(delete(Task).where(Task.created_at >= started))
        await db.execute(update(User).where(User.id == owner_id).values(phone=phone_before))
        await db.execute(update(Tenant).values(settings=settings_before))


# --- the morning briefing --------------------------------------------------------------------------------------------

def test_the_briefing_time_is_the_dealerships_local_time_across_a_clock_change():
    tenant = Tenant(name="X", timezones=["America/Chicago"], settings={"owner_assistant": {"briefing_time": "07:30", "briefing_on": True}})
    before = datetime(2026, 11, 27, 6, 0, tzinfo=CHI)
    assert briefing.next_time(tenant, before) == datetime(2026, 11, 27, 7, 30, tzinfo=CHI)
    assert briefing.next_time(tenant, datetime(2026, 11, 27, 7, 30, tzinfo=CHI)) == datetime(2026, 11, 28, 7, 30, tzinfo=CHI)  # already due: tomorrow
    # The night the clocks go forward (8 March 2026): still 7:30 on the wall, an hour earlier in UTC.
    spring = briefing.next_time(tenant, datetime(2026, 3, 7, 12, 0, tzinfo=CHI))
    assert spring.astimezone(CHI).strftime("%m-%d %H:%M") == "03-08 07:30" and spring.astimezone(UTC).hour == 12
    lagos = Tenant(name="Y", timezones=["Africa/Lagos"], settings={"owner_assistant": {"briefing_time": "08:00"}})
    assert briefing.next_time(lagos, datetime(2026, 11, 27, 5, 0, tzinfo=UTC)).astimezone(UTC).hour == 7  # 8 am in Lagos


async def test_the_briefing_arrives_at_the_configured_time_with_correct_counts(line):
    """Step 8 acceptance."""
    t = line.tenant
    async with tenant_session(t) as db:
        base = await briefing.counts(db)
        vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True)).limit(1))).scalar_one()
        regular = (await db.execute(select(Contact).where(Contact.is_vip.is_(False)).order_by(Contact.display_name).limit(2))).scalars().all()
        conv = (await db.execute(select(Conversation).where(Conversation.contact_id == regular[0].id).limit(1))).scalar_one_or_none()
        if conv is None:
            conv = Conversation(contact_id=regular[0].id, channel="sms", ai_mode="auto")
            db.add(conv)
            await db.flush()
        vip_had = (await db.execute(select(Task.id).where(Task.contact_id == vip.id, Task.status.in_(("open", "in_progress"))).limit(1))).first()
        hot_had = [(await db.execute(select(Task.id).where(Task.contact_id == c.id, Task.status.in_(("open", "in_progress")), Task.urgency == "high").limit(1))).first()
                   for c in regular]
        now = datetime.now(UTC)
        db.add(Task(title="VIP waiting", contact_id=vip.id, status="open", urgency="normal", due_at=now + timedelta(hours=3)))
        for c in regular:
            db.add(Task(title="Wants to buy today", contact_id=c.id, status="open", urgency="high", due_at=now + timedelta(hours=3)))
        db.add(Task(title="Call back", status="open", urgency="low", due_at=now - timedelta(hours=1)))  # overdue
        draft = Message(conversation_id=conv.id, direction="outbound", author_type="ai", body="Draft reply", status="queued", is_draft=True)
        db.add(draft)
        kind = (await db.execute(select(AppointmentType).limit(1))).scalar_one()
        noon = datetime.combine(now.astimezone(CHI).date(), datetime.min.time(), CHI) + timedelta(hours=12)
        appt = Appointment(contact_id=regular[0].id, appointment_type_id=kind.id, starts_at=noon, ends_at=noon + timedelta(minutes=30),
                           status="booked", source="staff")
        tomorrow = Appointment(contact_id=regular[1].id, appointment_type_id=kind.id, starts_at=noon + timedelta(days=1),
                               ends_at=noon + timedelta(days=1, minutes=30), status="booked", source="staff")
        db.add_all([appt, tomorrow])
        await db.flush()
        made = (draft.id, appt.id, tomorrow.id)
        after = await briefing.counts(db)
    expect = {"vips_waiting": base["vips_waiting"] + (0 if vip_had else 1), "hot_leads": base["hot_leads"] + sum(1 for h in hot_had if not h),
              "drafts": base["drafts"] + 1, "overdue_tasks": base["overdue_tasks"] + 1, "appointments": base["appointments"] + 1}  # tomorrow's isn't today's
    assert {k: after[k] for k in expect} == expect
    assert vip.display_name in after["vip_names"]

    # Switch it on for 7:30: the job is lined up for 7:30 in the dealership's own time.
    async with tenant_session(t) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        tenant.settings = {**(tenant.settings or {}), "owner_assistant": {"briefing_on": True, "briefing_time": "07:30"}}
        await db.flush()
        at = await briefing.schedule(db)
    assert at.astimezone(CHI).strftime("%H:%M") == "07:30" and at > datetime.now(UTC)
    async with tenant_session(t) as db:
        [job] = (await db.execute(select(Job).where(Job.kind == "owner_briefing", Job.status == "queued"))).scalars().all()
        assert job.run_at == at

    # 7:30 comes. The owner hasn't written in the last day, so it goes as the approved template, with the numbers
    # as they stand at 7:30 (by then today's unfinished tasks are overdue, and "today" is that day's appointments).
    async with tenant_session(t) as db:
        at_730 = await briefing.counts(db, at)
    assert at_730["overdue_tasks"] >= expect["overdue_tasks"] and at_730["drafts"] == expect["drafts"]
    assert await briefing.run(t, {}, now=at) == "sent to 1 of 1"
    [msg] = line.to_owner()
    assert msg.template["name"] == "ondra_morning_briefing"
    assert msg.template["params"] == ["Samuel", at.astimezone(CHI).strftime("%A, %B %-d"), *(str(at_730[k]) for k in
                                                                                         ("vips_waiting", "hot_leads", "drafts", "overdue_tasks", "appointments"))]
    async with tenant_session(t) as db:  # and tomorrow's is already lined up
        [nxt] = (await db.execute(select(Job).where(Job.kind == "owner_briefing", Job.status == "queued", Job.run_at > at))).scalars().all()
        assert nxt.run_at.astimezone(CHI).strftime("%H:%M") == "07:30" and nxt.run_at - at > timedelta(hours=22)
        # Inside the 24-hour window the same briefing is plain text with the names in it.
        db.add(AssistantMessage(user_id=line.owner, direction="in", kind="text", body="hi"))
    await briefing.send_now(t)
    text_ = line.to_owner()[-1]
    assert text_.template is None and f"VIP{'s' if expect['vips_waiting'] != 1 else ''} waiting" in text_.body and vip.display_name in text_.body
    # Switched off: nothing is lined up and a stray job does nothing.
    async with tenant_session(t) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        tenant.settings = {**(tenant.settings or {}), "owner_assistant": {"briefing_on": False}}
        await db.flush()
        assert await briefing.schedule(db) is None
    assert await briefing.run(t, {}) == "skipped: briefings are off"
    async with tenant_session(t) as db:
        await db.execute(delete(Message).where(Message.id == made[0]))
        await db.execute(delete(Appointment).where(Appointment.id.in_(made[1:])))


# --- voice notes and text ---------------------------------------------------------------------------------------------

async def test_a_voice_note_updates_the_right_client_and_creates_a_task(line):
    """Step 8 acceptance."""
    sarah = await line.client_named("Sarah King")
    async with tenant_session(line.tenant) as db:
        contacts_before = (await db.execute(text("SELECT count(*) FROM contacts"))).scalar()
        daniel = (await db.execute(select(User).where(User.name == "Daniel Okafor"))).scalar_one()
        deal_before = (await db.execute(select(Deal).where(Deal.contact_id == sarah.id, Deal.type == "sales"))).scalars().first()
        before = (dict(deal_before.vehicle_of_interest or {}), deal_before.budget_max, deal_before.id) if deal_before else None
    llm = line.script(
        [("find_clients", {"query": "Sara Kling"})],  # the transcript spells her name by ear
        [("update_deal", {"client_id": str(sarah.id), "vehicle_interest": "white Toyota Highlander", "budget_max": 40000}),
                         ("create_task", {"title": "Call Sarah about the white Highlander", "client_id": str(sarah.id), "assignee": "Daniel", "due": "tomorrow"})],
        "Updated Sarah King: wants the white Highlander, budget $40,000. Daniel has a task to call her, due tomorrow.")
    got = await line.owner_sends(voice="Sara Kling wants the white Highlander now, budget forty thousand. Have Daniel call her tomorrow.")
    assert got == {"stored": 0, "duplicates": 0}  # not stored as a customer message

    # The model was handed the transcript, and found the right Sarah despite the spelling.
    assert llm.requests[0]["messages"][-1]["content"].startswith("Sara Kling wants the white Highlander")
    found = json.loads(llm.requests[1]["messages"][-1]["content"][0]["content"])["clients"]
    assert found[0]["client_id"] == str(sarah.id) and found[0]["name"] == "Sarah King"
    async with tenant_session(line.tenant) as db:
        deal = (await db.execute(select(Deal).where(Deal.contact_id == sarah.id, Deal.type == "sales").order_by(Deal.updated_at.desc()))).scalars().first()
        assert deal.vehicle_of_interest["description"] == "white Toyota Highlander" and float(deal.budget_max) == 40000.0
        task = (await db.execute(select(Task).where(Task.contact_id == sarah.id).order_by(Task.created_at.desc()).limit(1))).scalar_one()
        assert (task.title, task.assignee_user_id, task.source) == ("Call Sarah about the white Highlander", daniel.id, "manual")
        due = task.due_at.astimezone(CHI)
        assert due.date() == (datetime.now(UTC).astimezone(CHI) + timedelta(days=1)).date() and due.hour == 17
        assert (await db.execute(text("SELECT count(*) FROM contacts"))).scalar() == contacts_before  # the owner didn't become a customer
        # put the deal back
        if before:
            await db.execute(update(Deal).where(Deal.id == before[2]).values(vehicle_of_interest=before[0], budget_max=before[1]))
        else:
            await db.execute(delete(Deal).where(Deal.id == deal.id))
    [reply] = line.to_owner()
    assert reply.body.startswith("Updated Sarah King") and reply.template is None  # they just wrote, so plain text is allowed
    voice, out = await line.thread()
    assert (voice.kind, voice.body.startswith("Sara Kling"), voice.meta["transcribed"]) == ("voice", True, True)
    assert out.meta["did"] == ["deal for Sarah King: wants white Toyota Highlander, budget up to $40,000", "task for Daniel Okafor: Call Sarah about the white Highlander"]


async def test_questions_notes_and_an_unreadable_voice_note(line):
    line.script([("who_wanted", {"what": "civic"})], "Jordan Price asked about the Civic Sport.")
    await line.owner_sends("who wanted a Civic?")
    assert "Jordan Price" in line.to_owner()[-1].body
    async with tenant_session(line.tenant) as db:
        owner = await db.get(User, line.owner)
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        desk = owner_assistant.OwnerDesk(db, owner, tenant)
        hits = await desk.who_wanted("civic")
        assert any(c["name"] == "Jordan Price" and "civic" in c["why"].lower() for c in hits["clients"])
        assert (await desk.who_wanted("zeppelin"))["clients"] == []
        assert (await desk.find_clients("Nobody Atall"))["clients"] == []  # no guess at somebody else
        sarah = await line.client_named("Sarah King")
        notes_before = sarah.notes
        saved = await desk.add_note(str(sarah.id), "Prefers calls after 5.")
        assert saved["saved"] and "Samuel (WhatsApp): Prefers calls after 5." in (await db.get(Contact, sarah.id)).notes
        assert "Nobody" in (await desk.create_task("Do a thing", assignee="Zebedee"))["error"]
        assert "which day" in (await desk.create_task("Do a thing", due="the day after the game"))["error"]
        await db.execute(update(Contact).where(Contact.id == sarah.id).values(notes=notes_before))
    # A voice note that can't be transcribed gets a plain request to resend, and the model isn't called.
    llm = line.script("must not be used")

    class Broken:
        provider = "broken"

        async def transcribe(self, audio, mime_type, *, hint=None):
            from ondra_core.transcription import TranscriptionError

            raise TranscriptionError("noise")

    owner_assistant.transcriber_factory, keep = (lambda: Broken()), owner_assistant.transcriber_factory
    try:
        await line.owner_sends(voice="(inaudible)")
    finally:
        owner_assistant.transcriber_factory = keep
    assert "couldn't make out that voice note" in line.to_owner()[-1].body and llm.requests == []


# --- approvals, alerts, and who counts as the owner --------------------------------------------------------------------

async def test_one_tap_approves_or_discards_a_draft(line):
    async with tenant_session(line.tenant) as db:
        c = (await db.execute(text("""SELECT c.id, cv.id AS conv FROM contacts c JOIN conversations cv ON cv.contact_id = c.id AND cv.channel = 'sms'
            WHERE NOT c.is_vip AND NOT EXISTS (SELECT 1 FROM consents s WHERE s.contact_id = c.id AND s.status = 'opted_out') LIMIT 1"""))).one()
        drafts = [Message(conversation_id=c.conv, direction="outbound", author_type="ai", body=f"Draft {i}", status="queued", is_draft=True) for i in (1, 2)]
        db.add_all(drafts)
        await db.flush()
        one, two = (d.id for d in drafts)
        name = (await db.get(Contact, c.id)).display_name
    await line.owner_sends(button=f"approve:{one}")
    assert channels.mock("sms").outbox[-1].body == "Draft 1" and line.to_owner()[-1].body == f"Sent to {name}."
    async with tenant_session(line.tenant) as db:
        m = await db.get(Message, one)
        assert (m.is_draft, m.status, m.author_user_id) == (False, "sent", line.owner)  # approved by the owner, sent by the one send path
    await line.owner_sends(button=f"approve:{one}")  # tapping twice does nothing more
    assert "isn't waiting any more" in line.to_owner()[-1].body and len(channels.mock("sms").outbox) == 1
    await line.owner_sends(button=f"discard:{two}")
    assert line.to_owner()[-1].body == "Discarded. Nothing was sent."
    async with tenant_session(line.tenant) as db:
        assert await db.get(Message, two) is None
        await db.execute(delete(Message).where(Message.id == one))
        await db.execute(text("DELETE FROM follow_ups WHERE created_at > now() - interval '2 minutes'"))


async def test_vip_alerts_reach_the_owner_and_only_whatsapp_from_the_owners_number_is_the_owner(line):
    async with tenant_session(line.tenant) as db:
        vip, phone = (await db.execute(text("""SELECT c.display_name, i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id
                                                AND i.kind = 'phone' WHERE c.is_vip LIMIT 1"""))).one()
    await line.owner_sends("Call me about the Escalade.", frm=phone)  # a VIP writes in: no AI, the owner is alerted on WhatsApp
    await worker.run_once()
    [alert] = line.to_owner()
    assert alert.template["name"] == "ondra_alert" and vip in alert.template["params"][1] and "VIP message waiting" in alert.body
    # Alerts off: recorded, not sent.
    async with tenant_session(line.tenant) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        tenant.settings = {**(tenant.settings or {}), "owner_assistant": {"alerts_on": False}}
    assert await deliver_alert(line.tenant, {"to": "owner", "reason": "x"}) == "skipped: alerts are off"

    # The same number by text message is a customer like any other: a text's sender can be faked.
    line.script("must not be used")
    got = await line.owner_sends("add a note to Sarah King: owes us nothing", channel="sms")
    assert got["stored"] == 1
    async with tenant_session(line.tenant) as db:
        assert (await db.execute(select(AssistantMessage).where(AssistantMessage.body.like("add a note%")))).scalars().all() == []
        ghost = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = :v"), {"v": OWNER})).scalars().all()
        await db.execute(delete(Task).where(Task.contact_id.in_(ghost)))
        await db.execute(delete(Contact).where(Contact.id.in_(ghost)))
        vip_id = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = :v LIMIT 1"), {"v": phone})).scalar()
        await db.execute(text("DELETE FROM messages WHERE created_at > now() - interval '2 minutes' AND conversation_id IN (SELECT id FROM conversations WHERE contact_id = :c)"), {"c": vip_id})
    # A manager's mobile on WhatsApp is not the owner's line either.
    assert (await line.owner_sends("hello", frm="+12145550101"))["stored"] == 1
    async with tenant_session(line.tenant) as db:
        ghost = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = '+12145550101'"))).scalars().all()
        await db.execute(delete(Task).where(Task.contact_id.in_(ghost)))
        await db.execute(delete(Contact).where(Contact.id.in_(ghost)))


async def test_outside_the_window_without_a_template_nothing_is_sent_and_dealers_are_isolated(line, database):
    assert await send_to_owner(line.tenant, line.owner, "a free-form note") is False  # no message from the owner in 24 h, no template
    [row] = await line.thread()
    assert row.status == "failed" and "24-hour window" in row.meta["error"] and line.to_owner() == []
    async with tenant_session(database["b"]) as db:
        assert (await db.execute(select(AssistantMessage))).scalars().all() == []
