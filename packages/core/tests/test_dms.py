"""The DMS interface: mock and CSV adapters, and reading a repair-order export."""

import pytest
from ondra_core.dms import CsvDms, MockDms, NotSupported, RepairOrder, digits, parse_repair_orders

CSV = """RO #,Status,Customer Phone,Email,Advisor,Year,Make,Model,Customer Note
55120,Waiting on Parts,(214) 555-1001,,Maria,2018,Honda,Accord,
55131,WIP,214-555-1002,ben@example.com,Maria,2021,Toyota,Tacoma,
55098,Ready for Pickup,+12145551003,,Maria,2020,Ford,Escape,Keys at the service desk.
55200,Exploded,2145551004,,Maria,2019,Kia,Soul,
55201,Open,,,Maria,2019,Kia,Soul,
"""


async def test_repair_orders_are_found_only_by_the_customers_own_phone_or_email():
    d = MockDms()
    [mine] = await d.get_repair_orders(phones=["+1 (214) 555-1001"], emails=[])
    assert (mine.number, mine.status) == ("RO-55120", "waiting_parts")
    assert await d.get_repair_orders(phones=["+12145559999"], emails=[]) == []
    assert await d.get_repair_orders(phones=[], emails=[]) == []  # nothing to match on: nothing returned
    assert digits("+1 (214) 555-0102") == digits("2145550102") == "2145550102"


def test_what_the_ai_is_told_has_no_time_or_money():
    told = RepairOrder("RO-1", "ready", "2020 Ford Escape", "Maria", phone="2145551003", note="Keys at the desk.").for_customer()
    assert told == {"repair_order": "RO-1", "vehicle": "2020 Ford Escape", "status": "ready", "what_it_means": "It's ready to be picked up.",
                    "service_advisor": "Maria", "advisor_note": "Keys at the desk."}


async def test_a_csv_export_is_read_with_vendor_status_words_and_bad_rows_reported():
    orders, skipped, error = parse_repair_orders(CSV)
    assert error is None and [(o.number, o.status, o.vehicle) for o in orders] == [
        ("55120", "waiting_parts", "2018 Honda Accord"), ("55131", "in_progress", "2021 Toyota Tacoma"), ("55098", "ready", "2020 Ford Escape")]
    assert skipped == [{"line": 5, "why": "Status 'Exploded' isn't one we know"}, {"line": 6, "why": "No phone or email to match the customer by"}]
    d = CsvDms(orders)
    assert [o.number for o in await d.get_repair_orders(phones=[], emails=["BEN@example.com"])] == ["55131"]
    assert (await d.health())[0] is True
    with pytest.raises(NotSupported):
        await d.get_service_slots("2026-12-01")
    assert parse_repair_orders("Name,Phone\nx,1\n")[2].startswith("This file needs columns")
    assert parse_repair_orders("")[2] == "This file is empty."


async def test_the_mock_can_book_so_the_interface_is_exercised():
    d = MockDms(orders=[])
    from ondra_core.dms import DmsCustomer

    ref = await d.book_service((await d.get_service_slots("2026-12-01"))[0], DmsCustomer("Ben"), "2021 Tacoma", "oil change")
    assert ref == "MOCK-0001" and d.booked[0]["concern"] == "oil change"
