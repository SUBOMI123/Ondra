"""The agent's tools (BUILD_PLAN.md §6.2), shared by text now and voice later.

`TOOL_SPECS` is what the model sees. `ToolBackend` is what runs them: the API implements it against Postgres
(tenant-scoped, so a tool can only ever see the current dealer's data), and the eval runner implements it against
a scenario's fixtures. The orchestrator only talks to the protocol.

Step 2 ships the tools that need no booking or DMS: get_contact_context, search_inventory, get_vehicle,
search_knowledge, update_lead_fields and handoff. Booking tools arrive in Step 4, repair-order status in Step 7.
"""

from __future__ import annotations

from typing import Any, Protocol

LEAD_FIELDS: dict[str, dict] = {
    "vehicle_interest": {"type": "string", "description": "Year/make/model/trim they want, e.g. 'Toyota Highlander'."},
    "needs": {"type": "string", "description": "Must-haves in their words, e.g. 'third row', 'towing'."},
    "budget_min": {"type": "number"},
    "budget_max": {"type": "number", "description": "Upper budget in dollars. '35k' is 35000."},
    "payment_method": {"type": "string", "enum": ["cash", "finance", "lease", "unknown"]},
    "financing": {"type": "string", "enum": ["needed", "not_needed", "unknown"]},
    "trade_in": {"type": "string", "description": "Year/make/model of the car they want to trade in."},
    "trade_in_mileage": {"type": "number"},
    "timeline": {"type": "string", "description": "When they want to buy, in their words."},
    "destination": {"type": "string", "description": "Where the car is going, if exporting/shipping."},
    "name": {"type": "string", "description": "Only if they told you their name."},
    "phone": {"type": "string", "description": "Only if they gave a number, E.164."},
    "email": {"type": "string"},
    "best_time": {"type": "string", "description": "When they prefer to be contacted."},
    "language": {"type": "string", "description": "ISO code of the language they write in, e.g. 'es'."},
}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "get_contact_context",
        "description": (
            "Who this customer is: name, vehicles on file, open deals and appointments, preferred language. "
            "Call it when knowing their history would change your answer (service questions, 'my car', 'my "
            "appointment')."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "search_inventory",
        "description": (
            "Search the dealer's live stock. Returns only vehicles that exist, with price already filtered by the "
            "dealer's price policy (a vehicle without `price` means you may not state its price). Never mention a "
            "vehicle this tool didn't return."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free text: make, model, trim, colour, body style."},
                "make": {"type": "string"},
                "model": {"type": "string"},
                "max_price": {"type": "number"},
                "min_year": {"type": "integer"},
                "min_seats": {"type": "integer", "description": "7 or 8 for a third row."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_vehicle",
        "description": "Full details for one vehicle by stock number or VIN, including a photos link.",
        "input_schema": {
            "type": "object",
            "properties": {"stock_or_vin": {"type": "string"}},
            "required": ["stock_or_vin"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_knowledge",
        "description": (
            "The dealer's own answers: hours, location, services offered, policies, financing and shipping "
            "process. Use it for any question about the dealership itself. If it returns nothing relevant, you "
            "don't know: hand off instead of guessing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_lead_fields",
        "description": (
            "Record what the customer told you about what they want, so the sales team doesn't have to ask "
            "again. Only record what they actually said. Don't call this for a question that isn't about buying "
            "or servicing a car (hours, directions, wrong number)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"fields": {"type": "object", "properties": LEAD_FIELDS, "additionalProperties": False}},
            "required": ["fields"],
            "additionalProperties": False,
        },
    },
    {
        "name": "handoff",
        "description": (
            "Pass the conversation to a person, with a brief so they don't have to read the thread. Use it "
            "whenever the dealer's rules need a person (prices below listed, discounts, trade-in values, "
            "financing decisions, delivery dates, complaints), when the customer asks for a person, or when you "
            "don't know the answer. After calling it, tell the customer who will follow up and roughly when; "
            "use the `tell_customer` text it returns. Also use it, at low urgency, when they want a car we don't "
            "have in stock, so sales can try to find one. Write your reply to the customer as text in the same "
            "message as this call, before it: that text is sent to the customer as soon as the handoff is made, so "
            "don't wait for this tool's result to write it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "pricing", "discount", "trade_in", "financing", "delivery_date", "complaint", "vehicle_request",
                        "asked_for_person", "unknown_answer", "shipping", "other",
                    ],
                },
                "brief": {"type": "string", "description": "Two or three sentences: who, what they want, what's next."},
                "urgency": {"type": "string", "enum": ["low", "normal", "high"]},
                "target_role": {
                    "type": "string", "enum": ["sales", "service", "manager", "owner"],
                    "description": "sales: buying, prices, trade-ins, financing, shipping. service: repairs, maintenance, parts, accessories and installs. manager: complaints and anger.",
                },
            },
            "required": ["reason", "brief", "urgency", "target_role"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = frozenset(t["name"] for t in TOOL_SPECS)


class ToolBackend(Protocol):
    async def get_contact_context(self) -> dict: ...
    async def search_inventory(self, **filters: Any) -> list[dict]: ...
    async def get_vehicle(self, stock_or_vin: str) -> dict | None: ...
    async def search_knowledge(self, query: str) -> list[dict]: ...
    async def update_lead_fields(self, fields: dict) -> dict: ...
    async def handoff(self, reason: str, brief: str, urgency: str, target_role: str) -> dict: ...


def apply_price_policy(vehicle: dict, price_disclosure: str) -> dict:
    """What the model may know about a vehicle's price. With `none` the model never sees a price, so it can't leak
    one; with `range` it sees a rounded band instead of the exact number."""
    v = dict(vehicle)
    price = v.pop("price", None)
    if price is None or price_disclosure == "none":
        v["price_note"] = "Price not shared by message. A salesperson will go over pricing."
        return v
    if price_disclosure == "range":
        low = int(price * 0.97 // 500 * 500)
        high = int(-(-price * 1.03 // 500) * 500)
        v["price_range"] = f"${low:,} to ${high:,}"
        return v
    v["price"] = int(price)
    v["price_note"] = "Listed price. Not a final or negotiated price."
    return v


def handoff_message(target_role: str, open_now: bool) -> str:
    who = {
        "sales": "someone from our sales team",
        "service": "one of our service advisors",
        "manager": "a manager",
        "owner": "the owner",
    }.get(target_role, "someone from our team")
    when = "shortly" if open_now else "when we open"
    return f"I've passed this to {who}; they'll get back to you {when}."


async def run_tool(backend: ToolBackend, name: str, args: dict) -> Any:
    if name == "get_contact_context":
        return await backend.get_contact_context()
    if name == "search_inventory":
        return await backend.search_inventory(**args)
    if name == "get_vehicle":
        return await backend.get_vehicle(args["stock_or_vin"]) or {"error": "No vehicle with that stock number or VIN."}
    if name == "search_knowledge":
        return await backend.search_knowledge(args["query"])
    if name == "update_lead_fields":
        return await backend.update_lead_fields(args.get("fields", {}))
    if name == "handoff":
        return await backend.handoff(args["reason"], args["brief"], args["urgency"], args["target_role"])
    raise KeyError(name)
