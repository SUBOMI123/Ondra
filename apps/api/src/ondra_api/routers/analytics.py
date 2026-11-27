"""The home dashboard's numbers (BUILD_PLAN.md §11.1, Step 9). Read-only; every number comes from `events`.

    GET /analytics                 a period's totals, the period before, a daily series, the pipeline now
    GET /analytics/trace           the events behind one number
    GET /today                     what needs the reader now, last night, and today's appointments
    PATCH /deals/{id}              move a deal to a stage (recorded as an event, which is what the pipeline reads)
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import Appointment, AppointmentType, Contact, Deal, Message, Task, Tenant, User
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.services import metrics

router = APIRouter(tags=["analytics"])
OPEN = ("open", "in_progress")


class StageIn(BaseModel):
    stage: Literal["new", "qualified", "appointment", "negotiating", "won", "lost"]


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


@router.patch("/deals/{deal_id}")
async def move_deal(deal_id: uuid.UUID, body: StageIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.DEALS_WRITE))) -> dict:
    caller, db = ctx
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404)
    changed = await metrics.set_stage(db, deal, body.stage, by=str(caller.user_id))
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
