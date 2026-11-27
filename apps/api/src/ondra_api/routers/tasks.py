"""Tasks and the client timeline (Step 3).

    GET   /tasks?scope=mine|all&status=open|done      tasks, soonest due first, with whether each is overdue
    POST  /tasks                                      a manual task; due time from urgency unless given
    PATCH /tasks/{id}                                 complete, reopen, reassign, change urgency or due time
    GET   /contacts/{id}/timeline                     everything that happened with a client, newest first

Tasks about a VIP are visible only to people who can see that VIP, or to whoever the task is assigned to.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import Appointment, Call, Contact, Conversation, Deal, Event, Message, Task, User
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.services.calls import CALLBACK_BRIEFS, mark_called_back
from ondra_api.services.tasks import new_task

router = APIRouter(tags=["tasks"])


def _task_out(t: Task, contact: Contact | None, names: dict, now: datetime) -> dict:
    return {
        "id": str(t.id), "title": t.title, "brief": t.brief, "status": t.status, "urgency": t.urgency, "source": t.source,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "overdue": bool(t.status in ("open", "in_progress") and t.due_at and t.due_at < now),
        "escalated": t.escalated_at is not None,
        "assignee": {"id": str(t.assignee_user_id), "name": names.get(t.assignee_user_id)} if t.assignee_user_id else None,
        "contact": {"id": str(contact.id), "name": contact.display_name, "is_vip": contact.is_vip} if contact else None,
        "conversation_id": str(t.conversation_id) if t.conversation_id else None,
    }


@router.get("/tasks")
async def list_tasks(
    scope: Literal["mine", "all"] = "mine",
    status: Literal["open", "done"] = "open",
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.TASKS_READ)),
) -> dict:
    caller, db = ctx
    stmt = select(Task, Contact).outerjoin(Contact, Contact.id == Task.contact_id)
    stmt = stmt.where(Task.status.in_(("open", "in_progress")) if status == "open" else Task.status == "done")
    if scope == "mine":
        stmt = stmt.where(Task.assignee_user_id == caller.user_id)
    if not can_see_vips(caller.role):
        stmt = stmt.where(or_(Contact.id.is_(None), Contact.is_vip.is_(False), Contact.vip_owner_user_id == caller.user_id,
                              Task.assignee_user_id == caller.user_id))
    stmt = stmt.order_by(Task.due_at.asc().nulls_last() if status == "open" else Task.updated_at.desc()).limit(300)
    rows = (await db.execute(stmt)).all()
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    now = datetime.now(UTC)
    out: dict = {"items": [_task_out(t, c, names, now) for t, c in rows]}
    if scope == "all":
        # The team board's columns: everyone who takes work, even with nothing open, so there's somewhere to drop it.
        out["people"] = [{"id": str(u.id), "name": u.name, "role": u.role} for u in (await db.execute(
            select(User).where(User.active.is_(True), User.role.in_(("owner", "manager", "sales", "service", "ops")),
                               User.password_hash.isnot(None) | User.clerk_user_id.isnot(None)).order_by(User.name))).scalars()]
    return out


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    contact_id: uuid.UUID | None = None
    assignee_user_id: uuid.UUID | None = None
    urgency: Literal["low", "normal", "high"] = "normal"
    due_at: datetime | None = None
    brief: str | None = Field(None, max_length=2000)


class TaskPatch(BaseModel):
    status: Literal["open", "in_progress", "done", "cancelled"] | None = None
    assignee_user_id: uuid.UUID | None = None
    urgency: Literal["low", "normal", "high"] | None = None
    due_at: datetime | None = None


async def _visible_task(db: AsyncSession, caller: Caller, task_id: uuid.UUID) -> tuple[Task, Contact | None]:
    t = await db.get(Task, task_id)
    c = await db.get(Contact, t.contact_id) if t and t.contact_id else None
    hidden = c is not None and c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id \
        and t.assignee_user_id != caller.user_id
    if t is None or hidden:
        raise HTTPException(404, "No task with that id.")
    return t, c


async def _active_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    u = await db.get(User, user_id)
    if u is None or not u.active:
        raise HTTPException(422, "Choose an active teammate.")


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.TASKS_WRITE))) -> dict:
    caller, db = ctx
    if body.assignee_user_id:
        await _active_user(db, body.assignee_user_id)
    contact = await db.get(Contact, body.contact_id) if body.contact_id else None
    if body.contact_id and contact is None:
        raise HTTPException(422, "No client with that id.")
    t = await new_task(db, title=body.title.strip(), contact_id=body.contact_id, brief=body.brief,
                       assignee_user_id=body.assignee_user_id or caller.user_id, urgency=body.urgency,
                       source="manual", **({"due_at": body.due_at} if body.due_at else {}))
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    return _task_out(t, contact, names, datetime.now(UTC))


@router.patch("/tasks/{task_id}")
async def update_task(task_id: uuid.UUID, body: TaskPatch,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.TASKS_WRITE))) -> dict:
    caller, db = ctx
    t, contact = await _visible_task(db, caller, task_id)
    if body.status and body.status != t.status:
        db.add(Event(type=f"task.{'completed' if body.status == 'done' else body.status}",
                     payload={"task_id": str(t.id), "by": str(caller.user_id)}))
        t.status = body.status
        if t.status == "done" and t.source == "rule" and t.brief in CALLBACK_BRIEFS and t.contact_id:
            # Finishing "Call Jordan back" is calling Jordan back: his missed calls leave the call-back list too.
            waiting = (await db.execute(select(Call).where(Call.contact_id == t.contact_id, Call.handled_by == "missed",
                                                           Call.callback_done_at.is_(None)).limit(1))).scalar_one_or_none()
            if waiting is not None:
                await mark_called_back(db, waiting, caller.user_id, finished=(t,))
    if body.assignee_user_id and body.assignee_user_id != t.assignee_user_id:
        await _active_user(db, body.assignee_user_id)
        t.assignee_user_id = body.assignee_user_id
    if body.urgency:
        t.urgency = body.urgency
    if body.due_at:
        # A new due time is a new deadline: it can escalate again if missed.
        t.due_at, t.escalated_at = body.due_at, None
    await db.flush()
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    return _task_out(t, contact, names, datetime.now(UTC))


@router.get("/contacts/{contact_id}/timeline")
async def timeline(contact_id: uuid.UUID, limit: int = Query(100, le=300),
                   ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    caller, db = ctx
    c = await db.get(Contact, contact_id)
    if c is None or (c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id):
        raise HTTPException(404, "No client with that id.")
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    items: list[dict] = []
    msgs = (await db.execute(
        select(Message, Conversation.channel).join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.contact_id == c.id, Message.is_draft.is_(False))
        .order_by(Message.created_at.desc()).limit(limit)
    )).all()
    for m, channel in msgs:
        items.append({"kind": "message", "at": m.created_at.isoformat(), "channel": channel, "direction": m.direction,
                      "author": m.author_type, "author_name": names.get(m.author_user_id), "body": m.body,
                      "conversation_id": str(m.conversation_id), "status": m.status})
    for t in (await db.execute(select(Task).where(Task.contact_id == c.id).order_by(Task.created_at.desc()).limit(50))).scalars():
        items.append({"kind": "task", "at": t.created_at.isoformat(), "title": t.title, "status": t.status,
                      "source": t.source, "assignee_name": names.get(t.assignee_user_id)})
    for a in (await db.execute(select(Appointment).where(Appointment.contact_id == c.id)
                               .order_by(Appointment.starts_at.desc()).limit(50))).scalars():
        items.append({"kind": "appointment", "at": a.starts_at.isoformat(), "status": a.status,
                      "service_type": a.service_type, "source": a.source})
    for k in (await db.execute(select(Call).where(Call.contact_id == c.id).order_by(Call.started_at.desc()).limit(50))).scalars():
        items.append({"kind": "call", "at": (k.started_at or k.created_at).isoformat(), "handled_by": k.handled_by,
                      "outcome": k.outcome, "duration_s": k.duration_s, "conversation_id": str(k.conversation_id),
                      "summary": None if c.is_vip else k.summary})  # VIPs never get AI content
    items.sort(key=lambda i: i["at"], reverse=True)

    from ondra_api.services.inbound import contact_opted_out

    deal = (await db.execute(select(Deal).where(Deal.contact_id == c.id).order_by(Deal.created_at.desc()).limit(1))
            ).scalar_one_or_none()
    nxt = (await db.execute(select(Task).where(Task.contact_id == c.id, Task.status.in_(("open", "in_progress")))
                            .order_by(Task.due_at.asc().nulls_last()).limit(1))).scalar_one_or_none()
    brief = None if c.is_vip else (await db.execute(
        select(Task.brief).where(Task.contact_id == c.id, Task.source == "ai_handoff").order_by(Task.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    latest_conv = (await db.execute(select(Conversation.id).where(Conversation.contact_id == c.id)
                                    .order_by(Conversation.updated_at.desc()).limit(1))).scalar_one_or_none()
    now = datetime.now(UTC)
    return {
        "items": items[:limit],
        "opted_out": await contact_opted_out(db, c.id),
        "deal": None if deal is None else {"stage": deal.stage, "vehicle": (deal.vehicle_of_interest or {}).get("description"),
                                           "budget_max": float(deal.budget_max) if deal.budget_max is not None else None},
        "next_task": None if nxt is None else {"title": nxt.title, "due_at": nxt.due_at.isoformat() if nxt.due_at else None,
                                               "overdue": bool(nxt.due_at and nxt.due_at < now)},
        "brief": brief,  # never for a VIP (product rule)
        "latest_conversation_id": str(latest_conv) if latest_conv else None,
    }

