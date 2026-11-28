"""One search across the dealership (the search box: sidebar, header bar, ⌘K).

    GET /search?q=          up to 5 each of clients, cars, conversations and deals

Clients match a name, an email or a phone number however it's typed ("214 555" finds +12145550100); cars a stock
number, VIN, make, model or year; conversations what was said in them; deals the client or the car they want.
VIPs are hidden from people who can't see them, exactly as on every list, and their conversations' text is never
searched by those people either.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from ondra_core.models import Contact, ContactIdentity, Conversation, Deal, Message, Vehicle
from ondra_core.permissions import Perm, can_see_vips
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, require

router = APIRouter(tags=["search"])
EACH = 5


def _visible(caller: Caller):
    """The VIP rule as a filter on Contact: everyone sees non-VIPs; VIPs only for those who may see them."""
    if can_see_vips(caller.role):
        return True
    return or_(Contact.is_vip.is_(False), Contact.vip_owner_user_id == caller.user_id)


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=100),
                 ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONTACTS_READ))) -> dict:
    caller, db = ctx
    term = q.strip()
    like = f"%{term}%"
    digits = re.sub(r"\D", "", term)
    visible = _visible(caller)

    # Clients
    idents = select(ContactIdentity.contact_id).where(ContactIdentity.value.ilike(like))
    if len(digits) >= 3:
        idents = idents.union(select(ContactIdentity.contact_id).where(
            ContactIdentity.kind == "phone", ContactIdentity.value.like(f"%{digits}%")))
    clients = (await db.execute(select(Contact).where(
        Contact.merged_into_id.is_(None), visible, or_(Contact.display_name.ilike(like), Contact.id.in_(idents)))
        .order_by(Contact.display_name).limit(EACH))).scalars().all()
    phones = {}  # what to show under the name: their phone if they have one (what dealers recognise), else email
    if clients:
        for i in (await db.execute(select(ContactIdentity).where(
                ContactIdentity.contact_id.in_([c.id for c in clients])))).scalars():
            if i.kind == "phone" or i.contact_id not in phones:
                phones[i.contact_id] = i.value

    # Cars
    year = cast(Vehicle.year, String)
    cars = (await db.execute(select(Vehicle).where(or_(
        Vehicle.stock_number.ilike(like), Vehicle.vin.ilike(like), Vehicle.make.ilike(like), Vehicle.model.ilike(like),
        func.concat(year, " ", Vehicle.make, " ", Vehicle.model).ilike(like), func.concat(Vehicle.make, " ", Vehicle.model).ilike(like)))
        .order_by(Vehicle.status, Vehicle.year.desc()).limit(EACH))).scalars().all()

    # Conversations: what was said (latest matching message per conversation)
    said = (await db.execute(
        select(Message, Conversation, Contact).join(Conversation, Conversation.id == Message.conversation_id)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(visible, Message.is_draft.is_(False), Message.body.ilike(like))
        .order_by(Message.created_at.desc()).limit(EACH * 4))).all()
    conversations, seen = [], set()
    for m, conv, c in said:
        if conv.id in seen:
            continue
        seen.add(conv.id)
        conversations.append({"id": str(conv.id), "client": c.display_name, "is_vip": c.is_vip, "channel": conv.channel,
                              "snippet": _snippet(m.body or "", term), "at": m.created_at.isoformat()})
        if len(conversations) == EACH:
            break

    # Deals: the client, or the car they want
    deal_rows = (await db.execute(select(Deal, Contact).join(Contact, Contact.id == Deal.contact_id).where(
        visible, or_(Contact.display_name.ilike(like), Deal.vehicle_of_interest["description"].astext.ilike(like)))
        .order_by(Deal.updated_at.desc()).limit(EACH))).all()

    return {
        "clients": [{"id": str(c.id), "name": c.display_name, "is_vip": c.is_vip, "detail": phones.get(c.id)} for c in clients],
        "cars": [{"id": str(v.id), "title": f"{v.year} {v.make} {v.model}", "trim": v.trim, "stock_number": v.stock_number,
                  "status": v.status, "price": str(v.price) if v.price is not None else None} for v in cars],
        "conversations": conversations,
        "deals": [{"id": str(d.id), "client": c.display_name, "is_vip": c.is_vip, "stage": d.stage,
                   "wants": (d.vehicle_of_interest or {}).get("description")} for d, c in deal_rows],
    }


def _snippet(body: str, term: str, width: int = 90) -> str:
    """The words around the match, so you can see why it came up."""
    i = body.lower().find(term.lower())
    if i < 0 or len(body) <= width:
        return body[:width]
    start = max(0, i - width // 3)
    out = body[start:start + width]
    return ("…" if start else "") + out + ("…" if start + width < len(body) else "")
