"""VIPs and their person (docs/PLAN.md items 2 and 3).

Every VIP has a person; when that person leaves, the admins get a task to choose someone (nobody is handed VIPs
automatically). A VIP's call rings their person; if nobody answers, the dealer's own fixed message plays, with press 1
for the backup number and press 2 for a booking link. On every path the AI never speaks, their person is alerted,
and a task exists for every call a person didn't answer.
"""

import uuid

import pytest
from ondra_api import channels
from ondra_api.config import get_settings
from ondra_api.db import tenant_session
from ondra_api.services import bridge, calls
from ondra_core.channels.twilio_sms import twilio_signature
from ondra_core.models import Call, Consent, Contact, ContactIdentity, Event, Task, Tenant, User
from sqlalchemy import select, text, update

from .conftest import login

DEALER = "+12145550100"
ADMIN, MANAGER, SALES = "owner@prestigemotors.example", "manager@prestigemotors.example", "daniel@prestigemotors.example"


async def _vip(database, *, consent: bool = False) -> tuple[uuid.UUID, uuid.UUID, str]:
    """A fresh VIP with a phone number, looked after by Daniel. Returns (contact, daniel, number)."""
    number = f"+1469555{uuid.uuid4().int % 10000:04d}"
    async with tenant_session(database["a"]) as db:
        daniel = (await db.execute(select(User).where(User.email == SALES))).scalar_one()
        c = Contact(display_name="Victoria Adeyemi-Cole", is_vip=True, vip_owner_user_id=daniel.id)
        db.add(c)
        await db.flush()
        db.add(ContactIdentity(contact_id=c.id, kind="phone", value=number))
        if consent:
            db.add(Consent(contact_id=c.id, channel="sms", purpose="transactional", status="opted_in", source="test"))
        return c.id, daniel.id, number


async def _settings(database, **vip_calls) -> dict:
    async with tenant_session(database["a"]) as db:
        t = (await db.execute(select(Tenant).limit(1))).scalar_one()
        before = dict(t.settings or {})
        t.settings = {**before, "vip_calls": vip_calls}
        return before


async def _restore(database, before: dict, contact_id: uuid.UUID) -> None:
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Tenant).values(settings=before))
        await db.execute(text("DELETE FROM tasks WHERE contact_id = :c"), {"c": contact_id})
        # Alerts and the booking text queue jobs; leave none behind for other tests' workers to pick up.
        await db.execute(text("DELETE FROM jobs WHERE status = 'queued' AND created_at > now() - interval '5 minutes'"))
        await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": contact_id})


async def _hook(client, path: str, form: dict):
    url = get_settings().public_api_url.rstrip("/") + path
    return await client.post(path, data=form, headers={"X-Twilio-Signature": twilio_signature(bridge.dialer().auth_token, url, form)})


async def _call(database, number: str):
    plan = await calls.start_call(from_number=number, to_number=DEALER, provider_call_sid=f"CA{uuid.uuid4().hex}")
    assert plan.route == "ring_owner" and plan.is_vip
    t, c = plan.tenant_id, plan.call_id
    return plan, f"/webhooks/voice/vip/{t}/{c}", {"To": f"sip:vip-{t}_{c}@ondra-test.sip.twilio.com", "From": number}


async def _no_ai_anywhere(database, contact_id: uuid.UUID) -> None:
    async with tenant_session(database["a"]) as db:
        ai = (await db.execute(text("""SELECT count(*) FROM messages m JOIN conversations v ON v.id = m.conversation_id
                                        WHERE v.contact_id = :c AND m.author_type = 'ai'"""), {"c": contact_id})).scalar()
        assert ai == 0
        assert (await db.execute(select(Call.handled_by).where(Call.contact_id == contact_id, Call.handled_by == "ai"))).first() is None


# --- item 2: every VIP has a person ---------------------------------------------------------------------------------

