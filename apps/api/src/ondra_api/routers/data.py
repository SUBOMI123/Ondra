"""Read endpoints for Step 1: the seeded contacts, vehicles and team, all tenant-scoped by RLS."""

import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ondra_core.models import Contact, ContactIdentity, User, Vehicle
from ondra_core.permissions import Perm, can_see_vips
from pydantic import BaseModel
from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.schemas import (
    ClientDealOut,
    ClientRowOut,
    ContactOut,
    IdentityOut,
    Page,
    TeamPage,
    UserOut,
    VehicleOut,
)

router = APIRouter(tags=["data"])


async def _page(db: AsyncSession, stmt: Select, limit: int, offset: int):
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return rows, total


@router.get("/contacts", response_model=Page[ClientRowOut])
async def list_contacts(
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ)),
    q: str | None = None, limit: int = Query(50, le=200), offset: int = 0, vip: bool | None = None,
    sort: Literal["recent", "name"] = "recent",
) -> Page[ClientRowOut]:
    """The Clients list. Search matches a name, an email or a phone number however it's typed ("214 555-0100" finds
    +12145550100). Most recently in touch first, unless sorted by name. Each row carries the client's latest deal,
    when you last heard from or wrote to them, and who looks after them."""
    from ondra_core.models import Conversation, Deal, Message, Task

    caller, db = ctx
    last = (select(Conversation.contact_id, func.max(Message.created_at).label("at"))
            .join(Message, Message.conversation_id == Conversation.id).where(Message.is_draft.is_(False))
            .group_by(Conversation.contact_id).subquery())
    stmt = select(Contact).outerjoin(last, last.c.contact_id == Contact.id).where(Contact.merged_into_id.is_(None))
    stmt = stmt.order_by(Contact.display_name) if sort == "name" else stmt.order_by(last.c.at.desc().nulls_last(), Contact.display_name)
    if vip is not None:
        stmt = stmt.where(Contact.is_vip.is_(vip))
    if not can_see_vips(caller.role):
        # VIPs are visible to the owner and managers, and to the person who handles that VIP.
        stmt = stmt.where(or_(Contact.is_vip.is_(False), Contact.vip_owner_user_id == caller.user_id))
    if q and q.strip():
        term = q.strip()
        digits = re.sub(r"\D", "", term)
        idents = select(ContactIdentity.contact_id).where(ContactIdentity.value.ilike(f"%{term}%"))
        if len(digits) >= 3:
            idents = idents.union(select(ContactIdentity.contact_id).where(
                ContactIdentity.kind == "phone", ContactIdentity.value.like(f"%{digits}%")))
        stmt = stmt.where(or_(Contact.display_name.ilike(f"%{term}%"), Contact.id.in_(idents)))
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(stmt.add_columns(last.c.at).limit(limit).offset(offset))).all()
    ids = [c.id for c, _ in rows]
    by_contact: dict = {}
    deals: dict = {}
    assigned: dict = {}
    if ids:
        for i in (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id.in_(ids)))).scalars():
            by_contact.setdefault(i.contact_id, []).append(IdentityOut.model_validate(i))
        for d in (await db.execute(select(Deal).where(Deal.contact_id.in_(ids)).order_by(Deal.updated_at.desc()))).scalars():
            deals.setdefault(d.contact_id, d)  # the latest one
        for cid, uid in (await db.execute(select(Conversation.contact_id, Conversation.assigned_user_id)
                                          .where(Conversation.contact_id.in_(ids), Conversation.assigned_user_id.is_not(None))
                                          .order_by(Conversation.updated_at.desc()))).all():
            assigned.setdefault(cid, uid)
        for cid, uid in (await db.execute(select(Task.contact_id, Task.assignee_user_id)
                                          .where(Task.contact_id.in_(ids), Task.assignee_user_id.is_not(None), Task.status.in_(("open", "in_progress")))
                                          .order_by(Task.created_at.desc()))).all():
            assigned.setdefault(cid, uid)  # nobody has the conversation: whoever has their open task
    people = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    items = []
    for c, at in rows:
        d = deals.get(c.id)
        who = (d.owner_user_id if d else None) or (c.vip_owner_user_id if c.is_vip else None) or assigned.get(c.id)
        items.append(ClientRowOut.model_validate(c).model_copy(update={
            "identities": by_contact.get(c.id, []),
            "last_contact_at": at,
            "deal": None if d is None else ClientDealOut(
                type=d.type, stage=d.stage, vehicle=(d.vehicle_of_interest or {}).get("description"),
                budget_max=float(d.budget_max) if d.budget_max is not None else None),
            "looks_after": people.get(who) if who else None,
        }))
    return Page(items=items, total=total)


