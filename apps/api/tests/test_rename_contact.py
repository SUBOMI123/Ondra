"""Correcting a client's name (founder, 2026-11-28): a name Ondra heard on a call is flagged until a person checks
it; a person's correction sticks, and Ondra never overwrites it."""

import uuid

from ondra_api.db import tenant_session
from ondra_api.services.agent_tools import DbToolBackend
from ondra_core.models import Contact, ContactIdentity, Conversation
from sqlalchemy import select, text

from .conftest import login


async def test_a_name_heard_on_a_call_is_flagged_staff_fix_it_and_it_sticks(client, database):
    t = database["a"]
    number = f"+1214555{uuid.uuid4().int % 10000:04d}"
    async with tenant_session(t) as db:
        c = Contact(display_name=number, preferred_channel="phone")
        db.add(c)
        await db.flush()
        db.add(ContactIdentity(contact_id=c.id, kind="phone", value=number))
        conv = Conversation(contact_id=c.id, channel="phone", ai_mode="auto")
        db.add(conv)
        await db.flush()
        await DbToolBackend(db, contact=c, conversation=conv, price_disclosure="none", open_now=True).update_lead_fields({"name": "Sue Bommy"})  # as speech recognition heard it
        cid = c.id
    try:
        sales = await login(client, "daniel@prestigemotors.example")
        got = (await client.get(f"/contacts/{cid}", headers=sales)).json()
        assert (got["display_name"], got["name_source"]) == ("Sue Bommy", "call")
        r = await client.patch(f"/contacts/{cid}", json={"display_name": "  Subomi   Adeyemi "}, headers=sales)
        assert r.status_code == 200 and (r.json()["display_name"], r.json()["name_source"]) == ("Subomi Adeyemi", "staff")
        assert (await client.patch(f"/contacts/{cid}", json={"display_name": "   "}, headers=sales)).status_code == 422
        assert (await client.patch(f"/contacts/{uuid.uuid4()}", json={"display_name": "X"}, headers=sales)).status_code == 404
        # Ondra hearing a name again later never replaces the one a person saved.
        async with tenant_session(t) as db:
            c = await db.get(Contact, cid)
            conv = (await db.execute(select(Conversation).where(Conversation.contact_id == cid))).scalar_one()
            await DbToolBackend(db, contact=c, conversation=conv, price_disclosure="none", open_now=True).update_lead_fields({"name": "Sue Bommy"})
            assert (c.display_name, c.name_source) == ("Subomi Adeyemi", "staff")
    finally:
        async with tenant_session(t) as db:
            await db.execute(text("DELETE FROM deals WHERE contact_id = :c"), {"c": cid})
            await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": cid})


async def test_a_vip_can_only_be_renamed_by_people_who_can_see_them(client, database):
    async with tenant_session(database["a"]) as db:
        vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True), Contact.vip_owner_user_id.is_(None)).limit(1))).scalar_one_or_none()
        if vip is None:
            vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True)).limit(1))).scalar_one()
        name, vid, owner = vip.display_name, vip.id, vip.vip_owner_user_id
    sales = await login(client, "maria@prestigemotors.example")
    me = (await client.get("/me", headers=sales)).json()["id"]
    if str(owner) != me:
        assert (await client.patch(f"/contacts/{vid}", json={"display_name": "Someone Else"}, headers=sales)).status_code == 404
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Contact, vid)).display_name == name
