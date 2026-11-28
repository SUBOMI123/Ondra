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
from ondra_api.security import client_ip

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
                    before=before, after=after, ip=client_ip(request)))


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


# --- the owner's WhatsApp assistant (BUILD_PLAN.md §4.4) ------------------------------------------------------------

class OwnerAssistantIn(BaseModel):
    briefing_on: bool
    briefing_time: str  # "HH:MM", 24h, in the dealership's time zone
    alerts_on: bool = True

    @field_validator("briefing_time")
    @classmethod
    def _time(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError("Choose a time for the briefing.")
        return v


async def _owner_assistant(db: AsyncSession, t: Tenant, caller: Caller) -> dict:
    """The WhatsApp assistant as one admin sees it: their own switches, the dealership's briefing time, and which
    admins have it on (so nobody wonders whether anyone gets the briefing)."""
    from ondra_core.models import User

    from ondra_api.services.owner import TEMPLATES, prefs_of, settings_of

    me = await db.get(User, caller.user_id)
    admins = (await db.execute(select(User).where(User.role == "admin", User.active.is_(True)).order_by(User.created_at))).scalars().all()
    wa = (await db.execute(select(ChannelAddress).where(ChannelAddress.channel == "whatsapp", ChannelAddress.active.is_(True)).limit(1))).scalar_one_or_none()
    mine = prefs_of(me) if me else {"briefing_on": False, "alerts_on": False}
    return {"briefing_time": settings_of(t)["briefing_time"], **mine, "has_mobile": bool(me and me.phone),
            "owners": [{"name": u.name, "has_mobile": bool(u.phone), "you": u.id == caller.user_id, **prefs_of(u)} for u in admins],
            "whatsapp": None if wa is None else {"address": wa.address, "live": wa.provider != "mock"},
            "templates": [{"name": k, "text": v} for k, v in TEMPLATES.items()], "can_edit": caller.role == "admin"}


@router.get("/owner-assistant")
async def get_owner_assistant(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    return await _owner_assistant(db, t, caller)


def _owner_only(caller: Caller) -> None:
    if caller.role != "admin":
        raise HTTPException(403, "Only admins have the assistant.")


@router.put("/owner-assistant")
async def put_owner_assistant(body: OwnerAssistantIn, request: Request, ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """An admin switches their own briefing and alerts on or off (their own WhatsApp: that choice, who made it and when,
    is kept in the audit log, since WhatsApp wants each person's opt-in), and sets the dealership's briefing time."""
    from ondra_core.models import User

    from ondra_api.services import briefing
    from ondra_api.services.owner import prefs_of, settings_of

    caller, db = ctx
    _owner_only(caller)
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    me = await db.get(User, caller.user_id)
    before = {**prefs_of(me), "briefing_time": settings_of(t)["briefing_time"]}
    me.notification_prefs = {**(me.notification_prefs or {}), "assistant": {"briefing_on": body.briefing_on, "alerts_on": body.alerts_on}}
    shared = (t.settings or {}).get("owner_assistant") or {}
    t.settings = {**(t.settings or {}), "owner_assistant": {**shared, "briefing_time": body.briefing_time}}
    await db.flush()
    at = await briefing.schedule(db)
    _audit(db, caller, request, "settings.owner_assistant", f"user:{caller.user_id}", before, body.model_dump())
    return {**await _owner_assistant(db, t, caller), "next_briefing_at": at.isoformat() if at else None}


@router.post("/owner-assistant/briefing")
async def send_briefing_now(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """Send me today's briefing now, as a preview: to the admin who asked, whether or not their morning briefing is
    switched on. `live` says whether it went to a real phone or to the test-mode WhatsApp number."""
    from ondra_core.models import User

    from ondra_api.services import briefing

    caller, db = ctx
    _owner_only(caller)
    me = await db.get(User, caller.user_id)
    if not me or not me.phone:
        raise HTTPException(409, "Add your mobile under Settings, Team first: that's where the briefing goes.")
    wa = (await db.execute(select(ChannelAddress).where(ChannelAddress.channel == "whatsapp", ChannelAddress.active.is_(True)).limit(1))).scalar_one_or_none()
    if wa is None:
        raise HTTPException(409, "Your dealership has no WhatsApp number yet. Add one under Settings, Channels.")
    await db.commit()
    out = await briefing.send_now(caller.tenant_id, only=caller.user_id)
    if out["sent"] == 0:
        raise HTTPException(502, "The briefing couldn't be sent. Check the WhatsApp number under Settings, Channels.")
    return {**{k: out[k] for k in ("vips_waiting", "hot_leads", "drafts", "overdue_tasks", "appointments", "sent")}, "live": wa.provider != "mock"}


@router.get("/owner-assistant/thread")
async def owner_assistant_thread(limit: int = 50, ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """An admin's own conversation with their WhatsApp assistant, newest last. Only they read it: it's their phone,
    their voice notes, their questions."""
    from ondra_core.models import AssistantMessage

    caller, db = ctx
    _owner_only(caller)
    rows = (await db.execute(select(AssistantMessage).where(AssistantMessage.user_id == caller.user_id)
                             .order_by(AssistantMessage.created_at.desc()).limit(max(1, min(limit, 200))))).scalars().all()[::-1]
    return {"messages": [{"id": str(m.id), "from": "you" if m.direction == "in" else "ondra", "kind": m.kind, "text": m.body,
                          "at": m.created_at.isoformat(), "failed": m.status == "failed", "error": (m.meta or {}).get("error"),
                          "did": (m.meta or {}).get("did") or [], "template": (m.meta or {}).get("template")} for m in rows]}


# --- when a VIP's call isn't answered (docs/PLAN.md item 3; services/vip_desk.py) ---------------------------------

class VipCallsIn(BaseModel):
    message: str | None = Field(None, max_length=400)
    backup_number: str | None = None
    booking_link: str | None = Field(None, max_length=500)


def _vip_calls(t: Tenant, caller: Caller) -> dict:
    from ondra_api.config import get_settings
    from ondra_api.services.vip_desk import settings_of

    s = settings_of(t)
    return {**s, "default_message": "Sorry we missed you, {first}. {person} has been told and will call you back shortly.",
            "live": get_settings().feature_vip_desk, "can_edit": has_perm(caller.role, Perm.SETTINGS_MANAGE)}


@router.get("/vip-calls")
async def get_vip_calls(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    return _vip_calls(t, caller)


@router.put("/vip-calls")
async def put_vip_calls(body: VipCallsIn, request: Request,
                        ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    """The dealer's own words for a VIP whose call nobody answered, the one backup number press 1 rings, and the
    booking link press 2 texts. The backup must be a phone a person answers: never one of the dealership's own lines,
    which forward to Ondra (a VIP would reach the AI)."""
    from ondra_api.routers.team import clean_phone

    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    backup = clean_phone(body.backup_number)
    if backup:
        own = (await db.execute(select(ChannelAddress.address).where(ChannelAddress.channel.in_(("phone", "sms"))))).scalars().all()
        if backup in own:
            raise HTTPException(422, "That's the dealership's own line, which Ondra answers. Choose a phone a person picks up, like the front desk's direct line or a manager's mobile.")
    link = (body.booking_link or "").strip() or None
    if link and not link.startswith("https://"):
        raise HTTPException(422, "The booking link should start with https://")
    message = (body.message or "").strip() or None
    before = _vip_calls(t, caller)
    t.settings = {**(t.settings or {}), "vip_calls": {"message": message, "backup_number": backup, "booking_link": link}}
    await db.flush()
    after = _vip_calls(t, caller)
    _audit(db, caller, request, "settings.vip_calls", f"tenant:{t.id}", before, after)
    return after


# --- the dealership's logo, in the sidebar (founder, 2026-11-28) ---------------------------------------------------

LOGO_TYPES = ("image/png", "image/jpeg", "image/webp", "image/svg+xml")
LOGO_MAX_BYTES = 300_000


class BrandingIn(BaseModel):
    """A logo as a data URL (data:image/png;base64,...), or null to remove it. `logo_dark` is an optional version
    for dark mode: a logo drawn for white paper often disappears on a dark screen."""
    logo: str | None = None
    logo_dark: str | None = None


def _check_logo(data_url: str | None) -> str | None:
    import base64
    import binascii

    if not data_url:
        return None
    head, _, body = data_url.partition(",")
    mime = head.removeprefix("data:").removesuffix(";base64")
    if not head.startswith("data:") or not head.endswith(";base64") or mime not in LOGO_TYPES:
        raise HTTPException(422, "Upload a PNG, JPG, WebP or SVG image.")
    try:
        size = len(base64.b64decode(body, validate=True))
    except (binascii.Error, ValueError):
        raise HTTPException(422, "That file didn't upload properly. Try again.") from None
    if size > LOGO_MAX_BYTES:
        raise HTTPException(422, f"That logo is {size // 1000} KB. Use one under {LOGO_MAX_BYTES // 1000} KB (an SVG or a PNG about 400 px wide is plenty).")
    return data_url


def _branding(t: Tenant) -> dict:
    s = t.settings or {}
    return {"name": t.name, "logo": s.get("logo"), "logo_dark": s.get("logo_dark")}


@router.get("/branding")
async def get_branding(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """The dealership's name and logo, for everyone signed in (the sidebar shows it)."""
    _, db = ctx
    return _branding((await db.execute(select(Tenant).limit(1))).scalar_one())


@router.put("/branding")
async def put_branding(body: BrandingIn, request: Request,
                       ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    t = (await db.execute(select(Tenant).limit(1))).scalar_one()
    logo, dark = _check_logo(body.logo), _check_logo(body.logo_dark)
    before = {k: bool(v) for k, v in _branding(t).items() if k != "name"}
    t.settings = {**(t.settings or {}), "logo": logo, "logo_dark": dark if logo else None}
    await db.flush()
    _audit(db, caller, request, "settings.branding", f"tenant:{t.id}", before, {"logo": bool(logo), "logo_dark": bool(dark and logo)})
    return _branding(t)
