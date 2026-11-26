"""The agent's tools, backed by Postgres. Every query runs in the caller's tenant session, so row-level security
limits each tool to the current dealer's data whatever the model asks for."""

from __future__ import annotations

import uuid
from typing import Any

from ondra_core.agent.tools import apply_price_policy, handoff_message
from ondra_core.models import (
    Appointment,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    KnowledgeGap,
    Task,
    User,
    Vehicle,
)
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

_DEAL_COLUMNS = {"budget_min", "budget_max", "payment_method", "timeline", "destination"}


def _vehicle_dict(v: Vehicle) -> dict:
    d = {
        "stock": v.stock_number, "vin": v.vin, "year": v.year, "make": v.make, "model": v.model, "trim": v.trim,
        "mileage": v.mileage, "status": v.status, "price": float(v.price) if v.price is not None else None,
    }
    for k in ("color", "seats", "body"):
        if k in (v.raw or {}):
            d[k] = v.raw[k]
    if v.photos:
        d["photos"] = v.photos[:1]
    return d


async def assignee_for(db: AsyncSession, role: str, preferred: uuid.UUID | None = None) -> uuid.UUID | None:
    """A person to give the task to. Round-robin and shifts arrive with the routing engine in Step 6; until then the
    first active user in the role, falling back to a manager, then the owner."""
    if preferred:
        return preferred
    order = [role, "manager", "owner"] if role not in ("manager", "owner") else [role, "owner"]
    for r in dict.fromkeys(order):
        uid = (await db.execute(
            select(User.id).where(User.role == r, User.active.is_(True)).order_by(User.created_at).limit(1)
        )).scalar_one_or_none()
        if uid:
            return uid
    return None


