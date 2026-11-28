"""The search box and New message: one search across clients, cars, conversations and deals, with VIPs hidden as on
every list; and a person writing to a client first, through the same send path (opt-outs block it, WhatsApp's
24-hour rule is said up front)."""

import pytest
from ondra_api import channels
from ondra_api.db import tenant_session
from ondra_core.models import Contact, Conversation, Message
from sqlalchemy import select, text

from .conftest import login

OWNER, SALES = "owner@prestigemotors.example", "daniel@prestigemotors.example"


@pytest.fixture
def outbox():
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    return channels.mock


async def _contact(tenant_id, name):
    async with tenant_session(tenant_id) as db:
        return (await db.execute(select(Contact).where(Contact.display_name == name))).scalar_one()


async def test_search_finds_clients_cars_conversations_and_deals(client, database):
    owner = await login(client, OWNER)
    r = (await client.get("/search", params={"q": "Grace"}, headers=owner)).json()
    assert any(c["name"] == "Grace Kim" for c in r["clients"])
    jordan_phone = (await client.get("/search", params={"q": "Jordan"}, headers=owner)).json()["clients"][0]["detail"]
    assert jordan_phone.startswith("+1")  # the phone is what shows under the name
    digits = "".join(ch for ch in jordan_phone if ch.isdigit())[-7:]
    by_phone = (await client.get("/search", params={"q": f"{digits[:3]} {digits[3:]}"}, headers=owner)).json()
    assert any(c["name"] == "Jordan Price" for c in by_phone["clients"])  # typed with a space, still found
    cars = (await client.get("/search", params={"q": "Highlander"}, headers=owner)).json()["cars"]
    assert cars and all("Highlander" in c["title"] for c in cars)
    said = (await client.get("/search", params={"q": "Lagos"}, headers=owner)).json()["conversations"]
    assert said and all("lagos" in s["snippet"].lower() for s in said)
    deals = (await client.get("/search", params={"q": "RAV4"}, headers=owner)).json()["deals"]
    assert any("RAV4" in (d["wants"] or "") for d in deals)


async def test_search_hides_vips_from_people_who_cant_see_them(client, database):
    owner, sales = await login(client, OWNER), await login(client, SALES)
    assert any(c["is_vip"] for c in (await client.get("/search", params={"q": "Robert"}, headers=owner)).json()["clients"])
    r = (await client.get("/search", params={"q": "Robert"}, headers=sales)).json()
    assert not any(c["is_vip"] for c in r["clients"])
    assert not any(c["is_vip"] for c in r["conversations"]) and not any(d["is_vip"] for d in r["deals"])


async def test_new_message_to_a_client_goes_through_the_send_path(client, database, outbox):
    owner = await login(client, OWNER)
    grace = await _contact(database["a"], "Grace Kim")
    opts = (await client.get(f"/contacts/{grace.id}/write-options", headers=owner)).json()
    by = {o["channel"]: o for o in opts["channels"]}
    assert by["sms"]["available"] and not opts["opted_out"]
    r = await client.post("/conversations/start", headers=owner,
                          json={"contact_id": str(grace.id), "channel": "sms", "body": "Hi Grace, your Camry is ready."})
    assert r.status_code == 201, r.text
    assert outbox("sms").outbox[-1].body == "Hi Grace, your Camry is ready."
    conv_id = r.json()["conversation_id"]
    # A second message goes into the same thread, not a new one.
    r2 = await client.post("/conversations/start", headers=owner,
                           json={"contact_id": str(grace.id), "channel": "sms", "body": "We close at 7 today."})
    assert r2.json()["conversation_id"] == conv_id
    async with tenant_session(database["a"]) as db:
        conv = await db.get(Conversation, conv_id)
        sent = (await db.execute(select(Message).where(Message.conversation_id == conv.id, Message.author_type == "user"))).scalars().all()
        assert conv.assigned_user_id is not None and len(sent) >= 2


async def test_new_message_says_why_it_cant_send(client, database, outbox):
    owner, sales = await login(client, OWNER), await login(client, SALES)
    # Opted out: nothing can be sent, on any channel.
    jordan = await _contact(database["a"], "Jordan Price")
    opts = (await client.get(f"/contacts/{jordan.id}/write-options", headers=owner)).json()
    assert opts["opted_out"] and opts["channels"] == []
    r = await client.post("/conversations/start", headers=owner,
                          json={"contact_id": str(jordan.id), "channel": "email", "body": "Hello"})
    assert r.status_code == 409 and "opted out" in r.json()["detail"]
    # WhatsApp: only within 24 hours of their last message.
    async with tenant_session(database["a"]) as db:
        name = (await db.execute(text(
            "SELECT c.display_name FROM contacts c JOIN contact_identities i ON i.contact_id = c.id AND i.kind = 'whatsapp' "
            "WHERE NOT c.is_vip AND NOT EXISTS (SELECT 1 FROM conversations v WHERE v.contact_id = c.id AND v.channel = 'whatsapp' "
            "AND v.last_inbound_at > now() - interval '24 hours') "
            "AND NOT EXISTS (SELECT 1 FROM consents s WHERE s.contact_id = c.id AND s.status = 'opted_out') LIMIT 1"))).scalar_one()
    someone = await _contact(database["a"], name)
    wa = next(o for o in (await client.get(f"/contacts/{someone.id}/write-options", headers=owner)).json()["channels"]
              if o["channel"] == "whatsapp")
    assert not wa["available"] and "24 hours" in wa["why"]
    r = await client.post("/conversations/start", headers=owner,
                          json={"contact_id": str(someone.id), "channel": "whatsapp", "body": "Hello"})
    assert r.status_code == 409 and "24 hours" in r.json()["detail"]
    # A VIP is hidden from a salesperson who isn't theirs, here too.
    robert = await _contact(database["a"], "Robert Hale")
    assert (await client.get(f"/contacts/{robert.id}/write-options", headers=sales)).status_code == 404
