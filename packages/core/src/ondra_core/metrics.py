"""What the dashboard's numbers mean, as plain functions over events (BUILD_PLAN.md §11.1, Step 9).

Every number on the dashboard is a count (or a median) of events in the `events` table, and nothing else. `METRICS`
says which events count toward which number; the same table drives the daily rollups, the totals and the "what's
behind this number" list, so the three can't disagree.

Events and the fields the metrics read:
    lead.captured       {deal_id, contact_id, channel, by: ai|user|owner|unknown, after_hours: bool}
    deal.stage_changed  {deal_id, from, to, by}
    response.sent       {message_id, conversation_id, channel, by: ai|user, seconds, after_hours}
    follow_up.sent      {follow_up_id, channel, step}
    appointment.booked  {appointment_id, source: ai|staff|customer_link, type}
    appointment.showed / appointment.no_show   {appointment_id}
    call.ended          {call_id, handled_by: ai|staff|owner|missed}
    message.received    {message_id, conversation_id, channel}
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median
from zoneinfo import ZoneInfo

STAGES = ("new", "qualified", "appointment", "negotiating", "won", "lost")
OPEN_STAGES = ("new", "qualified", "appointment", "negotiating")


@dataclass(frozen=True)
class Ev:
    type: str
    at: datetime  # timezone-aware
    payload: dict
    id: str = ""


def _is(type_: str, test: Callable[[dict], bool] | None = None) -> Callable[[Ev], bool]:
    return lambda e: e.type == type_ and (test is None or bool(test(e.payload)))


# metric -> (what it's called on the dashboard, which events count)
METRICS: dict[str, tuple[str, Callable[[Ev], bool]]] = {
    "leads": ("Leads captured", _is("lead.captured")),
    "leads_after_hours": ("Leads captured after hours", _is("lead.captured", lambda p: p.get("after_hours"))),
    "leads_by_ai": ("Leads captured by Ondra", _is("lead.captured", lambda p: p.get("by") == "ai")),
    "responses": ("First replies to a waiting customer", _is("response.sent")),
    "responses_by_ai": ("First replies sent by Ondra", _is("response.sent", lambda p: p.get("by") == "ai")),
    "responses_by_team": ("First replies sent by your team", _is("response.sent", lambda p: p.get("by") == "user")),
    "follow_ups_sent": ("Follow-ups sent", _is("follow_up.sent")),
    "appointments_booked": ("Appointments booked", _is("appointment.booked")),
    "appointments_booked_by_ai": ("Appointments booked by Ondra", _is("appointment.booked", lambda p: p.get("source") == "ai")),
    "appointments_showed": ("Appointments where the customer showed up", _is("appointment.showed")),
    "appointments_no_show": ("No-shows", _is("appointment.no_show")),
    "calls": ("Calls", _is("call.ended")),
    "calls_by_ai": ("Calls answered by Ondra", _is("call.ended", lambda p: p.get("handled_by") == "ai")),
    "calls_missed": ("Missed calls", _is("call.ended", lambda p: p.get("handled_by") == "missed")),
    "messages_in": ("Messages from customers", _is("message.received")),
}
EVENT_TYPES = ("lead.captured", "deal.stage_changed", "response.sent", "follow_up.sent", "appointment.booked", "appointment.showed",
               "appointment.no_show", "call.ended", "message.received")


def local_day(at: datetime, tz: str) -> date:
    """The dealership's calendar day an event belongs to (a 11 pm lead is that night's, not tomorrow's in UTC)."""
    return at.astimezone(ZoneInfo(tz)).date()


def day_summary(events: list[Ev]) -> dict:
    """One day's numbers, from that day's events. Sums of these across days give any period's totals; the reply
    times are kept whole (not averaged) so a period's median is exact."""
    out: dict = {m: sum(1 for e in events if test(e)) for m, (_label, test) in METRICS.items()}
    out["leads_by_channel"] = dict(Counter(e.payload.get("channel") or "unknown" for e in events if e.type == "lead.captured"))
    out["messages_in_by_channel"] = dict(Counter(e.payload.get("channel") or "unknown" for e in events if e.type == "message.received"))
    out["responses_by_channel"] = dict(Counter(e.payload.get("channel") or "unknown" for e in events if e.type == "response.sent"))
    out["calls_by"] = dict(Counter(e.payload.get("handled_by") or "unknown" for e in events if e.type == "call.ended"))
    out["response_seconds"] = sorted(int(e.payload["seconds"]) for e in events if e.type == "response.sent" and e.payload.get("seconds") is not None)
    by_person: dict[str, list[int]] = {}
    for e in events:
        if e.type == "response.sent" and e.payload.get("by") == "user" and e.payload.get("user_id") and e.payload.get("seconds") is not None:
            by_person.setdefault(e.payload["user_id"], []).append(int(e.payload["seconds"]))
    out["response_seconds_by_person"] = {k: sorted(v) for k, v in by_person.items()}
    out["response_seconds_ai"] = sorted(int(e.payload["seconds"]) for e in events
                                        if e.type == "response.sent" and e.payload.get("by") == "ai" and e.payload.get("seconds") is not None)
    return out


def total(days: list[dict]) -> dict:
    """A period's numbers from its days' summaries."""
    out: dict = {m: sum(d.get(m, 0) for d in days) for m in METRICS}
    for key in ("leads_by_channel", "messages_in_by_channel", "responses_by_channel", "calls_by"):
        c: Counter = Counter()
        for d in days:
            c.update(d.get(key) or {})
        out[key] = dict(c)
    people: dict[str, list[int]] = {}
    for d in days:
        for k, v in (d.get("response_seconds_by_person") or {}).items():
            people.setdefault(k, []).extend(v)
    out["response_seconds_by_person"] = people
    seconds = [s for d in days for s in d.get("response_seconds") or []]
    ai = [s for d in days for s in d.get("response_seconds_ai") or []]
    out["median_first_response_seconds"] = median(seconds) if seconds else None
    out["median_first_response_seconds_ai"] = median(ai) if ai else None
    handled_ai = out["responses_by_ai"] + out["calls_by_ai"]
    handled_team = out["responses_by_team"] + sum(v for k, v in out["calls_by"].items() if k in ("staff", "owner"))
    out["handled_by"] = {"ai": handled_ai, "team": handled_team}
    return out


def pipeline(events: list[Ev]) -> dict:
    """Where every deal stands now, from all lead and stage events in order: each deal's current stage, and who
    captured it. "Deals in play sourced by Ondra" is the open ones Ondra captured."""
    stage: dict[str, str] = {}
    by: dict[str, str] = {}
    for e in sorted(events, key=lambda e: e.at):
        deal = e.payload.get("deal_id")
        if not deal:
            continue
        if e.type == "lead.captured":
            stage.setdefault(deal, e.payload.get("stage") or "new")
            by.setdefault(deal, e.payload.get("by") or "unknown")
        elif e.type == "deal.stage_changed" and e.payload.get("to"):
            stage[deal] = e.payload["to"]
    by_stage = Counter(stage.values())
    in_play = [d for d, s in stage.items() if s in OPEN_STAGES]
    return {"by_stage": {s: by_stage.get(s, 0) for s in STAGES if by_stage.get(s, 0) or s in OPEN_STAGES},
            "in_play": len(in_play), "in_play_by_ai": sum(1 for d in in_play if by.get(d) == "ai"),
            "deal_ids_in_play_by_ai": sorted(d for d in in_play if by.get(d) == "ai")}
