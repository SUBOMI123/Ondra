"""The dashboard's numbers against a fixture worked out by hand (Step 9 acceptance).

The fixture: three days at a Dallas dealership (America/Chicago, UTC-6 in November).

Mon 23 Nov
  09:05  Lead A captured by Ondra on WhatsApp, in hours.      Ondra's first reply took 20 s.
  14:00  A text from a customer; the team replied after 600 s.
  23:30  Lead B captured by Ondra by text, AFTER HOURS.        Ondra's first reply took 40 s.   (05:30 UTC on the 24th: still Monday's)
Tue 24 Nov
  10:00  Lead C captured by a salesperson, by email.           The team replied after 1,800 s.
  11:00  Ondra booked a test drive (for lead A). Deal A -> appointment.
  12:00  Staff booked a service appointment.
  15:00  A call answered by Ondra; a call that was missed.
  16:00  A follow-up sent.
Wed 25 Nov
  09:00  The test drive: the customer showed. Deal A -> negotiating.
  10:00  The service appointment: no-show.
  11:00  Deal B -> lost.
  13:00  A call taken by staff.  A WhatsApp message; Ondra replied in 30 s.

By hand, for the three days:
  leads 3 (2 by Ondra, 1 after hours); by channel whatsapp 1, sms 1, email 1
  first replies 5: Ondra 3 (20, 40 and 30 s), team 2 (600 and 1,800 s)
  median first reply: sorted 20, 30, 40, 600, 1800 -> 40 s; Ondra's own: 20, 30, 40 -> 30 s
  appointments booked 2 (1 by Ondra), showed 1, no-show 1; follow-ups 1
  calls 3: Ondra 1, staff 1, missed 1
  handled: Ondra 3 replies + 1 call = 4; team 2 replies + 1 call = 3
  pipeline now: A negotiating, B lost, C new -> in play 2 (A, C), of which Ondra's 1 (A)
"""

from datetime import UTC, date, datetime

from ondra_core.metrics import METRICS, Ev, day_summary, local_day, pipeline, total

