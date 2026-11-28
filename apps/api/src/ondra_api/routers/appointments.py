"""Booking for staff (Step 4): appointment types and resources (Settings), the day calendar, and appointments.

    GET    /appointment-types                     all types (inactive too, for Settings)
    GET    /appointment-types/templates           the starting points (test drive, oil change, ...)
    POST   /appointment-types                     a new type, from a template or custom
    PATCH  /appointment-types/{id}                edit, or switch off
    GET    /resources | POST /resources | PATCH /resources/{id}     bays, loaners, rooms
    GET    /calendar?date=YYYY-MM-DD              lanes (salespeople, service bays) and the day's appointments
    GET    /availability?type_id=&date=           open slots, for staff booking
    POST   /appointments                          book a slot for a client
    POST   /appointments/{id}/reschedule          move to another slot
    PATCH  /appointments/{id}                     confirm, cancel, showed or no-show

Types and resources: owners and admins. Calendar: everyone who reads clients. Appointments: people who work leads.
A VIP's appointment shows as "Busy" to roles that can't see VIPs: they see the time is taken, not who it's for.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import Appointment, AppointmentType, AuditLog, Contact, Resource, Tenant, User
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.services import booking

router = APIRouter(tags=["booking"])

CATEGORIES = ("test_drive", "showroom", "appraisal", "service", "delivery", "custom")
ROLES = ("admin", "manager", "sales", "service", "ops")


# --- types -------------------------------------------------------------------------------------------------------

class TypeIn(BaseModel):
    template: str | None = None  # start from a template; fields below override it
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)
    category: Literal["test_drive", "showroom", "appraisal", "service", "delivery", "custom"] | None = None
    duration_min: int | None = Field(None, ge=10, le=480)
    buffer_min: int | None = Field(None, ge=0, le=240)
    eligible_roles: list[Literal["admin", "manager", "sales", "service", "ops"]] | None = None
    required_resource_kinds: list[Literal["service_bay", "loaner", "demo_vehicle", "room"]] | None = None
    min_notice_min: int | None = Field(None, ge=0, le=10080)
    max_days_ahead: int | None = Field(None, ge=1, le=365)
    reminder_schedule: list[int] | None = None
    active: bool | None = None

    @field_validator("reminder_schedule")
    @classmethod
    def _reminders(cls, v):
        if v is not None and (len(v) > 4 or any(m < 15 or m > 10080 for m in v)):
            raise ValueError("Reminders go between 15 minutes and 7 days before, at most four.")
        return v


def _type_out(t: AppointmentType) -> dict:
    return {"id": str(t.id), "name": t.name, "description": t.description, "category": t.category,
            "duration_min": t.duration_min, "buffer_min": t.buffer_min, "eligible_roles": list(t.eligible_roles or []),
            "required_resource_kinds": list(t.required_resource_kinds or []), "min_notice_min": t.min_notice_min,
            "max_days_ahead": t.max_days_ahead, "reminder_schedule": list(t.reminder_schedule or []), "active": t.active}


def _audit(db: AsyncSession, caller: Caller, action: str, resource: str, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource=resource,
                    before=before, after=after))


@router.get("/appointment-types")
async def list_types(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    _, db = ctx
    rows = (await db.execute(select(AppointmentType).order_by(AppointmentType.active.desc(), AppointmentType.name))).scalars()
    return {"items": [_type_out(t) for t in rows]}


@router.get("/appointment-types/templates")
async def templates(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    return {"items": [{"key": k, **v, "reminder_schedule": booking.DEFAULT_REMINDERS} for k, v in booking.TEMPLATES.items()]}


@router.post("/appointment-types", status_code=201)
async def create_type(body: TypeIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    base: dict = {"reminder_schedule": booking.DEFAULT_REMINDERS, "category": "custom", "duration_min": 30,
                  "buffer_min": 0, "eligible_roles": ["sales"], "required_resource_kinds": [], "min_notice_min": 60,
                  "max_days_ahead": 30}
    if body.template:
        if body.template not in booking.TEMPLATES:
            raise HTTPException(422, "No template with that name.")
        base |= booking.TEMPLATES[body.template]
    base |= body.model_dump(exclude_none=True, exclude={"template"})
    if not base.get("name"):
        raise HTTPException(422, "Give the appointment type a name.")
    if not base["eligible_roles"]:
        raise HTTPException(422, "Choose who can take it.")
    t = AppointmentType(**base)
    db.add(t)
    await db.flush()
    out = _type_out(t)
    _audit(db, caller, "booking.type_create", f"appointment_type:{t.id}", None, out)
    return out


@router.patch("/appointment-types/{type_id}")
async def update_type(type_id: uuid.UUID, body: TypeIn,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    t = await db.get(AppointmentType, type_id)
    if t is None:
        raise HTTPException(404, "No appointment type with that id.")
    before = _type_out(t)
    for k, v in body.model_dump(exclude_none=True, exclude={"template"}).items():
        setattr(t, k, v)
    if not t.eligible_roles and not t.eligible_user_ids:
        raise HTTPException(422, "Choose who can take it.")
    await db.flush()
    out = _type_out(t)
    _audit(db, caller, "booking.type_update", f"appointment_type:{t.id}", before, out)
    return out


# --- resources ---------------------------------------------------------------------------------------------------

class ResourceIn(BaseModel):
    kind: Literal["service_bay", "loaner", "demo_vehicle", "room"] | None = None
    name: str | None = Field(None, min_length=1, max_length=120)
    active: bool | None = None


def _res_out(r: Resource) -> dict:
    return {"id": str(r.id), "kind": r.kind, "name": r.name, "active": r.active}


@router.get("/resources")
async def list_resources(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    _, db = ctx
    rows = (await db.execute(select(Resource).order_by(Resource.kind, Resource.name))).scalars()
    return {"items": [_res_out(r) for r in rows]}


@router.post("/resources", status_code=201)
async def create_resource(body: ResourceIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    if not body.kind or not body.name:
        raise HTTPException(422, "Give it a kind and a name.")
    r = Resource(kind=body.kind, name=body.name.strip())
    db.add(r)
    await db.flush()
    _audit(db, caller, "booking.resource_create", f"resource:{r.id}", None, _res_out(r))
    return _res_out(r)


@router.patch("/resources/{resource_id}")
async def update_resource(resource_id: uuid.UUID, body: ResourceIn,
                          ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    r = await db.get(Resource, resource_id)
    if r is None:
        raise HTTPException(404, "No resource with that id.")
    before = _res_out(r)
    if body.name:
        r.name = body.name.strip()
    if body.active is not None:
        r.active = body.active
    await db.flush()
    _audit(db, caller, "booking.resource_update", f"resource:{r.id}", before, _res_out(r))
    return _res_out(r)


# --- calendar and appointments -----------------------------------------------------------------------------------

async def _tenant(db: AsyncSession) -> Tenant:
    return (await db.execute(select(Tenant).limit(1))).scalar_one()


async def _appointment_out(db: AsyncSession, caller: Caller, a: Appointment, types: dict, names: dict, bays: dict) -> dict:
    c = await db.get(Contact, a.contact_id)
    private = c is not None and c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id \
        and a.assigned_user_id != caller.user_id
    t = types.get(a.appointment_type_id)
    bay_ids = [r for r in (a.resource_ids or []) if r in bays]
    return {
        "id": str(a.id), "starts_at": a.starts_at.isoformat(), "ends_at": a.ends_at.isoformat(), "status": a.status,
        "source": a.source, "title": "Busy" if private else (t.name if t else "Appointment"),
        "category": t.category if t else None,
        "client": None if private else {"id": str(c.id), "name": c.display_name, "is_vip": c.is_vip},
        "with": names.get(a.assigned_user_id), "assigned_user_id": str(a.assigned_user_id) if a.assigned_user_id else None,
        "bays": [bays[r] for r in bay_ids], "lane_ids": [str(r) for r in bay_ids] or ([str(a.assigned_user_id)] if a.assigned_user_id else []),
        "details": {} if private else (a.details or {}), "conversation_id": str(a.conversation_id) if a.conversation_id and not private else None,
    }


@router.get("/calendar")
async def calendar(day: date = Query(alias="date"), ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    caller, db = ctx
    tenant = await _tenant(db)
    start, end = booking.local_window(tenant, day)
    users = list((await db.execute(select(User).where(User.active.is_(True)).order_by(User.name))).scalars())
    bays = list((await db.execute(select(Resource).where(Resource.kind == "service_bay", Resource.active.is_(True))
                                  .order_by(Resource.name))).scalars())
    lanes = [{"id": str(u.id), "name": u.name, "group": "Sales", "kind": "person"} for u in users if u.role in ("sales", "manager")]
    lanes += [{"id": str(r.id), "name": r.name, "group": "Service", "kind": "bay"} for r in bays]
    appts = (await db.execute(select(Appointment).where(Appointment.starts_at >= start, Appointment.starts_at < end,
                                                        Appointment.status != "cancelled").order_by(Appointment.starts_at))).scalars()
    types = {t.id: t for t in (await db.execute(select(AppointmentType))).scalars()}
    names = {u.id: u.name for u in users}
    bay_names = {r.id: r.name for r in bays}
    tz = booking.tz_of(tenant)
    return {"date": day.isoformat(), "timezone": str(tz), "lanes": lanes,
            "appointments": [await _appointment_out(db, caller, a, types, names, bay_names) for a in appts]}


@router.get("/availability")
async def availability(type_id: uuid.UUID, day: date | None = Query(None, alias="date"),
                       ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    _, db = ctx
    t = await db.get(AppointmentType, type_id)
    if t is None or not t.active:
        raise HTTPException(404, "No active appointment type with that id.")
    tenant = await _tenant(db)
    start, until = booking.local_window(tenant, day, days=14)
    slots = await booking.InternalCalendar(db, tenant).find_slots(t, start_from=start, until=until, limit=40)
    return {"items": [s.as_tool() for s in slots]}


class BookIn(BaseModel):
    slot_id: str
    contact_id: uuid.UUID
    details: dict = Field(default_factory=dict)


class StatusIn(BaseModel):
    status: Literal["booked", "confirmed", "showed", "no_show", "cancelled"]


class RescheduleIn(BaseModel):
    slot_id: str


def _booking_error(exc: Exception) -> HTTPException:
    if isinstance(exc, booking.SlotTaken):
        return HTTPException(409, "That time was just taken. Pick another.")
    return HTTPException(422, str(exc))


async def _visible(db: AsyncSession, caller: Caller, appointment_id: uuid.UUID) -> Appointment:
    a = await db.get(Appointment, appointment_id)
    c = await db.get(Contact, a.contact_id) if a else None
    if a is None or c is None or (c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id
                                  and a.assigned_user_id != caller.user_id):
        raise HTTPException(404, "No appointment with that id.")
    return a


async def _out(db: AsyncSession, caller: Caller, a: Appointment) -> dict:
    types = {t.id: t for t in (await db.execute(select(AppointmentType))).scalars()}
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    bays = {r.id: r.name for r in (await db.execute(select(Resource).where(Resource.kind == "service_bay"))).scalars()}
    return await _appointment_out(db, caller, a, types, names, bays)


@router.post("/appointments", status_code=201)
async def create_appointment(body: BookIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_WRITE))) -> dict:
    caller, db = ctx
    c = await db.get(Contact, body.contact_id)
    if c is None or (c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id):
        raise HTTPException(404, "No client with that id.")
    try:
        a = await booking.book(db, await _tenant(db), slot_id=body.slot_id, contact_id=c.id, source="staff", details=body.details)
    except (booking.SlotTaken, booking.NotBookable) as exc:
        raise _booking_error(exc) from None
    return await _out(db, caller, a)


@router.post("/appointments/{appointment_id}/reschedule")
async def reschedule_appointment(appointment_id: uuid.UUID, body: RescheduleIn,
                                 ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_WRITE))) -> dict:
    caller, db = ctx
    a = await _visible(db, caller, appointment_id)
    if a.status not in booking.LIVE:
        raise HTTPException(409, "Only upcoming appointments can be moved.")
    try:
        await booking.reschedule(db, await _tenant(db), a, body.slot_id)
    except (booking.SlotTaken, booking.NotBookable) as exc:
        raise _booking_error(exc) from None
    return await _out(db, caller, a)


@router.patch("/appointments/{appointment_id}")
async def update_appointment(appointment_id: uuid.UUID, body: StatusIn,
                             ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_WRITE))) -> dict:
    caller, db = ctx
    a = await _visible(db, caller, appointment_id)
    await booking.set_status(db, a, body.status, by=str(caller.user_id))
    return await _out(db, caller, a)


__all__ = ["CATEGORIES", "ROLES", "router"]
