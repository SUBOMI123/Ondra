"""The home dashboard's numbers (BUILD_PLAN.md §11.1, Step 9). Read-only; every number comes from `events`.

    GET /analytics                 a period's totals, the period before, a daily series, the pipeline now
    GET /analytics/trace           the events behind one number
    GET /today                     what needs the reader now, last night, and today's appointments
    GET /deals                     the sales board
    GET /deals/{id}                one deal in full: the car, money, trade-in, the conversation, what's next, history
    PATCH /deals/{id}              move a deal to a stage (recorded as an event, which is what the pipeline reads),
                                   or give it to someone
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import Appointment, AppointmentType, Contact, Deal, Message, Task, Tenant, User
from ondra_core.permissions import Perm, can_see_vips, has_perm
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.services import metrics

router = APIRouter(tags=["analytics"])
OPEN = ("open", "in_progress")


class StageIn(BaseModel):
    stage: Literal["new", "qualified", "appointment", "negotiating", "won", "lost"] | None = None
    lost_reason: str | None = None  # why, when the stage is "lost"
    owner_user_id: uuid.UUID | None = None  # give the deal to this person


async def _deal_context(db: AsyncSession, contact_ids: list) -> tuple[dict, dict, dict, dict]:
    """For a set of clients: when you were last in touch, their next appointment, their next open task, and who
    has their conversation or an open task (the fallback owner for a deal nobody was given)."""
    from ondra_core.models import Conversation

    if not contact_ids:
        return {}, {}, {}, {}
    now = datetime.now(UTC)
    last = dict((await db.execute(
        select(Conversation.contact_id, func.max(Message.created_at)).join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.contact_id.in_(contact_ids), Message.is_draft.is_(False)).group_by(Conversation.contact_id))).all())
    appts: dict = {}
    for a, t in (await db.execute(
            select(Appointment, AppointmentType).join(AppointmentType, AppointmentType.id == Appointment.appointment_type_id)
            .where(Appointment.contact_id.in_(contact_ids), Appointment.starts_at >= now, Appointment.status.in_(("booked", "confirmed")))
            .order_by(Appointment.starts_at))).all():
        appts.setdefault(a.contact_id, {"starts_at": a.starts_at.isoformat(), "what": a.service_type or t.name})
    tasks: dict = {}
    for t in (await db.execute(select(Task).where(Task.contact_id.in_(contact_ids), Task.status.in_(OPEN))
                               .order_by(Task.due_at.asc().nulls_last()))).scalars():
        tasks.setdefault(t.contact_id, {"title": t.title.split(": ", 1)[-1], "due_at": t.due_at.isoformat() if t.due_at else None,
                                        "overdue": bool(t.due_at and t.due_at < now), "assignee_user_id": t.assignee_user_id})
    held: dict = {}
    for cid, uid in (await db.execute(select(Conversation.contact_id, Conversation.assigned_user_id)
                                      .where(Conversation.contact_id.in_(contact_ids), Conversation.assigned_user_id.isnot(None))
                                      .order_by(Conversation.updated_at.desc()))).all():
        held.setdefault(cid, uid)
    for cid, t in tasks.items():
        if t["assignee_user_id"]:
            held.setdefault(cid, t["assignee_user_id"])
    return last, appts, tasks, held


@router.get("/analytics")
async def analytics(days: int = Query(7, ge=1, le=46), to: date | None = None,
                    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_READ))) -> dict:
    _caller, db = ctx
    return await metrics.report(db, days, to)


@router.get("/analytics/trace")
async def analytics_trace(metric: str, days: int = Query(7, ge=1, le=46), to: date | None = None,
                          ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_READ))) -> dict:
    """The events a number was counted from. VIP names are left out for people who can't see VIPs."""
    caller, db = ctx
    try:
        out = await metrics.trace(db, metric, days, to)
    except KeyError:
        raise HTTPException(404, "No such number.") from None
    if not can_see_vips(caller.role):
        vips = set((await db.execute(select(Contact.display_name).where(Contact.is_vip.is_(True)))).scalars())
        for e in out["events"]:
            if e["who"] in vips:
                e["who"] = "A VIP client"
    return out


STAGE_LABEL = {"new": "New", "qualified": "Qualified", "appointment": "Appointment", "negotiating": "Negotiating", "won": "Won", "lost": "Lost"}
CLOSED_FOR = timedelta(days=30)  # won and lost deals stay on the board this long


