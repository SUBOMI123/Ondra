"""The inbox API (BUILD_PLAN.md §11, Step 3).

    GET  /conversations?view=needs|ondra|team|all&q=   the list, sorted by latest activity, each with why it needs you
    GET  /conversations/{id}                           thread, client, deal, open tasks and Ondra's brief
    POST /conversations/{id}/reply                     a staff reply (same send path and gate as everything else)
    POST /conversations/{id}/takeover                  a person takes it: Ondra stops replying here
    POST /conversations/{id}/handback                  back to Ondra
    POST /conversations/{id}/assign                    give it to a teammate
    POST /messages/{id}/approve                        send an Ondra draft, as written or edited
    POST /messages/{id}/discard                        throw a draft away

VIP conversations are hidden from roles that can't see VIPs (the same rule as Clients), and look like they don't
exist. Edits to drafts are recorded (before and after) for the learning loop (§6.3a).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import (
    Call,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    Event,
    Message,
    Task,
    User,
)
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.db import tenant_session
from ondra_api.deps import Caller, require
from ondra_api.services.inbound import contact_opted_out
from ondra_api.services.outbound import Blocked, deliver

# A call with no end after this long is treated as over (the voice worker died before storing it).
LIVE_FOR = timedelta(hours=2)

router = APIRouter(tags=["inbox"])

View = Literal["needs", "ondra", "team", "all"]


# --- helpers -----------------------------------------------------------------------------------------------------

def _hidden_vip(caller: Caller, contact: Contact) -> bool:
    return contact.is_vip and not can_see_vips(caller.role) and contact.vip_owner_user_id != caller.user_id


async def _client_conversations(db: AsyncSession, conv: Conversation) -> list[Conversation]:
    """Every open conversation with this client, across channels (always including the one asked for)."""
    rows = (await db.execute(select(Conversation).where(Conversation.contact_id == conv.contact_id,
                                                        (Conversation.status != "closed") | (Conversation.id == conv.id))
                             .order_by(Conversation.created_at))).scalars().all()
    return list(rows)


async def _load(db: AsyncSession, caller: Caller, conversation_id: uuid.UUID) -> tuple[Conversation, Contact]:
    conv = await db.get(Conversation, conversation_id)
    contact = await db.get(Contact, conv.contact_id) if conv else None
    if conv is None or contact is None or _hidden_vip(caller, contact):
        raise HTTPException(404, "No conversation with that id.")
    return conv, contact


def call_line(handled_by: str | None, live: bool, is_vip: bool, transferred_to: str | None, summary: str | None) -> str:
    """A call, in words, for a list row or a thread."""
    if live:
        return "On a call now"
    if handled_by == "missed":
        return "Missed call"
    if handled_by == "owner":
        return "Rang you directly" if is_vip else "Call put through to the owner"
    if handled_by == "staff":
        return f"Call taken by {transferred_to}" if transferred_to else "Call taken by the team"
    return (summary if summary and not is_vip else "Call handled by Ondra")


def _last_activity(r, names: dict, now: datetime) -> dict:
    """The latest message or call, whichever is newer: a phone thread's activity is its calls."""
    msg = {"body": (r.last_body or "")[:200], "direction": r.last_direction, "author": r.last_author,
           "at": r.last_at.isoformat() if r.last_at else None, "is_draft": bool(r.last_is_draft), "kind": "message"}
    if r.call_at is None or (r.last_at is not None and r.last_at >= r.call_at):
        return msg
    live = r.call_ended_at is None and now - r.call_at < LIVE_FOR
    author = "ai" if (r.call_handled_by == "ai" or (live and not r.is_vip)) else "user"
    body = call_line(r.call_handled_by, live, r.is_vip, names.get(r.call_transferred_to), r.call_summary)
    return {"body": body[:200], "direction": "call", "author": author, "at": r.call_at.isoformat(), "is_draft": False,
            "kind": "call"}


