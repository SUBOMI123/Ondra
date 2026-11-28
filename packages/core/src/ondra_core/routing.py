"""The routing engine's rules, as plain functions (BUILD_PLAN.md §7). No database here: the API loads the dealer's
rules and people and asks these functions who gets the work.

Order of decisions, every time a message, call or AI handoff needs a person:

1. VIP: always the owner or the VIP's handler. Not a rule a dealer can edit or reorder (CLAUDE.md product rule);
   the caller handles it before any rule is read.
2. The dealer's rules, lowest priority number first. The first active rule whose conditions all match decides the
   role or person, and may set how the AI behaves (reply, draft only, or stay out).
3. No rule matches: the topic's usual role (`DEFAULT_ROLE`).
4. Within the role: someone on shift and under their limit, whoever was given work least recently (round-robin).
   Nobody on shift: the person whose shift starts soonest, and the customer is told it will be when they're in.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

TOPICS = ("sales", "service", "shipping", "finance", "complaint", "other")
DEFAULT_ROLE = {"sales": "sales", "service": "service", "shipping": "sales", "finance": "sales",
                "complaint": "manager", "other": "sales"}
# If nobody holds the role, who is asked next.
FALLBACK = {"sales": ("manager", "admin"), "service": ("manager", "admin"), "ops": ("manager", "admin"),
            "manager": ("admin",), "admin": ()}
AI_MODES = ("auto", "draft", "off")
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


# --- rules -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Facts:
    """What a rule can look at."""

    topic: str
    channel: str  # sms | whatsapp | email | phone
    open_now: bool  # is the dealership open
    language: str | None = None  # the customer's language, e.g. "es"
    deal_type: str | None = None  # sales | service, when the customer has an open deal


@dataclass(frozen=True)
class Rule:
    id: uuid.UUID | None
    priority: int
    conditions: dict  # {"topic": [...], "channel": [...], "hours": "open"|"closed", "language": [...], "deal_type": [...]}
    action: dict  # {"assign_role": str} or {"assign_user_id": str}; optional "ai": auto|draft|off, "alert": bool
    active: bool = True
    name: str = ""


def _one_of(wanted, value) -> bool:
    if wanted in (None, "", [], "any"):
        return True
    wanted = wanted if isinstance(wanted, list) else [wanted]
    return value is not None and str(value).lower() in {str(w).lower() for w in wanted}


def matches(conditions: dict, f: Facts) -> bool:
    """Every condition the rule sets must hold. A rule with no conditions matches everything."""
    hours = conditions.get("hours")
    if hours in ("open", "closed") and (hours == "open") != f.open_now:
        return False
    return (_one_of(conditions.get("topic"), f.topic) and _one_of(conditions.get("channel"), f.channel)
            and _one_of(conditions.get("language"), (f.language or "")[:2] or None)
            and _one_of(conditions.get("deal_type"), f.deal_type))


def first_match(rules: list[Rule], f: Facts) -> Rule | None:
    for r in sorted((r for r in rules if r.active), key=lambda r: r.priority):
        if matches(r.conditions, f):
            return r
    return None


def validate(conditions: dict, action: dict) -> str | None:
    """Why a rule can't be saved, or None. The settings form builds these, but the API checks too."""
    for key in conditions:
        if key not in ("topic", "channel", "hours", "language", "deal_type"):
            return f"Unknown condition '{key}'."
    for t in conditions.get("topic") or []:
        if t not in TOPICS:
            return f"Unknown topic '{t}'."
    for c in conditions.get("channel") or []:
        if c not in ("sms", "whatsapp", "email", "phone"):
            return f"Unknown channel '{c}'."
    if conditions.get("hours") not in (None, "", "any", "open", "closed"):
        return "Hours must be open, closed or any."
    if bool(action.get("assign_role")) == bool(action.get("assign_user_id")):
        return "Choose a team or a person to send it to (one, not both)."
    if action.get("assign_role") and action["assign_role"] not in FALLBACK:
        return f"Unknown team '{action['assign_role']}'."
    if action.get("ai") not in (None, *AI_MODES):
        return "Ondra can reply, draft only, or stay out."
    return None


# --- topics ------------------------------------------------------------------------------------------------------

_TOPIC_WORDS = {
    "complaint": (r"\b(complain\w*|unacceptable|ridiculous|terrible|worst|rip(?:ped)? ?off|scam|lawyer|sue|refund|"
                  r"furious|angry|disgusted|never coming back|bbb|manager now|speak to (?:a|the|your) manager)\b"),
    "shipping": (r"\b(ship\w*|deliver\w*|export\w*|freight|container|port|customs|overseas|lagos|nigeria|"
                 r"transport(?:ed|ing)? (?:it|the car) to)\b"),
    "finance": (r"\b(financ\w*|loan|apr|interest rate|credit (?:score|check|app\w*)|monthly payments?|down payment|"
                r"lease|pre-?approv\w*)\b"),
    "service": (r"\b(oil change|service|repair\w*|brakes?|tires?|tyres?|check engine|engine light|recall|maintenance|"
                r"inspection|alignment|battery|warranty work|loaner|parts?|noise|leak\w*|won'?t start)\b"),
    "sales": (r"\b(buy\w*|purchase|price|how much|in stock|available|test drive|trade[- ]?in|for sale|looking for|"
              r"interested in|inventory|suv|sedan|truck|new car|used car|mileage|stock (?:number|#))\b"),
}
# Checked in this order: an angry message about a repair is a complaint first.
_TOPIC_RE = [(t, re.compile(p, re.IGNORECASE)) for t, p in _TOPIC_WORDS.items()]


