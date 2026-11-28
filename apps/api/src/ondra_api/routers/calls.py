"""Calls for the dashboard (Step 5).

    GET  /calls?show=all|missed|ondra|people
                                     recent calls, newest first, with who handled them and whether a call-back is due.
                                     A caller who rang several times before anyone rang back is one row ("3 calls").
    GET  /calls/{id}                 one call: transcript, summary, recording (only with consent)
    POST /calls/{id}/called-back     {result: reached|left_message}. Reached: all their waiting calls are done and the
                                     call-back task is finished. Left a message: noted on the call, it stays on the list.
    POST /calls/{id}/reopen          undo "reached": the calls and the task go back to waiting
    POST /calls/{id}/bridge          call them back through the dealer's line: Ondra rings your phone, you press 1,
                                     it dials them showing the number they rang (services/bridge.py)

VIP calls show who called but never an AI summary (VIPs never get AI content), and are hidden from roles that can't
see VIPs, like everywhere else.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from ondra_core.models import Call, Contact, Event, Task, User
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.routers.conversations import LIVE_FOR, call_line
from ondra_api.services import bridge
from ondra_api.services.calls import (
    CALLBACK_BRIEFS,
    first_try,
    mark_called_back,
    reopen_called_back,
    waiting_calls,
)

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
    # how: left_message (marked by hand), short (a call through Ondra under a minute), no_answer (it rang out)
    return {"by": names.get(uuid.UUID(by)) if by else None, "at": s.get("at"), "how": s.get("how", "left_message"),
            "seconds": s.get("seconds")}


LIVE_BRIDGE = ("ringing_you", "asked", "dialing_them")


def _bridge_live(state: str | None, started: datetime | None) -> bool:
    """Still under way. Ringing or waiting for a key gives up after a few minutes even if a webhook never comes, so
    a lost callback can't block calling them again; a connected call can run as long as any call."""
    if state not in LIVE_BRIDGE or started is None:
        return False
    return datetime.now(UTC) - started < (LIVE_FOR if state == "dialing_them" else timedelta(minutes=3))


def _bridge_out(b: dict | None, names: dict) -> dict | None:
    """An outbound call-back through the dealer's line: who made it, where it's got to, and how it ended."""
    if not b:
        return None
    by = b.get("user_id")
    return {"by": names.get(uuid.UUID(by)) if by else None, "by_id": by, "state": b.get("state"), "result": b.get("result"),
            "for_call": b.get("for_call")}


SHOW = {"missed": ("missed",), "ondra": ("ai",), "people": ("staff", "owner")}


