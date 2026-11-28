"""Follow-ups, the parts that are plain rules: quiet hours, a step's shape, and filling in a fixed message.

A follow-up is the dealership writing first, so it is held to more than a reply is: never in quiet hours, never to
a VIP or someone who opted out, and by text or WhatsApp only with recorded consent (CLAUDE.md). The API enforces
those against the database (`services/follow_ups.py`); the time arithmetic and validation live here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Until the dealer sets their own: no follow-ups from 9 pm to 8 am, their time (the TCPA calling-hours window).
DEFAULT_QUIET = {"start": "21:00", "end": "08:00"}
MAX_STEPS = 6
MAX_AFTER_HOURS = 24 * 60


def quiet_span(quiet: dict | None) -> tuple[str, str]:
    q = quiet or {}
    return (q.get("start") or DEFAULT_QUIET["start"], q.get("end") or DEFAULT_QUIET["end"])


def in_quiet_hours(quiet: dict | None, tz: str, now: datetime) -> bool:
    start, end = quiet_span(quiet)
    clock = now.astimezone(ZoneInfo(tz)).strftime("%H:%M")
    if start == end:
        return False
    return start <= clock < end if start < end else (clock >= start or clock < end)  # the usual case spans midnight


def next_allowed(quiet: dict | None, tz: str, when: datetime) -> datetime:
    """`when`, or the end of quiet hours if it falls inside them."""
    if not in_quiet_hours(quiet, tz, when):
        return when
    _start, end = quiet_span(quiet)
    local = when.astimezone(ZoneInfo(tz))
    h, m = map(int, end.split(":"))
    candidate = local.replace(hour=h, minute=m, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(when.tzinfo)


def validate_steps(steps: list) -> str | None:
    """Why these steps can't be saved, or None."""
    if not steps:
        return "Add at least one follow-up."
    if len(steps) > MAX_STEPS:
        return f"A sequence can have up to {MAX_STEPS} follow-ups."
    for i, s in enumerate(steps, start=1):
        hours = s.get("after_hours")
        if not isinstance(hours, int) or not 1 <= hours <= MAX_AFTER_HOURS:
            return f"Follow-up {i}: choose a wait between 1 hour and 60 days."
        if s.get("write") not in ("ondra", "text"):
            return f"Follow-up {i}: choose who writes it."
        if s.get("write") == "text" and not (s.get("text") or "").strip():
            return f"Follow-up {i}: write the message, or let Ondra write it."
        if len(s.get("text") or "") > 600:
            return f"Follow-up {i}: keep the message under 600 characters."
    return None


def fill(text: str, *, first_name: str | None, dealership: str) -> str:
    """A fixed message with the customer's first name and the dealership filled in. "Hi {first_name}," with no
    name on file becomes "Hi there,"."""
    return text.replace("{first_name}", first_name or "there").replace("{dealership}", dealership).strip()


def first_name(display_name: str | None) -> str | None:
    name = (display_name or "").strip()
    return None if not name or name.startswith("+") or "@" in name else name.split()[0]
