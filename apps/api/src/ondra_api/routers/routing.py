"""Settings > Who gets what (BUILD_PLAN.md §7): the dealer's routing rules as structured data, never code.

Anyone signed in can read them; owners and admins can change them. Every change goes to the audit log. `preview`
answers "what would happen to this message right now" without sending anything or taking anyone's turn.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from ondra_core import routing
from ondra_core.models import AuditLog, RoutingRule, Tenant, User
from ondra_core.permissions import Perm, has_perm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, get_db, require
from ondra_api.services.routing import classify_topic, facts_for, load_people, load_rules

router = APIRouter(prefix="/routing", tags=["routing"])

Topic = Literal["sales", "service", "shipping", "finance", "complaint", "other"]
Channel = Literal["sms", "whatsapp", "email", "phone"]
Team = Literal["sales", "service", "manager", "owner", "ops", "admin"]
MAX_RULES = 50


class RuleIn(BaseModel):
    # When: every part that is set must match. Empty lists and "any" mean "whatever it is".
    topics: list[Topic] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    hours: Literal["any", "open", "closed"] = "any"
    language: str | None = Field(None, max_length=8)  # "es": the customer writes in Spanish
    deal_type: Literal["sales", "service"] | None = None
    # Then: a team or one person, what Ondra may do, and whether to alert them.
    team: Team | None = None
    user_id: uuid.UUID | None = None
    ai: Literal["auto", "draft", "off"] | None = None  # None: whatever Ondra would normally do
    alert: bool = False
    active: bool = True


class RulePatch(BaseModel):
    active: bool


class OrderIn(BaseModel):
    ids: list[uuid.UUID]


class PreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    channel: Channel = "sms"


def _audit(db: AsyncSession, caller: Caller, request: Request, action: str, resource: str, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource=resource,
                    before=before, after=after, ip=request.client.host if request.client else None))


def _out(r: RoutingRule) -> dict:
    c, a = r.conditions or {}, r.action or {}
    return {"id": str(r.id), "position": r.priority, "active": r.active,
            "topics": c.get("topic") or [], "channels": c.get("channel") or [], "hours": c.get("hours") or "any",
            "language": (c.get("language") or [None])[0], "deal_type": (c.get("deal_type") or [None])[0],
            "team": a.get("assign_role"), "user_id": a.get("assign_user_id"), "ai": a.get("ai"), "alert": bool(a.get("alert"))}


async def _to_columns(db: AsyncSession, body: RuleIn) -> tuple[dict, dict]:
    conditions: dict = {}
    if body.topics:
        conditions["topic"] = list(dict.fromkeys(body.topics))
    if body.channels:
        conditions["channel"] = list(dict.fromkeys(body.channels))
    if body.hours != "any":
        conditions["hours"] = body.hours
    if body.language and body.language.strip():
        conditions["language"] = [body.language.strip().lower()[:2]]
    if body.deal_type:
        conditions["deal_type"] = [body.deal_type]
    action: dict = {}
    if body.team:
        action["assign_role"] = body.team
    if body.user_id:
        person = await db.get(User, body.user_id)  # row-level security: only someone at this dealership is found
        if person is None or not person.active:
            raise HTTPException(422, "Choose someone who works here now.")
        action["assign_user_id"] = str(body.user_id)
    if body.ai:
        action["ai"] = body.ai
    if body.alert:
        action["alert"] = True
    problem = routing.validate(conditions, action)
    if problem:
        raise HTTPException(422, problem)
    return conditions, action


async def _rules(db: AsyncSession) -> list[RoutingRule]:
    return list((await db.execute(select(RoutingRule).order_by(RoutingRule.priority, RoutingRule.created_at))).scalars())


@router.get("")
async def get_routing(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    people = (await db.execute(select(User).where(User.active.is_(True)).order_by(User.name))).scalars()
    owner = (await db.execute(select(User.name).where(User.role == "owner", User.active.is_(True))
                              .order_by(User.created_at).limit(1))).scalar_one_or_none()
    return {
        "rules": [_out(r) for r in await _rules(db)],
        "people": [{"id": str(u.id), "name": u.name, "role": u.role} for u in people],
        "owner": owner,
        "can_edit": has_perm(caller.role, Perm.SETTINGS_MANAGE),
    }


@router.post("/rules", status_code=201)
async def add_rule(body: RuleIn, request: Request,
                   ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    count, last = (await db.execute(select(func.count(), func.max(RoutingRule.priority)).select_from(RoutingRule))).one()
    if count >= MAX_RULES:
        raise HTTPException(409, f"That's the limit of {MAX_RULES} rules. Remove one you no longer need first.")
    conditions, action = await _to_columns(db, body)
    r = RoutingRule(priority=(last or 0) + 1, conditions=conditions, action=action, active=body.active)
    db.add(r)
    await db.flush()
    _audit(db, caller, request, "routing.rule.add", f"routing_rule:{r.id}", None, _out(r))
    return _out(r)


@router.put("/rules/{rule_id}")
async def replace_rule(rule_id: uuid.UUID, body: RuleIn, request: Request,
                       ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    r = await db.get(RoutingRule, rule_id)
    if r is None:
        raise HTTPException(404)
    before = _out(r)
    r.conditions, r.action = await _to_columns(db, body)
    r.active = body.active
    await db.flush()
    _audit(db, caller, request, "routing.rule.update", f"routing_rule:{r.id}", before, _out(r))
    return _out(r)


@router.patch("/rules/{rule_id}")
async def switch_rule(rule_id: uuid.UUID, body: RulePatch, request: Request,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    caller, db = ctx
    r = await db.get(RoutingRule, rule_id)
    if r is None:
        raise HTTPException(404)
    before = _out(r)
    r.active = body.active
    await db.flush()
    _audit(db, caller, request, "routing.rule.update", f"routing_rule:{r.id}", before, _out(r))
    return _out(r)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: uuid.UUID, request: Request,
                      ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> None:
    caller, db = ctx
    r = await db.get(RoutingRule, rule_id)
    if r is None:
        raise HTTPException(404)
    _audit(db, caller, request, "routing.rule.delete", f"routing_rule:{r.id}", _out(r), None)
    await db.delete(r)


@router.put("/order")
async def reorder(body: OrderIn, request: Request,
                  ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.SETTINGS_MANAGE))) -> dict:
    """The order rules are checked in: the first one that matches decides."""
    caller, db = ctx
    rules = {r.id: r for r in await _rules(db)}
    if set(body.ids) != set(rules) or len(body.ids) != len(rules):
        raise HTTPException(409, "The rules changed while you were moving them. Reload and try again.")
    before = [str(r.id) for r in sorted(rules.values(), key=lambda r: r.priority)]
    for i, rid in enumerate(body.ids, start=1):
        rules[rid].priority = i
    await db.flush()
    _audit(db, caller, request, "routing.order", "routing_rules", before, [str(i) for i in body.ids])
    return {"rules": [_out(r) for r in await _rules(db)]}


@router.post("/preview")
async def preview(body: PreviewIn, ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """What would happen to this message if a customer (not a VIP) sent it now. Sends nothing, assigns nothing."""
    _caller, db = ctx
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    topic = await classify_topic(body.text)
    now = datetime.now(UTC)
    rule = routing.first_match(await load_rules(db), await facts_for(db, tenant, None, topic=topic, channel=body.channel, now=now))
    people = await load_people(db, tenant)
    named = None
    if rule is not None and rule.action.get("assign_user_id"):
        named = uuid.UUID(str(rule.action["assign_user_id"]))
        named = named if any(p.id == named for p in people) else None
    role = (rule.action.get("assign_role") if rule else None) or routing.DEFAULT_ROLE.get(topic, "sales")
    chosen = routing.pick(people, role, now, named=named)
    person = await db.get(User, chosen.user_id) if chosen.user_id else None
    return {
        "topic": topic,
        "rule_id": str(rule.id) if rule and rule.id else None,
        "team": chosen.role,
        "person": person.name if person else None,
        "in_now": chosen.on_shift,
        "back_at": chosen.available_at.isoformat() if chosen.available_at else None,
        "ai": (rule.action.get("ai") if rule else None) or "auto",
        "alert": bool(rule.action.get("alert")) if rule else False,
    }
