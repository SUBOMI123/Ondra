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
from ondra_api.schemas import ContactOut, IdentityOut, Page, TeamPage, UserOut, VehicleOut

router = APIRouter(tags=["data"])


async def _page(db: AsyncSession, stmt: Select, limit: int, offset: int):
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return rows, total


@router.get("/contacts", response_model=Page[ContactOut])
async def list_contacts(
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ)),
    q: str | None = None, limit: int = Query(50, le=200), offset: int = 0, vip: bool | None = None,
) -> Page[ContactOut]:
    caller, db = ctx
    stmt = select(Contact).where(Contact.merged_into_id.is_(None)).order_by(Contact.display_name)
    if vip is not None:
        stmt = stmt.where(Contact.is_vip.is_(vip))
    if not can_see_vips(caller.role):
        # VIPs are visible to the owner and managers, and to the person who handles that VIP.
        stmt = stmt.where(or_(Contact.is_vip.is_(False), Contact.vip_owner_user_id == caller.user_id))
    if q:
        stmt = stmt.where(Contact.display_name.ilike(f"%{q}%"))
    rows, total = await _page(db, stmt, limit, offset)
    ids = [c.id for c in rows]
    idents = (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id.in_(ids)))).scalars().all() if ids else []
    by_contact: dict = {}
    for i in idents:
        by_contact.setdefault(i.contact_id, []).append(IdentityOut.model_validate(i))
    items = [ContactOut.model_validate(c).model_copy(update={"identities": by_contact.get(c.id, [])}) for c in rows]
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
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action="contact.vip", resource=f"contact:{c.id}", before=before,
                    after={"vip": c.is_vip, "handler": str(c.vip_owner_user_id) if c.vip_owner_user_id else None},
                    ip=request.client.host if request.client else None))
    await db.flush()
    idents = (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == c.id))).scalars().all()
    return ContactOut.model_validate(c).model_copy(update={"identities": [IdentityOut.model_validate(i) for i in idents]})
