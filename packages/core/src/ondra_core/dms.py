"""The dealer management system (DMS), behind one interface (BUILD_PLAN.md §8).

Real vendors (CDK, Reynolds, Tekion, DealerCenter) only open their APIs through partner programs, so nothing here
talks to one. Two adapters ship: `MockDms` (fixtures, for local runs, tests and demos) and `CsvDms` (a repair-order
export the dealer uploads). A vendor adapter is added behind `DmsAdapter` when access is granted.
TODO(verify): every vendor API detail, when there is one to verify.

A repair order is found by the customer's own phone number or email, never by an RO number alone: a number read off
someone else's paperwork must not reveal their car.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Protocol

# What the service desk would say for each status. No completion times: only a person promises those.
STATUSES = {
    "scheduled": "It's booked in and hasn't been checked in yet.",
    "checked_in": "It's checked in and waiting for a technician.",
    "in_progress": "A technician is working on it now.",
    "waiting_parts": "It's waiting on parts.",
    "waiting_approval": "The service team needs the customer's go-ahead before they continue.",
    "ready": "It's ready to be picked up.",
    "picked_up": "It's been picked up.",
}
_STATUS_WORDS = {
    "open": "checked_in", "checkedin": "checked_in", "checkin": "checked_in", "received": "checked_in", "waiting": "checked_in",
    "inprogress": "in_progress", "working": "in_progress", "inshop": "in_progress", "inservice": "in_progress", "wip": "in_progress",
    "waitingparts": "waiting_parts", "waitingonparts": "waiting_parts", "partsonorder": "waiting_parts", "partshold": "waiting_parts",
    "waitingapproval": "waiting_approval", "awaitingapproval": "waiting_approval", "customerhold": "waiting_approval",
    "ready": "ready", "complete": "ready", "completed": "ready", "done": "ready", "readyforpickup": "ready", "finished": "ready",
    "pickedup": "picked_up", "closed": "picked_up", "delivered": "picked_up", "invoiced": "picked_up",
    "scheduled": "scheduled", "appointment": "scheduled", "booked": "scheduled",
}


class NotSupported(Exception):
    """This DMS can't do that (a CSV export can't book a service slot)."""


@dataclass(frozen=True)
class RepairOrder:
    number: str
    status: str  # a key of STATUSES
    vehicle: str = ""  # "2018 Honda Accord"
    advisor: str | None = None
    phone: str | None = None  # the customer's, digits only
    email: str | None = None
    opened: str | None = None
    note: str | None = None  # the advisor's note for the customer, if the DMS has one

    def for_customer(self) -> dict:
        """What the AI may say. No amounts and no completion time."""
        out = {"repair_order": self.number, "vehicle": self.vehicle or None, "status": self.status, "what_it_means": STATUSES[self.status],
               "service_advisor": self.advisor}
        if self.note:
            out["advisor_note"] = self.note
        return {k: v for k, v in out.items() if v is not None}


@dataclass(frozen=True)
class DmsCustomer:
    name: str
    phone: str | None = None
    email: str | None = None
    vehicles: tuple[str, ...] = ()


def digits(phone: str | None) -> str:
    """The last 10 digits: "+1 (214) 555-0102" and "2145550102" are the same customer."""
    return re.sub(r"\D", "", phone or "")[-10:]


class DmsAdapter(Protocol):
    provider: str

    async def get_customer(self, *, phone: str | None = None, email: str | None = None) -> DmsCustomer | None: ...
    async def get_repair_orders(self, *, phones: list[str], emails: list[str]) -> list[RepairOrder]: ...
    async def get_service_slots(self, day: str) -> list[str]: ...
    async def book_service(self, slot: str, customer: DmsCustomer, vehicle: str, concern: str) -> str: ...
    async def health(self) -> tuple[bool, str]: ...


def _mine(orders: list[RepairOrder], phones: list[str], emails: list[str]) -> list[RepairOrder]:
    p = {digits(x) for x in phones if digits(x)}
    e = {x.strip().lower() for x in emails if x}
    hits = [o for o in orders if (o.phone and digits(o.phone) in p) or (o.email and o.email.lower() in e)]
    return sorted(hits, key=lambda o: (o.status == "picked_up", o.opened or ""), reverse=False)  # open ones first


class MockDms:
    """Fixtures in memory. The default set matches the seeded demo dealership."""

    provider = "mock"

    def __init__(self, orders: list[RepairOrder] | None = None, customers: list[DmsCustomer] | None = None) -> None:
        self.orders = list(orders if orders is not None else DEMO_ORDERS)
        self.customers = list(customers or [])
        self.booked: list[dict] = []

    async def get_customer(self, *, phone: str | None = None, email: str | None = None) -> DmsCustomer | None:
        for c in self.customers:
            if (phone and digits(c.phone) == digits(phone)) or (email and c.email and c.email.lower() == email.lower()):
                return c
        return None

    async def get_repair_orders(self, *, phones: list[str], emails: list[str]) -> list[RepairOrder]:
        return _mine(self.orders, phones, emails)

    async def get_service_slots(self, day: str) -> list[str]:
        return [f"{day} 08:00", f"{day} 10:30", f"{day} 14:00"]

    async def book_service(self, slot: str, customer: DmsCustomer, vehicle: str, concern: str) -> str:
        self.booked.append({"slot": slot, "customer": customer.name, "vehicle": vehicle, "concern": concern})
        return f"MOCK-{len(self.booked):04d}"

    async def health(self) -> tuple[bool, str]:
        return True, f"Demo data: {len(self.orders)} repair orders."


class CsvDms:
    """Repair orders from a CSV export the dealer uploads. Read-only: it can't book."""

    provider = "csv"

    def __init__(self, orders: list[RepairOrder]) -> None:
        self.orders = orders

    async def get_customer(self, *, phone: str | None = None, email: str | None = None) -> DmsCustomer | None:
        mine = _mine(self.orders, [phone] if phone else [], [email] if email else [])
        return DmsCustomer(name="", phone=phone, email=email, vehicles=tuple(dict.fromkeys(o.vehicle for o in mine if o.vehicle))) if mine else None

    async def get_repair_orders(self, *, phones: list[str], emails: list[str]) -> list[RepairOrder]:
        return _mine(self.orders, phones, emails)

    async def get_service_slots(self, day: str) -> list[str]:
        raise NotSupported("A CSV export has no service schedule. Ondra's own calendar books service.")

    async def book_service(self, slot: str, customer: DmsCustomer, vehicle: str, concern: str) -> str:
        raise NotSupported("A CSV export can't take bookings. Ondra's own calendar books service.")

    async def health(self) -> tuple[bool, str]:
        return bool(self.orders), f"{len(self.orders)} repair orders from the last upload." if self.orders else "No repair orders uploaded yet."


