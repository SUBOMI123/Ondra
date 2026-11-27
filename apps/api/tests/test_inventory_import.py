"""Step 7: an inventory file updates stock (acceptance), with a preview first, permissions, and tenant isolation."""

import pytest
from ondra_api.db import tenant_session
from ondra_api.services.agent_tools import DbToolBackend
from ondra_core.models import Contact, Conversation, Integration, Vehicle
from sqlalchemy import delete, select, update

from tests.conftest import login

FILE = """Stock #,VIN,Year,Make,Model,Trim,Internet Price,Miles,Status,Body Style
{known},{known_vin},{year},{make},{model},Imported Trim,"$19,450",61000,In Stock,SUV
ZZ-NEW-1,1HGCV1F30LA000111,2020,Honda,Accord,Sport,"$22,300",38000,,Sedan
ZZ-NEW-2,5YJ3E1EA7KF000222,2019,Tesla,Model 3,Long Range,"$27,900",52000,Sale Pending,Sedan
ZZ-BAD,,2019,Kia,Soul,,cheap,80000,,
"""


@pytest.fixture
async def lot(database):
    t = database["a"]
    async with tenant_session(t) as db:
        v = (await db.execute(select(Vehicle).where(Vehicle.status == "available", Vehicle.vin.isnot(None)).order_by(Vehicle.stock_number).limit(1))).scalar_one()
        before = {"id": v.id, "stock": v.stock_number, "vin": v.vin, "year": v.year, "make": v.make, "model": v.model, "trim": v.trim,
                  "price": v.price, "mileage": v.mileage, "raw": dict(v.raw or {}), "source_feed": v.source_feed}
        count = len((await db.execute(select(Vehicle.id))).scalars().all())
    yield t, before, FILE.format(known=before["stock"], known_vin=before["vin"], year=before["year"], make=before["make"], model=before["model"])
    async with tenant_session(t) as db:
        await db.execute(delete(Vehicle).where(Vehicle.stock_number.like("ZZ-%")))
        await db.execute(update(Vehicle).where(Vehicle.id == before["id"]).values(
            trim=before["trim"], price=before["price"], mileage=before["mileage"], raw=before["raw"], source_feed=before["source_feed"], status="available"))
        await db.execute(update(Vehicle).where(Vehicle.source_feed.is_(None)).values(source_feed="seed"))
        await db.execute(delete(Integration).where(Integration.kind == "inventory_feed"))
        assert len((await db.execute(select(Vehicle.id))).scalars().all()) == count


