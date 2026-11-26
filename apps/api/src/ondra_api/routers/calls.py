"""Calls for the dashboard (Step 5).

    GET  /calls                      recent calls, newest first, with who handled them and whether a call-back is due
    GET  /calls/{id}                 one call: transcript, summary, recording (only with consent)
    POST /calls/{id}/called-back     mark the call-back done

VIP calls show who called but never an AI summary (VIPs never get AI content), and are hidden from roles that can't
see VIPs, like everywhere else.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from ondra_core.models import Call, Contact, Event, User
from ondra_core.permissions import Perm, can_see_vips
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.routers.conversations import LIVE_FOR, call_line

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
    }
    if full:
        out["transcript"] = call.transcript or []
        out["recording_url"] = call.recording_url if call.recording_consent else None
        out["latency"] = (call.metrics or {}).get("summary")
    return out


@router.get("/calls")
async def list_calls(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_READ))) -> dict:
    caller, db = ctx
    rows = (await db.execute(select(Call, Contact).outerjoin(Contact, Contact.id == Call.contact_id)
                             .order_by(Call.started_at.desc().nulls_last()).limit(100))).all()
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    tb = await _text_backs(db)
    return {"items": [_out(call, c, names, text_back=tb.get(str(call.id))) for call, c in rows if not _hidden(caller, c)]}


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


@router.post("/calls/{call_id}/called-back")
async def called_back(call_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    call, c = await _visible(db, caller, call_id)
    call.callback_done_at = datetime.now(UTC)
    db.add(Event(type="call.called_back", payload={"call_id": str(call.id), "by": str(caller.user_id)}))
    names = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    return _out(call, c, names)
