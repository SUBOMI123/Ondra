"""One agent turn (BUILD_PLAN.md §6.1): build context, run the model with tools, check the reply, return it.

The orchestrator never sends anything. It returns a `TurnResult`; the caller (the API, or the eval runner) applies
draft mode and the outbound gate, and stores everything. The pre-policy has already decided the AI may run.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from ondra_core.agent.detectors import ReplyContext, review_reply
from ondra_core.agent.llm import LLM
from ondra_core.agent.prompt import CustomerFacts, DealerFacts, build_system
from ondra_core.agent.tools import TOOL_SPECS, ToolBackend, handoff_message, run_tool

MAX_STEPS = 6  # model calls per turn, including tool rounds and one rewrite

_REASON_FOR_CHECK = {
    "quotes_final_price": "pricing",
    "promises_discount": "discount",
    "values_trade_in": "trade_in",
    "guarantees_financing": "financing",
    "promises_date": "delivery_date",
}


@dataclass
class ToolRecord:
    name: str
    input: dict
    output: Any


@dataclass
class TurnResult:
    reply: str
    tools: list[ToolRecord] = field(default_factory=list)
    handoff: dict | None = None  # the handoff tool's input, if a person was asked to take over
    blocked: dict[str, list[str]] = field(default_factory=dict)  # checks the first draft failed
    rewritten: bool = False
    fallback: str | None = None  # why the safe fallback reply was used instead of the model's
    latency_ms: int = 0
    model_calls: int = 0
    usage: list[dict] = field(default_factory=list)

    @property
    def tools_called(self) -> list[str]:
        return [t.name for t in self.tools]


@dataclass
class Turn:
    role: str  # "customer" | "assistant" (anything Ondra or staff sent)
    text: str


def _to_messages(history: list[Turn]) -> list[dict]:
    msgs: list[dict] = []
    for t in history:
        role = "user" if t.role == "customer" else "assistant"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n\n" + t.text
        else:
            msgs.append({"role": role, "content": t.text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return msgs


def _learn(ctx: ReplyContext, record: ToolRecord) -> None:
    """Remember the prices and makes tools returned, so the reply checks know what's real."""
    out = record.output
    vehicles = out if isinstance(out, list) else [out] if isinstance(out, dict) else []
    for v in vehicles:
        if not isinstance(v, dict):
            continue
        if isinstance(v.get("price"), (int, float)):
            ctx.listed_prices.add(int(v["price"]))
        if v.get("make"):
            ctx.known_makes.add(str(v["make"]))
        for car in v.get("vehicles_on_file", []) if isinstance(v.get("vehicles_on_file"), list) else []:
            if isinstance(car, dict) and car.get("make"):
                ctx.known_makes.add(str(car["make"]))


async def run_turn(
    *,
    llm: LLM,
    backend: ToolBackend,
    dealer: DealerFacts,
    customer: CustomerFacts,
    channel: str,
    history: list[Turn],
    known_makes: set[str] | None = None,
    preload_contact: bool = True,
) -> TurnResult:
    """`history` ends with the customer's new message(s)."""
    started = time.monotonic()
    result = TurnResult(reply="")
    contact_context = await backend.get_contact_context() if preload_contact and customer.known else None
    system = build_system(dealer, channel, customer, contact_context)
    messages = _to_messages(history)
    ctx = ReplyContext(
        price_disclosure=dealer.price_disclosure,
        known_makes=set(known_makes or ()) | {
            str(v["make"]) for v in (contact_context or {}).get("vehicles_on_file", []) if isinstance(v, dict) and v.get("make")
        },
        customer_text="\n".join(t.text for t in history if t.role == "customer"),
    )
    reply: str | None = None
    rewrites = 0

    while result.model_calls < MAX_STEPS:
        resp = await llm.create(system=system, messages=messages, tools=TOOL_SPECS)
        result.model_calls += 1
        result.usage.append(resp.usage)

        if resp.stop_reason == "refusal":
            result.fallback = "refusal"
            break

        if resp.tool_calls:
            messages.append({"role": "assistant", "content": resp.raw_content})
            results = []
            for call in resp.tool_calls:
                try:
                    output = await run_tool(backend, call.name, call.input)
                    is_error = False
                except Exception as exc:  # noqa: BLE001  a broken tool must not crash the turn; the model is told it failed
                    output, is_error = {"error": f"{type(exc).__name__}: tool failed"}, True
                rec = ToolRecord(call.name, call.input, output)
                result.tools.append(rec)
                _learn(ctx, rec)
                if call.name == "handoff" and not is_error:
                    result.handoff = call.input
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(output, default=str),
                    **({"is_error": True} if is_error else {}),
                })
            messages.append({"role": "user", "content": results})
            continue

        text = resp.text.strip()
        problems = review_reply(text, ctx, dealer.never_say) if text else {"empty": ["no reply"]}
        if not problems:
            reply = text
            break
        if not result.blocked:
            result.blocked = problems
        if rewrites >= 1:
            result.fallback = "failed_checks"
            break
        rewrites += 1
        result.rewritten = True
        # Not sent. Ask for a rewrite with an operator note; the bad draft isn't added to the conversation.
        messages.append({
            "role": "system",
            "content": (
                "Your last draft was not sent because it broke the dealer's rules: "
                + "; ".join(f"{k}: {' | '.join(v)[:200]}" for k, v in problems.items())
                + ". Write the reply again without that. If the customer needs a person for it, call handoff."
            ),
        })
    else:
        result.fallback = result.fallback or "too_many_steps"

    if reply is None:
        # The safe fallback: never send something unchecked. Make sure a person has it.
        if result.handoff is None:
            reason = next((_REASON_FOR_CHECK[k] for k in result.blocked if k in _REASON_FOR_CHECK), "other")
            args = {
                "reason": reason,
                "brief": f"Ondra couldn't answer safely ({result.fallback}). Please read the latest message and reply.",
                "urgency": "normal",
                "target_role": "sales",
            }
            out = await backend.handoff(**args)
            result.tools.append(ToolRecord("handoff", args, out))
            result.handoff = args
        reply = handoff_message(result.handoff["target_role"], dealer.open_now)

    result.reply = reply
    result.latency_ms = int((time.monotonic() - started) * 1000)
    return result