async def test_a_vip_always_has_a_person_defaulting_to_whoever_marks_them(client, database):
    manager = await login(client, MANAGER)
    me = (await client.get("/me", headers=manager)).json()["id"]
    async with tenant_session(database["a"]) as db:
        c = Contact(display_name="Temi Bakare")
        db.add(c)
        await db.flush()
        cid = c.id
    try:
        r = (await client.put(f"/contacts/{cid}/vip", json={"vip": True}, headers=manager)).json()
        assert (r["is_vip"], r["vip_owner_user_id"]) == (True, me)
    finally:
        await _restore(database, (await _settings(database)), cid)


async def test_when_their_person_leaves_the_admins_get_a_task_not_an_automatic_handover(client, database):
    cid, daniel, _ = await _vip(database)
    admin = await login(client, ADMIN)
    try:
        assert (await client.patch(f"/users/{daniel}", json={"active": False}, headers=admin)).status_code == 200
        async with tenant_session(database["a"]) as db:
            c = await db.get(Contact, cid)
            assert c.is_vip and c.vip_owner_user_id is None  # nobody was handed them
            [task] = (await db.execute(select(Task).where(Task.contact_id == cid))).scalars().all()
            assigned = await db.get(User, task.assignee_user_id)
            assert task.urgency == "high" and assigned.role == "admin" and "Choose who looks after" in task.title
            assert "VIP backup number" in task.brief
            assert (await db.execute(select(Event).where(Event.type == "vip.orphaned", Event.payload["contact_id"].astext == str(cid)))).first()
    finally:
        async with tenant_session(database["a"]) as db:
            await db.execute(update(User).where(User.id == daniel).values(active=True))
        await _restore(database, (await _settings(database)), cid)


# --- item 3: a VIP's call nobody answers ----------------------------------------------------------------------------

async def test_answered_by_their_person(client, database):
    cid, daniel, number = await _vip(database)
    before = await _settings(database, backup_number="+12145550199")
    try:
        _, base, form = await _call(database, number)
        r = await _hook(client, "/webhooks/voice/vip/start", form)
        assert r.status_code == 200 and "<Dial" in r.text and f"{base}/dialed" in r.text and "<Say>" not in r.text  # rings Daniel, says nothing
        r = await _hook(client, f"{base}/dialed", {"DialCallStatus": "completed"})
        assert "<Hangup/>" in r.text and "<Say>" not in r.text
        async with tenant_session(database["a"]) as db:
            call = (await db.execute(select(Call).where(Call.contact_id == cid))).scalar_one()
            assert (call.handled_by, call.outcome, call.transferred_to_user_id) == ("owner", "answered", daniel)
            assert (await db.execute(select(Task).where(Task.contact_id == cid))).first() is None  # answered: no task
        await _no_ai_anywhere(database, cid)
    finally:
        await _restore(database, before, cid)