@router.get("/deals")
async def list_deals(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_READ))) -> dict:
    """The sales board: open deals by stage, plus deals won or lost in the last 30 days. A deal's value is an
    estimate: the listed price of the car in stock they asked about, else their own budget, else none. VIP deals
    appear only for people who may see VIPs."""
    from ondra_core.models import Event, Vehicle

    caller, db = ctx
    now = datetime.now(UTC)
    rows = (await db.execute(select(Deal, Contact).join(Contact, Contact.id == Deal.contact_id).where(Deal.type == "sales")
                             .order_by(Deal.updated_at.desc()).limit(500))).all()
    sees_vips = can_see_vips(caller.role)
    names = dict((await db.execute(select(User.id, User.name))).all())
    by_ai = set((await db.execute(select(Event.payload["deal_id"].astext).where(Event.type == "lead.captured", Event.payload["by"].astext == "ai"))).scalars())
    prices = {v.stock_number.lower(): float(v.price) for v in (await db.execute(select(Vehicle).where(Vehicle.price.isnot(None)))).scalars()}
    last, appts, tasks, held = await _deal_context(db, list({c.id for _d, c in rows}))
    columns: dict[str, list[dict]] = {s: [] for s in STAGE_LABEL}
    for d, c in rows:
        if c.is_vip and not (sees_vips or c.vip_owner_user_id == caller.user_id):
            continue
        if d.stage not in columns or (d.stage in ("won", "lost") and now - d.updated_at > CLOSED_FOR):
            continue
        wants = d.vehicle_of_interest or {}
        listed = prices.get(str(wants.get("stock") or "").lower())
        value = listed or (float(d.value_estimate) if d.value_estimate else None) or (float(d.budget_max) if d.budget_max else None)
        owner = d.owner_user_id or (c.vip_owner_user_id if c.is_vip else None) or held.get(c.id)
        task = tasks.get(c.id)
        notes = [x for x in (f"Budget up to ${float(d.budget_max):,.0f}" if d.budget_max else None, d.timeline,
                             f"Paying by {d.payment_method}" if d.payment_method and d.payment_method != "unknown" else None,
                             f"Trade-in: {wants['trade_in']}" if wants.get("trade_in") else None) if x]
        columns[d.stage].append({
            "id": str(d.id), "contact_id": str(c.id), "client": c.display_name, "vip": c.is_vip, "stage": d.stage,
            "wants": wants.get("description") or (f"Stock {wants['stock']}" if wants.get("stock") else None), "note": ". ".join(notes) or None,
            "owner": names.get(owner), "owner_id": str(owner) if owner else None, "value": value,
            "last_contact_at": last[c.id].isoformat() if c.id in last else None, "next_appointment": appts.get(c.id),
            "next_task": None if task is None else {k: task[k] for k in ("title", "due_at", "overdue")}, "value_from": "listed price" if listed else "their budget" if value else None,
            "by_ondra": str(d.id) in by_ai and not c.is_vip, "updated_at": d.updated_at.isoformat(), "lost_reason": d.lost_reason,
        })
    open_ = [d for s in ("new", "qualified", "appointment", "negotiating") for d in columns[s]]
    return {"stages": [{"stage": s, "label": STAGE_LABEL[s], "deals": columns[s]} for s in STAGE_LABEL],
            "open": len(open_), "open_value": sum(d["value"] or 0 for d in open_), "open_without_value": sum(1 for d in open_ if not d["value"]),
            "open_by_ondra": sum(1 for d in open_ if d["by_ondra"]), "can_move": has_perm(caller.role, Perm.DEALS_WRITE)}