def _bucket(row, last: dict) -> tuple[str, str | None]:
    """Which view a conversation belongs in, and why it needs a person (in words)."""
    if row.is_vip and last["direction"] == "inbound":
        return "needs", "VIP waiting for you"
    if row.drafts:
        return "needs", "Draft to approve"
    if row.task_title:
        return "needs", row.task_title.split(": ", 1)[-1]
    if row.status == "waiting_staff":
        return "needs", "Waiting for your team"
    if last["author"] == "ai":
        return "ondra", None
    return "team", None


# --- list --------------------------------------------------------------------------------------------------------

AFTER_HOURS_WINDOW = timedelta(days=7)


@router.get("/conversations")
async def list_conversations(
    view: View = "all",
    q: str | None = Query(None, max_length=100),
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_READ)),
) -> dict:
    caller, db = ctx
    vip_filter = "" if can_see_vips(caller.role) else "AND (NOT ct.is_vip OR ct.vip_owner_user_id = :me)"
    rows = (await db.execute(text(f"""
        SELECT c.id, c.channel, c.status, c.ai_mode, c.assigned_user_id, c.updated_at,
               ct.id AS contact_id, ct.display_name, ct.is_vip,
               lm.body AS last_body, lm.direction AS last_direction, lm.author_type AS last_author,
               lm.created_at AS last_at, lm.is_draft AS last_is_draft,
               (SELECT count(*) FROM messages d WHERE d.conversation_id = c.id AND d.is_draft AND d.status = 'queued')
                 AS drafts,
               t.title AS task_title, t.due_at AS task_due, t.urgency AS task_urgency,
               lc.started_at AS call_at, lc.handled_by AS call_handled_by, lc.ended_at AS call_ended_at,
               lc.summary AS call_summary, lc.transferred_to_user_id AS call_transferred_to
        FROM conversations c
        JOIN contacts ct ON ct.id = c.contact_id
        LEFT JOIN LATERAL (
          SELECT body, direction, author_type, created_at, is_draft FROM messages m
          WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1
        ) lm ON true
        LEFT JOIN LATERAL (
          SELECT started_at, handled_by, ended_at, summary, transferred_to_user_id FROM calls k
          WHERE k.conversation_id = c.id ORDER BY k.started_at DESC NULLS LAST LIMIT 1
        ) lc ON true
        LEFT JOIN LATERAL (
          SELECT title, due_at, urgency FROM tasks t
          WHERE t.conversation_id = c.id AND t.status IN ('open', 'in_progress')
          ORDER BY (t.urgency = 'high') DESC, t.due_at NULLS LAST LIMIT 1
        ) t ON true
        WHERE c.status != 'closed' {vip_filter}
          AND (CAST(:q AS text) IS NULL OR ct.display_name ILIKE '%' || CAST(:q AS text) || '%')
        ORDER BY coalesce(greatest(lm.created_at, lc.started_at), c.updated_at) DESC
        LIMIT 200
    """), {"me": caller.user_id, "q": q})).all()

    now = datetime.now(UTC)
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    # Clients who first came in as a lead while the dealership was closed, in the last week ("After-hours leads").
    after_hours = {r[0] for r in (await db.execute(text("""
        SELECT DISTINCT payload->>'contact_id' FROM events
        WHERE type = 'lead.captured' AND (payload->>'after_hours')::boolean AND occurred_at > :since
    """), {"since": now - AFTER_HOURS_WINDOW})).all()}
    # One row per client (Inbox threads span channels): group the client's conversations, show their most urgent
    # reason and their latest activity on any channel. Rows come newest first, so a client's first row is latest.
    by_contact: dict = {}
    for r in rows:
        last = _last_activity(r, names, now)
        bucket, reason = _bucket(r, last)
        by_contact.setdefault(r.contact_id, []).append((r, last, bucket, reason))
    items, counts = [], {"needs": 0, "ondra": 0, "team": 0}
    for convs in by_contact.values():
        r0, last, _, _ = convs[0]  # latest activity
        lead = min(convs, key=lambda c: _urgency(c[0], c[2], c[3], now))  # what needs a person most
        r, _, bucket, reason = lead
        if bucket != "needs":
            r, _, bucket, reason = convs[0]
        counts[bucket] += 1
        if view != "all" and bucket != view:
            continue
        items.append({
            "id": str(r.id), "channel": r0.channel, "status": r.status, "ai_mode": r.ai_mode,
            "conversation_ids": [str(c[0].id) for c in convs],
            "channels": list(dict.fromkeys(c[0].channel for c in convs)),
            "assigned_user_id": str(r.assigned_user_id) if r.assigned_user_id else None,
            "contact": {"id": str(r.contact_id), "name": r.display_name, "is_vip": r.is_vip},
            "last_message": last,
            "bucket": bucket, "reason": reason,
            "overdue": bool(bucket == "needs" and r.task_due and r.task_due < now),
            "drafts": sum(c[0].drafts for c in convs),
            "after_hours_lead": str(r.contact_id) in after_hours,
        })
    return {"items": items, "counts": counts}