@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(contact_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> ContactOut:
    caller, db = ctx
    c = (await db.execute(select(Contact).where(Contact.id == contact_id))).scalar_one_or_none()
    # A VIP the caller may not see looks exactly like a contact that doesn't exist.
    if c is None or (c.is_vip and not can_see_vips(caller.role) and c.vip_owner_user_id != caller.user_id):
        raise HTTPException(404, "No client with that id.")
    idents = (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == c.id))).scalars().all()
    return ContactOut.model_validate(c).model_copy(update={"identities": [IdentityOut.model_validate(i) for i in idents]})


@router.get("/vehicles", response_model=Page[VehicleOut])
async def list_vehicles(
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.VEHICLES_READ)),
    status: str | None = None, q: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
) -> Page[VehicleOut]:
    _, db = ctx
    stmt = select(Vehicle).order_by(Vehicle.year.desc(), Vehicle.make, Vehicle.model)
    if status:
        stmt = stmt.where(Vehicle.status == status)
    for word in (q or "").split():
        # Every word must match somewhere: "2022 silverado" finds the 2022 Silverados.
        like = f"%{word}%"
        stmt = stmt.where(or_(Vehicle.make.ilike(like), Vehicle.model.ilike(like), Vehicle.trim.ilike(like),
                              Vehicle.stock_number.ilike(like), Vehicle.vin.ilike(like), cast(Vehicle.year, String).ilike(like)))
    rows, total = await _page(db, stmt, limit, offset)
    return Page(items=[VehicleOut.model_validate(v) for v in rows], total=total)


@router.get("/users", response_model=TeamPage)
async def list_users(
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_READ)),
    q: str | None = Query(None, max_length=100), role: str | None = None,
    status: Literal["active", "invited", "deactivated"] | None = None,
    limit: int = Query(200, le=200), offset: int = 0,
) -> TeamPage:
    """The team, searchable and paged so a dealership of any size stays quick: search by name or email, filter by
    role and status. `counts` covers the whole team (for the filters), not just this page."""
    _, db = ctx
    invited = User.password_hash.is_(None) & User.clerk_user_id.is_(None)
    stmt = select(User).order_by(User.active.desc(), User.name)
    if q and q.strip():
        like = f"%{q.strip()}%"
        terms = [User.name.ilike(like), cast(User.email, String).ilike(like)]
        digits = re.sub(r"\D", "", q)
        if len(digits) >= 4:  # "(214) 555-0102" and "5550102" both find +12145550102
            terms.append(User.phone.ilike(f"%{digits}%"))
        stmt = stmt.where(or_(*terms))
    if role:
        stmt = stmt.where(User.role == role)
    if status == "active":
        stmt = stmt.where(User.active.is_(True), ~invited)
    elif status == "invited":
        stmt = stmt.where(User.active.is_(True), invited)
    elif status == "deactivated":
        stmt = stmt.where(User.active.is_(False))
    rows, total = await _page(db, stmt, limit, offset)
    by_role = dict((await db.execute(select(User.role, func.count()).where(User.active.is_(True)).group_by(User.role))).all())
    by_status = {
        "active": (await db.execute(select(func.count()).where(User.active.is_(True), ~invited))).scalar_one(),
        "invited": (await db.execute(select(func.count()).where(User.active.is_(True), invited))).scalar_one(),
        "deactivated": (await db.execute(select(func.count()).where(User.active.is_(False)))).scalar_one(),
    }
    return TeamPage(items=[UserOut(id=u.id, email=u.email, name=u.name, role=u.role, active=u.active,
                                   invited=u.password_hash is None and u.clerk_user_id is None, phone=u.phone,
                                   work_hours=u.work_hours, timezone=u.timezone, max_open_tasks=u.max_open_tasks)
                           for u in rows], total=total, counts={"role": by_role, "status": by_status})

