"""The home dashboard's numbers (BUILD_PLAN.md §11.1, Step 9). Read-only; every number comes from `events`.

    GET /analytics                 a period's totals, the period before, a daily series, the pipeline now
    GET /analytics/trace           the events behind one number
    GET /today                     what needs the reader now, last night, and today's appointments
    GET /deals                     the sales board
    PATCH /deals/{id}              move a deal to a stage (recorded as an event, which is what the pipeline reads)
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
    stage: Literal["new", "qualified", "appointment", "negotiating", "won", "lost"]
    lost_reason: str | None = None  # why, when the stage is "lost"


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
    from ondra_core.models import Conversation, Event, Vehicle

    caller, db = ctx
    now = datetime.now(UTC)
    rows = (await db.execute(select(Deal, Contact).join(Contact, Contact.id == Deal.contact_id).where(Deal.type == "sales")
                             .order_by(Deal.updated_at.desc()).limit(500))).all()
    sees_vips = can_see_vips(caller.role)
    names = dict((await db.execute(select(User.id, User.name))).all())
    by_ai = set((await db.execute(select(Event.payload["deal_id"].astext).where(Event.type == "lead.captured", Event.payload["by"].astext == "ai"))).scalars())
    prices = {v.stock_number.lower(): float(v.price) for v in (await db.execute(select(Vehicle).where(Vehicle.price.isnot(None)))).scalars()}
    assigned = dict((await db.execute(select(Conversation.contact_id, Conversation.assigned_user_id).where(Conversation.assigned_user_id.isnot(None))
                                      .order_by(Conversation.updated_at))).all())
    columns: dict[str, list[dict]] = {s: [] for s in STAGE_LABEL}
    for d, c in rows:
        if c.is_vip and not (sees_vips or c.vip_owner_user_id == caller.user_id):
            continue
        if d.stage not in columns or (d.stage in ("won", "lost") and now - d.updated_at > CLOSED_FOR):
            continue
        wants = d.vehicle_of_interest or {}
        listed = prices.get(str(wants.get("stock") or "").lower())
        value = listed or (float(d.value_estimate) if d.value_estimate else None) or (float(d.budget_max) if d.budget_max else None)
        owner = d.owner_user_id or (c.vip_owner_user_id if c.is_vip else None) or assigned.get(c.id)
        notes = [x for x in (f"Budget up to ${float(d.budget_max):,.0f}" if d.budget_max else None, d.timeline,
                             f"Paying by {d.payment_method}" if d.payment_method and d.payment_method != "unknown" else None,
                             f"Trade-in: {wants['trade_in']}" if wants.get("trade_in") else None) if x]
        columns[d.stage].append({
            "id": str(d.id), "contact_id": str(c.id), "client": c.display_name, "vip": c.is_vip, "stage": d.stage,
            "wants": wants.get("description") or (f"Stock {wants['stock']}" if wants.get("stock") else None), "note": ". ".join(notes) or None,
            "owner": names.get(owner), "value": value, "value_from": "listed price" if listed else "their budget" if value else None,
            "by_ondra": str(d.id) in by_ai and not c.is_vip, "updated_at": d.updated_at.isoformat(), "lost_reason": d.lost_reason,
        })
    open_ = [d for s in ("new", "qualified", "appointment", "negotiating") for d in columns[s]]
    return {"stages": [{"stage": s, "label": STAGE_LABEL[s], "deals": columns[s]} for s in STAGE_LABEL],
            "open": len(open_), "open_value": sum(d["value"] or 0 for d in open_), "open_without_value": sum(1 for d in open_ if not d["value"]),
            "open_by_ondra": sum(1 for d in open_ if d["by_ondra"]), "can_move": has_perm(caller.role, Perm.DEALS_WRITE)}


@router.patch("/deals/{deal_id}")
async def move_deal(deal_id: uuid.UUID, body: StageIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_WRITE))) -> dict:
    caller, db = ctx
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404)
    contact = await db.get(Contact, deal.contact_id)
    if contact.is_vip and not (can_see_vips(caller.role) or contact.vip_owner_user_id == caller.user_id):
        raise HTTPException(404)  # a VIP's deal doesn't exist for someone who can't see VIPs
    changed = await metrics.set_stage(db, deal, body.stage, by=str(caller.user_id))
    if changed:
        deal.lost_reason = (body.lost_reason or "").strip()[:200] or None if body.stage == "lost" else None
    return {"id": str(deal.id), "stage": deal.stage, "changed": changed}


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