@router.get("/deals/{deal_id}")
async def deal_detail(deal_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_READ))) -> dict:
    """One deal, everything a salesperson needs before they pick up the phone: what the buyer wants and can spend,
    their trade-in, the car in stock if they named one, the latest conversation, what's booked and due, and how the
    deal has moved. A VIP's deal doesn't exist for someone who can't see VIPs, and shows nothing Ondra wrote."""
    from ondra_core.models import ContactIdentity, Conversation, Event, Vehicle

    caller, db = ctx
    deal = await db.get(Deal, deal_id)
    contact = await db.get(Contact, deal.contact_id) if deal else None
    if deal is None or contact is None or (contact.is_vip and not (can_see_vips(caller.role) or contact.vip_owner_user_id == caller.user_id)):
        raise HTTPException(404, "No deal with that id.")
    names = dict((await db.execute(select(User.id, User.name))).all())
    last, appts, tasks, held = await _deal_context(db, [contact.id])
    wants = dict(deal.vehicle_of_interest or {})
    car = None
    if wants.get("stock"):
        v = (await db.execute(select(Vehicle).where(func.lower(Vehicle.stock_number) == str(wants["stock"]).lower()))).scalar_one_or_none()
        if v is not None:
            car = {"id": str(v.id), "name": " ".join(str(x) for x in (v.year, v.make, v.model, v.trim) if x), "stock_number": v.stock_number,
                   "price": float(v.price) if v.price is not None else None, "status": v.status}
    conv = (await db.execute(select(Conversation).where(Conversation.contact_id == contact.id)
                             .order_by(Conversation.updated_at.desc()).limit(1))).scalar_one_or_none()
    messages = []
    if conv is not None:
        rows = (await db.execute(select(Message).where(Message.conversation_id == conv.id, Message.is_draft.is_(False))
                                 .order_by(Message.created_at.desc()).limit(6))).scalars().all()
        for m in reversed(rows):
            if contact.is_vip and m.author_type == "ai":
                continue  # never happens by the product rule; never shown if it somehow did
            messages.append({"from": m.author_type, "who": names.get(m.author_user_id) if m.author_user_id else None,
                             "body": m.body, "at": m.created_at.isoformat(), "channel": conv.channel})
    history = [{"from": e.payload.get("from"), "to": e.payload.get("to"), "at": e.created_at.isoformat(),
                "by": "Ondra" if e.payload.get("by") == "ai" else names.get(_uuid_or_none(e.payload.get("by")))}
               for e in (await db.execute(select(Event).where(Event.type == "deal.stage_changed", Event.payload["deal_id"].astext == str(deal.id))
                                          .order_by(Event.created_at))).scalars()]
    by_ai = (await db.execute(select(Event.id).where(Event.type == "lead.captured", Event.payload["deal_id"].astext == str(deal.id),
                                                     Event.payload["by"].astext == "ai").limit(1))).first() is not None
    idents = {i.kind: i.value for i in (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == contact.id))).scalars()}
    owner = deal.owner_user_id or (contact.vip_owner_user_id if contact.is_vip else None) or held.get(contact.id)
    can_move = has_perm(caller.role, Perm.DEALS_WRITE)
    people = []
    if can_move:
        people = [{"id": str(u.id), "name": u.name} for u in (await db.execute(
            select(User).where(User.active.is_(True), User.role.in_(("sales", "manager", "owner")),
                               User.password_hash.isnot(None) | User.clerk_user_id.isnot(None)).order_by(User.name))).scalars()]
    task = tasks.get(contact.id)
    return {
        "id": str(deal.id), "stage": deal.stage, "stage_label": STAGE_LABEL.get(deal.stage, deal.stage), "lost_reason": deal.lost_reason,
        "client": {"id": str(contact.id), "name": contact.display_name, "vip": contact.is_vip, "phone": idents.get("phone"),
                   "email": idents.get("email"), "preferred_channel": contact.preferred_channel, "language": contact.language},
        "owner": {"id": str(owner), "name": names.get(owner)} if owner else None, "owner_given": deal.owner_user_id is not None,
        "wants": wants.get("description") or (f"Stock {wants['stock']}" if wants.get("stock") else None),
        "car": car, "trade_in": wants.get("trade_in"),
        "budget_min": float(deal.budget_min) if deal.budget_min is not None else None,
        "budget_max": float(deal.budget_max) if deal.budget_max is not None else None,
        "payment_method": deal.payment_method if deal.payment_method != "unknown" else None,
        "timeline": deal.timeline, "destination": deal.destination, "source_channel": deal.source_channel,
        "by_ondra": by_ai and not contact.is_vip, "created_at": deal.created_at.isoformat(),
        "last_contact_at": last[contact.id].isoformat() if contact.id in last else None,
        "next_appointment": appts.get(contact.id),
        "next_task": None if task is None else {k: task[k] for k in ("title", "due_at", "overdue")},
        "conversation_id": str(conv.id) if conv else None, "messages": messages, "history": history,
        "can_move": can_move, "people": people,
    }


def _uuid_or_none(v: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(v))
    except ValueError:
        return None


