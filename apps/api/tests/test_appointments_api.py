"""The booking API for staff: a dealer creates a custom appointment type (Step 4 acceptance), books from offered
slots, sees the day in lanes, records no-shows; VIP appointments stay private to roles that can't see VIPs."""

from datetime import date, timedelta

from sqlalchemy import select

from ondra_api.db import tenant_session
from ondra_core.models import Contact

from .conftest import login

OWNER, SALES = "owner@prestigemotors.example", "daniel@prestigemotors.example"


def _next(weekday: int) -> date:
    d = date.today() + timedelta(days=2)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


async def test_a_dealer_creates_a_custom_type_and_books_it(client, database):
    owner = await login(client, OWNER)
    r = await client.post("/appointment-types", headers=owner, json={
        "name": "EV charging walkthrough", "category": "custom", "duration_min": 30, "buffer_min": 10,
        "eligible_roles": ["sales"], "description": "Set up home charging and the app with a product specialist."})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["reminder_schedule"] == [1440, 120] and t["active"]
    assert any(x["id"] == t["id"] for x in (await client.get("/appointment-types", headers=owner)).json()["items"])

    tue = _next(1)
    slots = (await client.get(f"/availability?type_id={t['id']}&date={tue.isoformat()}", headers=owner)).json()["items"]
    assert slots and slots[0]["when"].startswith(tue.strftime("%a"))
    async with tenant_session(database["a"]) as db:
        cid = (await db.execute(select(Contact.id).where(Contact.display_name == "Chloe Dubois"))).scalar_one()
    a = (await client.post("/appointments", headers=owner, json={"slot_id": slots[0]["slot_id"], "contact_id": str(cid)})).json()
    assert a["title"] == "EV charging walkthrough" and a["source"] == "staff" and a["with"]
    again = await client.post("/appointments", headers=owner, json={"slot_id": slots[0]["slot_id"], "contact_id": str(cid)})
    assert again.status_code == 409

    cal = (await client.get(f"/calendar?date={tue.isoformat()}", headers=owner)).json()
    assert {lane["group"] for lane in cal["lanes"]} == {"Sales", "Service"}
    assert any(x["id"] == a["id"] and x["lane_ids"] == [a["assigned_user_id"]] for x in cal["appointments"])

    # Switching the type off keeps it out of availability.
    await client.patch(f"/appointment-types/{t['id']}", headers=owner, json={"active": False})
    assert (await client.get(f"/availability?type_id={t['id']}", headers=owner)).status_code == 404
    assert (await client.patch(f"/appointments/{a['id']}", headers=owner, json={"status": "cancelled"})).json()["status"] == "cancelled"


async def test_from_template_and_rules(client, database):
    owner, sales = await login(client, OWNER), await login(client, SALES)
    tpl = (await client.get("/appointment-types/templates", headers=owner)).json()["items"]
    assert {x["key"] for x in tpl} >= {"test_drive", "oil_change", "trade_in_appraisal", "vehicle_delivery"}
    r = await client.post("/appointment-types", headers=owner, json={"template": "oil_change", "name": "Tire rotation", "duration_min": 45})
    t = r.json()
    assert t["required_resource_kinds"] == ["service_bay"] and t["duration_min"] == 45
    assert (await client.post("/appointment-types", headers=sales, json={"name": "Nope"})).status_code == 403
    assert (await client.post("/appointment-types", headers=owner, json={"name": "X", "eligible_roles": []})).status_code == 422
    bad = await client.post("/appointment-types", headers=owner, json={"name": "X", "reminder_schedule": [5]})
    assert bad.status_code == 422
    await client.patch(f"/appointment-types/{t['id']}", headers=owner, json={"active": False})


async def test_service_lands_in_the_bay_lane_and_no_show_is_recorded(client, database):
    owner = await login(client, OWNER)
    types = (await client.get("/appointment-types", headers=owner)).json()["items"]
    oil = next(t for t in types if t["name"] == "Oil change")
    wed = _next(2)
    slot = (await client.get(f"/availability?type_id={oil['id']}&date={wed.isoformat()}", headers=owner)).json()["items"][0]
    async with tenant_session(database["a"]) as db:
        cid = (await db.execute(select(Contact.id).where(Contact.display_name == "Darnell Brooks"))).scalar_one()
    a = (await client.post("/appointments", headers=owner, json={"slot_id": slot["slot_id"], "contact_id": str(cid),
                                                                "details": {"transport": "wait"}})).json()
    assert a["bays"] == ["Bay 1"]
    cal = (await client.get(f"/calendar?date={wed.isoformat()}", headers=owner)).json()
    bay1 = next(lane for lane in cal["lanes"] if lane["name"] == "Bay 1")
    assert next(x for x in cal["appointments"] if x["id"] == a["id"])["lane_ids"] == [bay1["id"]]
    assert (await client.patch(f"/appointments/{a['id']}", headers=owner, json={"status": "no_show"})).json()["status"] == "no_show"


async def test_vip_appointments_are_busy_blocks_for_sales(client, database):
    owner, sales = await login(client, OWNER), await login(client, SALES)
    types = (await client.get("/appointment-types", headers=owner)).json()["items"]
    td = next(t for t in types if t["name"] == "Test drive")
    thu = _next(3)
    slot = (await client.get(f"/availability?type_id={td['id']}&date={thu.isoformat()}", headers=owner)).json()["items"][-1]
    async with tenant_session(database["a"]) as db:
        vip = (await db.execute(select(Contact.id).where(Contact.display_name == "Tunde Bakare"))).scalar_one()
    r = await client.post("/appointments", headers=owner, json={"slot_id": slot["slot_id"], "contact_id": str(vip)})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["starts_at"][:10] in (thu.isoformat(), (thu + timedelta(days=1)).isoformat()), a["starts_at"]
    seen = next(x for x in (await client.get(f"/calendar?date={thu.isoformat()}", headers=sales)).json()["appointments"] if x["id"] == a["id"])
    if seen["assigned_user_id"] != (await client.get("/me", headers=sales)).json()["id"]:
        assert seen["title"] == "Busy" and seen["client"] is None
        assert (await client.patch(f"/appointments/{a['id']}", headers=sales, json={"status": "cancelled"})).status_code == 404
    await client.patch(f"/appointments/{a['id']}", headers=owner, json={"status": "cancelled"})
