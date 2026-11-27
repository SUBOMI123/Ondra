"""The Clients list: find anyone by name, email or phone (however it's typed), and see where they stand."""

from ondra_api.db import tenant_session
from ondra_core.models import Contact, ContactIdentity
from sqlalchemy import select

from tests.conftest import login


async def test_search_by_phone_or_email_and_rows_say_where_clients_stand(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    async with tenant_session(database["a"]) as db:
        sarah = (await db.execute(select(Contact).where(Contact.display_name == "Sarah King"))).scalar_one()
        ids = {i.kind: i.value for i in (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == sarah.id))).scalars()}
    phone, email = ids["phone"], ids["email"]

    def names(r):
        assert r.status_code == 200, r.text
        return [c["display_name"] for c in r.json()["items"]]

    typed = f"({phone[2:5]}) {phone[5:8]}-{phone[8:]}"  # "(214) 555-1003", as someone would type it
    assert names(await client.get("/contacts", params={"q": typed}, headers=owner)) == ["Sarah King"]
    assert names(await client.get("/contacts", params={"q": email.upper()}, headers=owner)) == ["Sarah King"]
    assert "Sarah King" in names(await client.get("/contacts", params={"q": "sarah"}, headers=owner))

    row = (await client.get("/contacts", params={"q": "Sarah King"}, headers=owner)).json()["items"][0]
    assert row["deal"] == {"type": "sales", "stage": "new", "vehicle": "2021 Toyota Highlander XLE", "budget_max": 31000.0}
    assert row["last_contact_at"] is not None
    assert row["looks_after"] == "Daniel Okafor"  # Sarah's conversation is with him

    # Most recently in touch first; anyone never in touch goes last.
    rows = (await client.get("/contacts", params={"limit": 200}, headers=owner)).json()["items"]
    seen = [r["last_contact_at"] for r in rows if r["last_contact_at"]]
    assert seen == sorted(seen, reverse=True) and all(r["last_contact_at"] is None for r in rows[len(seen):])
    by_name = names(await client.get("/contacts", params={"sort": "name", "limit": 200}, headers=owner))
    assert by_name == sorted(by_name)

    # Searching never reveals a VIP to someone who may not see them, not even by their phone number.
    async with tenant_session(database["a"]) as db:
        vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True), Contact.vip_owner_user_id.is_not(None)))).scalars().first()
        vphone = (await db.execute(select(ContactIdentity.value).where(ContactIdentity.contact_id == vip.id, ContactIdentity.kind == "phone"))).scalar_one()
    assert names(await client.get("/contacts", params={"q": vphone[2:]}, headers=owner)) == [vip.display_name]
    assert names(await client.get("/contacts", params={"q": vphone[2:]}, headers=sales)) == []
