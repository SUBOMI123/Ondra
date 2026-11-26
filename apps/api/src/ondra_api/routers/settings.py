"""Dealer settings (BUILD_PLAN.md §11): business details and opening hours, how Ondra replies, the dealer's own
channel addresses. Anyone signed in can read them; owners and admins can change them. Every change is written to
the audit log with before and after."""

from __future__ import annotations

import re
import uuid
from typing import Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Request
from ondra_core.channels.identity import normalize_email, normalize_phone
from ondra_core.models import AuditLog, ChannelAddress, Policy, Tenant
from ondra_core.permissions import Perm, has_perm
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.channels import real
from ondra_api.deps import Caller, get_db, require

router = APIRouter(prefix="/settings", tags=["settings"])

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_NAMES = dict(zip(DAYS, ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"), strict=True))
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_TIMEZONES = available_timezones()


# --- shapes ------------------------------------------------------------------------------------------------------

class BusinessIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    timezone: str
    # Each day: [opens, closes] as "HH:MM" (24h), or null when closed.
    hours: dict[str, list[str] | None]

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Add the dealership's name.")
        return v.strip()

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        if v not in _TIMEZONES:
            raise ValueError("Choose a time zone from the list.")
        return v

    @field_validator("hours")
    @classmethod
    def _hours(cls, v: dict) -> dict:
        if set(v) != set(DAYS):
            raise ValueError("Opening hours need all seven days.")
        for day, span in v.items():
            if span is None:
                continue
            if len(span) != 2 or not all(_HHMM.match(t) for t in span):
                raise ValueError(f"{DAY_NAMES.get(day, day)}: use times like 9:00 am and 7:00 pm.")
            if span[0] >= span[1]:
                raise ValueError(f"{DAY_NAMES.get(day, day)}: closing time must be after opening time.")
        return v


class RepliesIn(BaseModel):
    draft_mode: bool
    price_disclosure: Literal["none", "listed", "range"]
    handoff_triggers: list[str] = Field(default_factory=list, max_length=20)
    never_say: list[str] = Field(default_factory=list, max_length=50)
    ai_disclosure: Literal["when_asked", "upfront"] = "when_asked"

    @field_validator("handoff_triggers", "never_say")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        out = [s.strip()[:120] for s in v if s.strip()]
        return list(dict.fromkeys(out))


class ChannelIn(BaseModel):
    channel: Literal["sms", "whatsapp", "email", "phone"]
    address: str = Field(min_length=3, max_length=320)


class ChannelPatch(BaseModel):
    active: bool


# --- helpers -----------------------------------------------------------------------------------------------------

def _channel_out(c: ChannelAddress) -> dict:
    live = real(c.channel) is not None and c.provider != "mock"
    return {"id": str(c.id), "channel": c.channel, "address": c.address, "provider": c.provider, "active": c.active,
            "live": live}


async def _policy(db: AsyncSession) -> Policy:
    p = (await db.execute(select(Policy).limit(1))).scalar_one_or_none()
    if p is None:
        p = Policy()
        db.add(p)
        await db.flush()
    return p


def _audit(db: AsyncSession, caller: Caller, request: Request, action: str, resource: str, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource=resource,
                    before=before, after=after, ip=request.client.host if request.client else None))


def _replies(p: Policy, t: Tenant) -> dict:
    return {"draft_mode": p.draft_mode, "price_disclosure": p.price_disclosure,
            "handoff_triggers": list(p.handoff_triggers), "never_say": list(p.never_say),
            "ai_disclosure": (t.settings or {}).get("ai_disclosure", "when_asked")}


def _business(t: Tenant) -> dict:
    hours = t.business_hours or {}
    return {"name": t.name, "timezone": (t.timezones or ["America/Chicago"])[0],
            "hours": {d: hours.get(d) for d in DAYS}}


# --- endpoints ---------------------------------------------------------------------------------------------------

@router.get("")
async def get_settings_(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    p = await _policy(db)
    channels = (await db.execute(select(ChannelAddress).order_by(ChannelAddress.channel, ChannelAddress.created_at))).scalars()
    return {
        "business": _business(t),
        "replies": _replies(p, t),
        "channels": [_channel_out(c) for c in channels],
        "can_edit": has_perm(caller.role, Perm.SETTINGS_MANAGE),
        "timezones": sorted(z for z in _TIMEZONES if z.startswith(("America/", "Africa/", "Europe/")) or z == "UTC"),
    }


@router.put("/business")
async def put_business(body: BusinessIn, request: Request,
                       ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    before = _business(t)
    t.name = body.name
    # Keep any extra time zones (multi-site teams); the first is the dealership's own.
    t.timezones = [body.timezone, *[z for z in (t.timezones or [])[1:] if z != body.timezone]]
    t.business_hours = {d: span for d, span in body.hours.items() if span}
    await db.flush()
    after = _business(t)
    _audit(db, caller, request, "settings.business", f"tenant:{t.id}", before, after)
    return after


@router.put("/replies")
async def put_replies(body: RepliesIn, request: Request,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    p = await _policy(db)
    before = _replies(p, t)
    p.draft_mode = body.draft_mode
    p.price_disclosure = body.price_disclosure
    p.handoff_triggers = body.handoff_triggers
    p.never_say = body.never_say
    t.settings = {**(t.settings or {}), "ai_disclosure": body.ai_disclosure}
    await db.flush()
    after = _replies(p, t)
    _audit(db, caller, request, "settings.replies", f"policy:{p.id}", before, after)
    return after


@router.post("/channels", status_code=201)
async def add_channel(body: ChannelIn, request: Request,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    try:
        address = normalize_email(body.address) if body.channel == "email" else normalize_phone(body.address)
    except ValueError:
        raise HTTPException(422, "That doesn't look like a phone number.") from None
    if body.channel == "email" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", address):
        raise HTTPException(422, "That doesn't look like an email address.")
    # Messages to this address go through the live provider if it's switched on, otherwise the local mock.
    provider = real(body.channel).provider if real(body.channel) else "mock"
    row = ChannelAddress(channel=body.channel, address=address, provider=provider)
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        raise HTTPException(409, "That address is already connected to an Ondra account.") from None
    out = _channel_out(row)
    _audit(db, caller, request, "settings.channel_add", f"channel:{row.id}", None, out)
    return out


@router.patch("/channels/{channel_id}")
async def patch_channel(channel_id: uuid.UUID, body: ChannelPatch, request: Request,
                        ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    row = await db.get(ChannelAddress, channel_id)
    if row is None:
        raise HTTPException(404)
    before = _channel_out(row)
    row.active = body.active
    await db.flush()
    out = _channel_out(row)
    _audit(db, caller, request, "settings.channel_update", f"channel:{row.id}", before, out)
    return out


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: uuid.UUID, request: Request,
                         ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> None:
    caller, db = ctx
    row = await db.get(ChannelAddress, channel_id)
    if row is None:
        raise HTTPException(404)
    _audit(db, caller, request, "settings.channel_remove", f"channel:{row.id}", _channel_out(row), None)
    await db.delete(row)
