"""Booking (BUILD_PLAN.md §4.3, Step 4): appointment types, availability and appointments.

- `AvailabilityProvider` is the interface (§4.3). `InternalCalendar` is the default: Ondra's own calendar is the source
  of truth. Google/Microsoft calendars and DMS schedulers plug in behind the same interface later.
- A slot needs a free eligible person (spread across the team) and a free resource of each required kind (a bay
  for service). Slots are offered as opaque ids, so the AI can only book a time the calendar actually offered.
- Booking runs in a savepoint; the database's exclusion constraints refuse any overlap for the same person or bay,
  so two bookings racing for one slot can't both succeed. The loser gets `SlotTaken`.
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from ondra_core.models import Appointment, AppointmentResource, AppointmentType, Event, Resource, Tenant, User
from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
STEP = timedelta(minutes=30)
LIVE = ("booked", "confirmed")

# Starting points a dealer adjusts in Settings (BUILD_PLAN.md §4.3). Durations in minutes.
TEMPLATES: dict[str, dict] = {
    "test_drive": {"name": "Test drive", "category": "test_drive", "duration_min": 45, "buffer_min": 15,
                   "eligible_roles": ["sales"], "required_resource_kinds": [], "min_notice_min": 60,
                   "description": "Drive a car from stock with a salesperson."},
    "showroom_visit": {"name": "Showroom visit", "category": "showroom", "duration_min": 45, "buffer_min": 0,
                       "eligible_roles": ["sales"], "required_resource_kinds": [], "min_notice_min": 60,
                       "description": "Meet a salesperson to look at cars."},
    "trade_in_appraisal": {"name": "Trade-in appraisal", "category": "appraisal", "duration_min": 30, "buffer_min": 0,
                           "eligible_roles": ["sales", "manager"], "required_resource_kinds": [], "min_notice_min": 120,
                           "description": "We inspect your car and give you a written offer."},
    "oil_change": {"name": "Oil change", "category": "service", "duration_min": 60, "buffer_min": 0,
                   "eligible_roles": ["service"], "required_resource_kinds": ["service_bay"], "min_notice_min": 120,
                   "description": "Oil and filter change, with a multi-point check."},
    "service_inspection": {"name": "Service and repairs", "category": "service", "duration_min": 90, "buffer_min": 0,
                           "eligible_roles": ["service"], "required_resource_kinds": ["service_bay"], "min_notice_min": 120,
                           "description": "Diagnosis and repairs: brakes, noises, warning lights, inspections."},
    "vehicle_delivery": {"name": "Vehicle delivery", "category": "delivery", "duration_min": 60, "buffer_min": 15,
                         "eligible_roles": ["sales"], "required_resource_kinds": [], "min_notice_min": 1440,
                         "description": "Collect your new car: paperwork and a walkthrough."},
}
DEFAULT_REMINDERS = [1440, 120]  # minutes before: the day before, and two hours before


class SlotTaken(Exception):
    """Someone else booked that person or bay first."""


class NotBookable(Exception):
    """The slot breaks the type's rules (notice, hours, eligibility) or the id is malformed."""


