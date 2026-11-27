"""The agent's tools, backed by Postgres. Every query runs in the caller's tenant session, so row-level security
limits each tool to the current dealer's data whatever the model asks for."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ondra_core.agent.tools import apply_price_policy, handoff_message
from ondra_core.models import (
    Appointment,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    User,
    Vehicle,
)
from sqlalchemy import func, or_, select, text
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
    """A person in a role to give work to: whoever is on shift and whose turn it is, falling back to a manager, then
    the owner (services/routing.py). Used where the team is already known; AI handoffs go through `route`, which
    also reads the dealer's rules."""
    from ondra_api.services.routing import someone_in

    return await someone_in(db, role, preferred)


_HANDOFF_TITLES = {
    "pricing": "Talk price with {first}",
    "discount": "Talk price with {first}",
    "trade_in": "Value {first}'s trade-in",
    "financing": "Go over financing with {first}",
    "delivery_date": "Confirm a delivery date with {first}",
    "complaint": "Call {first} about their complaint",
    "asked_for_person": "Get back to {first}",
    "unknown_answer": "Answer {first}'s question",
    "shipping": "Sort out shipping for {first}",
    "vehicle_request": "Find a car for {first}",
}


def handoff_title(reason: str, name: str) -> str:
    """A task title a salesperson can act on: "Talk price with Sarah", not "pricing"."""
    first = name.split()[0] if name and not name.startswith("+") else "the customer"
    return _HANDOFF_TITLES.get(reason, "Follow up with {first}").format(first=first)


