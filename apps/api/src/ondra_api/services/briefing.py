"""The owner's morning briefing (BUILD_PLAN.md §4.4): what needs them today, at the time they chose, in the
dealership's own time zone. The numbers are counted the way the dashboard counts them, so the two never disagree.

    counts()     the five numbers, plus the names behind the ones the owner acts on first
    run()        the job: send to every owner, then line up tomorrow's
    schedule()   (re)queue the next briefing after the settings change
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ondra_core.models import Appointment, Contact, Job, Message, Task, Tenant
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.db import tenant_session
from ondra_api.services.jobs import enqueue
from ondra_api.services.owner import owners, send_to_owner, settings_of

OPEN = ("open", "in_progress")


def _tz(tenant: Tenant) -> ZoneInfo:
    return ZoneInfo((tenant.timezones or ["America/Chicago"])[0])


async def counts(db: AsyncSession, now: datetime | None = None) -> dict:
    """What the briefing says. VIPs waiting: VIP clients with an open task. Hot leads: other clients with an open
    high-urgency task. Drafts: Ondra's drafts waiting for approval. Overdue: open tasks past their due time.
    Appointments: booked or confirmed, starting today in the dealership's time zone."""
    now = now or datetime.now(UTC)
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    tz = _tz(tenant)
    start = datetime.combine(now.astimezone(tz).date(), time(0), tz)
    vip_rows = (await db.execute(select(Contact.display_name).join(Task, Task.contact_id == Contact.id)
                                 .where(Contact.is_vip.is_(True), Task.status.in_(OPEN)).group_by(Contact.id, Contact.display_name)
                                 .order_by(func.min(Task.created_at)))).scalars().all()
    hot_rows = (await db.execute(select(Contact.display_name).join(Task, Task.contact_id == Contact.id)
                                 .where(Contact.is_vip.is_(False), Task.status.in_(OPEN), Task.urgency == "high")
                                 .group_by(Contact.id, Contact.display_name).order_by(func.min(Task.created_at)))).scalars().all()
    drafts = (await db.execute(select(func.count()).select_from(Message).where(Message.is_draft.is_(True), Message.status == "queued"))).scalar_one()
    overdue = (await db.execute(select(func.count()).select_from(Task).where(Task.status.in_(OPEN), Task.due_at < now))).scalar_one()
    appts = (await db.execute(select(func.count()).select_from(Appointment).where(
        Appointment.starts_at >= start, Appointment.starts_at < start + timedelta(days=1), Appointment.status.in_(("booked", "confirmed"))))).scalar_one()
    return {"date": now.astimezone(tz).strftime("%A, %B %-d"), "vips_waiting": len(vip_rows), "hot_leads": len(hot_rows), "drafts": drafts,
            "overdue_tasks": overdue, "appointments": appts, "vip_names": list(vip_rows[:5]), "hot_names": list(hot_rows[:5])}


def _n(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


def render(first_name: str, c: dict) -> str:
    """The briefing in plain words, for an owner who has written in the last 24 hours (so free text is allowed)."""
    lines = [f"Good morning {first_name}. {c['date']}:"]
    vips = f"{_n(c['vips_waiting'], 'VIP')} waiting" + (f": {', '.join(c['vip_names'])}" if c["vip_names"] else "")
    hot = _n(c["hot_leads"], "hot lead") + (f": {', '.join(c['hot_names'])}" if c["hot_names"] else "")
    lines += [vips + ".", hot + ".", f"{_n(c['drafts'], 'draft')} to approve.", f"{_n(c['overdue_tasks'], 'overdue task')}.",
              f"{_n(c['appointments'], 'appointment')} today."]
    if not (c["vips_waiting"] or c["hot_leads"] or c["drafts"] or c["overdue_tasks"]):
        lines.append("Nothing is waiting on you.")
    lines.append("Reply here to ask about any of them.")
    return "\n".join(lines)


def template(first_name: str, c: dict) -> dict:
    return {"name": "ondra_morning_briefing", "language": "en_US",
            "params": [first_name, c["date"], str(c["vips_waiting"]), str(c["hot_leads"]), str(c["drafts"]), str(c["overdue_tasks"]),
                       str(c["appointments"])]}


def next_time(tenant: Tenant, now: datetime | None = None) -> datetime:
    """The next briefing time, in the dealership's time zone (so it stays at 7:30 across a clock change)."""
    now = now or datetime.now(UTC)
    tz = _tz(tenant)
    h, m = map(int, settings_of(tenant)["briefing_time"].split(":"))
    local = now.astimezone(tz)
    at = local.replace(hour=h, minute=m, second=0, microsecond=0)
    if at <= local:
        at = datetime.combine(local.date() + timedelta(days=1), time(h, m), tz)
    return at.astimezone(UTC)


async def schedule(db: AsyncSession) -> datetime | None:
    """Drop any briefing lined up and, if briefings are on, queue the next one. Call after the settings change."""
    await db.execute(delete(Job).where(Job.kind == "owner_briefing", Job.status == "queued"))
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    if not settings_of(tenant)["briefing_on"]:
        return None
    at = next_time(tenant)
    enqueue(db, "owner_briefing", {}, run_at=at)
    return at


async def send_now(tenant_id: uuid.UUID, now: datetime | None = None) -> dict:
    """Send the briefing to every owner. Returns the counts and how many it reached."""
    async with tenant_session(tenant_id) as db:
        c = await counts(db, now)
        to = [(u.id, u.name.split()[0]) for u in await owners(db)]
    sent = 0
    for user_id, first in to:
        sent += await send_to_owner(tenant_id, user_id, render(first, c), kind="briefing", template=template(first, c),
                                    meta={k: c[k] for k in ("vips_waiting", "hot_leads", "drafts", "overdue_tasks", "appointments")})
    return {**c, "owners": len(to), "sent": sent}


async def run(tenant_id: uuid.UUID, payload: dict, now: datetime | None = None) -> str:
    """The job. Tomorrow's is lined up first, so one failed send never stops the briefings."""
    async with tenant_session(tenant_id) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        if not settings_of(tenant)["briefing_on"]:
            return "skipped: briefings are off"
        enqueue(db, "owner_briefing", {}, run_at=next_time(tenant, (now or datetime.now(UTC)) + timedelta(minutes=1)))
    out = await send_now(tenant_id, now)
    return f"sent to {out['sent']} of {out['owners']}"
