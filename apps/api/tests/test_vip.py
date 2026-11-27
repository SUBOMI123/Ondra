"""Marking a client as a VIP: who may, and that Ondra stops for them at once."""

from datetime import UTC, datetime, timedelta

from ondra_api.db import tenant_session
from ondra_core.models import Contact, Conversation, FollowUp, FollowUpSequence, Message
from sqlalchemy import delete, select, update

from tests.conftest import login


async def test_owners_and_managers_mark_vips_and_ondra_stops_at_once(client, database):
    t = database["a"]
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    async with tenant_session(t) as db:
        c = (await db.execute(select(Contact).where(Contact.display_name == "Ben Carter"))).scalar_one()
        conv = (await db.execute(select(Conversation).where(Conversation.contact_id == c.id).limit(1))).scalar_one_or_none()
        if conv is None:
            conv = Conversation(contact_id=c.id, channel="sms", ai_mode="auto")
            db.add(conv)
            await db.flush()
        draft = Message(conversation_id=conv.id, direction="outbound", author_type="ai", body="Draft for Ben", status="queued", is_draft=True)
        seq = FollowUpSequence(name="Test", steps=[{"after_hours": 24, "write": "ondra", "text": "", "require_approval": True}])
        db.add_all([draft, seq])
        await db.flush()
        fu = FollowUp(sequence_id=seq.id, conversation_id=conv.id, contact_id=c.id, step=0, due_at=datetime.now(UTC) + timedelta(days=1))
        db.add(fu)
        await db.flush()
        ids = (c.id, draft.id, fu.id, seq.id)

    assert (await client.put(f"/contacts/{ids[0]}/vip", json={"vip": True}, headers=sales)).status_code == 403
    manager = await login(client, "manager@prestigemotors.example")
    me = (await client.get("/me", headers=manager)).json()
    r = await client.put(f"/contacts/{ids[0]}/vip", json={"vip": True, "handler_user_id": me["id"]}, headers=manager)
    assert r.status_code == 200, r.text
    assert (r.json()["is_vip"], r.json()["vip_owner_user_id"]) == (True, me["id"])
    async with tenant_session(t) as db:
        assert await db.get(Message, ids[1]) is None  # the draft Ondra wrote is gone
        assert (await db.get(FollowUp, ids[2])).status == "cancelled"  # and nothing more is lined up
    # A salesperson who doesn't look after them no longer sees them at all.
    assert (await client.get(f"/contacts/{ids[0]}", headers=sales)).status_code == 404
    vips = (await client.get("/contacts", params={"vip": "true"}, headers=owner)).json()["items"]
    assert "Ben Carter" in [v["display_name"] for v in vips]
    # Back to a regular client.
    back = (await client.put(f"/contacts/{ids[0]}/vip", json={"vip": False}, headers=owner)).json()
    assert (back["is_vip"], back["vip_owner_user_id"]) == (False, None)
    assert (await client.put(f"/contacts/{ids[0]}/vip", json={"vip": True, "handler_user_id": "00000000-0000-0000-0000-000000000000"}, headers=owner)).status_code == 422
    other = await login(client, "owner@lonestar.example")
    assert (await client.put(f"/contacts/{ids[0]}/vip", json={"vip": True}, headers=other)).status_code == 404  # never another dealer's
    async with tenant_session(t) as db:
        await db.execute(delete(FollowUpSequence).where(FollowUpSequence.id == ids[3]))
        await db.execute(update(Contact).where(Contact.id == ids[0]).values(is_vip=False, vip_owner_user_id=None))