def _urgency(r, bucket: str, reason: str | None, now: datetime) -> tuple:
    """Lower is more urgent: VIP waiting, then a draft to approve, then an overdue task, a task, waiting for the team."""
    if bucket != "needs":
        return (9,)
    if reason == "VIP waiting for you":
        return (0,)
    if reason == "Draft to approve":
        return (1,)
    if r.task_title:
        return (2 if r.task_due and r.task_due < now else 3, r.task_due or now)
    return (4,)


# --- detail ------------------------------------------------------------------------------------------------------

@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID,
                           ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_READ))) -> dict:
    caller, db = ctx
    conv, contact = await _load(db, caller, conversation_id)
    convs = await _client_conversations(db, conv)
    ids = [c.id for c in convs]
    channel_of = {c.id: c.channel for c in convs}
    messages = (await db.execute(select(Message).where(Message.conversation_id.in_(ids))
                                 .order_by(Message.created_at))).scalars().all()
    authors = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    identities = (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == contact.id))).scalars().all()
    deal = (await db.execute(select(Deal).where(Deal.contact_id == contact.id).order_by(Deal.created_at.desc()).limit(1))
            ).scalar_one_or_none()
    tasks = (await db.execute(select(Task).where(Task.conversation_id.in_(ids), Task.status.in_(("open", "in_progress")))
                              .order_by(Task.due_at))).scalars().all()
    brief = (await db.execute(select(Task.brief).where(Task.conversation_id.in_(ids), Task.source == "ai_handoff")
                              .order_by(Task.created_at.desc()).limit(1))).scalar_one_or_none()
    call_rows = (await db.execute(select(Call).where(Call.conversation_id.in_(ids)).order_by(Call.started_at))).scalars().all()
    # Reply where the client last wrote to us (never the phone line: it can't send texts).
    last_in = next((m for m in reversed(messages) if m.direction == "inbound" and channel_of[m.conversation_id] != "phone"), None)
    text_convs = [c for c in convs if c.channel != "phone"]
    reply_to = last_in.conversation_id if last_in else (conv.id if conv.channel != "phone" else
                                                       (text_convs[0].id if text_convs else None))
    now = datetime.now(UTC)
    from ondra_core.models import MessageRating

    ratings = dict((await db.execute(select(MessageRating.message_id, MessageRating.rating)
                                     .where(MessageRating.message_id.in_([m.id for m in messages])))).all())
    return {
        "id": str(conv.id), "channel": conv.channel, "status": conv.status,
        # Ondra is on only if it's on for every channel: a person who took over took over the client.
        "ai_mode": "off" if any(c.ai_mode == "off" for c in convs) else conv.ai_mode,
        "channels": [{"id": str(c.id), "channel": c.channel, "ai_mode": c.ai_mode} for c in convs],
        "reply_to": str(reply_to) if reply_to else None,
        "assigned_user_id": str(conv.assigned_user_id) if conv.assigned_user_id else None,
        "contact": {
            "id": str(contact.id), "name": contact.display_name, "is_vip": contact.is_vip, "language": contact.language,
            "opted_out": await contact_opted_out(db, contact.id),
            "identities": [{"kind": i.kind, "value": i.value} for i in identities],
        },
        "messages": [{
            "id": str(m.id), "direction": m.direction, "author": m.author_type, "channel": channel_of[m.conversation_id],
            "author_name": authors.get(m.author_user_id) if m.author_user_id else None,
            "body": m.body, "status": m.status, "is_draft": m.is_draft, "at": m.created_at.isoformat(),
            "rating": ratings.get(m.id),  # a person's verdict on one of Ondra's replies: good | wrong | tone
        } for m in messages],
        "deal": None if deal is None else {
            "type": deal.type, "stage": deal.stage, "vehicle_of_interest": deal.vehicle_of_interest,
            "budget_max": float(deal.budget_max) if deal.budget_max is not None else None,
            "payment_method": deal.payment_method, "timeline": deal.timeline,
        },
        "tasks": [{"id": str(t.id), "title": t.title, "urgency": t.urgency, "due_at": t.due_at.isoformat() if t.due_at else None,
                   "overdue": bool(t.due_at and t.due_at < now), "assignee": authors.get(t.assignee_user_id)} for t in tasks],
        "calls": [{
            "id": str(c.id), "at": (c.started_at or c.created_at).isoformat(), "handled_by": c.handled_by,
            "outcome": c.outcome, "duration_s": c.duration_s,
            "summary": None if contact.is_vip else c.summary,  # VIPs never get AI content
            "transferred_to": authors.get(c.transferred_to_user_id),
            "needs_callback": c.handled_by == "missed" and c.callback_done_at is None,
            "live": c.ended_at is None and c.started_at is not None and now - c.started_at < LIVE_FOR,
            "line": call_line(c.handled_by, c.ended_at is None and c.started_at is not None and now - c.started_at < LIVE_FOR,
                              contact.is_vip, authors.get(c.transferred_to_user_id), None),
        } for c in call_rows],
        # VIPs never get AI content (product rule), so no brief either.
        "brief": None if contact.is_vip else brief,
    }