_RO_HEADERS = {
    "number": ("ro", "ronumber", "ro#", "repairorder", "repairordernumber", "ordernumber", "workorder", "invoice"),
    "status": ("status", "rostatus", "state"),
    "phone": ("phone", "customerphone", "cell", "mobile", "cellphone", "homephone", "phonenumber"),
    "email": ("email", "customeremail", "emailaddress"),
    "advisor": ("advisor", "serviceadvisor", "writer", "advisorname"),
    "year": ("year", "modelyear"), "make": ("make",), "model": ("model",), "vehicle": ("vehicle", "vehicledescription"),
    "opened": ("opened", "opendate", "dateopened", "datein", "created"),
    "note": ("note", "customernote", "advisornote", "notes"),
}
_RO_SPELL = {s: k for k, spellings in _RO_HEADERS.items() for s in spellings}
MAX_ORDERS = 2000


def parse_repair_orders(text: str) -> tuple[list[RepairOrder], list[dict], str | None]:
    """(orders, skipped rows with the reason, error for the whole file)."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        headers = next(reader)
    except StopIteration:
        return [], [], "This file is empty."
    names = [_RO_SPELL.get(re.sub(r"[^a-z0-9#]", "", h.lower())) for h in headers]
    if "number" not in names or "status" not in names or not ({"phone", "email"} & set(names)):
        return [], [], "This file needs columns for the RO number, its status, and the customer's phone or email."
    orders, skipped = [], []
    for line, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        row = {n: v.strip() for n, v in zip(names, values, strict=False) if n}
        status = _STATUS_WORDS.get(re.sub(r"[^a-z]", "", row.get("status", "").lower())) or (
            row.get("status", "").lower().replace(" ", "_") if row.get("status", "").lower().replace(" ", "_") in STATUSES else None)
        if not row.get("number"):
            skipped.append({"line": line, "why": "No RO number"})
        elif status is None:
            skipped.append({"line": line, "why": f"Status '{row.get('status', '')[:30]}' isn't one we know"})
        elif not digits(row.get("phone")) and not row.get("email"):
            skipped.append({"line": line, "why": "No phone or email to match the customer by"})
        else:
            vehicle = row.get("vehicle") or " ".join(x for x in (row.get("year"), row.get("make"), row.get("model")) if x)
            orders.append(RepairOrder(number=row["number"][:40], status=status, vehicle=vehicle[:120], advisor=row.get("advisor") or None,
                                      phone=digits(row.get("phone")) or None, email=(row.get("email") or "").lower() or None,
                                      opened=row.get("opened") or None, note=(row.get("note") or "")[:300] or None))
        if len(orders) > MAX_ORDERS:
            return [], [], f"This file has more than {MAX_ORDERS} repair orders. Export only the open ones."
    return orders, skipped, None


# The seeded demo dealership's service lane (phones match seeded contacts 1001-1003).
DEMO_ORDERS = [
    RepairOrder("RO-55120", "waiting_parts", "2018 Honda Accord", "Maria", phone="2145551001", opened="2026-11-23"),
    RepairOrder("RO-55131", "in_progress", "2021 Toyota Tacoma", "Maria", phone="2145551002", opened="2026-11-26"),
    RepairOrder("RO-55098", "ready", "2020 Ford Escape", "Maria", phone="2145551003", opened="2026-11-24",
                note="Brake pads and rotors replaced. Keys are at the service desk."),
]
