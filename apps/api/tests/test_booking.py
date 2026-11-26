"""Booking: availability follows the rules, nothing double-books (even in a race), and reminders behave."""

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select, text

from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.security import hash_password
from ondra_api.services import booking
from ondra_api.services.booking import InternalCalendar, NotBookable, SlotTaken, decode_slot_id, find_type, tz_of
from ondra_api.services.reminders import reminder_time, send_reminder
from ondra_core.models import (
    Appointment,
    AppointmentResource,
    Contact,
    Conversation,
    Job,
    Message,
    Resource,
    Tenant,
    User,
)


def _next(weekday: int) -> date:
    """The next given weekday (0 = Monday) at least 2 days out, so notice rules never bite."""
    d = date.today() + timedelta(days=2)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


async def _ctx(database):
    db_cm = tenant_session(database["a"])
    db = await db_cm.__aenter__()
    tenant = (await db.execute(select(Tenant))).scalar_one()
    return db_cm, db, tenant


async def _contact(db, name="Hannah Weiss"):
    return (await db.execute(select(Contact).where(Contact.display_name == name))).scalar_one()


def _day_window(tenant, d: date):
    tz = tz_of(tenant)
    start = datetime.combine(d, time(0), tz).astimezone(UTC)
    return start, start + timedelta(days=1)