def _getting_around(a) -> str | None:
    """What the transport choice means for the customer, in words, so the reply says it right (on a call Ondra
    once said "you'll have a loaner while you wait": a loaner is so they don't wait)."""
    d = a.details or {}
    if a.transport == "loaner":
        return (f"They leave their car with us and drive {d['loaner']} until it's ready." if d.get("loaner")
                else d.get("loaner_note") or "They need a loaner; the service team will arrange it.")
    return {"wait": "They wait at the dealership while it's done.",
            "drop_off": "They drop the car off and pick it up when it's ready.",
            "dropoff": "They drop the car off and pick it up when it's ready."}.get(a.transport or "")


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
            "upcoming_appointments": [await self._appointment_out(a) for a in appts],
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
            word = word.strip(",.?!").lower()
            if len(word) > 3 and word.endswith("s"):
                word = word[:-1]  # "SUVs", "trucks"
            if word in ("3-row", "third-row", "7-seater", "8-seater") and not min_seats:
                q = q.where(text("coalesce((vehicles.raw->>'seats')::int, 0) >= 7"))
                continue
            w = f"%{word}%"
            q = q.where(or_(Vehicle.make.ilike(w), Vehicle.model.ilike(w), Vehicle.trim.ilike(w),
                            Vehicle.raw["color"].astext.ilike(w), Vehicle.raw["body"].astext.ilike(w),
                            Vehicle.stock_number.ilike(w)))
        rows = (await self.db.execute(q.order_by(Vehicle.price).limit(5))).scalars().all()
        return [apply_price_policy(_vehicle_dict(v), self.price_disclosure) for v in rows]

    async def get_vehicle(self, stock_or_vin: str) -> dict | None:
        v = (await self.db.execute(
            select(Vehicle).where(or_(Vehicle.stock_number.ilike(stock_or_vin), Vehicle.vin.ilike(stock_or_vin)))
        )).scalar_one_or_none()
        return apply_price_policy(_vehicle_dict(v), self.price_disclosure) if v else None

    async def search_knowledge(self, query: str) -> list[dict]:
        self.last_question = query
        from ondra_api.services import knowledge

        return await knowledge.search(self.db, query)

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
            await self.db.flush()
            from ondra_api.services.metrics import lead_captured

            lead_captured(self.db, deal, by="ai", after_hours=not self.open_now)
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
        from ondra_api.services.crm import maybe_queue

        await maybe_queue(self.db, self.contact)  # a lead worth a salesperson's time goes to the dealer's CRM
        return {"saved": sorted(fields)}

    async def handoff(self, reason: str, brief: str, urgency: str, target_role: str) -> dict:
        from ondra_core.routing import topic_for_handoff

        from ondra_api.services.routing import route
        from ondra_api.services.tasks import new_task

        c, conv = self.contact, self.conversation
        # The dealer's routing rules decide who gets it; the model's `target_role` is the fallback when no rule
        # matches. The person already looking after this customer keeps them if they're on that team and in.
        r = await route(self.db, topic=topic_for_handoff(reason, target_role, conv.topic), channel=conv.channel,
                        contact=c, role_hint=target_role, prefer=conv.assigned_user_id)
        urgency = urgency if urgency in ("low", "normal", "high") else "normal"
        task = await new_task(
            self.db,
            title=f"{c.display_name}: {handoff_title(reason, c.display_name)}",
            contact_id=c.id,
            conversation_id=conv.id,
            assignee_user_id=r.user_id,
            source="ai_handoff",
            urgency="high" if r.alert else urgency,
            brief=brief,
        )
        if r.alert:
            from ondra_core.models import Event

            self.db.add(Event(type="alert.created", payload={"task_id": str(task.id), "to": r.role, "urgency": "high",
                                                             "contact_id": str(c.id), "reason": handoff_title(reason, c.display_name)}))
        conv.status = "waiting_staff"
        if conv.assigned_user_id is None and r.user_id:
            conv.assigned_user_id = r.user_id  # from here on, this customer has one contact
        if reason == "unknown_answer":
            await self._record_gap(self.last_question or brief)
        await self.db.flush()
        from ondra_api.services.crm import maybe_queue

        await maybe_queue(self.db, c)
        # "Shortly" only if the person it went to is in now (Lagos staff may be, while Dallas is closed).
        return {"task_id": str(task.id), "tell_customer": handoff_message(r.role or target_role, r.on_shift)}

    # --- booking ----------------------------------------------------------------------------------------------

    async def _tenant(self):
        from ondra_core.models import Tenant

        return (await self.db.execute(select(Tenant).limit(1))).scalar_one()

    async def _appointment_out(self, a) -> dict:
        from ondra_core.models import AppointmentType, Resource

        from ondra_api.services.booking import slot_label, tz_of

        t = await self.db.get(AppointmentType, a.appointment_type_id)
        names = [r.name for r in (await self.db.execute(select(Resource).where(Resource.id.in_(a.resource_ids or []),
                                                                               Resource.kind == "service_bay"))).scalars()]
        who = await self.db.get(User, a.assigned_user_id) if a.assigned_user_id else None
        return {"appointment_id": str(a.id), "kind": t.name if t else None, "status": a.status,
                "when": slot_label(a.starts_at, tz_of(await self._tenant()), names), "with": who.name if who else None,
                "loaner": (a.details or {}).get("loaner"), "getting_around": _getting_around(a)}

    async def check_availability(self, kind: str, day: str | None = None, part_of_day: str | None = None) -> dict:
        from ondra_api.services.booking import (
            InternalCalendar,
            describe_day,
            find_type,
            local_window,
            resolve_day,
        )

        t = await find_type(self.db, kind)
        if t is None:
            from ondra_core.models import AppointmentType

            names = (await self.db.execute(select(AppointmentType.name).where(AppointmentType.active.is_(True)))).scalars().all()
            return {"error": f"No appointment type called '{kind}'.", "types_offered": list(names)}
        tenant = await self._tenant()
        d = resolve_day(tenant, day)
        if day and d is None:
            # Never quietly search other days: the caller would be told their day is full.
            return {"error": f"Couldn't tell which day '{day}' means. Use a weekday (saturday), today, tomorrow or "
                             "YYYY-MM-DD, and put the time of day in part_of_day."}
        start, until = local_window(tenant, d, days=7)
        slots = await InternalCalendar(self.db, tenant).find_slots(t, start_from=start, until=until, limit=6,
                                                                   part_of_day=part_of_day)
        searched = describe_day(d) if d else "the next 7 days"
        if not slots and d is not None:  # nothing that day: offer the next openings instead
            start, until = local_window(tenant, None, days=10)
            slots = await InternalCalendar(self.db, tenant).find_slots(t, start_from=start, until=until, limit=6,
                                                                       part_of_day=part_of_day)
            note = f"Nothing open {searched}{' ' + part_of_day if part_of_day else ''}; next openings:"
            from ondra_api.services.booking import tz_of

            now = datetime.now(UTC).astimezone(tz_of(tenant))
            if d == now.date():
                # "Thursday at 3" said on Thursday evening: don't just call the day full. It's over, and they may
                # mean next week (a real call: "Nothing's open Thursday afternoon", with no reason given).
                clock = now.strftime("%-I:%M %p").lower()
                note = (f"{searched} is today and it's already {clock} here, so nothing is left today"
                        f"{' in the ' + part_of_day if part_of_day else ''}. Tell them that. If they meant next "
                        f"{now.strftime('%A')}, check day {(d + timedelta(days=7)).isoformat()}. The next openings:")
            return {"kind": t.name, "duration_minutes": t.duration_min, "searched": searched, "note": note,
                    "slots": [s.as_tool() for s in slots]}
        return {"kind": t.name, "duration_minutes": t.duration_min, "searched": searched,
                "slots": [s.as_tool() for s in slots]}

    async def book_appointment(self, slot_id: str, details: dict | None = None) -> dict:
        from ondra_api.services import booking

        tenant = await self._tenant()
        try:
            a = await booking.book(self.db, tenant, slot_id=slot_id, contact_id=self.contact.id, source="ai",
                                   conversation_id=self.conversation.id, details=details or {})
        except booking.SlotTaken:
            return {"error": "That time was just taken. Check availability again and offer new times."}
        except booking.NotBookable as exc:
            return {"error": str(exc)}
        return {"booked": await self._appointment_out(a)}

    async def reschedule_or_cancel(self, appointment_id: str, action: str, new_slot_id: str | None = None) -> dict:
        from ondra_core.models import Appointment

        from ondra_api.services import booking

        try:
            a = await self.db.get(Appointment, uuid.UUID(appointment_id))
        except ValueError:
            a = None
        if a is None or a.contact_id != self.contact.id or a.status not in booking.LIVE:
            return {"error": "No upcoming appointment with that id for this customer."}
        if action == "cancel":
            await booking.set_status(self.db, a, "cancelled", by="ai")
            return {"cancelled": await self._appointment_out(a)}
        if not new_slot_id:
            return {"error": "To move it, check availability and pass new_slot_id."}
        try:
            await booking.reschedule(self.db, await self._tenant(), a, new_slot_id)
        except booking.SlotTaken:
            return {"error": "That time was just taken. Check availability again."}
        except booking.NotBookable as exc:
            return {"error": str(exc)}
        return {"moved": await self._appointment_out(a)}

    async def get_repair_order_status(self, ro_number: str | None = None) -> dict:
        from ondra_api.services.dms import repair_order_status

        ids = (await self.db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == self.contact.id))).scalars().all()
        return await repair_order_status(self.db, phones=[i.value for i in ids if i.kind in ("phone", "whatsapp")],
                                         emails=[i.value for i in ids if i.kind == "email"], ro_number=ro_number)

    async def _record_gap(self, question: str) -> None:
        from ondra_api.services.learning import record_gap

        await record_gap(self.db, question, self.conversation.id)


__all__: list[Any] = ["DbToolBackend", "assignee_for"]
