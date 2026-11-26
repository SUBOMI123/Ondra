"""One phone call, outside LiveKit: what the voice agent knows, the tools it runs, and what's kept afterwards.

The same pattern as LiveKit's vehicle-service example (a "desk" that holds every rule, with thin Agent classes on
top), but the rules aren't new: tools run through the shared tool layer (`ondra_core.agent.tools.run_tool` on the
API's `DbToolBackend`), the same one text uses, so a booking, a handoff or a price works identically on every
channel. Each tool call opens its own short tenant-scoped transaction; a call lasts minutes and must never hold one.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ondra_api.db import tenant_session
from ondra_api.services.agent_tools import DbToolBackend, assignee_for
from ondra_api.services.calls import CallPlan
from ondra_api.services.inbound import dealer_clock
from ondra_core.agent.detectors import ReplyContext
from ondra_core.agent.orchestrator import ToolRecord, _learn
from ondra_core.agent.prompt import CustomerFacts, DealerFacts
from ondra_core.agent.tools import run_tool
from ondra_core.models import Contact, Conversation, Policy, Tenant, User, Vehicle
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
            )
            customer = CustomerFacts(known=plan.known and plan.caller_name is not None, name=plan.caller_name,
                                     language=contact.language)
            backend = await _backend(db, plan, dealer)
            # Plan §4.2: look the caller up before the greeting, so the agent starts knowing who they are.
            context = await backend.get_contact_context() if plan.known else None
            stock = (await db.execute(select(Vehicle.make, Vehicle.model).where(Vehicle.status == "available")
                                      .distinct().limit(40))).all()
        checks = ReplyContext(price_disclosure=dealer.price_disclosure, today=local_time.split()[0])
        vocabulary = list(dict.fromkeys([dealer.name] + [w for make, model in stock for w in (make, model)]))[:60]
        desk = cls(plan=plan, dealer=dealer, customer=customer, contact_context=context, checks=checks,
                   vocabulary=vocabulary)
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
            out = await run_tool(backend, name, args)
        self.tools_called.append(name)
        _learn(self.checks, ToolRecord(name, args, out))
        return self._short_slots(out)

    def _short_slots(self, out: Any) -> Any:
        if isinstance(out, dict) and isinstance(out.get("slots"), list):
            for slot in out["slots"]:
                if isinstance(slot, dict) and slot.get("slot_id"):
                    alias = f"slot{len(self.slot_aliases) + 1}"
                    self.slot_aliases[alias] = slot["slot_id"]
                    slot["slot_id"] = alias
        return out

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
        e2e_sorted = sorted(e2e)
        summary = {
            "turns": len(e2e),
            "avg_ms": round(sum(e2e) / len(e2e)) if e2e else None,
            "p90_ms": e2e_sorted[min(len(e2e_sorted) - 1, int(len(e2e_sorted) * 0.9))] if e2e else None,
            "over_1s": sum(1 for x in e2e if x > 1000),
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


def turn_metrics_from(report: dict) -> dict:
    """LiveKit's per-message `MetricsReport` (seconds) to milliseconds, keeping the parts we report on."""
    ms = {k: round(v * 1000) for k, v in report.items() if isinstance(v, (int, float)) and k.endswith(("_delay", "_ttft", "_ttfb", "_latency"))}
    return {
        "e2e_ms": ms.get("e2e_latency"),
        "llm_ttft_ms": ms.get("llm_node_ttft"),
        "tts_ttfb_ms": ms.get("tts_node_ttfb"),
        "end_of_turn_ms": ms.get("end_of_turn_delay"),
        "transcription_ms": ms.get("transcription_delay"),
    }
