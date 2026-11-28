"""Demo photos (docs/PLAN.md item 8): every demo car has its model's photo; a real dealer's car never gets one (no
feed photo means no photo), and Ondra never offers a demo photo to a customer as if it were the car."""

from ondra_api.db import tenant_session
from ondra_api.demo_photos import FILES, PREFIX, ensure_demo_photos
from ondra_api.services.agent_tools import _vehicle_dict
from ondra_core.models import Integration, Vehicle
from sqlalchemy import delete, select, update

from tests.conftest import login

FEED = """Stock #,VIN,Year,Make,Model,Trim,Internet Price,Miles,Status
ZZ-PH-1,1HGCV1F30LA000999,2022,Toyota,Highlander,XLE,"$33,900",21000,In Stock
"""


async def test_every_listed_model_has_its_file_its_credit_and_its_cars_get_the_photo(database):
    import json
    from pathlib import Path

    web = Path(__file__).resolve().parents[2] / "web"
    credits = json.loads((web / "lib" / "demo-photo-credits.json").read_text())
    for f in FILES.values():
        assert (web / "public" / "demo-cars" / f).stat().st_size > 20_000, f
        assert credits[f"{PREFIX}{f}"]["license"] and credits[f"{PREFIX}{f}"]["artist"], f
    async with tenant_session(database["a"]) as db:
        await ensure_demo_photos(db)
        for v in (await db.execute(select(Vehicle).where(Vehicle.source_feed == "seed"))).scalars():
            listed = f"{v.make} {v.model}" in FILES
            assert (v.photos[:1] == [f"{PREFIX}{FILES[f'{v.make} {v.model}']}"]) if listed else not any(u.startswith(PREFIX) for u in v.photos)
        assert await ensure_demo_photos(db) == 0  # idempotent
        await db.rollback()


async def test_a_real_dealers_car_without_a_feed_photo_shows_none(client, database):
    t = database["a"]
    manager = await login(client, "manager@prestigemotors.example")
    try:
        r = await client.post("/inventory/import", json={"filename": "lot.csv", "content": FEED, "dry_run": False}, headers=manager)
        assert r.status_code == 200, r.text
        async with tenant_session(t) as db:
            v = (await db.execute(select(Vehicle).where(Vehicle.stock_number == "ZZ-PH-1"))).scalar_one()
            assert v.source_feed == "upload" and v.photos == []  # same model as a demo car, still no photo
            await ensure_demo_photos(db)
            await db.refresh(v)
            assert v.photos == []  # the demo backfill never touches a feed car
        listed = (await client.get("/inventory", params={"q": "ZZ-PH-1"}, headers=manager)).json()
        rows = listed.get("items", listed if isinstance(listed, list) else [])
        assert all(not c["photos"] for c in rows if c.get("stock_number") == "ZZ-PH-1")
    finally:
        async with tenant_session(t) as db:
            await db.execute(delete(Vehicle).where(Vehicle.stock_number == "ZZ-PH-1"))
            await db.execute(update(Vehicle).where(Vehicle.source_feed.is_(None)).values(source_feed="seed"))
            await db.execute(delete(Integration).where(Integration.kind == "inventory_feed"))


async def test_ondra_never_offers_a_demo_photo_to_a_customer(database):
    async with tenant_session(database["a"]) as db:
        v = (await db.execute(select(Vehicle).where(Vehicle.source_feed == "seed").limit(1))).scalar_one()
        v.photos = ["/demo-cars/toyota-highlander.jpg"]
        assert "photos" not in _vehicle_dict(v)
        v.photos = ["https://dealer.example/photos/1.jpg", *v.photos]
        assert _vehicle_dict(v)["photos"] == ["https://dealer.example/photos/1.jpg"]
        await db.rollback()
