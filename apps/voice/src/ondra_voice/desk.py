"""One phone call, outside LiveKit: what the voice agent knows, the tools it runs, and what's kept afterwards.

The same pattern as LiveKit's vehicle-service example (a "desk" that holds every rule, with thin Agent classes on
top), but the rules aren't new: tools run through the shared tool layer (`ondra_core.agent.tools.run_tool` on the
API's `DbToolBackend`), the same one text uses, so a booking, a handoff or a price works identically on every
channel. Each tool call opens its own short tenant-scoped transaction; a call lasts minutes and must never hold one.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ondra_api.db import tenant_session
from ondra_api.services.agent_tools import DbToolBackend, assignee_for
from ondra_api.services.calls import CallPlan
from ondra_api.services.inbound import dealer_clock
from ondra_api.services.routing import teams_now
from ondra_core.agent.detectors import ReplyContext
from ondra_core.agent.orchestrator import ToolRecord, _learn
from ondra_core.agent.prompt import CustomerFacts, DealerFacts
from ondra_core.agent.tools import run_tool
from ondra_core.models import ChannelAddress, Contact, Conversation, Policy, Tenant, User, Vehicle
from sqlalchemy import select

BLOCK_REASON = {"quotes_final_price": "pricing", "promises_discount": "discount", "values_trade_in": "trade_in",
                "guarantees_financing": "financing", "promises_date": "delivery_date"}


@dataclass
class TransferTarget:
    user_id: uuid.UUID
    name: str
    phone: str


@dataclass
class CallDesk:
    plan: CallPlan
    dealer: DealerFacts
    customer: CustomerFacts
    contact_context: dict | None
    checks: ReplyContext
    transcript: list[dict] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)  # names of checks that replaced a sentence
    turn_metrics: list[dict] = field(default_factory=list)
    # Tools that crashed or refused (e.g. a booking that didn't go through), kept on the call record so staff and
    # engineers can see why without reading the worker's logs.
    tool_problems: list[dict] = field(default_factory=list)
    # Words speech recognition should expect: the dealership's name and the makes and models in stock.
    vocabulary: list[str] = field(default_factory=list)
    # Short names for the calendar's slot ids ("slot3"): the real ids are ~200 characters, and on a call the model
    # writing one out before booking was most of a 1.9 s wait (and a chance to garble it).
    slot_aliases: dict[str, str] = field(default_factory=dict)
    # The full result of the last stock search: on a call Ondra names the best two, and can text all of them.
    last_cars: list[dict] = field(default_factory=list)
    can_text: bool = False  # the dealer's SMS is live, so offering to text the caller is honest
    # Quick fillers: whether one was said this turn and last turn, and which phrase comes next.
    filled_this_turn: bool = False
    filled_last_turn: bool = False
    filler_index: int = 0
    # Timings waiting to be attached to the next spoken reply: the caller's side of the turn (how long LiveKit
    # waited to be sure they'd finished, and for the transcript), and time spent inside tools.
    caller_side: dict = field(default_factory=dict)
    tool_ms: int = 0
    tool_count: int = 0
    transferred_to: TransferTarget | None = None
    pending: list[asyncio.Task] = field(default_factory=list)  # follow-ups to finish before the call is stored
    started: float = field(default_factory=time.monotonic)
    blocked_follow_up_queued: bool = False

    # --- set up, before the first word ------------------------------------------------------------------------

    @classmethod
    async def open(cls, plan: CallPlan) -> CallDesk:
        async with tenant_session(plan.tenant_id) as db:
            tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
            policy = (await db.execute(select(Policy).limit(1))).scalar_one_or_none()
            contact = await db.get(Contact, plan.contact_id)
            local_time, open_now = dealer_clock(tenant)
            dealer = DealerFacts(
                name=tenant.name, local_time=local_time, open_now=open_now,
                price_disclosure=policy.price_disclosure if policy else "none",
                handoff_triggers=list(policy.handoff_triggers) if policy else [],
                never_say=list(policy.never_say) if policy else [],
                disclose_upfront=(tenant.settings or {}).get("ai_disclosure") == "upfront",
                teams=await teams_now(db, tenant),
            )
            customer = CustomerFacts(known=plan.known and plan.caller_name is not None, name=plan.caller_name,
                                     language=contact.language)
            backend = await _backend(db, plan, dealer)
            # Plan §4.2: look the caller up before the greeting, so the agent starts knowing who they are.
            context = await backend.get_contact_context() if plan.known else None
            stock = (await db.execute(select(Vehicle.make, Vehicle.model).where(Vehicle.status == "available")
                                      .distinct().limit(40))).all()
            sms = (await db.execute(select(ChannelAddress.provider).where(ChannelAddress.channel == "sms", ChannelAddress.active.is_(True))
                                    .limit(1))).scalar_one_or_none()
        # Only offer to text if a text would actually reach the caller. Callers were told "it's on its way" while the
        # dealer's SMS was still the mock. VOICE_TEXT_ON_MOCK=1 lets local runs and tests use the mock on purpose.
        can_text = sms is not None and (sms != "mock" or os.getenv("VOICE_TEXT_ON_MOCK") == "1")
        checks = ReplyContext(price_disclosure=dealer.price_disclosure, today=local_time.split()[0])
        # Dealership words callers use ("I need the loaner" was heard as "lunar skill" on a real call), then stock.
        trade = ["loaner", "oil change", "test drive", "trade-in", "service appointment", "brake", "tire rotation"]
        vocabulary = list(dict.fromkeys([dealer.name, *trade] + [w for make, model in stock for w in (make, model)]))[:60]
        desk = cls(plan=plan, dealer=dealer, customer=customer, contact_context=context, checks=checks,
                   vocabulary=vocabulary, can_text=can_text)
        if context:
            _learn(checks, ToolRecord("get_contact_context", {}, context))
        return desk

    # --- tools ------------------------------------------------------------------------------------------------

    async def run(self, name: str, args: dict) -> Any:
        """Run one shared tool for this caller, in its own transaction, and remember what it returned so the
        spoken-reply checks know which prices and cars are real."""
        args = self._real_slots(name, args)
        async with tenant_session(self.plan.tenant_id) as db:
            backend = await _backend(db, self.plan, self.dealer)
            if self.transcript:
                backend.last_question = next((t["text"] for t in reversed(self.transcript) if t["who"] == "caller"), "")
            started = time.monotonic()
            out = await run_tool(backend, name, args)
            self.tool_ms += round((time.monotonic() - started) * 1000)
            self.tool_count += 1
        self.tools_called.append(name)
        _learn(self.checks, ToolRecord(name, args, out))  # every price found counts as real, not just the two named
        if name == "search_inventory" and isinstance(out, list):
            return self._best_two(out)
        return self._short_slots(out)

    def _best_two(self, cars: list[dict]) -> Any:
        """On a call, the model gets two cars to name, not a list to read out: reading four cars and prices aloud
        was hard to follow on real calls, and an instruction to "name one or two" didn't hold. The cheapest, and the
        newest if that's a different car. The rest are offered by text."""
        self.last_cars = cars
        if len(cars) <= 3:  # "we have three" then naming two sounded odd on a call: three short ones are fine
            return cars
        cheapest = cars[0]  # search results come cheapest first
        newest = max(cars, key=lambda c: (c.get("year") or 0, -(c.get("mileage") or 0)))
        best = [cheapest] + ([newest] if newest is not cheapest else [cars[1]])
        return {"total_found": len(cars), "best": [_spoken(c) for c in best],
                "next": f"Say there are {len(cars)}. Then name only these two, each as year, model and price, "
                        "nothing else: mileage and trim only if they ask. Ask one question to narrow it down "
                        "(budget, newer or lower miles). " + (
                            "Offer to text all of them; call text_details once they ask for it or say yes." if self.can_text else
                            "Texts can't be sent from this line yet, so don't offer one: offer to go through the rest, "
                            "or to have someone from sales follow up with the full list.")}

    async def text_details(self, stock_numbers: list[str] | None, said: str) -> dict:
        """Text the caller the cars from the last search, after they agreed on the call. Their yes is recorded as
        consent (CLAUDE.md: no automated texts without recorded consent), and the text goes through the one send
        path, which re-checks opt-outs and VIP status."""
        from ondra_api.services.inbound import contact_opted_out
        from ondra_api.services.jobs import enqueue
        from ondra_core.models import Consent, Event, Message

        if not self.can_text:
            return {"error": "Texts can't be sent from this line yet. Tell them plainly, and offer to have sales follow up "
                             "with the list instead (handoff, low urgency)."}
        if not _AGREED.search(said or ""):
            return {"error": "They haven't agreed to a text yet. Ask first, and wait for a yes."}
        wanted = {s.strip().upper() for s in (stock_numbers or []) if s}
        cars = [c for c in self.last_cars if not wanted or str(c.get("stock", "")).upper() in wanted] or self.last_cars
        if not cars:
            return {"error": "There's nothing to text yet: look the cars up first."}
        async with tenant_session(self.plan.tenant_id) as db:
            if await contact_opted_out(db, self.plan.contact_id):
                return {"error": "They've opted out of texts, so nothing can be sent. Offer to go over it by phone."}
            db.add(Consent(contact_id=self.plan.contact_id, channel="sms", purpose="transactional", status="opted_in",
                           source="voice_call", evidence={"call_id": str(self.plan.call_id), "said": said[:300],
                                                          "asked_for": "vehicle details by text"}))
            conv = (await db.execute(select(Conversation).where(
                Conversation.contact_id == self.plan.contact_id, Conversation.channel == "sms",
                Conversation.status != "closed").limit(1))).scalar_one_or_none()
            if conv is None:
                conv = Conversation(contact_id=self.plan.contact_id, channel="sms", ai_mode="auto")
                db.add(conv)
                await db.flush()
            m = Message(conversation_id=conv.id, direction="outbound", author_type="ai", status="queued",
                        body=_details_text(self.dealer.name, cars))
            db.add(m)
            await db.flush()
            enqueue(db, "send_message", {"message_id": str(m.id)})
            db.add(Event(type="call.texted_details", payload={"call_id": str(self.plan.call_id), "message_id": str(m.id),
                                                              "cars": len(cars)}))
        self.tools_called.append("text_details")
        return {"sent": True, "cars": len(cars), "tell_caller": "It's on its way to the number you're calling from."}

    def _short_slots(self, out: Any) -> Any:
        """Swap each long slot id for a short name the model can copy quickly. The name carries the day and time
        ("sat-9am", "fri-1230pm"), not a position: with "slot1, slot2, slot3" a caller who said "three works"
        (three o'clock) got the third slot, 1 pm, on a test call."""
        if isinstance(out, dict) and isinstance(out.get("slots"), list):
            known = {real: alias for alias, real in self.slot_aliases.items()}
            for slot in out["slots"]:
                if isinstance(slot, dict) and slot.get("slot_id"):
                    real = slot["slot_id"]
                    alias = known.get(real) or self._slot_name(str(slot.get("when") or ""))
                    self.slot_aliases[alias] = known[real] = real
                    slot["slot_id"] = alias
                if isinstance(slot, dict) and isinstance(slot.get("with"), str):
                    slot["with"] = slot["with"].split()[0]  # on the phone it's "with Maria", not "with Maria Lopez"
        for appointment in ([out.get(k) for k in ("booked", "moved", "cancelled")] if isinstance(out, dict) else []):
            if isinstance(appointment, dict) and isinstance(appointment.get("with"), str):
                appointment["with"] = appointment["with"].split()[0]
        return out

    def _slot_name(self, when: str) -> str:
        """"Sat 9:00 am, Bay 1" -> "sat-9am". Two people free at the same time get "sat-9am-b", "-c"."""
        base = re.sub(r"[^a-z0-9]+", "-", when.split(",")[0].lower().replace(":00", "").replace(":", "").replace(" am", "am").replace(" pm", "pm")).strip("-") or "slot"
        name, n = base, 1
        while name in self.slot_aliases:
            n += 1
            name = f"{base}-{chr(96 + n)}"
        return name

    def _real_slots(self, name: str, args: dict) -> dict:
        keys = {"book_appointment": "slot_id", "reschedule_or_cancel": "new_slot_id"}
        key = keys.get(name)
        if key and args.get(key) in self.slot_aliases:
            return {**args, key: self.slot_aliases[args[key]]}
        return args

    def follow_up_on_block(self, problems: list[str]) -> None:
        """The spoken check replaced a sentence and told the caller a person will follow up: make that true.
        One task per call, and none if the agent already handed off."""
        if self.blocked_follow_up_queued or "handoff" in self.tools_called:
            return
        self.blocked_follow_up_queued = True
        reason = next((BLOCK_REASON[p] for p in problems if p in BLOCK_REASON), "other")
        said = next((t["text"] for t in reversed(self.transcript) if t["who"] == "caller"), "")
        brief = (f"On a call, Ondra stopped itself from committing to something it isn't allowed to ({', '.join(problems)}) "
                 f"and told the caller someone would follow up. They said: \"{said[:200]}\". Please call them back.")
        self.pending.append(asyncio.create_task(self.run("handoff", {
            "reason": reason, "brief": brief, "urgency": "normal",
            "target_role": "service" if reason == "delivery_date" else "sales"})))

    async def settle(self) -> None:
        if self.pending:
            await asyncio.gather(*self.pending, return_exceptions=True)

    async def transfer_target(self, role: str) -> TransferTarget | None:
        """Who to ring for a warm transfer: the person the router would assign, if they have a phone."""
        async with tenant_session(self.plan.tenant_id) as db:
            uid = await assignee_for(db, role)
            u = await db.get(User, uid) if uid else None
            if u is None or not u.phone or not u.active:
                return None
            return TransferTarget(u.id, u.name, u.phone)

    # --- what we keep -----------------------------------------------------------------------------------------

    def heard(self, who: str, text: str) -> None:
        if text.strip():
            self.transcript.append({"who": who, "text": text.strip()})
            if who == "caller":
                self.checks.customer_text += "\n" + text.strip()

    def metrics(self) -> dict:
        """Per-turn latency (plan §6.4 target: under 1 s on average) and a summary for the latency report."""
        e2e = [m["e2e_ms"] for m in self.turn_metrics if m.get("e2e_ms") is not None]

        def avg(key: str) -> int | None:
            v = [m[key] for m in self.turn_metrics if m.get(key) is not None]
            return round(sum(v) / len(v)) if v else None

        e2e_sorted = sorted(e2e)
        summary = {
            "turns": len(e2e),
            "avg_ms": round(sum(e2e) / len(e2e)) if e2e else None,
            "p90_ms": e2e_sorted[min(len(e2e_sorted) - 1, int(len(e2e_sorted) * 0.9))] if e2e else None,
            "over_1s": sum(1 for x in e2e if x > 1000),
            # Where the wait goes: deciding the caller has finished, the model's first word, the voice starting,
            # and tools (per reply that followed one).
            "avg_end_of_turn_ms": avg("end_of_turn_ms"), "avg_llm_ttft_ms": avg("llm_ttft_ms"),
            "avg_tts_ttfb_ms": avg("tts_ttfb_ms"), "avg_tool_ms": avg("tool_ms"),
            "tools": self.tools_called,
            "blocked": self.blocked,
            "tool_problems": self.tool_problems,
        }
        return {"summary": summary, "turns": self.turn_metrics, "recording_notice": self.plan.disclose_recording}