TZ = "America/Chicago"


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A wall-clock time in Dallas that week, as UTC (Chicago is UTC-6)."""
    h = hour + 6
    return datetime(2026, 11, day + h // 24, h % 24, minute, tzinfo=UTC)


FIXTURE = [
    Ev("lead.captured", at(23, 9, 5), {"deal_id": "A", "channel": "whatsapp", "by": "ai", "after_hours": False}),
    Ev("message.received", at(23, 9, 4), {"channel": "whatsapp"}),
    Ev("response.sent", at(23, 9, 5), {"channel": "whatsapp", "by": "ai", "seconds": 20}),
    Ev("message.received", at(23, 14), {"channel": "sms"}),
    Ev("response.sent", at(23, 14, 10), {"channel": "sms", "by": "user", "seconds": 600, "user_id": "dan"}),
    Ev("message.received", at(23, 23, 29), {"channel": "sms"}),
    Ev("lead.captured", at(23, 23, 30), {"deal_id": "B", "channel": "sms", "by": "ai", "after_hours": True}),
    Ev("response.sent", at(23, 23, 30), {"channel": "sms", "by": "ai", "seconds": 40}),
    Ev("message.received", at(24, 9, 30), {"channel": "email"}),
    Ev("lead.captured", at(24, 10), {"deal_id": "C", "channel": "email", "by": "user", "after_hours": False}),
    Ev("response.sent", at(24, 10), {"channel": "email", "by": "user", "seconds": 1800, "user_id": "dan"}),
    Ev("appointment.booked", at(24, 11), {"appointment_id": "t1", "source": "ai", "type": "Test drive"}),
    Ev("deal.stage_changed", at(24, 11), {"deal_id": "A", "from": "new", "to": "appointment"}),
    Ev("appointment.booked", at(24, 12), {"appointment_id": "s1", "source": "staff", "type": "Oil change"}),
    Ev("call.ended", at(24, 15), {"handled_by": "ai"}),
    Ev("call.ended", at(24, 15, 30), {"handled_by": "missed"}),
    Ev("follow_up.sent", at(24, 16), {"channel": "sms", "step": 0}),
    Ev("appointment.showed", at(25, 9), {"appointment_id": "t1"}),
    Ev("deal.stage_changed", at(25, 9, 30), {"deal_id": "A", "from": "appointment", "to": "negotiating"}),
    Ev("appointment.no_show", at(25, 10), {"appointment_id": "s1"}),
    Ev("deal.stage_changed", at(25, 11), {"deal_id": "B", "from": "new", "to": "lost"}),
    Ev("call.ended", at(25, 13), {"handled_by": "staff"}),
    Ev("message.received", at(25, 13), {"channel": "whatsapp"}),
    Ev("response.sent", at(25, 13), {"channel": "whatsapp", "by": "ai", "seconds": 30}),
    Ev("routing.decided", at(25, 13), {"topic": "sales"}),  # other events are ignored
]


def by_day() -> dict[date, list[Ev]]:
    days: dict[date, list[Ev]] = {}
    for e in FIXTURE:
        days.setdefault(local_day(e.at, TZ), []).append(e)
    return days


def test_an_event_belongs_to_the_dealerships_day_not_utcs():
    late = at(23, 23, 30)
    assert late.day == 24 and local_day(late, TZ) == date(2026, 11, 23)  # 11:30 pm Monday in Dallas is Tuesday in UTC
    assert sorted(by_day()) == [date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)]


def test_each_days_numbers_match_the_hand_count():
    days = {d: day_summary(evs) for d, evs in by_day().items()}
    mon, tue, wed = (days[date(2026, 11, d)] for d in (23, 24, 25))
    assert (mon["leads"], mon["leads_after_hours"], mon["leads_by_ai"], mon["responses"], mon["response_seconds"]) == (2, 1, 2, 3, [20, 40, 600])
    assert (tue["leads"], tue["appointments_booked"], tue["appointments_booked_by_ai"], tue["calls"], tue["calls_missed"], tue["follow_ups_sent"]) == (1, 2, 1, 2, 1, 1)
    assert (wed["appointments_showed"], wed["appointments_no_show"], wed["calls_by"], wed["responses_by_ai"]) == (1, 1, {"staff": 1}, 1)
    assert mon["leads_by_channel"] == {"whatsapp": 1, "sms": 1}


def test_the_periods_totals_match_the_hand_count():
    t = total([day_summary(evs) for evs in by_day().values()])
    assert (t["leads"], t["leads_by_ai"], t["leads_after_hours"]) == (3, 2, 1)
    assert t["leads_by_channel"] == {"whatsapp": 1, "sms": 1, "email": 1}
    assert (t["responses"], t["responses_by_ai"], t["responses_by_team"]) == (5, 3, 2)
    assert (t["median_first_response_seconds"], t["median_first_response_seconds_ai"]) == (40, 30)
    assert (t["appointments_booked"], t["appointments_booked_by_ai"], t["appointments_showed"], t["appointments_no_show"]) == (2, 1, 1, 1)
    assert (t["follow_ups_sent"], t["calls"], t["calls_by_ai"], t["calls_missed"]) == (1, 3, 1, 1)
    assert t["calls_by"] == {"ai": 1, "missed": 1, "staff": 1}
    assert t["handled_by"] == {"ai": 4, "team": 3}
    assert t["response_seconds_by_person"] == {"dan": [600, 1800]}  # one salesperson answered both
    assert t["messages_in"] == 5 and t["messages_in_by_channel"] == {"whatsapp": 2, "sms": 2, "email": 1}
    assert total([])["median_first_response_seconds"] is None  # no replies: no median, not zero


def test_the_pipeline_is_where_each_deal_stands_now():
    p = pipeline(FIXTURE)
    assert p["by_stage"] == {"new": 1, "qualified": 0, "appointment": 0, "negotiating": 1, "lost": 1}
    assert (p["in_play"], p["in_play_by_ai"], p["deal_ids_in_play_by_ai"]) == (2, 1, ["A"])


def test_every_metric_names_the_events_behind_it():
    """Traceable: for each number, the events that count are exactly the ones its rule picks."""
    assert [e.payload["deal_id"] for e in FIXTURE if METRICS["leads_after_hours"][1](e)] == ["B"]
    assert len([e for e in FIXTURE if METRICS["responses_by_team"][1](e)]) == 2
    for name, (label, test) in METRICS.items():
        assert label and day_summary(FIXTURE)[name] == sum(1 for e in FIXTURE if test(e)), name


def test_time_to_call_back_is_the_median_first_try_and_ignores_undone_ones():
    at = datetime(2026, 11, 25, 16, tzinfo=UTC)
    evs = [Ev("callback.first_try", at, {"by": "dan", "seconds": 600, "result": "reached"}),
           Ev("callback.first_try", at, {"by": "dan", "seconds": 1800, "result": "left_message"}),
           Ev("callback.first_try", at, {"by": "ana", "seconds": 300, "result": "reached"}),
           Ev("callback.first_try", at, {"by": "ana", "seconds": 60, "result": "reached", "undone": True})]
    day = day_summary(evs)
    assert day["callbacks"] == 3 and day["callback_seconds"] == [300, 600, 1800]
    t = total([day, day_summary([])])
    assert t["median_callback_seconds"] == 600 and t["callback_seconds_by_person"] == {"dan": [600, 1800], "ana": [300]}
    assert total([day_summary([])])["median_callback_seconds"] is None