# --- actions -----------------------------------------------------------------------------------------------------

class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ApproveIn(BaseModel):
    body: str | None = Field(None, min_length=1, max_length=4000)  # edited text; omitted = send as drafted


class AssignIn(BaseModel):
    user_id: uuid.UUID | None


async def _send_or_explain(tenant_id: uuid.UUID, message_id: uuid.UUID) -> dict:
    try:
        d = await deliver(tenant_id, message_id)
    except Blocked as b:
        why = "They've opted out, so nothing can be sent to them." if b.reason == "opted_out" else "This can't be sent."
        raise HTTPException(409, why) from None
    if not d.ok:
        raise HTTPException(502, f"Couldn't send: {d.error}. The message is saved; try again.")
    return {"id": str(message_id), "status": "sent"}


@router.post("/conversations/{conversation_id}/reply", status_code=201)
async def reply(conversation_id: uuid.UUID, body: ReplyIn,
                ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    conv, contact = await _load(db, caller, conversation_id)
    if await contact_opted_out(db, contact.id):
        raise HTTPException(409, "They've opted out, so nothing can be sent to them.")
    # Saved in its own transaction (committed before sending), so the send never holds a transaction open.
    async with tenant_session(caller.tenant_id) as w:
        # A person replying supersedes any draft Ondra had waiting.
        for d in (await w.execute(select(Message).where(Message.conversation_id == conv.id, Message.is_draft.is_(True),
                                                        Message.status == "queued"))).scalars():
            await w.delete(d)
        m = Message(conversation_id=conv.id, direction="outbound", author_type="user", author_user_id=caller.user_id,
                    body=body.body.strip(), status="queued")
        w.add(m)
        c = await w.get(Conversation, conv.id)
        if c.assigned_user_id is None:
            c.assigned_user_id = caller.user_id
        await w.flush()
        message_id = m.id
    return await _send_or_explain(caller.tenant_id, message_id)


@router.post("/messages/{message_id}/approve")
async def approve(message_id: uuid.UUID, body: ApproveIn,
                  ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    m = await db.get(Message, message_id)
    if m is None or not m.is_draft or m.status != "queued":
        raise HTTPException(404, "No draft waiting with that id.")
    await _load(db, caller, m.conversation_id)
    async with tenant_session(caller.tenant_id) as w:
        m = await w.get(Message, message_id)
        edited = body.body is not None and body.body.strip() != (m.body or "").strip()
        w.add(Event(type="draft.approved", payload={"message_id": str(m.id), "by": str(caller.user_id), "edited": edited}))
        if edited:
            # The learning loop: what Ondra wrote, and what a person sent instead.
            w.add(Event(type="draft.edited", payload={"message_id": str(m.id), "before": m.body, "after": body.body.strip()}))
            m.body = body.body.strip()
        m.is_draft = False
        m.author_user_id = caller.user_id  # who approved it; author_type stays "ai"
    return await _send_or_explain(caller.tenant_id, message_id)


@router.post("/messages/{message_id}/discard", status_code=204)
async def discard(message_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> None:
    caller, db = ctx
    m = await db.get(Message, message_id)
    if m is None or not m.is_draft or m.status != "queued":
        raise HTTPException(404, "No draft waiting with that id.")
    await _load(db, caller, m.conversation_id)
    db.add(Event(type="draft.discarded", payload={"message_id": str(m.id), "by": str(caller.user_id), "body": m.body}))
    from ondra_api.services.follow_ups import discarded

    await discarded(db, m.id)  # if it was a follow-up, the sequence ends here
    await db.delete(m)


@router.post("/conversations/{conversation_id}/takeover")
async def takeover(conversation_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    conv, _ = await _load(db, caller, conversation_id)
    for c in await _client_conversations(db, conv):  # the person takes over the client, on every channel
        c.ai_mode, c.assigned_user_id = "off", caller.user_id
    db.add(Event(type="conversation.takeover", payload={"conversation_id": str(conv.id), "by": str(caller.user_id)}))
    return {"id": str(conv.id), "ai_mode": conv.ai_mode, "assigned_user_id": str(caller.user_id)}


@router.post("/conversations/{conversation_id}/handback")
async def handback(conversation_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    conv, contact = await _load(db, caller, conversation_id)
    if contact.is_vip:
        raise HTTPException(409, "VIP conversations stay with a person.")
    for c in await _client_conversations(db, conv):
        c.ai_mode = "auto"
    conv.ai_mode = "auto"
    db.add(Event(type="conversation.handback", payload={"conversation_id": str(conv.id), "by": str(caller.user_id)}))
    return {"id": str(conv.id), "ai_mode": conv.ai_mode}


@router.post("/conversations/{conversation_id}/assign")
async def assign(conversation_id: uuid.UUID, body: AssignIn,
                 ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    conv, _ = await _load(db, caller, conversation_id)
    if body.user_id is not None:
        u = await db.get(User, body.user_id)
        if u is None or not u.active:
            raise HTTPException(422, "Choose an active teammate.")
    for c in await _client_conversations(db, conv):
        c.assigned_user_id = body.user_id
    db.add(Event(type="conversation.assigned", payload={"conversation_id": str(conv.id), "to": str(body.user_id),
                                                        "by": str(caller.user_id)}))
    return {"id": str(conv.id), "assigned_user_id": str(body.user_id) if body.user_id else None}

