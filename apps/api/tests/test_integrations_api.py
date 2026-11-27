"""Integration settings and health: CRM address and test lead, scheduled inventory feed, DMS choice and upload."""

import pytest
from ondra_api import channels
from ondra_api.db import tenant_session
from ondra_api.services import feed_fetch
from ondra_core import adf
from ondra_core.models import Integration, Job, Vehicle
from sqlalchemy import delete, select, update

from tests.conftest import login

FEED = "stock,year,make,model,price\nZF-1,2022,Mazda,CX-5,26500\nZF-2,2021,Mazda,Mazda3,19900\n"


@pytest.fixture
async def clean(database):
    t = database["a"]
    channels.mock("email").outbox.clear()
    async with tenant_session(t) as db:
        dms_before = (await db.execute(select(Integration.config).where(Integration.kind == "dms"))).scalar_one()
    yield t
    async with tenant_session(t) as db:
        await db.execute(delete(Integration).where(Integration.kind.in_(("crm_adf", "inventory_feed"))))
        await db.execute(update(Integration).where(Integration.kind == "dms").values(config=dms_before, status="ok"))
        await db.execute(delete(Vehicle).where(Vehicle.stock_number.like("ZF-%")))
        await db.execute(delete(Job).where(Job.kind == "inventory_fetch"))


def test_feed_addresses_that_arent_public_https_are_refused():
    assert feed_fetch.check_url("https://feeds.example.com/lot.csv") == "https://feeds.example.com/lot.csv"
    for bad in ("http://feeds.example.com/lot.csv", "https://localhost/x", "https://10.0.0.5/x", "https://169.254.169.254/latest/meta-data",
                "https://user:pw@feeds.example.com/x", "https://feeds.example.com:8443/x", "https://intranet/x", "ftp://x.example.com/a",
                "https://db.internal/x", "https://[::1]/x", ""):
        with pytest.raises(feed_fetch.FeedError):
            feed_fetch.check_url(bad)


async def test_crm_settings_test_lead_and_health(client, clean):
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    got = (await client.get("/integrations", headers=sales)).json()
    assert got["crm"]["state"] == "off" and got["can_edit"] is False and got["dms"] == {**got["dms"], "provider": "mock", "state": "ok"}
    assert (await client.put("/integrations/crm", json={"email": "leads@crm.example"}, headers=sales)).status_code == 403
    assert (await client.put("/integrations/crm", json={"email": "not an address"}, headers=owner)).status_code == 422
    assert (await client.put("/integrations/crm", json={"email": "Leads@CRM.example"}, headers=owner)).json() == {"email": "leads@crm.example", "active": True}
    assert (await client.post("/integrations/crm/test", headers=owner)).json() == {"sent": True}
    [mail] = channels.mock("email").outbox
    assert mail.to_address == "leads@crm.example" and mail.subject.startswith("TEST lead") and adf.problems(mail.body) == []
    got = (await client.get("/integrations", headers=owner)).json()["crm"]
    assert (got["state"], got["last"]["detail"], got["has_sender"]) == ("ok", "Test lead sent.", True) and got["last_ok_at"]
    channels.mock("email").fail_next = True
    r = await client.post("/integrations/crm/test", headers=owner)
    assert r.status_code == 502 and "Couldn't send the test lead" in r.json()["detail"]
    assert (await client.get("/integrations", headers=owner)).json()["crm"]["state"] == "error"  # the failure shows as its health


async def test_a_scheduled_feed_is_fetched_imported_and_rescheduled(client, clean, monkeypatch):
    owner = await login(client, "owner@prestigemotors.example")
    assert (await client.put("/integrations/inventory-feed", json={"url": "http://feeds.example.com/lot.csv", "every_hours": 6}, headers=owner)).status_code == 422
    r = await client.put("/integrations/inventory-feed", json={"url": "https://feeds.example.com/lot.csv", "every_hours": 6}, headers=owner)
    assert r.status_code == 200, r.text
    async with tenant_session(clean) as db:
        [job] = (await db.execute(select(Job).where(Job.kind == "inventory_fetch", Job.status == "queued"))).scalars().all()
        payload = job.payload
        job.status = "done"

    async def ok(url):
        return FEED

    async def down(url):
        raise feed_fetch.FeedError("The feed answered with an error (503).")

    monkeypatch.setattr(feed_fetch, "fetcher", ok)
    assert await feed_fetch.run(clean, payload) == "imported"
    async with tenant_session(clean) as db:
        assert {v.stock_number for v in (await db.execute(select(Vehicle).where(Vehicle.source_feed == "feed"))).scalars()} == {"ZF-1", "ZF-2"}
        [nxt] = (await db.execute(select(Job).where(Job.kind == "inventory_fetch", Job.status == "queued"))).scalars().all()
        assert nxt.payload == payload  # the next fetch is lined up, six hours on
    inv = (await client.get("/integrations", headers=owner)).json()["inventory"]
    assert inv["last"]["created"] == 2 and inv["every_hours"] == 6 and inv["state"] in ("ok", "warning")
    # A feed that's down shows as an error and keeps its schedule; the lot is untouched.
    monkeypatch.setattr(feed_fetch, "fetcher", down)
    assert (await feed_fetch.run(clean, payload)).startswith("failed: The feed answered with an error")
    inv = (await client.get("/integrations", headers=owner)).json()["inventory"]
    assert inv["state"] == "error" and "503" in inv["last"]["error"]
    # Changing the schedule makes the old jobs stop.
    await client.put("/integrations/inventory-feed", json={"url": "", "every_hours": 0}, headers=owner)
    assert await feed_fetch.run(clean, payload) == "skipped: no scheduled feed"


async def test_dms_choice_and_repair_order_upload(client, clean):
    owner = await login(client, "owner@prestigemotors.example")
    assert (await client.put("/integrations/dms", json={"provider": "csv"}, headers=owner)).status_code == 422  # nothing uploaded yet
    bad = await client.post("/integrations/dms/upload", json={"filename": "x.csv", "content": "Name\nx\n"}, headers=owner)
    assert bad.status_code == 422 and "RO number" in bad.json()["detail"]
    up = (await client.post("/integrations/dms/upload", json={"filename": "ros.csv", "content": "RO,Status,Phone\n88001,WIP,2145551001\n"}, headers=owner)).json()
    assert up["loaded"] == 1
    got = (await client.get("/integrations", headers=owner)).json()["dms"]
    assert (got["provider"], got["orders"], got["state"]) == ("csv", 1, "ok")
    assert (await client.put("/integrations/dms", json={"provider": "off"}, headers=owner)).json() == {"provider": "off"}
    assert (await client.get("/integrations", headers=owner)).json()["dms"]["state"] == "off"
    other = await login(client, "owner@lonestar.example")
    assert (await client.get("/integrations", headers=other)).json()["dms"]["provider"] == "off"  # another dealer's is its own
