"""The dashboard's numbers (BUILD_PLAN.md §11.1, Step 9). Everything is computed from `events`; what each number
means is in `ondra_core.metrics`.

    lead_captured(), response_sent(), set_stage()   record the events at the moment they happen
    rollup()        one dealership day's numbers into `metric_days` (a cache that can always be rebuilt)
    report()        a period's totals, the period before it, a daily series and the pipeline as it stands
    trace()         the events behind one number
    backfill()      events for things that happened before these events were recorded (marked as backfilled)
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from ondra_core import metrics as m
from ondra_core.models import (
    Appointment,
    Call,
    Contact,
    Conversation,
    Deal,
    Event,
    FollowUp,
    Message,
    MetricDay,
    Tenant,
    User,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_DAYS = 92
STALE = timedelta(minutes=5)  # today's rollup is recomputed if older than this


# --- recording ---------------------------------------------------------------------------------------------------

def lead_captured(db: AsyncSession, deal: Deal, *, by: str, after_hours: bool, at: datetime | None = None, **extra) -> None:
    db.add(Event(type="lead.captured", payload={"deal_id": str(deal.id), "contact_id": str(deal.contact_id), "channel": deal.source_channel,
                                                "by": by, "after_hours": after_hours, "stage": deal.stage, **extra},
                 **({"occurred_at": at} if at else {})))


async def set_stage(db: AsyncSession, deal: Deal, stage: str, *, by: str) -> bool:
    """Move a deal to a stage and record it. False if it's already there."""
    if stage not in m.STAGES:
        raise ValueError(f"Unknown stage '{stage}'.")
    if deal.stage == stage:
        return False
    db.add(Event(type="deal.stage_changed", payload={"deal_id": str(deal.id), "from": deal.stage, "to": stage, "by": by}))
    deal.stage = stage
    return True


async def response_sent(db: AsyncSession, msg: Message, conv: Conversation) -> None:
    """A message just went out. If the customer had written and nobody had answered yet, record how long they
    waited and who answered. Only a first answer counts: a second message to someone who's been answered doesn't."""
    if msg.author_type not in ("ai", "user"):
        return
    last_out = (await db.execute(select(Message.created_at).where(
        Message.conversation_id == conv.id, Message.direction == "outbound", Message.is_draft.is_(False), Message.status == "sent",
        Message.id != msg.id).order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()
    q = select(Message.created_at).where(Message.conversation_id == conv.id, Message.direction == "inbound")
    if last_out is not None:
        q = q.where(Message.created_at > last_out)
    waiting_since = (await db.execute(q.order_by(Message.created_at).limit(1))).scalar_one_or_none()
    if waiting_since is None:
        return
    from ondra_api.services.inbound import dealer_clock

    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    now = datetime.now(UTC)
    db.add(Event(type="response.sent", payload={
        "message_id": str(msg.id), "conversation_id": str(conv.id), "channel": conv.channel, "by": msg.author_type,
        "seconds": max(0, int((now - waiting_since).total_seconds())), "after_hours": not dealer_clock(tenant, waiting_since)[1],
        # Who on the team answered (an approved Ondra draft is still Ondra's reply).
        **({"user_id": str(msg.author_user_id)} if msg.author_type == "user" and msg.author_user_id else {})}))


# --- reading -----------------------------------------------------------------------------------------------------

def _tz(tenant: Tenant) -> str:
    return (tenant.timezones or ["America/Chicago"])[0]


def _bounds(day: date, tz: str) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0), ZoneInfo(tz))
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


async def _events(db: AsyncSession, start: datetime, end: datetime, types: tuple[str, ...] = m.EVENT_TYPES) -> list[m.Ev]:
    rows = (await db.execute(select(Event).where(Event.type.in_(types), Event.occurred_at >= start, Event.occurred_at < end)
                             .order_by(Event.occurred_at))).scalars()
    return [m.Ev(e.type, e.occurred_at, e.payload or {}, str(e.id)) for e in rows]


