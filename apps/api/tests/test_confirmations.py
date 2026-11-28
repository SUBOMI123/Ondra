"""Booking confirmations (docs/PLAN.md item 4): the customer's channel plus an email copy with a calendar invite, one
link to move or cancel, at most two messages per change, the same consent, opt-out and VIP rules as everything else,
and quiet hours. Plus the booking's own page, reached by that link."""

import base64
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from ondra_api import channels
from ondra_api.db import tenant_session
from ondra_api.services import booking, confirmations
from ondra_api.services.booking import InternalCalendar, find_type, tz_of
from ondra_core.models import (
    Appointment,
    Consent,
    Contact,
    ContactIdentity,
    Conversation,
    Job,
    Message,
    Task,
    Tenant,
    User,
)
from sqlalchemy import select, text

CHI = ZoneInfo("America/Chicago")


def _next(weekday: int) -> date:
    d = date.today() + timedelta(days=2)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


@pytest.fixture
def outbox():
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    return channels.mock


async def _person(database, name, *, phone=True, email=True, sms_consent=True, vip=False, opted_out=False,
                  preferred="sms", whatsapp_recent=None) -> uuid.UUID:
    tag = uuid.uuid4().hex[:6]
    async with tenant_session(database["a"]) as db:
        c = Contact(display_name=f"{name} {tag}", preferred_channel=preferred, is_vip=vip)
        db.add(c)
        await db.flush()
        if vip:
            c.vip_owner_user_id = (await db.execute(select(User.id).where(User.email == "daniel@prestigemotors.example"))).scalar_one()
        if phone:
            db.add(ContactIdentity(contact_id=c.id, kind="phone", value=f"+1972555{uuid.uuid4().int % 10000:04d}"))
        if email:
            db.add(ContactIdentity(contact_id=c.id, kind="email", value=f"{tag}@example.com"))
        if sms_consent:
            db.add(Consent(contact_id=c.id, channel="sms", purpose="transactional", status="opted_in", source="test"))
        if opted_out:
            db.add(Consent(contact_id=c.id, channel="sms", purpose="marketing", status="opted_out", source="STOP"))
        if whatsapp_recent is not None:
            conv = Conversation(contact_id=c.id, channel="whatsapp", ai_mode="auto")
            db.add(conv)
            await db.flush()
            db.add(Message(conversation_id=conv.id, direction="inbound", author_type="customer", body="hi", status="received",
                           created_at=datetime.now(UTC) - whatsapp_recent))
        return c.id


async def _book(database, contact_id, *, source="staff", channel=None, nth=0):
    """Book a test drive next Tuesday afternoon; returns (appointment id, the confirmation job's payload)."""
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        td = await find_type(db, "test_drive")
        start = datetime.combine(_next(1), time(0), tz_of(tenant)).astimezone(UTC)
        slots = await InternalCalendar(db, tenant).find_slots(td, start_from=start + timedelta(hours=13), until=start + timedelta(days=1), limit=8)
        conv_id = None
        if channel:
            conv = Conversation(contact_id=contact_id, channel=channel, ai_mode="auto")
            db.add(conv)
            await db.flush()
            conv_id = conv.id
        a = await booking.book(db, tenant, slot_id=slots[nth].slot_id, contact_id=contact_id, source=source, conversation_id=conv_id)
        jobs = (await db.execute(select(Job).where(Job.kind == "appointment_confirmation", Job.payload["appointment_id"].astext == str(a.id)))).scalars().all()
        assert len(jobs) == 1
        return a.id, jobs[0].payload, [s.slot_id for s in slots]


async def _appt(database, aid) -> Appointment:
    async with tenant_session(database["a"]) as db:
        return await db.get(Appointment, aid)


async def _cleanup(database, *contact_ids):
    async with tenant_session(database["a"]) as db:
        for cid in contact_ids:
            await db.execute(text("DELETE FROM appointments WHERE contact_id = :c"), {"c": cid})
            await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": cid})
        await db.execute(text("DELETE FROM jobs WHERE kind IN ('appointment_confirmation', 'appointment_reminder') AND status = 'queued'"))


async def test_a_staff_booking_is_confirmed_by_text_with_an_email_copy_and_invite(database, outbox):
    cid = await _person(database, "Ada Nwosu")
    try:
        aid, payload, _ = await _book(database, cid)
        result = await confirmations.send(database["a"], payload)
        assert result == "sent, sent"
        [sms] = outbox("sms").outbox
        [mail] = outbox("email").outbox
        assert sms.body.startswith("Booked: your test drive at Prestige Motors,") and "/b?t=" in sms.body
        assert mail.subject.startswith("Booked: your test drive at Prestige Motors") and mail.body == sms.body
        [att] = mail.attachments
        assert att["name"] == "invite.ics" and "method=REQUEST" in att["content_type"]
        ics = base64.b64decode(att["content_b64"]).decode()
        assert f"UID:{aid}@ondra" in ics and "METHOD:REQUEST" in ics and "SEQUENCE:0" in ics and "\r\n" in ics
        assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))  # folded per RFC 5545
        # Twice is once: a retried job sends nothing more.
        assert await confirmations.send(database["a"], payload) == "skipped: already done"
        assert len(outbox("sms").outbox) == 1
        assert confirmations.summary(await _appt(database, aid)) == ["Confirmation sent by text and email."]
    finally:
        await _cleanup(database, cid)


