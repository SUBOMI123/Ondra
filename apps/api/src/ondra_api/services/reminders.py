"""Appointment reminders (BUILD_PLAN.md §4.3: 24 h and 2 h before, on the customer's channel).

Each booking queues one job per reminder. When a job runs it re-checks everything: an appointment that was cancelled,
moved or already reminded is skipped, and the send goes through the one outbound path, so opt-outs block reminders
on every channel like everything else.

Quiet hours: reminders go out between 8 am and 8 pm, dealer time. One that would land outside moves to the evening
before (or 8 pm the same day); if that's already past, it's skipped (the customer was just confirmed in the chat).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

from ondra_core.models import Appointment, AppointmentType, Conversation, Event, Message, Tenant, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.db import tenant_session
from ondra_api.services.booking import DEFAULT_REMINDERS, LIVE, tz_of
from ondra_api.services.jobs import enqueue

QUIET_START, QUIET_END = time(20, 0), time(8, 0)  # no reminders from 8 pm to 8 am


def reminder_time(tenant: Tenant, starts_at: datetime, minutes_before: int) -> datetime:
    tz = tz_of(tenant)
    t = (starts_at - timedelta(minutes=minutes_before)).astimezone(tz)
    if t.time() >= QUIET_START:
        t = t.replace(hour=20, minute=0, second=0, microsecond=0) - timedelta(minutes=1)
    elif t.time() < QUIET_END:
        t = (t - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    return t.astimezone(UTC)


async def schedule_reminders(db: AsyncSession, tenant: Tenant, a: Appointment, t: AppointmentType) -> list[datetime]:
    now = datetime.now(UTC)
    planned = []
    for minutes in (t.reminder_schedule or DEFAULT_REMINDERS):
        at = reminder_time(tenant, a.starts_at, int(minutes))
        if now < at < a.starts_at:
            enqueue(db, "appointment_reminder", {"appointment_id": str(a.id), "starts_at": a.starts_at.isoformat(),
                                                 "minutes_before": int(minutes)}, run_at=at)
            planned.append(at)
    return planned


def _when(tenant: Tenant, starts_at: datetime, now: datetime) -> str:
    tz = tz_of(tenant)
    s, n = starts_at.astimezone(tz), now.astimezone(tz)
    clock = s.strftime("%-I:%M %p").replace("AM", "am").replace("PM", "pm").replace(":00 ", " ")
    if s.date() == n.date():
        return f"today at {clock}"
    if s.date() == n.date() + timedelta(days=1):
        return f"tomorrow at {clock}"
    return f"{s.strftime('%A')} at {clock}"


async def send_reminder(tenant_id: uuid.UUID, payload: dict) -> str:
    """Job handler. Returns what happened (for tests and logs)."""
    from ondra_api.services.outbound import Blocked, deliver

    async with tenant_session(tenant_id) as db:
        a = await db.get(Appointment, uuid.UUID(payload["appointment_id"]))
        if a is None or a.status not in LIVE:
            return "skipped: not live"
        if a.starts_at.isoformat() != payload["starts_at"]:
            return "skipped: moved"  # the reschedule queued fresh reminders
        sent = list(a.reminders_sent or [])
        if payload["minutes_before"] in sent:
            return "skipped: already sent"
        conv_id = a.conversation_id or (await db.execute(
            select(Conversation.id).where(Conversation.contact_id == a.contact_id).order_by(Conversation.updated_at.desc()).limit(1)
        )).scalar_one_or_none()
        if conv_id is None:
            db.add(Event(type="appointment.reminder_skipped", payload={"appointment_id": str(a.id), "reason": "no channel"}))
            return "skipped: no channel"
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        t = await db.get(AppointmentType, a.appointment_type_id)
        who = (await db.get(User, a.assigned_user_id)).name.split()[0] if a.assigned_user_id else None
        bits = [f"Reminder from {tenant.name}: your {t.name.lower()} is {_when(tenant, a.starts_at, datetime.now(UTC))}"]
        if who and t.category != "service":
            bits[0] += f" with {who}"
        text = bits[0] + ". Reply here if you need to change it."
        m = Message(conversation_id=conv_id, direction="outbound", author_type="system", body=text, status="queued")
        db.add(m)
        a.reminders_sent = [*sent, payload["minutes_before"]]
        await db.flush()
        message_id = m.id
    try:
        d = await deliver(tenant_id, message_id)
    except Blocked as b:
        return f"blocked: {b.reason}"
    return "sent" if d.ok else f"failed: {d.error}"
