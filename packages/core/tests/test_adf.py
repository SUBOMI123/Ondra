"""ADF 1.0 lead XML: built in the DTD's order, escaped, and checked."""

from datetime import UTC, datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pytest
from ondra_core.adf import Lead, Vehicle, build, problems

WHEN = datetime(2026, 11, 27, 14, 5, 9, 123456, tzinfo=timezone(timedelta(hours=-6)))
LEAD = Lead(id="deal-123", requested_at=WHEN, vendor="Prestige Motors", first_name="Sarah", last_name="King",
            email="sarah@example.com", phone="+12145551234", timeframe="This month", finance_method="finance", budget_max=30000,
            comments="Asked about the CR-V; wants a Saturday test drive. Budget < $30k & has a trade-in.",
            vehicle=Vehicle(year=2023, make="Honda", model="CR-V", vin="2HKRS4H7XPH400001", stock="H23-1148", trim="EX-L",
                            odometer=23512, price=25100.0), vendor_email="sales@prestigemotors.example")


def test_a_full_lead_is_valid_and_carries_everything():
    xml = build(LEAD)
    assert problems(xml) == []
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<?adf version="1.0"?>\n<adf>')
    p = ET.fromstring(xml.encode()).find("prospect")
    assert p.get("status") == "new" and p.findtext("requestdate") == "2026-11-27T14:05:09-06:00"
    assert [c.tag for c in p] == ["id", "requestdate", "vehicle", "customer", "vendor", "provider"]
    v = p.find("vehicle")
    assert (v.get("interest"), v.get("status")) == ("buy", "used")
    assert [c.tag for c in v] == ["year", "make", "model", "vin", "stock", "trim", "odometer", "price", "finance"]
    assert (v.findtext("price"), v.find("price").get("type"), v.findtext("finance/method")) == ("25100", "asking", "finance")
    names = {n.get("part"): n.text for n in p.findall("customer/contact/name")}
    assert names == {"first": "Sarah", "last": "King"}
    assert p.findtext("customer/comments").endswith("Budget < $30k & has a trade-in.")  # escaped on the way out, intact on the way in
    assert p.findtext("vendor/vendorname") == "Prestige Motors" and p.findtext("provider/name") == "Ondra"


def test_a_lead_with_no_specific_car_is_still_valid():
    xml = build(Lead(id="d2", requested_at=datetime.now(UTC), vendor="Prestige Motors", full_name="+12145559999", phone="+12145559999",
                     vehicle=Vehicle(comments="A 3-row SUV under $35k")))
    assert problems(xml) == []
    v = ET.fromstring(xml.encode()).find("prospect/vehicle")
    assert [c.tag for c in v] == ["year", "make", "model", "comments"] and v.findtext("make") is None or v.findtext("make") == ""


def test_the_checker_catches_what_a_crm_would_choke_on():
    good = build(LEAD)
    assert "processing instruction" in problems(good.replace('<?adf version="1.0"?>\n', ""))[0]
    swapped = good.replace("<year>2023</year><make>Honda</make>", "<make>Honda</make><year>2023</year>")
    assert any("out of order" in p for p in problems(swapped))
    assert any("missing <vendorname>" in p for p in problems(good.replace("<vendorname>Prestige Motors</vendorname>", "")))
    assert any("isn't one of" in p for p in problems(good.replace('interest="buy"', 'interest="browse"')))
    assert any("ISO 8601" in p for p in problems(good.replace("2026-11-27T14:05:09-06:00", "11/27/2026 2:05 PM")))
    no_reach = build(Lead(id="d3", requested_at=WHEN, vendor="X", full_name="Nobody"))
    assert problems(no_reach) == ["the customer has no email or phone"]
    assert problems("<adf><prospect>")[0].startswith("not well-formed")


def test_dates_must_carry_a_time_zone():
    with pytest.raises(ValueError, match="time zone"):
        build(Lead(id="d", requested_at=datetime(2026, 1, 1), vendor="X", phone="1"))
