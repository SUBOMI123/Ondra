"""A customer's own booking, reached from the link in their confirmation (`/b?t=<token>` on the web app).

No sign-in: the signed token is the key, and it opens that one booking only (services/confirmations.py). They can see
it, add it to their calendar, move it to another free time, or cancel it. Each change goes through the same booking
service as staff and Ondra use (no double-booking), and is confirmed by the same rules.

    GET  /public/bookings/{token}             the booking, and Add-to-calendar links
    GET  /public/bookings/{token}/invite.ics  the calendar invite (Apple Calendar and everything else)
    GET  /public/bookings/{token}/times       other free times for the same kind of appointment
    POST /public/bookings/{token}/move        {slot_id}
    POST /public/bookings/{token}/cancel
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from ondra_core.models import Appointment, AppointmentType, Tenant, User
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.db import tenant_session
from ondra_api.services import booking, confirmations

router = APIRouter(prefix="/public/bookings", tags=["public"])
GONE = "This link doesn't match a booking. Reply to the message it came in, and we'll help."
# A link stops working 30 days after the booking: it's for that booking, not a standing key to the customer's record.
LINK_LIFE = timedelta(days=30)
# Moves through one link before it has to go through the dealership (each move sends confirmations).
MAX_LINK_MOVES = 5


async def _load(db: AsyncSession, appointment_id: uuid.UUID) -> tuple[Appointment, AppointmentType, Tenant]:
    a = await db.get(Appointment, appointment_id)
    if a is None or a.ends_at < datetime.now(UTC) - LINK_LIFE:
        raise HTTPException(404, GONE)
    return a, await db.get(AppointmentType, a.appointment_type_id), (await db.execute(select(Tenant).limit(1))).scalar_one()


def _ids(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    found = confirmations.read_token(token)
    if found is None:
        raise HTTPException(404, GONE)
    return found


def _changeable(a: Appointment) -> bool:
    return a.status in booking.LIVE and a.starts_at > datetime.now(UTC)


async def _out(db: AsyncSession, token: str, tenant_id: uuid.UUID, a: Appointment, t: AppointmentType, tenant: Tenant) -> dict:
    url = confirmations.manage_url(tenant_id, a.id)
    person = await db.get(User, a.assigned_user_id) if a.assigned_user_id else None
    return {
        "dealer": tenant.name, "address": (tenant.settings or {}).get("address"), "phone": (tenant.settings or {}).get("phone"),
        "what": t.name, "starts_at": a.starts_at.isoformat(), "ends_at": a.ends_at.isoformat(), "timezone": str(booking.tz_of(tenant)),
        "with": person.name.split()[0] if person and t.category != "service" else None,
        "status": "cancelled" if a.status == "cancelled" else "past" if a.starts_at <= datetime.now(UTC) else "booked",
        "can_change": _changeable(a),
        "calendar": {**confirmations.calendar_links(tenant, a, t, url), "ics": f"/public/bookings/{token}/invite.ics"},
    }


@router.get("/{token}")
async def view(token: str) -> dict:
    tenant_id, appointment_id = _ids(token)
    async with tenant_session(tenant_id) as db:
        a, t, tenant = await _load(db, appointment_id)
        return await _out(db, token, tenant_id, a, t, tenant)


@router.get("/{token}/invite.ics")
async def invite(token: str) -> Response:
    tenant_id, appointment_id = _ids(token)
    async with tenant_session(tenant_id) as db:
        a, t, tenant = await _load(db, appointment_id)
        moves = sum(1 for c in a.confirmations or [] if c.get("kind") in ("moved", "cancelled"))
        body = confirmations.ics(tenant, a, t, cancelled=a.status == "cancelled", sequence=moves,
                                 url=confirmations.manage_url(tenant_id, a.id))
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{t.name.lower().replace(" ", "-")}.ics"'})


@router.get("/{token}/times")
async def times(token: str) -> dict:
    tenant_id, appointment_id = _ids(token)
    async with tenant_session(tenant_id) as db:
        a, t, tenant = await _load(db, appointment_id)
        if not _changeable(a):
            return {"items": []}
        start, until = booking.local_window(tenant, None, days=14)
        slots = await booking.InternalCalendar(db, tenant).find_slots(t, start_from=start, until=until, limit=120)
        return {"items": [{"slot_id": s.slot_id, "starts_at": s.starts_at.isoformat(), "with": s.user_name.split()[0] if s.user_name and t.category != "service" else None}
                          for s in slots if s.starts_at != a.starts_at]}


class MoveIn(BaseModel):
    slot_id: str


@router.post("/{token}/move")
async def move(token: str, body: MoveIn) -> dict:
    tenant_id, appointment_id = _ids(token)
    async with tenant_session(tenant_id) as db:
        a, t, tenant = await _load(db, appointment_id)
        if not _changeable(a):
            raise HTTPException(409, "This booking can't be changed online any more. Reply to the message it came in, and we'll help.")
        if sum(1 for c in a.confirmations or [] if c.get("kind") == "moved") >= MAX_LINK_MOVES:
            raise HTTPException(409, "This booking has been moved a few times already. Reply to the message it came in, and we'll find a time.")
        # Only a time this page offered: a slot id isn't signed, so one made up by hand (an off-grid start, or a
        # person who isn't on this kind of booking) is refused rather than trusted.
        start, until = booking.local_window(tenant, None, days=14)
        offered = {s.slot_id for s in await booking.InternalCalendar(db, tenant).find_slots(t, start_from=start, until=until, limit=120)}
        if body.slot_id not in offered:
            raise HTTPException(409, "That time isn't free any more. Choose another.")
        try:
            await booking.reschedule(db, tenant, a, body.slot_id)
        except booking.SlotTaken:
            raise HTTPException(409, "Someone just took that time. Choose another.") from None
        except booking.NotBookable as e:
            raise HTTPException(422, str(e)) from None
        return await _out(db, token, tenant_id, a, t, tenant)


@router.post("/{token}/cancel")
async def cancel(token: str) -> dict:
    tenant_id, appointment_id = _ids(token)
    async with tenant_session(tenant_id) as db:
        a, t, tenant = await _load(db, appointment_id)
        if not _changeable(a):
            raise HTTPException(409, "This booking can't be changed online any more. Reply to the message it came in, and we'll help.")
        await booking.set_status(db, a, "cancelled", by="customer_link")
        return await _out(db, token, tenant_id, a, t, tenant)