async def test_booked_by_ondra_in_a_text_thread_gets_only_the_email_copy(database, outbox):
    cid = await _person(database, "Bola Ade")
    try:
        aid, payload, _ = await _book(database, cid, source="ai", channel="sms")
        assert await confirmations.send(database["a"], payload) == "sent"
        assert outbox("sms").outbox == [] and len(outbox("email").outbox) == 1
        assert "No confirmation by text: Ondra confirmed it in the conversation." in confirmations.summary(await _appt(database, aid))
    finally:
        await _cleanup(database, cid)


async def test_booked_by_ondra_on_a_call_is_confirmed_by_text(database, outbox):
    cid = await _person(database, "Chidi Obi", email=False)
    try:
        _, payload, _ = await _book(database, cid, source="ai", channel="phone")
        assert await confirmations.send(database["a"], payload) == "sent"
        assert len(outbox("sms").outbox) == 1 and outbox("email").outbox == []
    finally:
        await _cleanup(database, cid)


async def test_no_text_without_consent_and_staff_see_why(database, outbox):
    cid = await _person(database, "Dayo Kale", email=False, sms_consent=False)
    try:
        aid, payload, _ = await _book(database, cid)
        assert await confirmations.send(database["a"], payload) == "nothing sent"
        assert outbox("sms").outbox == []
        assert confirmations.summary(await _appt(database, aid)) == ["No confirmation by text: no consent to texts on file."]
    finally:
        await _cleanup(database, cid)


async def test_an_opt_out_blocks_every_channel_email_included(database, outbox):
    cid = await _person(database, "Efe Ojo", opted_out=True)
    try:
        _, payload, _ = await _book(database, cid)
        assert await confirmations.send(database["a"], payload) == "nothing sent"
        assert outbox("sms").outbox == [] and outbox("email").outbox == []
    finally:
        await _cleanup(database, cid)


async def test_whatsapp_only_inside_its_24_hour_window(database, outbox):
    inside = await _person(database, "Femi Lawal", email=False, preferred="whatsapp", whatsapp_recent=timedelta(hours=3))
    outside = await _person(database, "Gbemi Lawal", email=False, preferred="whatsapp", whatsapp_recent=timedelta(days=3))
    try:
        _, p1, _ = await _book(database, inside, channel="whatsapp")
        assert await confirmations.send(database["a"], p1) == "sent" and len(outbox("whatsapp").outbox) == 1
        aid, p2, _ = await _book(database, outside, channel="whatsapp", nth=1)
        assert await confirmations.send(database["a"], p2) == "nothing sent"
        assert "24-hour window" in confirmations.summary(await _appt(database, aid))[0]
    finally:
        await _cleanup(database, inside, outside)


async def test_a_vip_gets_no_automatic_confirmation_their_person_gets_a_task(database, outbox):
    cid = await _person(database, "Halima Bello", vip=True)
    try:
        aid, payload, _ = await _book(database, cid)
        assert await confirmations.send(database["a"], payload) == "vip: task for their person"
        assert outbox("sms").outbox == [] and outbox("email").outbox == []
        async with tenant_session(database["a"]) as db:
            [task] = (await db.execute(select(Task).where(Task.contact_id == cid))).scalars().all()
            daniel = (await db.execute(select(User.id).where(User.email == "daniel@prestigemotors.example"))).scalar_one()
            assert task.assignee_user_id == daniel and "personally (VIP)" in task.title
            # Reminders follow the same rule.
            from ondra_api.services.reminders import send_reminder

            a = await db.get(Appointment, aid)
            conv = Conversation(contact_id=cid, channel="sms", ai_mode="off")
            db.add(conv)
            await db.flush()
            a.conversation_id = conv.id
            starts = a.starts_at.isoformat()
        assert (await send_reminder(database["a"], {"appointment_id": str(aid), "starts_at": starts, "minutes_before": 120})).startswith("skipped: VIPs")
        async with tenant_session(database["a"]) as db:
            await db.execute(text("DELETE FROM tasks WHERE contact_id = :c"), {"c": cid})
    finally:
        await _cleanup(database, cid)


