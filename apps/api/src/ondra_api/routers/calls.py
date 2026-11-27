"""Calls for the dashboard (Step 5).

    GET  /calls?show=all|missed|ondra|people
                                     recent calls, newest first, with who handled them and whether a call-back is due.
                                     A caller who rang several times before anyone rang back is one row ("3 calls").
    GET  /calls/{id}                 one call: transcript, summary, recording (only with consent)
    POST /calls/{id}/called-back     {result: reached|left_message}. Reached: all their waiting calls are done and the
                                     call-back task is finished. Left a message: noted on the call, it stays on the list.
    POST /calls/{id}/reopen          undo "reached": the calls and the task go back to waiting

VIP calls show who called but never an AI summary (VIPs never get AI content), and are hidden from roles that can't
see VIPs, like everywhere else.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import Call, Contact, Event, Task, User
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.routers.conversations import LIVE_FOR, call_line
from ondra_api.services.calls import CALLBACK_BRIEFS, mark_called_back

router = APIRouter(tags=["calls"])


def _hidden(caller: Caller, c: Contact | None) -> bool:
    return c is not None and c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id


async def _text_backs(db: AsyncSession) -> dict[str, dict]:
    """For missed calls: whether Ondra texted the caller back, or why not (the consent rule)."""
    rows = (await db.execute(select(Event).where(Event.type.in_(("call.text_back", "call.text_back_skipped")))
                             .order_by(Event.created_at.desc()).limit(500))).scalars()
    out: dict[str, dict] = {}
    for e in rows:
        cid = (e.payload or {}).get("call_id")
        if cid and cid not in out:
            out[cid] = {"sent": True} if e.type == "call.text_back" else {"sent": False, "reason": e.payload.get("reason")}
    return out


def _stamp(s: dict | None, names: dict) -> dict | None:
    """Who did it and when, for "Called back by Daniel at 3:10 pm"."""
    if not s:
        return None
    by = s.get("by")
    return {"by": names.get(uuid.UUID(by)) if by else None, "at": s.get("at")}


SHOW = {"missed": ("missed",), "ondra": ("ai",), "people": ("staff", "owner")}


def _out(call: Call, c: Contact | None, names: dict, full: bool = False, text_back: dict | None = None) -> dict:
    vip = bool(c and c.is_vip)
    needs_callback = call.handled_by == "missed" and call.callback_done_at is None
    out = {
        "id": str(call.id), "direction": call.direction, "handled_by": call.handled_by, "outcome": call.outcome,
        "started_at": call.started_at.isoformat() if call.started_at else None, "duration_s": call.duration_s,
        "live": call.ended_at is None and call.started_at is not None and datetime.now(UTC) - call.started_at < LIVE_FOR,
        "line": call_line(call.handled_by, call.ended_at is None and call.started_at is not None
                          and datetime.now(UTC) - call.started_at < LIVE_FOR, vip, names.get(call.transferred_to_user_id), None),
        "recording_notice": bool((call.metrics or {}).get("recording_notice")),
        "needs_callback": needs_callback, "from_number": call.from_number,
        "contact": {"id": str(c.id), "name": c.display_name, "is_vip": vip} if c else None,
        "conversation_id": str(call.conversation_id) if call.conversation_id else None,
        "transferred_to": names.get(call.transferred_to_user_id),
        "summary": None if vip else call.summary,
        "text_back": text_back,
        "called_back": _stamp((call.metrics or {}).get("callback"), names) if call.callback_done_at else None,
        "attempts": [_stamp(a, names) for a in (call.metrics or {}).get("callback_attempts") or []],
    }
    if full:
        out["transcript"] = call.transcript or []
        out["recording_url"] = call.recording_url if call.recording_consent else None
        out["latency"] = (call.metrics or {}).get("summary")
        # What went wrong on the call (a tool that crashed or refused), for staff and for debugging.
        out["problems"] = ((call.metrics or {}).get("summary") or {}).get("tool_problems") or []
    return out


@router.get("/calls")
async def list_calls(show: Literal["all", "missed", "ondra", "people"] = Query("all"),
                     ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_READ))) -> dict:
    caller, db = ctx
    rows = [(call, c) for call, c in (await db.execute(
        select(Call, Contact).outerjoin(Contact, Contact.id == Call.contact_id)
        .order_by(Call.started_at.desc().nulls_last()).limit(300))).all() if not _hidden(caller, c)]
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    tb = await _text_backs(db)
    # Who is due to ring each waiting caller back: the call-back task's assignee.
    owners = {t.contact_id: names.get(t.assignee_user_id) for t in (await db.execute(
        select(Task).where(Task.source == "rule", Task.brief.in_(CALLBACK_BRIEFS), Task.status.in_(("open", "in_progress")),
                           Task.contact_id.in_([c.id for _, c in rows if c])))).scalars()}
    # A caller who rang several times before anyone rang back is one row: the latest ring, with the count.
    items, waiting = [], {}
    for call, c in rows:
        out = _out(call, c, names, text_back=tb.get(str(call.id)))
        if out["needs_callback"]:
            key = str(call.contact_id or call.from_number)
            if key in waiting:
                waiting[key]["rings"] += 1
                waiting[key]["first_rang_at"] = out["started_at"]
                continue
            out["rings"], out["first_rang_at"] = 1, out["started_at"]
            out["callback_by"] = owners.get(call.contact_id)
            waiting[key] = out
        items.append(out)
    counts = {k: sum(1 for i in items if i["handled_by"] in v and not i["live"]) for k, v in SHOW.items()}
    counts["all"] = len(items)
    if show != "all":
        items = [i for i in items if i["handled_by"] in SHOW[show] and not i["live"]]
    return {"items": items[:100], "counts": counts}


async def _visible(db: AsyncSession, caller: Caller, call_id: uuid.UUID) -> tuple[Call, Contact | None]:
    call = await db.get(Call, call_id)
    c = await db.get(Contact, call.contact_id) if call and call.contact_id else None
    if call is None or _hidden(caller, c):
        raise HTTPException(404, "No call with that id.")
    return call, c


@router.get("/calls/{call_id}")
async def get_call(call_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_READ))) -> dict:
    caller, db = ctx
    call, c = await _visible(db, caller, call_id)
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    out = _out(call, c, names, full=True, text_back=(await _text_backs(db)).get(str(call.id)))
    if c and c.is_vip:
        out["transcript"] = []  # VIP calls are taken by people; no AI transcript is shown
    return out


class CalledBackIn(BaseModel):
    result: Literal["reached", "left_message"] = "reached"


@router.post("/calls/{call_id}/called-back")
async def called_back(call_id: uuid.UUID, body: CalledBackIn | None = None,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    call, c = await _visible(db, caller, call_id)
    if call.handled_by != "missed":
        raise HTTPException(409, "Only a missed call needs a call-back.")
    if (body or CalledBackIn()).result == "left_message":
        # They didn't pick up: note the try, keep them on the list.
        attempt = {"by": str(caller.user_id), "at": datetime.now(UTC).isoformat()}
        call.metrics = {**(call.metrics or {}), "callback_attempts": [*(call.metrics or {}).get("callback_attempts", []), attempt]}
        db.add(Event(type="call.callback_attempt", payload={"call_id": str(call.id), "by": str(caller.user_id)}))
    elif call.callback_done_at is None:
        await mark_called_back(db, call, caller.user_id)
    await db.flush()
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    return _out(call, c, names)


@router.post("/calls/{call_id}/reopen")
async def reopen(call_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    call, c = await _visible(db, caller, call_id)
    stamp = (call.metrics or {}).get("callback")
    if call.callback_done_at is None or not stamp:
        raise HTTPException(409, "This call isn't marked as called back.")
    for cid in stamp.get("calls") or [str(call.id)]:
        k = await db.get(Call, uuid.UUID(cid))
        if k is not None:
            k.callback_done_at = None
            k.metrics = {key: v for key, v in (k.metrics or {}).items() if key != "callback"}
    for tid in stamp.get("tasks") or []:
        t = await db.get(Task, uuid.UUID(tid))
        if t is not None and t.status == "done":
            t.status = "open"
    db.add(Event(type="call.callback_reopened", payload={"call_id": str(call.id), "by": str(caller.user_id)}))
    await db.flush()
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    return _out(call, c, names)
