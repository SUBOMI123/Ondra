"""Settings > Follow-ups: the sequences a dealer sets for customers who go quiet, and the quiet hours no follow-up
is sent in. Anyone signed in can read them; owners and admins can change them; every change is audited."""

from __future__ import annotations

import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from ondra_core import follow_ups as rules
from ondra_core.models import AuditLog, FollowUp, FollowUpSequence, Policy
from ondra_core.permissions import Perm, has_perm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, get_db, require

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MAX_SEQUENCES = 20
Topic = Literal["sales", "service", "shipping", "finance", "complaint", "other"]


class StepIn(BaseModel):
    after_hours: int = Field(ge=1, le=rules.MAX_AFTER_HOURS)
    write: Literal["ondra", "text"]
    text: str = Field("", max_length=600)  # the fixed message, or what to send if Ondra has nothing to say
    require_approval: bool = True


class SequenceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    topics: list[Topic] = Field(default_factory=list)  # empty: any conversation
    steps: list[StepIn]
    active: bool = True


class QuietIn(BaseModel):
    start: str
    end: str


def _audit(db: AsyncSession, caller: Caller, request: Request, action: str, resource: str, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource=resource,
                    before=before, after=after, ip=request.client.host if request.client else None))


def _out(s: FollowUpSequence) -> dict:
    return {"id": str(s.id), "name": s.name, "active": s.active, "topics": list(s.topics or []),
            "steps": [{"after_hours": st.get("after_hours"), "write": st.get("write"), "text": st.get("text") or "",
                       "require_approval": bool(st.get("require_approval", True))} for st in (s.steps or [])]}


def _apply(s: FollowUpSequence, body: SequenceIn) -> None:
    steps = [st.model_dump() for st in body.steps]
    problem = rules.validate_steps(steps)
    if problem:
        raise HTTPException(422, problem)
    if not body.name.strip():
        raise HTTPException(422, "Give the sequence a name.")
    s.name, s.topics, s.steps, s.active = body.name.strip(), list(dict.fromkeys(body.topics)), steps, body.active


@router.get("")
async def get_follow_ups(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    seqs = (await db.execute(select(FollowUpSequence).order_by(FollowUpSequence.created_at))).scalars()
    policy = (await db.execute(select(Policy).limit(1))).scalar_one_or_none()
    start, end = rules.quiet_span(policy.quiet_hours if policy else None)
    counts = dict((await db.execute(select(FollowUp.status, func.count()).where(
        FollowUp.status.in_(("scheduled", "awaiting_approval"))).group_by(FollowUp.status))).all())
    return {"sequences": [_out(s) for s in seqs], "quiet_hours": {"start": start, "end": end},
            "scheduled": counts.get("scheduled", 0), "awaiting_approval": counts.get("awaiting_approval", 0),
            "draft_mode": bool(policy.draft_mode) if policy else True,
            "can_edit": has_perm(caller.role, Perm.SETTINGS_MANAGE)}


@router.post("", status_code=201)
async def add_sequence(body: SequenceIn, request: Request,
                       ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    if (await db.execute(select(func.count()).select_from(FollowUpSequence))).scalar_one() >= MAX_SEQUENCES:
        raise HTTPException(409, f"That's the limit of {MAX_SEQUENCES} sequences. Remove one you no longer use first.")
    s = FollowUpSequence(name="", steps=[])
    _apply(s, body)
    db.add(s)
    await db.flush()
    _audit(db, caller, request, "follow_ups.add", f"follow_up_sequence:{s.id}", None, _out(s))
    return _out(s)


@router.put("/quiet-hours")
async def put_quiet_hours(body: QuietIn, request: Request,
                          ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    if not (_HHMM.match(body.start) and _HHMM.match(body.end)) or body.start == body.end:
        raise HTTPException(422, "Choose a start and an end time that differ.")
    policy = (await db.execute(select(Policy).limit(1))).scalar_one_or_none()
    if policy is None:
        policy = Policy()
        db.add(policy)
    before = dict(policy.quiet_hours or {})
    policy.quiet_hours = {"start": body.start, "end": body.end}
    await db.flush()
    _audit(db, caller, request, "follow_ups.quiet_hours", "policy", before, policy.quiet_hours)
    return policy.quiet_hours


@router.put("/{sequence_id}")
async def replace_sequence(sequence_id: uuid.UUID, body: SequenceIn, request: Request,
                           ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    s = await db.get(FollowUpSequence, sequence_id)
    if s is None:
        raise HTTPException(404)
    before = _out(s)
    _apply(s, body)
    await db.flush()
    _audit(db, caller, request, "follow_ups.update", f"follow_up_sequence:{s.id}", before, _out(s))
    return _out(s)


@router.delete("/{sequence_id}", status_code=204)
async def delete_sequence(sequence_id: uuid.UUID, request: Request,
                          ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> None:
    """Deleting a sequence also drops every follow-up it had lined up (the rows cascade)."""
    caller, db = ctx
    s = await db.get(FollowUpSequence, sequence_id)
    if s is None:
        raise HTTPException(404)
    _audit(db, caller, request, "follow_ups.delete", f"follow_up_sequence:{s.id}", _out(s), None)
    await db.delete(s)