async def test_slots_follow_the_types_rules(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        cal = InternalCalendar(db, tenant)
        td = await find_type(db, "test_drive")
        oil = await find_type(db, "oil change")
        tue = _next(1)
        slots = await cal.find_slots(td, start_from=_day_window(tenant, tue)[0], until=_day_window(tenant, tue)[1], limit=40)
        assert slots and all(s.user_name for s in slots)
        local = [s.starts_at.astimezone(tz_of(tenant)) for s in slots]
        assert local[0].time() == time(9, 0) and all(lt.time() <= time(18, 15) for lt in local)  # 45 min within 9-7
        sales = {u.name for u in (await db.execute(select(User).where(User.role == "sales"))).scalars()}
        assert {s.user_name for s in slots} <= sales

        service = await cal.find_slots(oil, start_from=_day_window(tenant, tue)[0], until=_day_window(tenant, tue)[1],
                                       limit=40, part_of_day="morning")
        assert service and all(s.resource_names and s.resource_names[0].startswith("Bay") for s in service)
        assert service[0].starts_at.astimezone(tz_of(tenant)).time() == time(7, 0)  # service opens at 7
        assert all(s.starts_at.astimezone(tz_of(tenant)).hour < 12 for s in service)
        assert service[0].label.startswith(tue.strftime("%a")) and service[0].label.endswith("Bay 1")

        # Not before the minimum notice.
        soon = await cal.find_slots(td, start_from=datetime.now(UTC), until=datetime.now(UTC) + timedelta(days=3))
        assert all(s.starts_at >= datetime.now(UTC) + timedelta(minutes=td.min_notice_min) for s in soon)


async def test_book_holds_the_person_and_the_bay_and_refuses_a_second_booking(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        oil = await find_type(db, "oil change")
        wed = _next(2)
        [slot] = await InternalCalendar(db, tenant).find_slots(oil, start_from=_day_window(tenant, wed)[0],
                                                               until=_day_window(tenant, wed)[1], limit=1)
        c = await _contact(db)
        a = await booking.book(db, tenant, slot_id=slot.slot_id, contact_id=c.id, source="staff", details={"transport": "loaner"})
        held = (await db.execute(select(AppointmentResource).where(AppointmentResource.appointment_id == a.id))).scalars().all()
        kinds = {(await db.get(Resource, h.resource_id)).kind for h in held}
        assert kinds == {"service_bay", "loaner"} and a.details["loaner"] == "Loaner 1"
        with pytest.raises(SlotTaken):
            await booking.book(db, tenant, slot_id=slot.slot_id, contact_id=c.id, source="staff")
        # The calendar no longer offers that person-and-bay pairing at that time.
        again = await InternalCalendar(db, tenant).find_slots(oil, start_from=slot.starts_at, until=slot.ends_at, limit=5)
        assert all(s.slot_id != slot.slot_id for s in again)
        await booking.set_status(db, a, "cancelled", by="test")


async def test_two_bookings_racing_for_one_slot_only_one_wins(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        td = await find_type(db, "test_drive")
        thu = _next(3)
        [slot] = await InternalCalendar(db, tenant).find_slots(td, start_from=_day_window(tenant, thu)[0],
                                                               until=_day_window(tenant, thu)[1], limit=1)
        contact_id = (await _contact(db, "Ethan Walker")).id

    async def attempt():
        try:
            async with tenant_session(database["a"]) as db:
                tenant = (await db.execute(select(Tenant))).scalar_one()
                await booking.book(db, tenant, slot_id=slot.slot_id, contact_id=contact_id, source="ai")
            return "won"
        except SlotTaken:
            return "taken"

    results = await asyncio.gather(*(attempt() for _ in range(5)))
    assert sorted(results) == ["taken"] * 4 + ["won"]
    async with tenant_session(database["a"]) as db:
        a = (await db.execute(select(Appointment).where(Appointment.contact_id == contact_id,
                                                        Appointment.status == "booked"))).scalars().all()
        assert len(a) == 1
        await booking.set_status(db, a[0], "cancelled", by="test")


async def test_a_bay_cannot_be_double_booked_even_with_two_advisors(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        second = User(email=f"advisor{uuid.uuid4().hex[:6]}@prestigemotors.example", name="Second Advisor",
                      role="service", password_hash=hash_password("x" * 12))
        db.add(second)
        await db.flush()
        oil = await find_type(db, "oil change")
        fri = _next(4)
        [slot] = await InternalCalendar(db, tenant).find_slots(oil, start_from=_day_window(tenant, fri)[0],
                                                               until=_day_window(tenant, fri)[1], limit=1)
        c = await _contact(db)
        a = await booking.book(db, tenant, slot_id=slot.slot_id, contact_id=c.id, source="staff")
        # Same time and same bay, but the other advisor: a hand-crafted slot id (what a confused caller might send).
        t, s, _, rs = decode_slot_id(slot.slot_id)
        crafted = booking.Slot(t, s, slot.ends_at, slot.blocks_until, second.id, second.name, rs, slot.resource_names).slot_id
        with pytest.raises(SlotTaken):
            await booking.book(db, tenant, slot_id=crafted, contact_id=c.id, source="staff")
        await booking.set_status(db, a, "cancelled", by="test")
        second.active = False


async def test_invented_or_rule_breaking_slots_are_refused(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        td = await find_type(db, "test_drive")
        c = await _contact(db)
        with pytest.raises(NotBookable):
            await booking.book(db, tenant, slot_id="sat-10am", contact_id=c.id, source="ai")
        sales = (await db.execute(select(User).where(User.role == "sales"))).scalars().first()
        sunday_noon = datetime.combine(_next(6), time(12), tz_of(tenant)).astimezone(UTC)  # closed on Sunday
        bad = booking.Slot(td.id, sunday_noon, sunday_noon + timedelta(minutes=45), sunday_noon, sales.id, sales.name).slot_id
        with pytest.raises(NotBookable):
            await booking.book(db, tenant, slot_id=bad, contact_id=c.id, source="ai")
        soon = datetime.now(UTC) + timedelta(minutes=5)
        bad = booking.Slot(td.id, soon, soon + timedelta(minutes=45), soon, sales.id, sales.name).slot_id
        with pytest.raises(NotBookable):
            await booking.book(db, tenant, slot_id=bad, contact_id=c.id, source="ai")


async def test_reschedule_and_cancel_free_the_old_slot(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        oil = await find_type(db, "oil change")
        mon = _next(0)
        slots = await InternalCalendar(db, tenant).find_slots(oil, start_from=_day_window(tenant, mon)[0],
                                                              until=_day_window(tenant, mon)[1], limit=10)
        first = slots[0]
        second = next(x for x in slots if x.starts_at >= first.blocks_until)  # doesn't overlap the first
        c = await _contact(db)
        a = await booking.book(db, tenant, slot_id=first.slot_id, contact_id=c.id, source="staff")
        await booking.reschedule(db, tenant, a, second.slot_id)
        assert a.starts_at == second.starts_at
        reopened = await InternalCalendar(db, tenant).find_slots(oil, start_from=first.starts_at, until=first.ends_at, limit=3)
        assert any(s.starts_at == first.starts_at and s.resource_names == first.resource_names for s in reopened)
        await booking.set_status(db, a, "cancelled", by="test")
        assert not (await db.execute(select(AppointmentResource).where(AppointmentResource.appointment_id == a.id,
                                                                       AppointmentResource.active.is_(True)))).first()


# --- reminders ---------------------------------------------------------------------------------------------------

def test_reminders_stay_out_of_quiet_hours():
    t = Tenant(name="T", timezones=["America/Chicago"])
    tz = tz_of(t)
    at = lambda d, h, m=0: datetime.combine(d, time(h, m), tz)  # noqa: E731
    d = date(2026, 12, 2)
    assert reminder_time(t, at(d, 15), 120) == at(d, 13)  # plain 2 h before
    assert reminder_time(t, at(d, 7, 30), 120) == at(d - timedelta(days=1), 19)  # 5:30 am -> 7 pm the evening before
    assert reminder_time(t, at(d, 21, 30), 60) == at(d, 19, 59)  # 8:30 pm -> just before 8 pm
    assert reminder_time(t, at(d, 9), 1440) == at(d - timedelta(days=1), 9)  # the day before


async def test_reminders_are_queued_sent_once_and_skipped_when_moved_or_cancelled(database):
    channels.mock("sms").outbox.clear()
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        td = await find_type(db, "test_drive")
        tue = _next(1)
        a_slot, b_slot = await InternalCalendar(db, tenant).find_slots(td, start_from=_day_window(tenant, tue)[0] + timedelta(hours=15),
                                                                        until=_day_window(tenant, tue)[1], limit=2)
        c = await _contact(db, "Ben Carter")
        conv = Conversation(contact_id=c.id, channel="sms", ai_mode="auto")
        db.add(conv)
        await db.flush()
        a = await booking.book(db, tenant, slot_id=a_slot.slot_id, contact_id=c.id, source="ai", conversation_id=conv.id)
        jobs = (await db.execute(select(Job).where(Job.kind == "appointment_reminder", Job.payload["appointment_id"].astext == str(a.id)))).scalars().all()
        assert sorted(j.payload["minutes_before"] for j in jobs) == [120, 1440]
        payload = next(j.payload for j in jobs if j.payload["minutes_before"] == 120)
        a_id = a.id

    assert await send_reminder(database["a"], payload) == "sent"
    assert await send_reminder(database["a"], payload) == "skipped: already sent"
    sent = channels.mock("sms").outbox[-1].body
    assert sent.startswith("Reminder from Prestige Motors: your test drive is") and "Reply here" in sent

    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        a = await db.get(Appointment, a_id)
        await booking.reschedule(db, tenant, a, b_slot.slot_id)
    assert await send_reminder(database["a"], {**payload, "minutes_before": 1440}) == "skipped: moved"
    async with tenant_session(database["a"]) as db:
        a = await db.get(Appointment, a_id)
        await booking.set_status(db, a, "cancelled", by="test")
    moved = {**payload, "starts_at": b_slot.starts_at.isoformat()}
    assert await send_reminder(database["a"], moved) == "skipped: not live"


async def test_opted_out_customers_get_no_reminders(database):
    async with tenant_session(database["a"]) as db:
        tenant = (await db.execute(select(Tenant))).scalar_one()
        jordan = await _contact(db, "Jordan Price")  # opted out in the seed
        td = await find_type(db, "test_drive")
        wed = _next(2)
        [slot] = await InternalCalendar(db, tenant).find_slots(td, start_from=_day_window(tenant, wed)[0] + timedelta(hours=16),
                                                               until=_day_window(tenant, wed)[1], limit=1)
        conv = (await db.execute(select(Conversation).where(Conversation.contact_id == jordan.id))).scalars().first()
        a = await booking.book(db, tenant, slot_id=slot.slot_id, contact_id=jordan.id, source="staff",
                               conversation_id=conv.id if conv else None)
        payload = {"appointment_id": str(a.id), "starts_at": a.starts_at.isoformat(), "minutes_before": 120}
        a_id = a.id
    result = await send_reminder(database["a"], payload)
    assert result in ("blocked: opted_out", "skipped: no channel")
    async with tenant_session(database["a"]) as db:
        await booking.set_status(db, await db.get(Appointment, a_id), "cancelled", by="test")


__all__ = ["json", "text", "Message", "worker"]