async def test_a_csv_import_updates_stock_after_a_preview(client, database, lot):
    """Step 7 acceptance: inventory CSV import updates stock."""
    t, before, content = lot
    manager = await login(client, "manager@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    body = {"filename": "lot.csv", "content": content}
    assert (await client.post("/inventory/import", json=body, headers=sales)).status_code == 403

    preview = (await client.post("/inventory/import", json=body, headers=manager)).json()  # dry run by default
    assert (preview["created"], preview["updated"], preview["sold"], preview["skipped_count"]) == (2, 1, 0, 1)
    assert preview["skipped"] == [{"line": 5, "why": "Price 'cheap' isn't a number"}]
    assert preview["examples"]["created"][0] == "2020 Honda Accord, $22,300 (ZZ-NEW-1)"
    async with tenant_session(t) as db:  # a preview changes nothing
        assert (await db.execute(select(Vehicle).where(Vehicle.stock_number.like("ZZ-%")))).scalars().all() == []

    done = (await client.post("/inventory/import", json={**body, "dry_run": False}, headers=manager)).json()
    assert (done["created"], done["updated"]) == (2, 1)
    async with tenant_session(t) as db:
        known = await db.get(Vehicle, before["id"])
        assert (float(known.price), known.mileage, known.trim, known.raw["body"]) == (19450.0, 61000, "Imported Trim", "SUV")
        new = {v.stock_number: v for v in (await db.execute(select(Vehicle).where(Vehicle.stock_number.like("ZZ-%")))).scalars()}
        assert (new["ZZ-NEW-1"].status, new["ZZ-NEW-2"].status, new["ZZ-NEW-1"].source_feed) == ("available", "hold", "upload")
        integ = (await db.execute(select(Integration).where(Integration.kind == "inventory_feed"))).scalar_one()
        assert integ.status == "warning" and integ.config["last"]["skipped_count"] == 1 and integ.last_sync_at is not None
        # The AI's own search sees the new stock and the new price straight away.
        contact = (await db.execute(select(Contact).limit(1))).scalar_one()
        conv = Conversation(contact_id=contact.id, channel="sms", ai_mode="auto")
        db.add(conv)
        await db.flush()
        backend = DbToolBackend(db, contact=contact, conversation=conv, price_disclosure="listed", open_now=True)
        accords = await backend.search_inventory(make="Honda", model="Accord")
        assert any(c["stock"] == "ZZ-NEW-1" and c["price"] == 22300.0 for c in accords)
        assert all(c["stock"] != "ZZ-NEW-2" for c in await backend.search_inventory(make="Tesla"))  # on hold: not offered
        await db.delete(conv)

    # Importing the same file again changes nothing.
    again = (await client.post("/inventory/import", json={**body, "dry_run": False}, headers=manager)).json()
    assert (again["created"], again["updated"], again["unchanged"]) == (0, 0, 3)


async def test_a_whole_lot_file_marks_missing_feed_cars_sold_and_never_hand_entered_ones(client, database, lot):
    t, before, content = lot
    owner = await login(client, "owner@prestigemotors.example")
    await client.post("/inventory/import", json={"filename": "lot.csv", "content": content, "dry_run": False}, headers=owner)
    whole = {"filename": "lot.csv", "whole_lot": True, "dry_run": False}
    # The seeded lot came from a feed too. A "whole lot" file listing 2 of ~50 cars looks cut short: nothing is marked sold.
    cut = (await client.post("/inventory/import", json={**whole, "content": content}, headers=owner)).json()
    assert (cut["partial"], cut["sold"]) == (True, 0)
    async with tenant_session(t) as db:  # now treat the seeded cars as entered by hand
        await db.execute(update(Vehicle).where(Vehicle.source_feed == "seed").values(source_feed=None))
    shorter = "\n".join(line for line in content.splitlines() if "ZZ-NEW-2" not in line and "ZZ-BAD" not in line)
    out = (await client.post("/inventory/import", json={"filename": "lot.csv", "content": shorter, "whole_lot": True, "dry_run": False}, headers=owner)).json()
    assert out["sold"] == 1 and out["examples"]["sold"] == ["2019 Tesla Model 3 (ZZ-NEW-2)"]
    async with tenant_session(t) as db:
        assert (await db.execute(select(Vehicle.status).where(Vehicle.stock_number == "ZZ-NEW-2"))).scalar_one() == "sold"
        hand_entered = (await db.execute(select(Vehicle).where(Vehicle.source_feed.is_(None), Vehicle.status == "available"))).scalars().all()
        assert len(hand_entered) > 10  # the seeded lot wasn't in the file and is untouched


async def test_unreadable_files_are_refused_with_the_reason_and_dealers_are_isolated(client, database, lot):
    t, _before, content = lot
    owner = await login(client, "owner@prestigemotors.example")
    r = await client.post("/inventory/import", json={"filename": "people.csv", "content": "Name,Phone\nSarah,555\n", "dry_run": False}, headers=owner)
    assert r.status_code == 422 and "year, make and model" in r.json()["detail"]
    async with tenant_session(t) as db:
        integ = (await db.execute(select(Integration).where(Integration.kind == "inventory_feed"))).scalar_one()
        assert integ.status == "error"  # the failed attempt shows in the integration's health
    await client.post("/inventory/import", json={"filename": "lot.csv", "content": content, "dry_run": False}, headers=owner)
    async with tenant_session(database["b"]) as db:
        assert (await db.execute(select(Vehicle).where(Vehicle.stock_number.like("ZZ-%")))).scalars().all() == []
        assert (await db.execute(select(Integration).where(Integration.kind == "inventory_feed"))).scalars().all() == []


async def test_a_hold_placed_in_ondra_survives_an_import_and_only_managers_mark_cars_sold(client, database, lot):
    t, before, content = lot
    manager = await login(client, "manager@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    async with tenant_session(t) as db:
        sarah = (await db.execute(select(Contact).where(Contact.display_name == "Sarah King"))).scalar_one()
    vid = str(before["id"])
    held = await client.patch(f"/vehicles/{vid}", headers=sales, json={"status": "hold", "for_contact_id": str(sarah.id)})
    assert held.status_code == 200, held.text
    assert (held.json()["hold"]["by"], held.json()["hold"]["for"]["name"]) == ("Daniel Okafor", "Sarah King")
    # The file still says "In Stock": the hold stays until someone releases it.
    await client.post("/inventory/import", json={"filename": "lot.csv", "content": content, "dry_run": False}, headers=manager)
    d = (await client.get(f"/vehicles/{vid}", headers=sales)).json()
    assert (d["status"], d["hold"]["for"]["name"]) == ("hold", "Sarah King")
    # Selling is a manager's call; releasing a hold isn't.
    assert (await client.patch(f"/vehicles/{vid}", headers=sales, json={"status": "sold"})).status_code == 403
    assert (await client.patch(f"/vehicles/{vid}", headers=sales, json={"status": "available"})).json()["hold"] is None
    assert (await client.patch(f"/vehicles/{vid}", headers=manager, json={"status": "sold"})).json()["status"] == "sold"
    assert (await client.patch(f"/vehicles/{vid}", headers=sales, json={"status": "available"})).status_code == 403


async def test_the_list_shows_days_on_the_lot_and_which_buyers_are_asking(client, database, lot):
    from datetime import UTC, datetime, timedelta

    from ondra_core.models import Deal

    t, before, _content = lot
    sales = await login(client, "daniel@prestigemotors.example")
    async with tenant_session(t) as db:
        sarah = (await db.execute(select(Contact).where(Contact.display_name == "Sarah King"))).scalar_one()
        deal = Deal(contact_id=sarah.id, type="sales", stage="qualified", vehicle_of_interest={"stock": before["stock"], "description": "the one online"})
        db.add(deal)
        await db.execute(update(Vehicle).where(Vehicle.id == before["id"]).values(created_at=datetime.now(UTC) - timedelta(days=75)))
        await db.flush()
        deal_id = deal.id
    try:
        page = (await client.get("/vehicles", params={"sort": "asked", "limit": 200}, headers=sales)).json()
        row = next(v for v in page["items"] if v["id"] == str(before["id"]))
        assert (row["asked_about"], row["days_on_lot"]) == (1, 75)
        asked = [v["asked_about"] for v in page["items"]]
        assert asked == sorted(asked, reverse=True) and asked[0] >= 1
        assert before["make"] in page["makes"] and page["total"] >= 40
        oldest = (await client.get("/vehicles", params={"sort": "oldest", "limit": 200}, headers=sales)).json()["items"]
        assert [v["days_on_lot"] for v in oldest] == sorted((v["days_on_lot"] for v in oldest), reverse=True)
        by_make = (await client.get("/vehicles", params={"make": before["make"].upper(), "limit": 200}, headers=sales)).json()["items"]
        assert by_make and {v["make"] for v in by_make} == {before["make"]}
        d = (await client.get(f"/vehicles/{before['id']}", headers=sales)).json()
        assert [b["client"]["name"] for b in d["buyers"]][0] == "Sarah King" and d["buyers"][0]["by_stock"] is True
        assert d["buyers"][0]["said"]["body"].startswith("whats the best")
        assert (d["can_hold"], d["can_sell"]) == (True, False)
    finally:
        async with tenant_session(t) as db:
            await db.execute(delete(Deal).where(Deal.id == deal_id))
