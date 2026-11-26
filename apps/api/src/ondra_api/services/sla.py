"""Response-time targets for tasks. The clock only runs while the dealership is open: a high-urgency lead that
arrives at 11 pm is due 15 minutes after opening, not at 11:15 pm."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ondra_core.models import Tenant

# Counted in open hours: "low" is about one working day (8 open hours), not 24 open hours (2 to 3 days).
SLA = {"high": timedelta(minutes=15), "normal": timedelta(hours=2), "low": timedelta(hours=8)}
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _spans(tenant: Tenant, day: datetime) -> tuple[datetime, datetime] | None:
    hours = (tenant.business_hours or {}).get(_DAYS[day.weekday()])
    if not hours:
        return None
    (oh, om), (ch, cm) = (map(int, hours[0].split(":")), map(int, hours[1].split(":")))
    return day.replace(hour=oh, minute=om, second=0, microsecond=0), day.replace(hour=ch, minute=cm, second=0, microsecond=0)


def add_business_time(tenant: Tenant, start: datetime, duration: timedelta) -> datetime:
    """`start` plus `duration` of open time. With no opening hours set, plain clock time."""
    if not tenant.business_hours:
        return start + duration
    tz = ZoneInfo((tenant.timezones or ["America/Chicago"])[0])
    t = start.astimezone(tz)
    left = duration
    for _ in range(60):  # at most two months of days
        span = _spans(tenant, t)
        if span:
            open_, close = span
            t = max(t, open_)
            if t < close:
                if t + left <= close:
                    return (t + left).astimezone(UTC)
                left -= close - t
        t = (t + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (start + duration).astimezone(UTC)


def due_for(tenant: Tenant, urgency: str, now: datetime | None = None) -> datetime:
    return add_business_time(tenant, now or datetime.now(UTC), SLA.get(urgency, SLA["normal"]))
