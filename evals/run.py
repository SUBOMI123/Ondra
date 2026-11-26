"""Run the golden conversations against the real agent (BUILD_PLAN.md §9).

    uv run python evals/run.py                 # every scenario Step 2 can run
    uv run python evals/run.py --only 003      # scenarios whose id starts with 003
    uv run python evals/run.py --repeat 3      # each scenario 3 times (models vary; look at the pass rate)

Each turn goes through the same code as production: the pre-policy (VIP, consent, draft mode), the orchestrator with
the real model and the shared tools (backed here by the scenario's fixtures instead of Postgres), and the reply
checks. Then the turn's `expect` block is checked.

Needs ANTHROPIC_API_KEY for any turn that reaches the model. Without it, turns the policy layer handles on its own
(VIP, opted out, STOP) still run, and every other turn is reported as NOT RUN, never as a pass. Results are written
to evals/results/ (gitignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from ondra_core.agent.detectors import BLOCKING_CHECKS, POSITIVE_CHECKS, ReplyContext
from ondra_core.agent.llm import LLM, AnthropicLLM
from ondra_core.agent.orchestrator import Turn, run_turn
from ondra_core.agent.policy import InboundFacts, evaluate_inbound
from ondra_core.agent.prompt import CustomerFacts, DealerFacts
from ondra_core.agent.tools import apply_price_policy, handoff_message
from ondra_core.embeddings import MIN_SIMILARITY, VoyageEmbedder, cosine

ROOT = Path(__file__).parent
GOLDEN = ROOT / "golden"
RESULTS = ROOT / "results"
STEP = 2
LATENCY_BUDGET_MS = 5000


# --- fixtures-backed tools ---------------------------------------------------------------------------------------

_STOP = {"the", "a", "an", "is", "are", "do", "does", "you", "u", "r", "your", "we", "i", "to", "of", "on", "in", "it",
         "for", "and", "or", "what", "when", "how", "can", "guys", "any", "have", "my", "me", "be", "at", "this"}


def _words(s: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) > 1}


class FixtureBackend:
    def __init__(self, scenario: dict) -> None:
        self.s = scenario
        ctx = scenario.get("context") or {}
        self.inventory: list[dict] = ctx.get("inventory", [])
        self.knowledge: list[dict] = ctx.get("knowledge", [])
        self.price_disclosure = scenario["dealer"]["policy"].get("price_disclosure", "listed")
        self.fields: dict = {}
        self.handoffs: list[dict] = []

    async def get_contact_context(self) -> dict:
        c = self.s["contact"]
        return {"name": c.get("name"), "language": c.get("language"), "vehicles_on_file": c.get("vehicles_on_file", []),
                "open_deals": [], "upcoming_appointments": []}

    async def search_inventory(self, query=None, make=None, model=None, max_price=None, min_year=None, min_seats=None):
        out = []
        for v in self.inventory:
            hay = " ".join(str(v.get(k, "")) for k in ("make", "model", "trim", "color", "stock")).lower()
            if make and make.lower() not in v["make"].lower():
                continue
            if model and model.lower() not in v["model"].lower():
                continue
            if max_price and v.get("price", 0) > max_price:
                continue
            if min_year and v["year"] < min_year:
                continue
            if min_seats and v.get("seats", 99) < min_seats:
                continue
            if query and not all(w in hay for w in query.lower().split()):
                continue
            out.append(apply_price_policy(v, self.price_disclosure))
        return out[:5]

    async def get_vehicle(self, stock_or_vin: str):
        for v in self.inventory:
            if stock_or_vin.lower() in (str(v.get("stock", "")).lower(), str(v.get("vin", "")).lower()):
                return apply_price_policy(v, self.price_disclosure)
        return None

    async def search_knowledge(self, query: str) -> list[dict]:
        # Same semantic search as production when a Voyage key is set; word overlap otherwise.
        if os.environ.get("VOYAGE_API_KEY") and self.knowledge:
            emb = VoyageEmbedder(os.environ["VOYAGE_API_KEY"])
            try:
                if not hasattr(self, "_doc_vectors"):
                    self._doc_vectors = await emb.embed([k["q"] + "\n" + k["a"] for k in self.knowledge], "document")
                [qv] = await emb.embed([query], "query")
            except Exception:  # noqa: BLE001  same fallback as production (rate limits, outages)
                return self._keyword_search(query)
            scored = sorted(((cosine(qv, d), k) for d, k in zip(self._doc_vectors, self.knowledge)), key=lambda x: -x[0])
            return [{"title": k["q"], "answer": k["a"]} for sim, k in scored[:3] if sim >= MIN_SIMILARITY["voyage-4"]]
        return self._keyword_search(query)

    def _keyword_search(self, query: str) -> list[dict]:
        q = _words(query)
        hits = [(len(q & _words(k["q"] + " " + k["a"])), k) for k in self.knowledge]
        return [{"title": k["q"], "answer": k["a"]} for n, k in sorted(hits, key=lambda x: -x[0]) if n > 0][:3]

    async def update_lead_fields(self, fields: dict) -> dict:
        self.fields.update({k: v for k, v in fields.items() if v not in (None, "")})
        return {"saved": sorted(fields)}

    async def handoff(self, reason, brief, urgency, target_role) -> dict:
        self.handoffs.append({"reason": reason, "brief": brief, "urgency": urgency, "target_role": target_role})
        return {"task_id": f"task-{len(self.handoffs)}",
                "tell_customer": handoff_message(target_role, self.s["dealer"].get("open_now", False))}


# --- checking ----------------------------------------------------------------------------------------------------

_SPANISH = {"el", "la", "los", "las", "que", "de", "está", "esta", "tenemos", "hola", "gracias", "precio", "puede",
            "quiere", "usted", "para", "con", "una", "un", "sí", "si", "verla", "verlo", "prueba"}


def _language(text: str) -> str:
    words = re.findall(r"[a-záéíóúñ]+", text.lower())
    return "es" if words and sum(w in _SPANISH for w in words) / len(words) > 0.12 else "en"


def _norm(v: Any) -> str:
    s = str(v).lower().replace("3rd", "third").replace("-", " ")
    return re.sub(r"[^a-z0-9 ]", "", s)


def field_matches(expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    if isinstance(expected, (int, float)):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    if str(expected).startswith("+"):
        return re.sub(r"\D", "", str(actual)).endswith(re.sub(r"\D", "", str(expected))[-10:])
    exp, act = _norm(expected).split(), _norm(actual)
    return all(w in act for w in exp if w not in ("am", "pm"))  # "after 5" and "after 5 pm" mean the same


@dataclass
class TurnReport:
    index: int
    status: str  # pass | fail | not_run
    failures: list[str] = field(default_factory=list)
    reply: str = ""
    tools: list[str] = field(default_factory=list)
    latency_ms: int | None = None
    blocked_first_draft: list[str] = field(default_factory=list)


@dataclass
class ScenarioReport:
    id: str
    status: str
    turns: list[TurnReport]


def _check_policy_turn(expect: dict, decision) -> list[str]:
    f = []
    if expect.get("reply", True):
        f.append(f"expected a reply but the policy layer stopped the AI ({decision.reason})")
    if (a := expect.get("alert")) and (decision.alert is None or decision.alert.to != a["to"]
                                       or decision.alert.urgency != a["urgency"]):
        f.append(f"alert {a} expected, got {decision.alert}")
    if (c := expect.get("consent")) and decision.consent_change != c:
        f.append(f"consent {c} expected, got {decision.consent_change}")
    return f


def _check_ai_turn(expect: dict, result, backend: FixtureBackend, ctx: ReplyContext, decision,
                   handoffs_before: int) -> list[str]:
    f = []
    if expect.get("ai_invoked") is False:
        f.append(f"AI must not run here, but the policy allowed it ({decision.reason})")
    if expect.get("reply") is False:
        f.append("expected no reply")
    if "draft" in expect and decision.draft != expect["draft"]:
        f.append(f"draft={expect['draft']} expected, got {decision.draft}")
    called = set(result.tools_called)
    for t in expect.get("tools_called", []):
        if t not in called:
            f.append(f"tool {t} not called")
    for t in expect.get("tools_not_called", []):
        if t in called:
            f.append(f"tool {t} called but must not be")
    for k, v in (expect.get("fields") or {}).items():
        if not field_matches(v, backend.fields.get(k)):
            f.append(f"field {k}: expected {v!r}, got {backend.fields.get(k)!r}")
    new_handoffs = backend.handoffs[handoffs_before:]
    h = expect.get("handoff")
    if h == "none" and new_handoffs:
        f.append(f"unexpected handoff {new_handoffs[-1]['reason']}")
    elif isinstance(h, dict):
        if not new_handoffs:
            f.append(f"expected handoff to {h['target_role']}")
        else:
            got = new_handoffs[-1]
            for k in ("target_role", "urgency"):
                if k in h and got[k] != h[k]:
                    f.append(f"handoff {k}: expected {h[k]}, got {got[k]}")
    if (lang := expect.get("reply_language")) and _language(result.reply) != lang:
        f.append(f"reply language: expected {lang}")
    for name in expect.get("must", []):
        fn = POSITIVE_CHECKS.get(name)
        if fn is None:
            f.append(f"check {name} needs a tool from a later step")
        elif not fn(result.reply, ctx):
            f.append(f"must {name}")
    for name in expect.get("must_not", []):
        fn = BLOCKING_CHECKS.get(name)
        if fn and fn(result.reply, ctx):
            f.append(f"must_not {name}")
    if result.fallback:
        f.append(f"safe fallback used ({result.fallback})")
    return f


async def run_scenario(s: dict, llm: LLM | None) -> ScenarioReport:
    backend = FixtureBackend(s)
    policy = s["dealer"]["policy"]
    c = s["contact"]
    opted_out = bool(c.get("opted_out"))
    dealer = DealerFacts(name="Prestige Motors", local_time=s["dealer"]["local_time"], open_now=s["dealer"]["open_now"],
                         price_disclosure=policy.get("price_disclosure", "listed"))
    customer = CustomerFacts(known=c.get("known", False), name=c.get("name"), language=c.get("language"))
    known_makes = {v["make"] for v in c.get("vehicles_on_file", []) if v.get("make")}
    history: list[Turn] = []
    reports: list[TurnReport] = []

    for i, t in enumerate(s["turns"]):
        msgs = t["customer"] if isinstance(t["customer"], list) else [t["customer"]]
        expect = t["expect"]
        history += [Turn("customer", m) for m in msgs]
        decision = evaluate_inbound(InboundFacts(
            channel=s["channel"], body=msgs[-1], contact_is_vip=bool(c.get("vip")), contact_opted_out=opted_out,
            conversation_ai_mode="auto", tenant_draft_mode=bool(policy.get("draft_mode")),
        ))
        if decision.consent_change == "opted_out_all_channels":
            opted_out = True
        elif decision.consent_change == "opted_in":
            opted_out = False

        if not decision.run_ai:
            f = _check_policy_turn(expect, decision)
            reports.append(TurnReport(i, "fail" if f else "pass", f))
            continue
        if llm is None:
            reports.append(TurnReport(i, "not_run", ["no ANTHROPIC_API_KEY"]))
            break  # later turns depend on this reply

        handoffs_before = len(backend.handoffs)
        started = time.monotonic()
        result = await run_turn(llm=llm, backend=backend, dealer=dealer, customer=customer, channel=s["channel"],
                                history=history, known_makes=known_makes)
        latency = int((time.monotonic() - started) * 1000)
        ctx = ReplyContext(price_disclosure=dealer.price_disclosure, known_makes=set(known_makes),
                           customer_text="\n".join(x.text for x in history if x.role == "customer"))
        for rec in result.tools:  # what the tools returned this turn is what's real
            for v in rec.output if isinstance(rec.output, list) else [rec.output]:
                if isinstance(v, dict):
                    if isinstance(v.get("price"), (int, float)):
                        ctx.listed_prices.add(int(v["price"]))
                    if v.get("make"):
                        ctx.known_makes.add(v["make"])
        f = _check_ai_turn(expect, result, backend, ctx, decision, handoffs_before)
        reports.append(TurnReport(i, "fail" if f else "pass", f, result.reply, result.tools_called, latency,
                                  sorted(result.blocked)))
        history.append(Turn("assistant", result.reply))

    statuses = {r.status for r in reports}
    status = "fail" if "fail" in statuses else "not_run" if "not_run" in statuses else "pass"
    return ScenarioReport(s["id"], status, reports)


def load(only: str | None = None) -> tuple[list[dict], list[dict]]:
    runnable, later = [], []
    for f in sorted(GOLDEN.glob("*.yaml")):
        s = yaml.safe_load(f.read_text())
        if only and not s["id"].startswith(only):
            continue
        (later if s.get("requires_step", STEP) > STEP else runnable).append(s)
    return runnable, later


def make_llm() -> LLM | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return AnthropicLLM(api_key=key, model=os.environ.get("MODEL_CONVERSATION") or "claude-sonnet-5-5",
                        effort=os.environ.get("AGENT_EFFORT") or "low",
                        base_url=os.environ.get("ANTHROPIC_API_BASE") or "https://api.anthropic.com")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()
    runnable, later = load(args.only)
    llm = make_llm()
    if llm is None:
        print("ANTHROPIC_API_KEY is not set: only the turns the policy layer handles alone will run.\n")

    reports: list[ScenarioReport] = []
    for s in runnable:
        for _ in range(args.repeat):
            r = await run_scenario(s, llm)
            reports.append(r)
            mark = {"pass": "PASS", "fail": "FAIL", "not_run": "NOT RUN"}[r.status]
            print(f"{mark:8} {r.id}")
            for t in r.turns:
                for fl in t.failures:
                    if t.status != "not_run":
                        print(f"           turn {t.index + 1}: {fl}")
                if t.status == "fail" and t.reply:
                    print(f"           reply: {t.reply!r}")
    for s in later:
        print(f"{'LATER':8} {s['id']} (needs Step {s['requires_step']} tools)")

    counts = {k: sum(r.status == k for r in reports) for k in ("pass", "fail", "not_run")}
    lat = [t.latency_ms for r in reports for t in r.turns if t.latency_ms is not None]
    print(f"\n{counts['pass']} passed, {counts['fail']} failed, {counts['not_run']} not run, {len(later)} for later steps")
    if lat:
        print(f"model turn latency: median {statistics.median(lat)} ms, max {max(lat)} ms, "
              f"over {LATENCY_BUDGET_MS} ms: {sum(x > LATENCY_BUDGET_MS for x in lat)}")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({
        "model": getattr(llm, "model", None), "counts": counts,
        "scenarios": [{"id": r.id, "status": r.status, "turns": [t.__dict__ for t in r.turns]} for r in reports],
    }, indent=2))
    print(f"results: {out.relative_to(ROOT.parent)}")
    return 0 if counts["fail"] == 0 and counts["not_run"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