async def rollup(db: AsyncSession, day: date, tenant: Tenant) -> dict:
    """Compute one day from its events and store it."""
    events = await _events(db, *_bounds(day, _tz(tenant)))
    data = m.day_summary(events)
    row = (await db.execute(select(MetricDay).where(MetricDay.day == day))).scalar_one_or_none()
    if row is None:
        row = MetricDay(day=day)
        db.add(row)
    row.data, row.events, row.computed_at = data, len(events), datetime.now(UTC)
    await db.flush()
    return data


async def days(db: AsyncSession, start: date, end: date, tenant: Tenant, now: datetime | None = None) -> dict[date, dict]:
    """Each day's numbers from `start` to `end` inclusive. A day is computed once it's over; today (and a day that
    was computed before it ended) is recomputed when its rollup is more than a few minutes old."""
    now = now or datetime.now(UTC)
    have = {r.day: r for r in (await db.execute(select(MetricDay).where(MetricDay.day >= start, MetricDay.day <= end))).scalars()}
    out: dict[date, dict] = {}
    d = start
    while d <= end:
        row = have.get(d)
        _s, day_end = _bounds(d, _tz(tenant))
        fresh = row is not None and (row.computed_at >= day_end or now - row.computed_at < STALE)
        out[d] = row.data if fresh else await rollup(db, d, tenant)
        d += timedelta(days=1)
    return out