async def test_a_move_updates_the_invite_and_a_cancellation_removes_it(database, outbox):
    cid = await _person(database, "Ike Uche")
    try:
        aid, payload, slots = await _book(database, cid)
        await confirmations.send(database["a"], payload)
        async with tenant_session(database["a"]) as db:
            tenant = (await db.execute(select(Tenant))).scalar_one()
            a = await db.get(Appointment, aid)
            await booking.reschedule(db, tenant, a, slots[2])
            moved = (await db.execute(select(Job).where(Job.kind == "appointment_confirmation", Job.payload["kind"].astext == "moved",
                                                        Job.payload["appointment_id"].astext == str(aid)))).scalar_one().payload
        assert await confirmations.send(database["a"], moved) == "sent, sent"
        assert await confirmations.send(database["a"], payload) == "skipped: changed since"  # the old time is old news
        ics = base64.b64decode(outbox("email").outbox[-1].attachments[0]["content_b64"]).decode()
        assert outbox("sms").outbox[-1].body.startswith("Moved:") and "SEQUENCE:1" in ics and f"UID:{aid}@ondra" in ics
        async with tenant_session(database["a"]) as db:
            a = await db.get(Appointment, aid)
            await booking.set_status(db, a, "cancelled", by="test")
            gone = (await db.execute(select(Job).where(Job.kind == "appointment_confirmation", Job.payload["kind"].astext == "cancelled",
                                                       Job.payload["appointment_id"].astext == str(aid)))).scalar_one().payload
        assert await confirmations.send(database["a"], gone) == "sent, sent"
        last = outbox("email").outbox[-1]
        ics = base64.b64decode(last.attachments[0]["content_b64"]).decode()
        assert last.subject.startswith("Cancelled:") and "METHOD:CANCEL" in ics and "STATUS:CANCELLED" in ics and "SEQUENCE:2" in ics
        assert len(confirmations.summary(await _appt(database, aid))) == 3
    finally:
        await _cleanup(database, cid)


def test_quiet_hours_hold_a_late_booking_until_8_am():
    tenant = Tenant(name="X", timezones=["America/Chicago"])
    late = datetime(2026, 12, 1, 22, 15, tzinfo=CHI).astimezone(UTC)
    early = datetime(2026, 12, 2, 6, 40, tzinfo=CHI).astimezone(UTC)
    day = datetime(2026, 12, 2, 11, 0, tzinfo=CHI).astimezone(UTC)
    assert confirmations.quiet_until(tenant, late) == datetime(2026, 12, 2, 8, 0, tzinfo=CHI).astimezone(UTC)
    assert confirmations.quiet_until(tenant, early) == datetime(2026, 12, 2, 8, 0, tzinfo=CHI).astimezone(UTC)
    assert confirmations.quiet_until(tenant, day) is None


# --- the booking's own page -----------------------------------------------------------------------------------------

async def test_the_link_opens_that_booking_only_and_moves_or_cancels_it(client, database, outbox):
    cid = await _person(database, "Jide Afolabi")
    try:
        aid, _, _ = await _book(database, cid)
        token = confirmations.manage_token(database["a"], aid)
        page = (await client.get(f"/public/bookings/{token}")).json()
        assert page["dealer"] == "Prestige Motors" and page["what"] == "Test drive" and page["can_change"] and page["status"] == "booked"
        assert page["calendar"]["google"].startswith("https://calendar.google.com/calendar/render?action=TEMPLATE")
        assert "outlook.live.com" in page["calendar"]["outlook"]
        r = await client.get(page["calendar"]["ics"])
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar") and "BEGIN:VEVENT" in r.text
        # A changed character, another dealer's booking or rubbish: nothing.
        bad = token[:-1] + ("A" if token[-1] != "A" else "B")
        assert (await client.get(f"/public/bookings/{bad}")).status_code == 404
        assert (await client.get(f"/public/bookings/{confirmations.manage_token(database['b'], aid)}")).status_code == 404
        assert (await client.get("/public/bookings/nonsense")).status_code == 404

        times = (await client.get(f"/public/bookings/{token}/times")).json()["items"]
        assert times
        moved = await client.post(f"/public/bookings/{token}/move", json={"slot_id": times[0]["slot_id"]})
        assert moved.status_code == 200 and moved.json()["starts_at"] == times[0]["starts_at"]
        assert (await client.post(f"/public/bookings/{token}/cancel")).json()["status"] == "cancelled"
        assert (await client.post(f"/public/bookings/{token}/cancel")).status_code == 409  # already cancelled
        assert (await client.post(f"/public/bookings/{token}/move", json={"slot_id": times[1]["slot_id"]})).status_code == 409
        async with tenant_session(database["a"]) as db:
            kinds = [j.payload["kind"] for j in (await db.execute(select(Job).where(
                Job.kind == "appointment_confirmation", Job.payload["appointment_id"].astext == str(aid)).order_by(Job.created_at))).scalars()]
        assert kinds == ["booked", "moved", "cancelled"]  # each change confirmed by the same rules
    finally:
        await _cleanup(database, cid)