async def _backend(db, plan: CallPlan, dealer: DealerFacts) -> DbToolBackend:
    contact = await db.get(Contact, plan.contact_id)
    conv = await db.get(Conversation, plan.conversation_id)
    return DbToolBackend(db, contact=contact, conversation=conv, price_disclosure=dealer.price_disclosure,
                         open_now=dealer.open_now)


_AGREED = re.compile(r"\b(yes|yeah|yep|yup|sure|ok(?:ay)?|please|go ahead|do it|send it|text (?:it|me|them)|"
                     r"that works|sounds good|perfect|absolutely|of course)\b", re.IGNORECASE)


def _spoken(c: dict) -> dict:
    """The parts of a car worth saying on a phone."""
    keep = ("stock", "year", "make", "model", "trim", "mileage", "color", "price", "price_range", "price_note")
    return {k: c[k] for k in keep if c.get(k) is not None}


def _details_text(dealer: str, cars: list[dict]) -> str:
    lines = [f"{dealer}: the cars we talked about."]
    for c in cars[:6]:
        name = " ".join(str(c[k]) for k in ("year", "make", "model", "trim") if c.get(k))
        price = f"${c['price']:,.0f}" if isinstance(c.get("price"), (int, float)) else c.get("price_range") or "ask us"
        miles = f"{c['mileage']:,} mi" if c.get("mileage") else "new"
        lines.append(f"{name}, {miles}, {price} (stock {c.get('stock')})")
    lines.append("Reply here with questions, or to book a test drive.")
    return "\n".join(lines)


def turn_metrics_from(report: dict) -> dict:
    """LiveKit's per-message `MetricsReport` (seconds) to milliseconds, keeping the parts we report on. A reply's
    report has the model and voice times; the caller's message has the wait before the reply could start."""
    ms = {k: round(v * 1000) for k, v in report.items() if isinstance(v, (int, float)) and k.endswith(("_delay", "_ttft", "_ttfb", "_latency"))}
    names = {"e2e_ms": "e2e_latency", "llm_ttft_ms": "llm_node_ttft", "tts_ttfb_ms": "tts_node_ttfb",
             "end_of_turn_ms": "end_of_turn_delay", "transcription_ms": "transcription_delay",
             "before_reply_hook_ms": "on_user_turn_completed_delay"}
    return {ours: ms[theirs] for ours, theirs in names.items() if theirs in ms}