async def report(db: AsyncSession, period: int = 7, end: date | None = None) -> dict:
    """The dashboard: this period, the one before it (for comparison), a daily series, and the pipeline now."""
    period = max(1, min(period, MAX_DAYS // 2))
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    tz = _tz(tenant)
    end = end or datetime.now(UTC).astimezone(ZoneInfo(tz)).date()
    start = end - timedelta(days=period - 1)
    by_day = await days(db, start - timedelta(days=period), end, tenant)
    this = [by_day[start + timedelta(days=i)] for i in range(period)]
    before = [by_day[start - timedelta(days=period) + timedelta(days=i)] for i in range(period)]
    lifetime = await _events(db, datetime(2000, 1, 1, tzinfo=UTC), datetime.now(UTC) + timedelta(days=1), ("lead.captured", "deal.stage_changed"))
    names = {str(u.id): u.name for u in (await db.execute(select(User))).scalars()}
    people = []
    for uid, secs in (m.total(this).get("response_seconds_by_person") or {}).items():
        secs = sorted(secs)
        people.append({"user_id": uid, "name": names.get(uid, "Someone who has left"), "first_replies": len(secs),
                       "median_first_response_seconds": secs[len(secs) // 2] if len(secs) % 2 else (secs[len(secs) // 2 - 1] + secs[len(secs) // 2]) / 2})
    people.sort(key=lambda p: -p["first_replies"])
    callback_people = []
    for uid, secs in (m.total(this).get("callback_seconds_by_person") or {}).items():
        callback_people.append({"user_id": uid, "name": names.get(uid, "Someone who has left"), "callbacks": len(secs),
                                "median_callback_seconds": median(secs)})
    callback_people.sort(key=lambda p: -p["callbacks"])
    series = [{"day": (start + timedelta(days=i)).isoformat(), "leads": d["leads"], "responses_by_ai": d["responses_by_ai"],
               "responses_by_team": d["responses_by_team"], "appointments_booked": d["appointments_booked"]} for i, d in enumerate(this)]
    pipe = m.pipeline(lifetime)
    return {"from": start.isoformat(), "to": end.isoformat(), "days": period, "timezone": tz, "totals": m.total(this),
            "previous": m.total(before), "series": series, "pipeline": {k: v for k, v in pipe.items() if k != "deal_ids_in_play_by_ai"},
            "labels": {k: label for k, (label, _t) in m.METRICS.items()}, "people": people,
            "callback_people": callback_people}


async def trace(db: AsyncSession, metric: str, period: int = 7, end: date | None = None, limit: int = 200) -> dict:
    """The events behind one number, newest first, with who or what each was about."""
    if metric not in m.METRICS:
        raise KeyError(metric)
    period = max(1, min(period, MAX_DAYS // 2))
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    tz = _tz(tenant)
    end = end or datetime.now(UTC).astimezone(ZoneInfo(tz)).date()
    start = end - timedelta(days=period - 1)
    label, test = m.METRICS[metric]
    events = [e for e in await _events(db, _bounds(start, tz)[0], _bounds(end, tz)[1]) if test(e)]
    names: dict[str, str] = {}
    contact_ids = {e.payload.get("contact_id") for e in events if e.payload.get("contact_id")}
    conv_ids = {e.payload.get("conversation_id") for e in events if e.payload.get("conversation_id")}
    if conv_ids:
        for cid, contact in (await db.execute(select(Conversation.id, Conversation.contact_id).where(Conversation.id.in_([uuid.UUID(c) for c in conv_ids])))).all():
            names[str(cid)] = str(contact)
            contact_ids.add(str(contact))
    if contact_ids:
        for c in (await db.execute(select(Contact).where(Contact.id.in_([uuid.UUID(c) for c in contact_ids])))).scalars():
            names[str(c.id)] = c.display_name
    people = {str(u.id): u.name for u in (await db.execute(select(User))).scalars()} if metric == "callbacks" else {}
    items = []
    for e in reversed(events[-limit:]):
        contact = e.payload.get("contact_id") or names.get(e.payload.get("conversation_id") or "")
        items.append({"event_id": e.id, "type": e.type, "at": e.at.isoformat(), "who": names.get(contact or ""),
                      "detail": {k: v for k, v in e.payload.items() if k in ("channel", "by", "seconds", "after_hours", "source", "type", "handled_by", "step", "result", "rings")},
                      "backfilled": bool(e.payload.get("backfilled"))})
        if people:  # a call-back is by a person: name them, not their id
            items[-1]["detail"]["by"] = people.get(e.payload.get("by") or "", "Someone who has left")
    return {"metric": metric, "label": label, "count": len(events), "from": start.isoformat(), "to": end.isoformat(), "events": items}


# --- events for what happened before they were recorded ----------------------------------------------------------

async def backfill(db: AsyncSession) -> dict:
    """Write the missing events for existing deals, replies, appointments, follow-ups and calls, dated when they
    happened and marked `backfilled`. Safe to run again: nothing is written twice. Who captured an old lead isn't
    known, so those say `by: unknown` and don't count toward Ondra's or the team's."""
    from ondra_api.services.inbound import dealer_clock

    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    made = {"lead.captured": 0, "response.sent": 0, "appointment.booked": 0, "appointment.showed": 0, "appointment.no_show": 0,
            "follow_up.sent": 0, "call.ended": 0}

    async def seen(type_: str, key: str) -> set[str]:
        return set((await db.execute(text("SELECT payload->>:k FROM events WHERE type = :t"), {"k": key, "t": type_})).scalars())

    have = await seen("lead.captured", "deal_id")
    for d in (await db.execute(select(Deal).where(Deal.type == "sales"))).scalars():
        if str(d.id) not in have:
            lead_captured(db, d, by="unknown", after_hours=not dealer_clock(tenant, d.created_at)[1], at=d.created_at, backfilled=True)
            if d.stage != "new":
                db.add(Event(type="deal.stage_changed", occurred_at=d.updated_at, payload={"deal_id": str(d.id), "from": "new", "to": d.stage, "by": "unknown", "backfilled": True}))
            made["lead.captured"] += 1

    have = await seen("response.sent", "message_id")
    convs = (await db.execute(select(Conversation))).scalars().all()
    for conv in convs:
        waiting = None
        for msg in (await db.execute(select(Message).where(Message.conversation_id == conv.id, Message.is_draft.is_(False)).order_by(Message.created_at))).scalars():
            if msg.direction == "inbound":
                waiting = waiting or msg.created_at
            elif msg.status == "sent" and msg.author_type in ("ai", "user"):
                if waiting is not None and str(msg.id) not in have:
                    db.add(Event(type="response.sent", occurred_at=msg.created_at, payload={
                        "message_id": str(msg.id), "conversation_id": str(conv.id), "channel": conv.channel, "by": msg.author_type,
                        "seconds": max(0, int((msg.created_at - waiting).total_seconds())), "after_hours": not dealer_clock(tenant, waiting)[1], "backfilled": True}))
                    made["response.sent"] += 1
                waiting = None

    booked = await seen("appointment.booked", "appointment_id")
    showed, missed = await seen("appointment.showed", "appointment_id"), await seen("appointment.no_show", "appointment_id")
    for a in (await db.execute(select(Appointment))).scalars():
        if str(a.id) not in booked:
            db.add(Event(type="appointment.booked", occurred_at=a.created_at, payload={"appointment_id": str(a.id), "source": a.source, "backfilled": True}))
            made["appointment.booked"] += 1
        if a.status == "showed" and str(a.id) not in showed:
            db.add(Event(type="appointment.showed", occurred_at=a.starts_at, payload={"appointment_id": str(a.id), "backfilled": True}))
            made["appointment.showed"] += 1
        if a.status == "no_show" and str(a.id) not in missed:
            db.add(Event(type="appointment.no_show", occurred_at=a.starts_at, payload={"appointment_id": str(a.id), "backfilled": True}))
            made["appointment.no_show"] += 1

    have = await seen("follow_up.sent", "follow_up_id")
    for f, channel in (await db.execute(select(FollowUp, Conversation.channel).join(Conversation, Conversation.id == FollowUp.conversation_id)
                                        .where(FollowUp.status == "sent"))).all():
        if str(f.id) not in have:
            db.add(Event(type="follow_up.sent", occurred_at=f.sent_at or f.updated_at, payload={"follow_up_id": str(f.id), "channel": channel, "step": f.step, "backfilled": True}))
            made["follow_up.sent"] += 1

    have = await seen("call.ended", "call_id")
    for c in (await db.execute(select(Call).where(Call.handled_by.isnot(None)))).scalars():
        if str(c.id) not in have:
            db.add(Event(type="call.ended", occurred_at=c.ended_at or c.started_at or c.created_at,
                         payload={"call_id": str(c.id), "handled_by": c.handled_by, "contact_id": str(c.contact_id) if c.contact_id else None, "backfilled": True}))
            made["call.ended"] += 1
    await db.flush()
    await db.execute(text("DELETE FROM metric_days"))  # the cache is rebuilt from the events on the next read
    return made


async def overnight(db: AsyncSession, now: datetime | None = None) -> dict | None:
    """What happened while the dealership was last closed: from the last closing time to the opening after it (or
    to now, if it hasn't opened yet). None if no opening hours are set."""
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    hours = tenant.business_hours or {}
    if not hours:
        return None
    tz = ZoneInfo(_tz(tenant))
    local = (now or datetime.now(UTC)).astimezone(tz)
    days_ = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

    def span(d: date) -> tuple[datetime, datetime] | None:
        h = hours.get(days_[d.weekday()])
        if not h:
            return None
        (oh, om), (ch, cm) = (map(int, h[0].split(":")), map(int, h[1].split(":")))
        return datetime.combine(d, time(oh, om), tz), datetime.combine(d, time(ch, cm), tz)

    # The most recent closing time at or before now, then the first opening after it.
    closed_at = None
    for back in range(8):
        sp = span(local.date() - timedelta(days=back))
        if sp and sp[1] <= local:
            closed_at = sp[1]
            break
    if closed_at is None:
        return None
    opened_at = None
    for ahead in range(8):
        sp = span(closed_at.date() + timedelta(days=ahead))
        if sp and sp[0] > closed_at:
            opened_at = sp[0]
            break
    until = min(opened_at, local) if opened_at else local
    events = await _events(db, closed_at.astimezone(UTC), until.astimezone(UTC))
    t = m.total([m.day_summary(events)])
    return {"from": closed_at.isoformat(), "to": until.isoformat(), "leads": t["leads"], "responses_by_ai": t["responses_by_ai"],
            "responses_by_team": t["responses_by_team"], "appointments_booked": t["appointments_booked"],
            "appointments_booked_by_ai": t["appointments_booked_by_ai"], "median_first_response_seconds": t["median_first_response_seconds"],
            "calls_by_ai": t["calls_by_ai"], "calls_missed": t["calls_missed"]}