def _out(call: Call, c: Contact | None, names: dict, full: bool = False, text_back: dict | None = None) -> dict:
    vip = bool(c and c.is_vip)
    needs_callback = call.handled_by == "missed" and call.callback_done_at is None
    out = {
        "id": str(call.id), "direction": call.direction, "handled_by": call.handled_by, "outcome": call.outcome,
        "started_at": call.started_at.isoformat() if call.started_at else None, "duration_s": call.duration_s,
        # Ondra on a call right now. A call-back a person is making through the line isn't that (see "bridge").
        "live": call.direction != "outbound" and call.ended_at is None and call.started_at is not None
                and datetime.now(UTC) - call.started_at < LIVE_FOR,
        "line": call_line(call.handled_by, call.ended_at is None and call.started_at is not None
                          and datetime.now(UTC) - call.started_at < LIVE_FOR, vip, names.get(call.transferred_to_user_id), None),
        "recording_notice": bool((call.metrics or {}).get("recording_notice")),
        "needs_callback": needs_callback, "from_number": call.from_number,
        "contact": {"id": str(c.id), "name": c.display_name, "is_vip": vip} if c else None,
        "conversation_id": str(call.conversation_id) if call.conversation_id else None,
        "transferred_to": names.get(call.transferred_to_user_id),
        "summary": None if vip else call.summary,
        "text_back": text_back,
        "bridge": _bridge_out((call.metrics or {}).get("bridge"), names),
        "called_back": _stamp((call.metrics or {}).get("callback"), names) if call.callback_done_at else None,
        "attempts": [_stamp(a, names) for a in (call.metrics or {}).get("callback_attempts") or []],
    }
    if call.direction == "outbound" and out["bridge"]:
        b = out["bridge"]
        who = (b["by"] or "Someone").split(" ")[0]
        out["line"] = {"spoke": f"{who} called them back", "short": f"{who} called them back, a short call",
                       "voicemail": f"{who} called them back and got their voicemail",
                       "no_answer": f"{who} called them back, no answer"}.get(b["result"] or "", f"{who} is calling them back")
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
    # A call-back in progress shows on the caller's waiting row ("Ondra is ringing Daniel").
    calling = {i["contact"]["id"]: i["bridge"] for i in items if i["direction"] == "outbound" and i["bridge"] and i["contact"]
               and _bridge_live(i["bridge"]["state"], datetime.fromisoformat(i["started_at"]) if i["started_at"] else None)}
    for i in items:
        if i["needs_callback"] and i["contact"]:
            i["calling"] = calling.get(i["contact"]["id"])
    # A call-back is a row of its own once it has rung the customer; while it's under way the caller's row says so,
    # and one the salesperson never connected (didn't pick up, didn't press 1) never reached the customer at all.
    items = [i for i in items if i["direction"] != "outbound" or (i["bridge"] and i["bridge"]["result"])]
    inbound = [i for i in items if i["direction"] != "outbound"]
    counts = {k: sum(1 for i in inbound if i["handled_by"] in v and not i["live"]) for k, v in SHOW.items()}
    counts["all"] = len(items)
    if show != "all":
        items = [i for i in inbound if i["handled_by"] in SHOW[show] and not i["live"]]
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
        await first_try(db, await waiting_calls(db, call), caller.user_id, "left_message")
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
    await reopen_called_back(db, call)
    db.add(Event(type="call.callback_reopened", payload={"call_id": str(call.id), "by": str(caller.user_id)}))
    await db.flush()
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    return _out(call, c, names)


@router.post("/calls/{call_id}/bridge", status_code=201)
async def call_through_ondra(call_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    """A person returning a missed call, placed through the dealer's line. Never automatic: a person taps it each
    time, and it rings them first."""
    caller, db = ctx
    missed, c = await _visible(db, caller, call_id)
    if missed.handled_by != "missed" or missed.callback_done_at is not None:
        raise HTTPException(409, "This caller isn't waiting for a call back.")
    if not missed.from_number or not missed.to_number:
        raise HTTPException(409, "There's no number to call them back on.")
    me = await db.get(User, caller.user_id)
    if not me or not me.phone:
        raise HTTPException(409, "Ondra needs your mobile number to ring you first. An admin can add it on Team.")
    busy = (await db.execute(select(Call).where(Call.direction == "outbound", Call.contact_id == missed.contact_id,
                                                Call.ended_at.is_(None), Call.started_at > datetime.now(UTC) - LIVE_FOR))).scalars()
    if any(_bridge_live(((k.metrics or {}).get("bridge") or {}).get("state"), k.started_at) for k in busy):
        raise HTTPException(409, "Someone is already calling them back.")
    name = c.display_name if c and not c.display_name.startswith("+") else "the caller"
    out = Call(conversation_id=missed.conversation_id, contact_id=missed.contact_id, direction="outbound", handled_by="staff",
               started_at=datetime.now(UTC), from_number=missed.to_number, to_number=missed.from_number,
               transferred_to_user_id=me.id, provider_call_sid=f"pending-{uuid.uuid4().hex}",
               metrics={"bridge": {"for_call": str(missed.id), "user_id": str(me.id), "state": "ringing_you"}})
    db.add(out)
    await db.flush()
    base = bridge.webhook_base(caller.tenant_id, out.id)
    try:
        out.provider_call_sid = await bridge.dialer().place(to=me.phone, from_=missed.to_number,
                                                            twiml=bridge.ask_to_connect(base, name),
                                                            status_callback=f"{base}/status")
    except bridge.BridgeError as e:
        out.ended_at, out.outcome = datetime.now(UTC), "failed"
        out.metrics = {"bridge": {**out.metrics["bridge"], "state": "failed"}}
        await db.commit()
        raise HTTPException(502, str(e)) from None
    db.add(Event(type="call.bridge_started", payload={"call_id": str(out.id), "for_call": str(missed.id), "by": str(me.id)}))
    return {"id": str(out.id), "state": "ringing_you", "your_phone": me.phone}
