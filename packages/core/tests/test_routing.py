"""The routing rules as plain functions: matching, topics, shifts and whose turn it is."""

import uuid
from datetime import UTC, datetime, timedelta

from ondra_core.routing import (
    Facts,
    Person,
    Rule,
    first_match,
    matches,
    pick,
    shift,
    topic_for_handoff,
    topic_from_words,
    validate,
)

NOON_TUE = datetime(2026, 11, 24, 18, 0, tzinfo=UTC)  # Tuesday 12:00 in Chicago, 19:00 in Lagos
WEEKDAYS = {d: ["09:00", "18:00"] for d in ("mon", "tue", "wed", "thu", "fri")}
F = Facts(topic="sales", channel="whatsapp", open_now=True)


def person(role="sales", hours=None, tz="America/Chicago", **kw) -> Person:
    return Person(uuid.uuid4(), role, tz, WEEKDAYS if hours is None else hours, **kw)


def test_a_rule_matches_only_when_every_condition_holds():
    assert matches({}, F)
    assert matches({"topic": ["sales", "finance"], "channel": ["whatsapp"], "hours": "open"}, F)
    assert not matches({"topic": ["service"]}, F)
    assert not matches({"topic": ["sales"], "channel": ["email"]}, F)
    assert not matches({"hours": "closed"}, F)
    assert matches({"language": ["es"]}, Facts("sales", "sms", True, language="es-MX"))
    assert not matches({"language": ["es"]}, F)  # language unknown: a Spanish-only rule doesn't apply
    assert matches({"deal_type": ["service"]}, Facts("other", "sms", True, deal_type="service"))


def test_the_lowest_priority_number_wins_and_inactive_rules_are_skipped():
    rules = [Rule(None, 20, {}, {"assign_role": "sales"}, name="catch-all"),
             Rule(None, 10, {"topic": ["sales"]}, {"assign_role": "manager"}, name="sales to manager"),
             Rule(None, 1, {"topic": ["sales"]}, {"assign_role": "owner"}, active=False, name="off")]
    assert first_match(rules, F).name == "sales to manager"
    assert first_match(rules, Facts("service", "sms", True)).name == "catch-all"
    assert first_match([], F) is None


def test_rules_are_checked_before_they_are_saved():
    assert validate({"topic": ["sales"]}, {"assign_role": "sales", "ai": "draft"}) is None
    assert "Unknown topic" in validate({"topic": ["cars"]}, {"assign_role": "sales"})
    assert "one, not both" in validate({}, {"assign_role": "sales", "assign_user_id": str(uuid.uuid4())})
    assert "one, not both" in validate({}, {})
    assert validate({}, {"assign_role": "sales", "ai": "always"}) is not None
    assert validate({"weather": "sunny"}, {"assign_role": "sales"}) is not None


def test_topics_from_the_words_used():
    assert topic_from_words("is the highlander still available?") == "sales"
    assert topic_from_words("my check engine light came on") == "service"
    assert topic_from_words("can you ship it to Lagos?") == "shipping"
    assert topic_from_words("what APR can I get on a loan") == "finance"
    assert topic_from_words("this is unacceptable, I want a refund") == "complaint"
    assert topic_from_words("what time do you close") == "other"


def test_a_handoffs_topic_comes_from_its_reason_first():
    assert topic_for_handoff("complaint", "sales", "sales") == "complaint"  # whatever the model asked for
    assert topic_for_handoff("discount", "sales", None) == "sales"
    assert topic_for_handoff("delivery_date", "service", "service") == "service"  # "when is my car ready"
    assert topic_for_handoff("delivery_date", "sales", "sales") == "shipping"
    assert topic_for_handoff("asked_for_person", "service", None) == "service"
    assert topic_for_handoff("unknown_answer", "sales", "finance") == "finance"


def test_shifts_are_in_the_persons_own_timezone():
    assert shift(WEEKDAYS, "America/Chicago", NOON_TUE) == (True, None)
    on, start = shift(WEEKDAYS, "Africa/Lagos", NOON_TUE)  # 19:00 in Lagos: gone home
    assert not on and start == datetime(2026, 11, 25, 8, 0, tzinfo=UTC)  # 09:00 Wednesday in Lagos
    assert shift({}, "America/Chicago", NOON_TUE) == (True, None)  # no hours: always on
    sat = NOON_TUE + timedelta(days=4)
    on, start = shift(WEEKDAYS, "America/Chicago", sat)
    assert not on and start.astimezone(UTC) == datetime(2026, 11, 30, 15, 0, tzinfo=UTC)  # Monday 09:00 Chicago


def test_round_robin_gives_it_to_whoever_waited_longest():
    a = person(last_assigned_at=NOON_TUE - timedelta(hours=1))
    b = person(last_assigned_at=NOON_TUE - timedelta(hours=3))
    c = person(role="service")
    got = pick([a, b, c], "sales", NOON_TUE)
    assert (got.user_id, got.on_shift, got.why) == (b.id, True, "round_robin")
    never = person()
    assert pick([a, b, never], "sales", NOON_TUE).user_id == never.id  # never had one: first in line


def test_people_at_their_limit_are_skipped_unless_everyone_is():
    full = person(open_tasks=5, max_open_tasks=5)
    busy = person(open_tasks=9, last_assigned_at=NOON_TUE)
    assert pick([full, busy], "sales", NOON_TUE).user_id == busy.id
    other_full = person(open_tasks=3, max_open_tasks=3)
    got = pick([full, other_full], "sales", NOON_TUE)
    assert (got.user_id, got.why) == (other_full.id, "at_capacity")  # the least loaded, rather than nobody


def test_nobody_in_queues_it_for_the_next_shift():
    dallas = person()
    lagos = person(tz="Africa/Lagos")
    night = datetime(2026, 11, 25, 5, 0, tzinfo=UTC)  # Tue 23:00 Chicago, Wed 06:00 Lagos
    got = pick([dallas, lagos], "sales", night)
    assert (got.user_id, got.on_shift, got.why) == (lagos.id, False, "next_shift")
    assert got.available_at == datetime(2026, 11, 25, 8, 0, tzinfo=UTC)
    later = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)  # Lagos is in, Dallas asleep
    got = pick([dallas, lagos], "sales", later)
    assert (got.user_id, got.on_shift) == (lagos.id, True)


def test_a_named_person_and_a_customers_own_contact():
    a, b = person(last_assigned_at=NOON_TUE), person()
    assert pick([a, b], "sales", NOON_TUE, named=a.id).why == "named"
    got = pick([a, b], "sales", NOON_TUE, prefer=a.id)  # b's turn, but a already looks after this customer
    assert (got.user_id, got.why) == (a.id, "their_contact")
    off = person(hours={"sun": ["09:00", "10:00"]})
    assert pick([off, b], "sales", NOON_TUE, prefer=off.id).user_id == b.id  # their contact is out: someone who's in


def test_an_empty_team_falls_back_to_a_manager_then_the_owner():
    manager, owner = person(role="manager"), person(role="owner")
    got = pick([manager, owner], "service", NOON_TUE)
    assert (got.user_id, got.role, got.why) == (manager.id, "manager", "fallback")
    assert pick([owner], "service", NOON_TUE).user_id == owner.id
    assert pick([], "sales", NOON_TUE).user_id is None
