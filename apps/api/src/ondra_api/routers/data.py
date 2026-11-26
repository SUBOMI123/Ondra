"""Read endpoints for Step 1: the seeded contacts, vehicles and team, all tenant-scoped by RLS."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require
from ondra_api.schemas import ContactOut, IdentityOut, Page, UserOut, VehicleOut
from ondra_core.models import Contact, ContactIdentity, User, Vehicle
from ondra_core.permissions import Perm, can_see_vips

router = APIRouter(tags=["data"])


async def _page(db: AsyncSession, stmt: Select, limit: int, offset: int):
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return rows, total


@router.get("/contacts", response_model=Page[ContactOut])
async def list_contacts(
    ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ)),
    q: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
) -> Page[ContactOut]:
    caller, db = ctx
    stmt = select(Contact).where(Contact.merged_into_id.is_(None)).order_by(Contact.display_name)
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


@router.get("/users", response_model=Page[UserOut])
async def list_users(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.USERS_READ))) -> Page[UserOut]:
    _, db = ctx
    rows, total = await _page(db, select(User).order_by(User.name), 200, 0)
    return Page(items=[UserOut.model_validate(u) for u in rows], total=total)