class VipIn(BaseModel):
    vip: bool
    handler_user_id: uuid.UUID | None = None  # who looks after them; null: the owner


async def _tell_vip_handler(db: AsyncSession, c: Contact, caller: Caller) -> None:
    """Whoever is chosen to look after a VIP hears about it now, not when the VIP's call rings through to them:
    a task in their list, and a WhatsApp alert to their own mobile (never to the owners instead)."""
    from ondra_core.models import Event

    from ondra_api.services.tasks import new_task

    handler = await db.get(User, c.vip_owner_user_id)
    by = await db.get(User, caller.user_id)
    first = c.display_name.split()[0]
    brief = (f"{by.name if by else 'A manager'} made {first} a VIP and chose you to look after them. Their calls ring your "
             "mobile, their messages come to you, and Ondra never replies to them.")
    if handler is not None and not handler.phone:
        brief += " Add your mobile under Settings, People, or their calls ring the owner instead."
    task = await new_task(db, title=f"{c.display_name}: You now look after {first} (VIP)", contact_id=c.id,
                          assignee_user_id=c.vip_owner_user_id, source="rule", urgency="normal", brief=brief)
    db.add(Event(type="alert.created", payload={
        "task_id": str(task.id), "to": "owner", "urgency": "normal", "contact_id": str(c.id), "only_handler": True,
        "reason": f"You now look after {c.display_name}, a VIP. Their calls ring you directly and Ondra never replies to them"}))


@router.put("/contacts/{contact_id}/vip", response_model=ContactOut)
async def set_vip(contact_id: uuid.UUID, body: VipIn, request: Request,
                  ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_WRITE))) -> ContactOut:
    """Make a client a VIP (or not). Owners and managers only: they're the people who can see VIPs at all.
    From the moment a client is a VIP, Ondra stops: any reply it drafted for them is thrown away and any follow-up
    lined up is cancelled, so nothing automated reaches them (CLAUDE.md product rule)."""
    from ondra_core.models import AuditLog, Conversation, Event, Message

    from ondra_api.services.follow_ups import cancel_for

    caller, db = ctx
    if not can_see_vips(caller.role):
        raise HTTPException(403, "Only owners and managers can choose VIPs.")
    c = await db.get(Contact, contact_id)
    if c is None or c.merged_into_id is not None:
        raise HTTPException(404, "No client with that id.")
    if body.handler_user_id is not None:
        handler = await db.get(User, body.handler_user_id)
        if handler is None or not handler.active:
            raise HTTPException(422, "Choose someone who works here now.")
    before = {"vip": c.is_vip, "handler": str(c.vip_owner_user_id) if c.vip_owner_user_id else None}
    c.is_vip = body.vip
    c.vip_owner_user_id = body.handler_user_id if body.vip else None
    stopped = {"drafts": 0, "follow_ups": 0}
    if body.vip:
        convs = (await db.execute(select(Conversation.id).where(Conversation.contact_id == c.id))).scalars().all()
        drafts = (await db.execute(select(Message).where(Message.conversation_id.in_(convs), Message.is_draft.is_(True),
                                                         Message.status == "queued", Message.author_type == "ai"))).scalars().all() if convs else []
        for d in drafts:
            await db.delete(d)
        stopped = {"drafts": len(drafts), "follow_ups": await cancel_for(db, c.id, "vip")}
    db.add(Event(type="contact.vip_changed", payload={"contact_id": str(c.id), "vip": body.vip, "by": str(caller.user_id), **stopped}))
    if c.is_vip and c.vip_owner_user_id and c.vip_owner_user_id != caller.user_id and str(c.vip_owner_user_id) != before["handler"]:
        await _tell_vip_handler(db, c, caller)
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action="contact.vip", resource=f"contact:{c.id}", before=before,
                    after={"vip": c.is_vip, "handler": str(c.vip_owner_user_id) if c.vip_owner_user_id else None},
                    ip=request.client.host if request.client else None))
    await db.flush()
    idents = (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == c.id))).scalars().all()
    return ContactOut.model_validate(c).model_copy(update={"identities": [IdentityOut.model_validate(i) for i in idents]})