@dataclass
class Slot:
    type_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    blocks_until: datetime
    user_id: uuid.UUID | None
    user_name: str | None
    resource_ids: list[uuid.UUID] = field(default_factory=list)
    resource_names: list[str] = field(default_factory=list)
    label: str = ""

    @property
    def slot_id(self) -> str:
        raw = json.dumps([str(self.type_id), self.starts_at.isoformat(), str(self.user_id) if self.user_id else None,
                          [str(r) for r in self.resource_ids]], separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    def as_tool(self) -> dict:
        return {"slot_id": self.slot_id, "when": self.label, "with": self.user_name,
                "resources": self.resource_names, "starts_at": self.starts_at.isoformat()}


def decode_slot_id(slot_id: str) -> tuple[uuid.UUID, datetime, uuid.UUID | None, list[uuid.UUID]]:
    try:
        raw = base64.urlsafe_b64decode(slot_id + "=" * (-len(slot_id) % 4)).decode()
        t, s, u, rs = json.loads(raw)
        return uuid.UUID(t), datetime.fromisoformat(s), uuid.UUID(u) if u else None, [uuid.UUID(r) for r in rs]
    except (ValueError, TypeError, json.JSONDecodeError):
        raise NotBookable("That time isn't one I offered. Check availability again.") from None


def tz_of(tenant: Tenant) -> ZoneInfo:
    return ZoneInfo((tenant.timezones or ["America/Chicago"])[0])


def slot_label(start: datetime, tz: ZoneInfo, resource_names: list[str]) -> str:
    local = start.astimezone(tz)
    label = local.strftime("%a %-I:%M %p").replace("AM", "am").replace("PM", "pm")
    return label + (f", {', '.join(resource_names)}" if resource_names else "")


def _hours_for(t: AppointmentType, tenant: Tenant, day: date) -> tuple[time, time] | None:
    hours = (t.bookable_hours or {}) or (tenant.business_hours or {})
    span = hours.get(DAYS[day.weekday()])
    if not span:
        return None
    return time.fromisoformat(span[0]), time.fromisoformat(span[1])


class AvailabilityProvider(Protocol):
    async def find_slots(self, t: AppointmentType, *, start_from: datetime, until: datetime, limit: int = 6,
                         part_of_day: str | None = None) -> list[Slot]: ...


class InternalCalendar:
    """Ondra's own calendar, read from appointments in Postgres (tenant-scoped like everything else)."""

    def __init__(self, db: AsyncSession, tenant: Tenant) -> None:
        self.db = db
        self.tenant = tenant
        self.tz = tz_of(tenant)

    async def _staff(self, t: AppointmentType) -> list[User]:
        if not t.eligible_roles and not t.eligible_user_ids:
            return []
        q = select(User).where(User.active.is_(True))
        conds = []
        if t.eligible_roles:
            conds.append(User.role.in_(t.eligible_roles))
        if t.eligible_user_ids:
            conds.append(User.id.in_(t.eligible_user_ids))
        from sqlalchemy import or_

        return list((await self.db.execute(q.where(or_(*conds)).order_by(User.name))).scalars())

    async def find_slots(self, t: AppointmentType, *, start_from: datetime, until: datetime, limit: int = 6,
                         part_of_day: str | None = None) -> list[Slot]:
        now = datetime.now(UTC)
        start_from = max(start_from, now + timedelta(minutes=t.min_notice_min or 0))
        until = min(until, now + timedelta(days=t.max_days_ahead or 30))
        if start_from >= until:
            return []
        staff = await self._staff(t)
        if (t.eligible_roles or t.eligible_user_ids) and not staff:
            return []
        resources = {
            kind: list((await self.db.execute(select(Resource).where(Resource.kind == kind, Resource.active.is_(True))
                                              .order_by(Resource.name))).scalars())
            for kind in (t.required_resource_kinds or [])
        }
        if any(not rs for rs in resources.values()):
            return []
        busy_user = (await self.db.execute(
            select(Appointment.assigned_user_id, Appointment.starts_at, Appointment.blocks_until)
            .where(Appointment.status.in_(LIVE), Appointment.starts_at < until, Appointment.blocks_until > start_from)
        )).all()
        busy_res = (await self.db.execute(
            select(AppointmentResource.resource_id, AppointmentResource.starts_at, AppointmentResource.blocks_until)
            .where(AppointmentResource.active.is_(True), AppointmentResource.starts_at < until,
                   AppointmentResource.blocks_until > start_from)
        )).all()

        def free(busy, key, s, e) -> bool:
            return not any(b[0] == key and b[1] < e and b[2] > s for b in busy)

        duration = timedelta(minutes=t.duration_min)
        buffer = timedelta(minutes=t.buffer_min or 0)
        slots: list[Slot] = []
        day = start_from.astimezone(self.tz).date()
        last = until.astimezone(self.tz).date()
        while day <= last and len(slots) < limit:
            hours = _hours_for(t, self.tenant, day)
            if hours:
                cursor = datetime.combine(day, hours[0], self.tz)
                close = datetime.combine(day, hours[1], self.tz)
                load: dict[uuid.UUID, int] = {u.id: sum(1 for b in busy_user if b[0] == u.id and
                                                         b[1].astimezone(self.tz).date() == day) for u in staff}
                while cursor + duration <= close and len(slots) < limit:
                    s, e = cursor.astimezone(UTC), (cursor + duration).astimezone(UTC)
                    block = e + buffer
                    hour = cursor.hour
                    wanted = (part_of_day is None or (part_of_day == "morning" and hour < 12)
                              or (part_of_day == "afternoon" and 12 <= hour < 17) or (part_of_day == "evening" and hour >= 17))
                    if start_from <= s < until and wanted:
                        who = None
                        if staff:
                            free_staff = [u for u in staff if free(busy_user, u.id, s, block)]
                            who = min(free_staff, key=lambda u: load[u.id]) if free_staff else None
                        picked = []
                        for rs in resources.values():
                            r = next((r for r in rs if free(busy_res, r.id, s, block)), None)
                            if r is None:
                                break
                            picked.append(r)
                        if (who is not None or not staff) and len(picked) == len(resources):
                            names = [r.name for r in picked]
                            slots.append(Slot(t.id, s, e, block, who.id if who else None, who.name if who else None,
                                              [r.id for r in picked], names, slot_label(s, self.tz, names)))
                    cursor += STEP
            day += timedelta(days=1)
        return slots


async def find_type(db: AsyncSession, kind: str) -> AppointmentType | None:
    """An active appointment type by id, name or category ("test_drive", "service", "Oil change")."""
    q = select(AppointmentType).where(AppointmentType.active.is_(True))
    try:
        hit = (await db.execute(q.where(AppointmentType.id == uuid.UUID(kind)))).scalar_one_or_none()
        if hit:
            return hit
    except ValueError:
        pass
    types = list((await db.execute(q.order_by(AppointmentType.name))).scalars())
    k = kind.strip().lower().replace("_", " ")
    for t in types:
        if t.name.lower() == k:
            return t
    for t in types:
        if t.category.replace("_", " ") == k or k in t.name.lower():
            return t
    return None


async def _hold_resources(db: AsyncSession, a: Appointment, resource_ids: list[uuid.UUID]) -> None:
    for rid in resource_ids:
        db.add(AppointmentResource(appointment_id=a.id, resource_id=rid, starts_at=a.starts_at,
                                   blocks_until=a.blocks_until))


async def _check(db: AsyncSession, tenant: Tenant, t: AppointmentType, start: datetime, user_id, resource_ids) -> tuple:
    if not t.active:
        raise NotBookable("That appointment type isn't offered any more.")
    now = datetime.now(UTC)
    if start < now + timedelta(minutes=t.min_notice_min or 0) or start > now + timedelta(days=t.max_days_ahead or 30):
        raise NotBookable("That time is too soon or too far ahead to book.")
    tz = tz_of(tenant)
    hours = _hours_for(t, tenant, start.astimezone(tz).date())
    end = start + timedelta(minutes=t.duration_min)
    if hours is None or not (hours[0] <= start.astimezone(tz).time() and end.astimezone(tz).time() <= hours[1]):
        raise NotBookable("That time is outside the hours for this appointment.")
    user = await db.get(User, user_id) if user_id else None
    if (t.eligible_roles or t.eligible_user_ids) and (
        user is None or not user.active or (user.role not in (t.eligible_roles or []) and user.id not in (t.eligible_user_ids or []))
    ):
        raise NotBookable("That person can't take this appointment.")
    res = [await db.get(Resource, r) for r in resource_ids]
    kinds = sorted(r.kind for r in res if r is not None and r.active)
    if kinds != sorted(t.required_resource_kinds or []):
        raise NotBookable("That appointment needs a different bay or resource.")
    return end, end + timedelta(minutes=t.buffer_min or 0), user, [r.name for r in res]


async def book(db: AsyncSession, tenant: Tenant, *, slot_id: str, contact_id: uuid.UUID, source: str,
               conversation_id: uuid.UUID | None = None, details: dict | None = None) -> Appointment:
    type_id, start, user_id, resource_ids = decode_slot_id(slot_id)
    t = await db.get(AppointmentType, type_id)
    if t is None:
        raise NotBookable("That appointment type doesn't exist.")
    end, block, user, names = await _check(db, tenant, t, start, user_id, resource_ids)
    details = dict(details or {})
    a = Appointment(contact_id=contact_id, appointment_type_id=t.id, starts_at=start, ends_at=end, blocks_until=block,
                    assigned_user_id=user.id if user else None, resource_ids=resource_ids, source=source, status="booked",
                    conversation_id=conversation_id, details=details,
                    service_type=details.get("service_type") or (t.name if t.category == "service" else None),
                    transport=details.get("transport"), vin=details.get("vin"))
    try:
        async with db.begin_nested():
            db.add(a)
            await db.flush()
            await _hold_resources(db, a, resource_ids)
            if details.get("transport") == "loaner":
                await _try_hold_loaner(db, a)
            await db.flush()
    except IntegrityError as exc:
        if "no_double_booking" in str(exc.orig):
            raise SlotTaken("That time was just taken.") from None
        raise
    db.add(Event(type="appointment.booked", payload={"appointment_id": str(a.id), "source": source,
                                                     "type": t.name, "starts_at": start.isoformat()}))
    from ondra_api.services.reminders import schedule_reminders

    await schedule_reminders(db, tenant, a, t)
    return a


async def _try_hold_loaner(db: AsyncSession, a: Appointment) -> None:
    """Hold a free loaner for the appointment if there is one; otherwise note that a person has to arrange it."""
    loaners = (await db.execute(select(Resource).where(Resource.kind == "loaner", Resource.active.is_(True))
                                .order_by(Resource.name))).scalars().all()
    for r in loaners:
        try:
            async with db.begin_nested():
                db.add(AppointmentResource(appointment_id=a.id, resource_id=r.id, starts_at=a.starts_at,
                                           blocks_until=a.blocks_until))
                await db.flush()
            a.resource_ids = [*a.resource_ids, r.id]
            a.details = {**a.details, "loaner": r.name}
            return
        except IntegrityError:
            continue
    a.details = {**a.details, "loaner": None, "loaner_note": "No loaner free at that time; the service team will arrange transport."}


async def reschedule(db: AsyncSession, tenant: Tenant, a: Appointment, slot_id: str) -> Appointment:
    type_id, start, user_id, resource_ids = decode_slot_id(slot_id)
    if type_id != a.appointment_type_id:
        raise NotBookable("That time is for a different kind of appointment.")
    t = await db.get(AppointmentType, type_id)
    end, block, user, _ = await _check(db, tenant, t, start, user_id, resource_ids)
    before = a.starts_at
    try:
        async with db.begin_nested():
            await db.execute(update(AppointmentResource).where(AppointmentResource.appointment_id == a.id).values(active=False))
            a.starts_at, a.ends_at, a.blocks_until = start, end, block
            a.assigned_user_id = user.id if user else None
            a.resource_ids = resource_ids
            await db.flush()
            await _hold_resources(db, a, resource_ids)
            if a.transport == "loaner":
                await _try_hold_loaner(db, a)
            await db.flush()
    except IntegrityError as exc:
        await db.refresh(a)
        if "no_double_booking" in str(exc.orig):
            raise SlotTaken("That time was just taken.") from None
        raise
    a.reminders_sent = []
    db.add(Event(type="appointment.rescheduled", payload={"appointment_id": str(a.id), "from": before.isoformat(),
                                                          "to": start.isoformat()}))
    from ondra_api.services.reminders import schedule_reminders

    await schedule_reminders(db, tenant, a, t)
    return a


async def set_status(db: AsyncSession, a: Appointment, status: str, by: str) -> Appointment:
    """cancel, confirm, or record whether they showed up (no-show tracking)."""
    if status not in ("booked", "confirmed", "showed", "no_show", "cancelled"):
        raise NotBookable("Unknown status.")
    before = a.status
    a.status = status
    if status in ("cancelled",):
        await db.execute(update(AppointmentResource).where(and_(AppointmentResource.appointment_id == a.id))
                         .values(active=False))
    db.add(Event(type=f"appointment.{status}", payload={"appointment_id": str(a.id), "from": before, "by": by}))
    await db.flush()
    return a


def resolve_day(tenant: Tenant, day: str | None) -> date | None:
    """The day a person or the model means: 'today', 'tomorrow', a weekday name or abbreviation (the next one, today
    included), or an ISO date, found anywhere in the text, so "this Saturday" and "Saturday 9 am" work too. (On a
    call, "Saturday 9 am" wasn't understood, the search quietly fell back to other days, and the caller was told
    Saturday was full.) None if no day is named."""
    if not day:
        return None
    today = datetime.now(UTC).astimezone(tz_of(tenant)).date()
    d = day.strip().lower()
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", d)
    if iso:
        try:
            return date.fromisoformat(iso.group(1))
        except ValueError:
            return None
    if re.search(r"\btoday\b|\btonight\b", d):
        return today
    if re.search(r"\btomorrow\b", d):
        return today + timedelta(days=1)
    for i, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")):
        if re.search(rf"\b({name}|{name[:3]})\b", d):
            return today + timedelta(days=(i - today.weekday()) % 7)
    return None


def describe_day(day: date) -> str:
    return day.strftime("%a %b %-d")


def local_window(tenant: Tenant, day: date | None, days: int = 7) -> tuple[datetime, datetime]:
    tz = tz_of(tenant)
    if day is None:
        return datetime.now(UTC), datetime.now(UTC) + timedelta(days=days)
    start = datetime.combine(day, time(0), tz)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)
