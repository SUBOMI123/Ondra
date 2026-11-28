"""Follow-up rules that need no database: quiet hours, step validation, filling a fixed message."""

from datetime import UTC, datetime

from ondra_core.follow_ups import fill, first_name, in_quiet_hours, next_allowed, validate_steps

CHI = "America/Chicago"


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 24, hour, minute, tzinfo=UTC)  # Chicago is UTC-6 on this date


def test_quiet_hours_default_to_nine_pm_to_eight_am_in_the_dealers_time():
    assert in_quiet_hours(None, CHI, at(4))  # 10 pm Monday in Chicago
    assert in_quiet_hours({}, CHI, at(13, 59))  # 7:59 am
    assert not in_quiet_hours(None, CHI, at(14))  # 8:00 am
    assert not in_quiet_hours(None, CHI, at(2, 59))  # 8:59 pm
    assert in_quiet_hours(None, CHI, at(3))  # 9:00 pm


def test_a_dealers_own_quiet_hours_and_a_daytime_span():
    assert in_quiet_hours({"start": "19:00", "end": "09:00"}, CHI, at(1, 30))  # 7:30 pm
    assert in_quiet_hours({"start": "12:00", "end": "13:00"}, CHI, at(18, 30))  # a lunch-hour span, 12:30 pm
    assert not in_quiet_hours({"start": "12:00", "end": "13:00"}, CHI, at(19))


def test_a_send_due_in_quiet_hours_waits_until_they_end():
    assert next_allowed(None, CHI, at(16)) == at(16)  # 10 am: goes as planned
    assert next_allowed(None, CHI, at(4)) == at(14)  # 10 pm: 8 am the next morning
    assert next_allowed(None, CHI, at(12)) == at(14)  # 6 am: 8 am the same morning


def test_steps_are_checked_before_saving():
    ok = [{"after_hours": 24, "write": "ondra", "require_approval": True}, {"after_hours": 72, "write": "text", "text": "Hi {first_name}"}]
    assert validate_steps(ok) is None
    assert validate_steps([]) is not None
    assert "wait" in validate_steps([{"after_hours": 0, "write": "ondra"}])
    assert "write the message" in validate_steps([{"after_hours": 24, "write": "text", "text": "  "}])
    assert validate_steps([{"after_hours": 24, "write": "ondra"}] * 7) is not None


def test_fixed_messages_fill_in_names():
    assert fill("Hi {first_name}, it's {dealership}.", first_name="Sarah", dealership="Prestige Motors") == "Hi Sarah, it's Prestige Motors."
    assert fill("Hi {first_name},", first_name=None, dealership="X") == "Hi there,"
    assert first_name("Sarah Miller") == "Sarah" and first_name("+12145551234") is None and first_name("a@b.com") is None