@router.patch("/deals/{deal_id}")
async def move_deal(deal_id: uuid.UUID, body: StageIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_WRITE))) -> dict:
    """Move a deal to a stage, give it to someone, or both."""
    from ondra_core.models import AuditLog

    caller, db = ctx
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404)
    contact = await db.get(Contact, deal.contact_id)
    if contact.is_vip and not (can_see_vips(caller.role) or contact.vip_owner_user_id == caller.user_id):
        raise HTTPException(404)  # a VIP's deal doesn't exist for someone who can't see VIPs
    if body.stage is None and body.owner_user_id is None:
        raise HTTPException(422, "Say which stage to move it to, or who to give it to.")
    changed = False
    if body.stage is not None:
        changed = await metrics.set_stage(db, deal, body.stage, by=str(caller.user_id))
        if changed:
            deal.lost_reason = (body.lost_reason or "").strip()[:200] or None if body.stage == "lost" else None
    if body.owner_user_id is not None and body.owner_user_id != deal.owner_user_id:
        person = await db.get(User, body.owner_user_id)
        if person is None or not person.active:
            raise HTTPException(422, "Choose someone who works here now.")
        db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action="deal.owner", resource=f"deal:{deal.id}",
                        before={"owner": str(deal.owner_user_id) if deal.owner_user_id else None}, after={"owner": str(person.id)}))
        deal.owner_user_id = person.id
        changed = True
    return {"id": str(deal.id), "stage": deal.stage, "owner_user_id": str(deal.owner_user_id) if deal.owner_user_id else None, "changed": changed}


@router.get("/today")
async def today(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.TASKS_READ))) -> dict:
    """What needs the reader now (their own work, or everyone's for an owner or manager), how last night went, and
    today's appointments. VIPs appear only for people who may see them."""
    caller, db = ctx
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    tz = ZoneInfo((tenant.timezones or ["America/Chicago"])[0])
    now = datetime.now(UTC)
    everything = caller.role in ("owner", "manager", "admin")
    sees_vips = can_see_vips(caller.role)
    q = select(Task, Contact).outerjoin(Contact, Contact.id == Task.contact_id).where(Task.status.in_(OPEN))
    if not everything:
        q = q.where(Task.assignee_user_id == caller.user_id)
    rows = (await db.execute(q.order_by(Task.due_at.nulls_last()).limit(300))).all()
    vips, overdue, hot = [], [], []
    for t, c in rows:
        if c is not None and c.is_vip:
            if sees_vips or c.vip_owner_user_id == caller.user_id:
                vips.append({"task_id": str(t.id), "client": c.display_name, "title": t.title, "since": t.created_at.isoformat(),
                             "conversation_id": str(t.conversation_id) if t.conversation_id else None})
            continue
        item = {"task_id": str(t.id), "client": c.display_name if c else None, "title": t.title, "due_at": t.due_at.isoformat() if t.due_at else None,
                "conversation_id": str(t.conversation_id) if t.conversation_id else None}
        if t.due_at is not None and t.due_at < now:
            overdue.append(item)
        elif t.urgency == "high":
            hot.append(item)
    drafts = (await db.execute(select(func.count()).select_from(Message).where(Message.is_draft.is_(True), Message.status == "queued"))).scalar_one()
    start = datetime.combine(now.astimezone(tz).date(), time(0), tz)
    names = dict((await db.execute(select(User.id, User.name))).all())
    appts = (await db.execute(
        select(Appointment, Contact, AppointmentType.name).join(Contact, Contact.id == Appointment.contact_id)
        .join(AppointmentType, AppointmentType.id == Appointment.appointment_type_id)
        .where(Appointment.starts_at >= start, Appointment.starts_at < start + timedelta(days=1), Appointment.status.in_(("booked", "confirmed", "showed")))
        .order_by(Appointment.starts_at))).all()
    return {
        "timezone": str(tz),
        "needs": {"vips": vips[:10], "drafts": drafts if caller.role != "viewer" else 0, "overdue": overdue[:10], "overdue_count": len(overdue),
                  "hot": hot[:10], "scope": "everyone" if everything else "mine"},
        "overnight": await metrics.overnight(db),
        "appointments": [{"id": str(a.id), "starts_at": a.starts_at.isoformat(), "kind": kind,
                          "client": "A VIP client" if c.is_vip and not (sees_vips or c.vip_owner_user_id == caller.user_id) else c.display_name,
                          "with": (names.get(a.assigned_user_id) or "").split(" ")[0] or None, "by_ondra": a.source == "ai", "vip": bool(c.is_vip)}
                         for a, c, kind in appts],
    }