class DbToolBackend:
    def __init__(self, db: AsyncSession, *, contact: Contact, conversation: Conversation, price_disclosure: str,
                 open_now: bool) -> None:
        self.db = db
        self.contact = contact
        self.conversation = conversation
        self.price_disclosure = price_disclosure
        self.open_now = open_now
        self.last_question = ""

    async def get_contact_context(self) -> dict:
        c = self.contact
        deals = (await self.db.execute(
            select(Deal).where(Deal.contact_id == c.id, Deal.stage.notin_(("won", "lost"))).limit(5)
        )).scalars().all()
        appts = (await self.db.execute(
            select(Appointment).where(Appointment.contact_id == c.id, Appointment.starts_at >= func.now(),
                                      Appointment.status.in_(("booked", "confirmed"))).limit(5)
        )).scalars().all()
        return {
            "name": c.display_name,
            "language": c.language,
            "open_deals": [{"type": d.type, "stage": d.stage, "vehicle_of_interest": d.vehicle_of_interest} for d in deals],
            "vehicles_on_file": [d.vehicle_of_interest for d in deals if d.type == "service" and d.vehicle_of_interest],
            "upcoming_appointments": [
                {"starts_at": a.starts_at.isoformat(), "service_type": a.service_type, "status": a.status} for a in appts
            ],
        }

    async def search_inventory(self, query: str | None = None, make: str | None = None, model: str | None = None,
                               max_price: float | None = None, min_year: int | None = None,
                               min_seats: int | None = None) -> list[dict]:
        q = select(Vehicle).where(Vehicle.status == "available")
        if make:
            q = q.where(Vehicle.make.ilike(f"%{make}%"))
        if model:
            q = q.where(Vehicle.model.ilike(f"%{model}%"))
        if max_price:
            q = q.where(Vehicle.price <= max_price)
        if min_year:
            q = q.where(Vehicle.year >= min_year)
        if min_seats:
            # Seat counts come from the inventory feed (raw.seats); vehicles without one aren't excluded.
            q = q.where(text("coalesce((vehicles.raw->>'seats')::int, 99) >= :seats").bindparams(seats=min_seats))
        for word in (query or "").split():
            w = f"%{word}%"
            q = q.where(or_(Vehicle.make.ilike(w), Vehicle.model.ilike(w), Vehicle.trim.ilike(w),
                            Vehicle.raw["color"].astext.ilike(w), Vehicle.stock_number.ilike(w)))
        rows = (await self.db.execute(q.order_by(Vehicle.price).limit(5))).scalars().all()
        return [apply_price_policy(_vehicle_dict(v), self.price_disclosure) for v in rows]

    async def get_vehicle(self, stock_or_vin: str) -> dict | None:
        v = (await self.db.execute(
            select(Vehicle).where(or_(Vehicle.stock_number.ilike(stock_or_vin), Vehicle.vin.ilike(stock_or_vin)))
        )).scalar_one_or_none()
        return apply_price_policy(_vehicle_dict(v), self.price_disclosure) if v else None

    async def search_knowledge(self, query: str) -> list[dict]:
        self.last_question = query
        # Full-text search with OR semantics across the query's words. Embeddings come later (docs/DECISIONS.md).
        rows = (await self.db.execute(
            text("""
                SELECT title, body, ts_rank(doc, q) AS rank
                FROM knowledge_docs,
                     to_tsvector('english', title || ' ' || body) AS doc,
                     CAST(NULLIF(replace(plainto_tsquery('english', :q)::text, '&', '|'), '') AS tsquery) AS q
                WHERE doc @@ q
                ORDER BY rank DESC LIMIT 3
            """),
            {"q": query},
        )).all()
        return [{"title": r.title, "answer": r.body} for r in rows]

    async def update_lead_fields(self, fields: dict) -> dict:
        fields = {k: v for k, v in fields.items() if v not in (None, "")}
        # A name the customer gave replaces a placeholder (their number or address), never a name staff entered.
        name = self_name = self.contact.display_name
        if fields.get("name") and (self_name.startswith("+") or "@" in name):
            self.contact.display_name = str(fields["name"])[:200]
        if fields.get("language"):
            self.contact.language = str(fields["language"])[:20]
        if fields.get("phone") or fields.get("email"):
            for kind in ("phone", "email"):
                if fields.get(kind):
                    exists = (await self.db.execute(select(ContactIdentity.id).where(
                        ContactIdentity.kind == kind, ContactIdentity.value == str(fields[kind]).lower()))).first()
                    if not exists:
                        self.db.add(ContactIdentity(contact_id=self.contact.id, kind=kind, value=str(fields[kind]).lower()))
        deal = (await self.db.execute(
            select(Deal).where(Deal.contact_id == self.contact.id, Deal.type == "sales",
                               Deal.stage.notin_(("won", "lost"))).order_by(Deal.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if deal is None:
            deal = Deal(contact_id=self.contact.id, type="sales", stage="new", source_channel=self.conversation.channel)
            self.db.add(deal)
        voi = dict(deal.vehicle_of_interest or {})
        for k, v in fields.items():
            if k in _DEAL_COLUMNS:
                setattr(deal, k, v)
            elif k == "vehicle_interest":
                voi["description"] = v
            elif k not in ("name", "language", "phone", "email"):
                voi[k] = v
        deal.vehicle_of_interest = voi
        await self.db.flush()
        return {"saved": sorted(fields)}

    async def handoff(self, reason: str, brief: str, urgency: str, target_role: str) -> dict:
        c = self.contact
        preferred = c.vip_owner_user_id if target_role == "owner" else None
        task = Task(
            title=f"{c.display_name}: {reason.replace('_', ' ')}",
            contact_id=c.id,
            conversation_id=self.conversation.id,
            assignee_user_id=await assignee_for(self.db, target_role, preferred),
            source="ai_handoff",
            urgency=urgency if urgency in ("low", "normal", "high") else "normal",
            brief=brief,
        )
        self.db.add(task)
        self.conversation.status = "waiting_staff"
        if reason == "unknown_answer":
            await self._record_gap(self.last_question or brief)
        await self.db.flush()
        return {"task_id": str(task.id), "tell_customer": handoff_message(target_role, self.open_now)}

    async def _record_gap(self, question: str) -> None:
        q = " ".join(question.lower().split())[:500]
        gap = (await self.db.execute(
            select(KnowledgeGap).where(and_(KnowledgeGap.question == q, KnowledgeGap.status == "open"))
        )).scalar_one_or_none()
        if gap:
            gap.occurrences += 1
            gap.example_conversation_ids = list({*gap.example_conversation_ids, self.conversation.id})[:20]
        else:
            self.db.add(KnowledgeGap(question=q, example_conversation_ids=[self.conversation.id]))


__all__: list[Any] = ["DbToolBackend", "assignee_for"]