def topic_from_words(text: str) -> str:
    """A free, instant guess from the words used. The model's classification is preferred when there is one; this
    is the fallback (no key, the model is down, or it answered with something that isn't a topic)."""
    for topic, pattern in _TOPIC_RE:
        if pattern.search(text or ""):
            return topic
    return "other"


_REASON_TOPIC = {"pricing": "sales", "discount": "sales", "trade_in": "sales", "vehicle_request": "sales",
                 "financing": "finance", "delivery_date": "shipping", "shipping": "shipping", "complaint": "complaint"}
_ROLE_TOPIC = {"sales": "sales", "service": "service", "manager": "complaint"}


def topic_for_handoff(reason: str, target_role: str, conversation_topic: str | None) -> str:
    """The topic of an AI handoff: its reason when that says it (a complaint is a complaint whatever the thread was
    about), else what the conversation has been about, else the team the AI asked for."""
    if reason in _REASON_TOPIC:
        if reason in ("delivery_date",) and conversation_topic == "service":
            return "service"  # "when will my car be ready" in a service thread
        return _REASON_TOPIC[reason]
    if conversation_topic in TOPICS and conversation_topic != "other":
        return conversation_topic
    return _ROLE_TOPIC.get(target_role, "other")


# --- people ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Person:
    id: uuid.UUID
    role: str
    timezone: str  # theirs, else the dealership's
    work_hours: dict  # {"mon": ["09:00", "18:00"], ...}; theirs, else the dealership's. Empty: always on.
    open_tasks: int = 0
    max_open_tasks: int | None = None
    last_assigned_at: datetime | None = None
    joined_at: datetime | None = None


def shift(work_hours: dict, tz: str, now: datetime) -> tuple[bool, datetime | None]:
    """(on shift now, when their next shift starts). With no hours set they're always on. Hours are in the
    person's own timezone, so Lagos staff can cover a Dallas dealership's night."""
    if not work_hours:
        return True, None
    local = now.astimezone(ZoneInfo(tz))
    for ahead in range(8):
        day = local + timedelta(days=ahead)
        span = work_hours.get(_DAYS[day.weekday()])
        if not span:
            continue
        (oh, om), (ch, cm) = (map(int, span[0].split(":")), map(int, span[1].split(":")))
        start = day.replace(hour=oh, minute=om, second=0, microsecond=0)
        end = day.replace(hour=ch, minute=cm, second=0, microsecond=0)
        if ahead == 0 and start <= local < end:
            return True, None
        if start > local:
            return False, start.astimezone(UTC)
    return False, None


@dataclass(frozen=True)
class Pick:
    user_id: uuid.UUID | None
    role: str | None  # the role that actually took it (after fallback)
    on_shift: bool
    available_at: datetime | None = None  # when they're next in, if not on shift
    why: str = ""  # round_robin | named | next_shift | at_capacity | fallback | nobody


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _turn_order(p: Person) -> tuple:
    return (p.last_assigned_at or _EPOCH, p.joined_at or _EPOCH, str(p.id))


def pick(people: list[Person], role: str, now: datetime, *, named: uuid.UUID | None = None,
         prefer: uuid.UUID | None = None) -> Pick:
    """Who gets it. `named` is a person a rule names: theirs whatever their shift. `prefer` is the person already
    looking after this customer: theirs if they hold the role and are on shift, so a customer keeps one contact."""
    by_id = {p.id: p for p in people}
    if named and named in by_id:
        on, start = shift(by_id[named].work_hours, by_id[named].timezone, now)
        return Pick(named, by_id[named].role, on, start, "named")
    for i, r in enumerate((role, *FALLBACK.get(role, ("manager", "admin")))):
        team = [p for p in people if p.role == r]
        if not team:
            continue
        shifts = {p.id: shift(p.work_hours, p.timezone, now) for p in team}
        on = [p for p in team if shifts[p.id][0]]
        free = [p for p in on if p.max_open_tasks is None or p.open_tasks < p.max_open_tasks]
        why = "round_robin" if i == 0 else "fallback"
        if prefer and any(p.id == prefer for p in free):
            return Pick(prefer, r, True, None, "their_contact")
        if free:
            return Pick(min(free, key=_turn_order).id, r, True, None, why)
        if on:  # everyone on shift is at their limit: the least loaded takes it rather than nobody
            return Pick(min(on, key=lambda p: (p.open_tasks, *_turn_order(p))).id, r, True, None, "at_capacity")
        # Nobody in this team is in. Queue it for whoever is in next.
        nxt = min(team, key=lambda p: (shifts[p.id][1] or datetime.max.replace(tzinfo=UTC), *_turn_order(p)))
        return Pick(nxt.id, r, False, shifts[nxt.id][1], "next_shift")
    return Pick(None, None, False, None, "nobody")