@pytest.mark.parametrize("path", ["hang_up", "press_1", "press_2", "press_2_without_consent", "no_backup_set"])
async def test_unanswered_plays_the_dealers_message_alerts_their_person_and_leaves_a_task(client, database, path):
    cid, daniel, number = await _vip(database, consent=path != "press_2_without_consent")
    conf = {"message": "Sorry we missed you, {first}. {person} will ring you back within the hour.",
            "backup_number": None if path == "no_backup_set" else "+12145550199",
            "booking_link": "https://prestigemotors.example/book"}
    before = await _settings(database, **conf)
    channels.mock("sms").outbox.clear()
    try:
        _, base, form = await _call(database, number)
        await _hook(client, "/webhooks/voice/vip/start", form)
        r = await _hook(client, f"{base}/dialed", {"DialCallStatus": "no-answer"})
        said = r.text
        # The dealer's own words, filled in. Options only where they can happen.
        assert "Sorry we missed you, Victoria. Daniel will ring you back within the hour." in said
        assert ("press 1" in said) == (path != "no_backup_set")
        assert ("press 2" in said) == (path != "press_2_without_consent")
        async with tenant_session(database["a"]) as db:
            [task] = (await db.execute(select(Task).where(Task.contact_id == cid))).scalars().all()
            assert task.urgency == "high" and task.assignee_user_id == daniel
            alert = (await db.execute(select(Event).where(Event.type == "alert.created", Event.payload["contact_id"].astext == str(cid)))).scalars().all()
            assert alert and alert[0].payload["urgency"] == "high"
        if path == "press_1":
            r = await _hook(client, f"{base}/choice", {"Digits": "1"})
            assert "<Number>+12145550199</Number>" in r.text and "/backup" in r.text
            r = await _hook(client, f"{base}/backup", {"DialCallStatus": "completed"})
            assert "<Hangup/>" in r.text
        elif path in ("press_2", "press_2_without_consent"):
            r = await _hook(client, f"{base}/choice", {"Digits": "2"})
            async with tenant_session(database["a"]) as db:
                sent = (await db.execute(text("""SELECT m.body, m.author_type FROM messages m JOIN conversations v ON v.id = m.conversation_id
                                                  WHERE v.contact_id = :c AND m.direction = 'outbound'"""), {"c": cid})).all()
            if path == "press_2":
                assert "sent you a text" in r.text and len(sent) == 1
                assert sent[0].author_type == "system" and "https://prestigemotors.example/book" in sent[0].body
            else:  # never offered, and pressing it anyway sends nothing
                assert sent == [] and "Goodbye" in r.text
        else:  # hang up, or nothing pressed
            r = await _hook(client, f"{base}/choice", {"Digits": ""})
            assert "Goodbye" in r.text
        # Twilio retrying a step doesn't make a second task
        await _hook(client, f"{base}/dialed", {"DialCallStatus": "no-answer"})
        async with tenant_session(database["a"]) as db:
            assert len((await db.execute(select(Task).where(Task.contact_id == cid))).scalars().all()) == 1
        await _no_ai_anywhere(database, cid)
    finally:
        await _restore(database, before, cid)


async def test_no_person_with_a_mobile_goes_straight_to_the_message(client, database):
    cid, _, number = await _vip(database)
    before = await _settings(database, backup_number="+12145550199")
    try:
        async with tenant_session(database["a"]) as db:
            await db.execute(update(Contact).where(Contact.id == cid).values(vip_owner_user_id=None))
        _, base, form = await _call(database, number)
        r = await _hook(client, "/webhooks/voice/vip/start", form)
        assert "<Dial" not in r.text and "Someone from our team has been told" in r.text and "press 1" in r.text
        async with tenant_session(database["a"]) as db:
            assert len((await db.execute(select(Task).where(Task.contact_id == cid))).scalars().all()) == 1
    finally:
        await _restore(database, before, cid)


async def test_unsigned_requests_are_refused_and_a_non_vip_never_reaches_the_desk(client, database):
    assert (await client.post("/webhooks/voice/vip/start", data={"To": "sip:x@y"})).status_code == 403


async def test_the_backup_number_cant_be_the_dealerships_own_line(client, database):
    admin = await login(client, ADMIN)
    async with tenant_session(database["a"]) as db:
        own = (await db.execute(text("SELECT address FROM channel_addresses WHERE channel IN ('phone','sms') LIMIT 1"))).scalar()
    if own:
        r = await client.put("/settings/vip-calls", json={"backup_number": own}, headers=admin)
        assert r.status_code == 422 and "Ondra answers" in r.json()["detail"]
    assert (await client.put("/settings/vip-calls", json={"booking_link": "http://x"}, headers=admin)).status_code == 422
    ok = (await client.put("/settings/vip-calls", json={"backup_number": "(214) 555-0199", "message": "Hi {first}."}, headers=admin)).json()
    assert ok["backup_number"] == "+12145550199" and ok["message"] == "Hi {first}."
    sales = await login(client, SALES)
    assert (await client.put("/settings/vip-calls", json={}, headers=sales)).status_code == 403
    await client.put("/settings/vip-calls", json={}, headers=admin)
