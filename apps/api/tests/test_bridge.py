"""Calling a missed caller back through the dealer's line: Ondra rings the salesperson, they press 1, it dials the
customer showing the dealer's number, and the result is logged as the call-back without anyone ticking it."""

import uuid

import httpx
from ondra_api import worker
from ondra_api.db import tenant_session
from ondra_api.services import bridge, calls
from ondra_core.channels.twilio_sms import twilio_signature
from ondra_core.models import Call, Event, Task, User
from sqlalchemy import select, text, update

from .conftest import login

DEALER = "+12145550100"
CALLER = "+14695550177"


async def _missed(database) -> uuid.UUID:
    plan = await calls.start_call(from_number=CALLER, to_number=DEALER, provider_call_sid=f"CA{uuid.uuid4().hex}")
    await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="no answer")
    await worker.run_once()
    return plan.call_id


async def _hook(client, placed, step: str, form: dict):
    url = placed.status_callback.rsplit("/", 1)[0] + f"/{step}"
    sig = twilio_signature(bridge.dialer().auth_token, url, form)
    return await client.post(url.replace(bridge.get_settings().public_api_url.rstrip("/"), ""), data=form,
                             headers={"X-Twilio-Signature": sig})


async def _cleanup(database):
    async with tenant_session(database["a"]) as db:
        await db.execute(text("DELETE FROM contacts WHERE display_name = :n"), {"n": CALLER})


async def test_press_one_and_talk_marks_them_called_back(client, database):
    missed = await _missed(database)
    owner = await login(client, "owner@prestigemotors.example")
    r = await client.post(f"/calls/{missed}/bridge", headers=owner)
    assert r.status_code == 201, r.text
    placed = bridge.dialer().placed[-1]
    # Ondra rings the salesperson first, from the number the customer rang, and asks them to press 1.
    assert placed.to == "+12145550100" and placed.from_ == DEALER
    assert '<Gather numDigits="1"' in placed.twiml and "Press 1" in placed.twiml and "/connect" in placed.twiml
    # Someone else can't start a second call-back over this one.
    assert (await client.post(f"/calls/{missed}/bridge", headers=owner)).status_code == 409

    rows = (await client.get("/calls?show=missed", headers=owner)).json()["items"]
    assert next(i for i in rows if i["id"] == str(missed))["calling"]["state"] == "ringing_you"
    # A call-back under way shows on the caller's row only, and never as Ondra on a call.
    assert not any(i["direction"] == "outbound" or i["live"] for i in (await client.get("/calls", headers=owner)).json()["items"]
                   if i["contact"] and i["contact"]["name"] == CALLER)
    convs = (await client.get("/conversations?view=all", headers=owner)).json()["items"]
    row = next(c for c in convs if c["contact"]["name"] == CALLER)
    assert row["last_message"]["author"] != "ai" and row["last_message"]["body"] == "Samuel called them back"

    assert (await _hook(client, placed, "status", {"CallSid": placed.sid, "CallStatus": "in-progress"})).status_code == 204
    dial = await _hook(client, placed, "connect", {"CallSid": placed.sid, "Digits": "1"})
    # The customer sees the dealer's number, never the salesperson's.
    assert f'<Dial callerId="{DEALER}"' in dial.text and f">{CALLER}</Number>" in dial.text
    assert 'machineDetection="Enable"' in dial.text and "/amd" in dial.text
    done = await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "95"})
    assert "<Hangup/>" in done.text
    # Twilio retries: nothing is recorded twice.
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "95"})

    async with tenant_session(database["a"]) as db:
        call = await db.get(Call, missed)
        assert call.callback_done_at is not None
        tries = (await db.execute(select(Event).where(Event.type == "callback.first_try",
                                                      Event.payload["contact_id"].astext == str(call.contact_id)))).scalars().all()
        assert len(tries) == 1 and tries[0].payload["result"] == "reached"
        assert all(t.status == "done" for t in (await db.execute(select(Task).where(Task.contact_id == call.contact_id))).scalars())
    out = next(i for i in (await client.get("/calls", headers=owner)).json()["items"]
               if i["direction"] == "outbound" and i["from_number"] == DEALER and i["contact"]["id"] == str(call.contact_id))
    assert out["line"] == "Samuel called them back" and out["duration_s"] == 95
    # Outbound call-backs aren't counted as calls that came in.
    assert all(i["direction"] == "inbound" for i in (await client.get("/calls?show=people", headers=owner)).json()["items"])
    await _cleanup(database)


async def test_a_short_call_is_a_try_and_they_stay_on_the_list(client, database):
    missed = await _missed(database)
    owner = await login(client, "owner@prestigemotors.example")
    await client.post(f"/calls/{missed}/bridge", headers=owner)
    placed = bridge.dialer().placed[-1]
    await _hook(client, placed, "connect", {"CallSid": placed.sid, "Digits": "1"})
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "22"})
    row = next(i for i in (await client.get("/calls?show=missed", headers=owner)).json()["items"] if i["id"] == str(missed))
    assert row["needs_callback"] and row["attempts"][-1]["how"] == "short"
    async with tenant_session(database["a"]) as db:
        e = (await db.execute(select(Event).where(Event.type == "callback.first_try",
                                                  Event.payload["call_ids"].astext.contains(str(missed))))).scalar_one()
        assert e.payload["result"] == "short"
    # A second try, now through Ondra again, with no answer: still waiting, and not a second first try.
    await client.post(f"/calls/{missed}/bridge", headers=owner)
    placed = bridge.dialer().placed[-1]
    await _hook(client, placed, "connect", {"CallSid": placed.sid, "Digits": "1"})
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "no-answer", "DialCallDuration": "0"})
    row = next(i for i in (await client.get("/calls?show=missed", headers=owner)).json()["items"] if i["id"] == str(missed))
    assert row["needs_callback"] and [a["how"] for a in row["attempts"]] == ["short", "no_answer"]
    async with tenant_session(database["a"]) as db:
        assert len((await db.execute(select(Event).where(Event.type == "callback.first_try",
                                                         Event.payload["call_ids"].astext.contains(str(missed))))).all()) == 1
    await _cleanup(database)


async def test_nothing_pressed_means_nobody_is_called(client, database):
    missed = await _missed(database)
    owner = await login(client, "owner@prestigemotors.example")
    await client.post(f"/calls/{missed}/bridge", headers=owner)
    placed = bridge.dialer().placed[-1]
    r = await _hook(client, placed, "connect", {"CallSid": placed.sid})  # their voicemail picked up: no digits
    assert "<Dial" not in r.text and "<Hangup/>" in r.text
    await _hook(client, placed, "status", {"CallSid": placed.sid, "CallStatus": "completed"})
    row = next(i for i in (await client.get("/calls?show=missed", headers=owner)).json()["items"] if i["id"] == str(missed))
    assert row["needs_callback"] and row["attempts"] == [] and not row.get("calling")
    assert not any(i["direction"] == "outbound" and i["contact"]["name"] == CALLER
                   for i in (await client.get("/calls", headers=owner)).json()["items"] if i["contact"])
    # Webhooks must be signed.
    url = placed.status_callback.replace(bridge.get_settings().public_api_url.rstrip("/"), "")
    assert (await client.post(url, data={"CallStatus": "completed"}, headers={"X-Twilio-Signature": "nope"})).status_code == 403
    await _cleanup(database)


async def test_ondra_needs_your_number_and_only_missed_calls_are_called_back(client, database):
    missed = await _missed(database)
    sales = await login(client, "daniel@prestigemotors.example")
    async with tenant_session(database["a"]) as db:
        await db.execute(update(User).where(User.email == "daniel@prestigemotors.example").values(phone=None))
    try:
        r = await client.post(f"/calls/{missed}/bridge", headers=sales)
        assert r.status_code == 409 and "mobile number" in r.json()["detail"]
    finally:
        async with tenant_session(database["a"]) as db:
            await db.execute(update(User).where(User.email == "daniel@prestigemotors.example").values(phone="+12145550102"))
    owner = await login(client, "owner@prestigemotors.example")
    answered = next(i for i in (await client.get("/calls?show=ondra", headers=owner)).json()["items"])
    assert (await client.post(f"/calls/{answered['id']}/bridge", headers=owner)).status_code == 409
    await _cleanup(database)


async def test_the_twilio_request_matches_the_docs():
    seen = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], request.content.decode()
        return httpx.Response(201, json={"sid": "CA123"})

    d = bridge.TwilioDialer(account_sid="AC1", auth_token="tok", client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    sid = await d.place(to="+12145550102", from_="+12145550100", twiml="<Response/>", status_callback="https://x.example/s")
    assert sid == "CA123" and seen["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC1/Calls.json"
    assert seen["auth"].startswith("Basic ")
    body = seen["body"]
    assert "To=%2B12145550102" in body and "From=%2B12145550100" in body and "Twiml=%3CResponse%2F%3E" in body
    assert body.count("StatusCallbackEvent=") == 2 and "Timeout=25" in body

    def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "unverified caller id"})

    d = bridge.TwilioDialer(account_sid="AC1", auth_token="tok", client=httpx.AsyncClient(transport=httpx.MockTransport(fail)))
    try:
        await d.place(to="+1", from_="+1", twiml="<Response/>", status_callback="https://x.example/s")
        raise AssertionError("should have failed")
    except bridge.BridgeError:
        pass


async def _connected(client, database, owner):
    missed = await _missed(database)
    await client.post(f"/calls/{missed}/bridge", headers=owner)
    placed = bridge.dialer().placed[-1]
    await _hook(client, placed, "connect", {"CallSid": placed.sid, "Digits": "1"})
    return missed, placed


async def _state(database, missed):
    async with tenant_session(database["a"]) as db:
        call = await db.get(Call, missed)
        task = (await db.execute(select(Task).where(Task.contact_id == call.contact_id))).scalars().all()
        tries = (await db.execute(select(Event).where(Event.type == "callback.first_try",
                                                      Event.payload["contact_id"].astext == str(call.contact_id)))).scalars().all()
        return call, task, tries


async def test_a_person_picking_up_counts_even_on_a_short_call(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    missed, placed = await _connected(client, database, owner)
    assert (await _hook(client, placed, "amd", {"CallSid": "CAchild", "AnsweredBy": "human"})).status_code == 204
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "20"})
    call, tasks, tries = await _state(database, missed)
    assert call.callback_done_at is not None and all(t.status == "done" for t in tasks)
    assert [e.payload["result"] for e in tries] == ["reached"]
    await _cleanup(database)


async def test_their_voicemail_is_a_try_even_on_a_long_message(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    missed, placed = await _connected(client, database, owner)
    await _hook(client, placed, "amd", {"CallSid": "CAchild", "AnsweredBy": "machine_start"})
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "95"})
    call, tasks, tries = await _state(database, missed)
    assert call.callback_done_at is None and any(t.status == "open" for t in tasks)
    assert [e.payload["result"] for e in tries] == ["voicemail"]
    row = next(i for i in (await client.get("/calls?show=missed", headers=owner)).json()["items"] if i["id"] == str(missed))
    assert row["needs_callback"] and row["attempts"][-1]["how"] == "voicemail"
    out = next(i for i in (await client.get("/calls", headers=owner)).json()["items"]
               if i["direction"] == "outbound" and i["contact"] and i["contact"]["name"] == CALLER)
    assert out["line"] == "Samuel called them back and got their voicemail"
    await _cleanup(database)


async def test_a_late_verdict_corrects_what_was_recorded(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    # 95 s and no verdict yet: counted as spoke to them...
    missed, placed = await _connected(client, database, owner)
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "95"})
    call, tasks, _ = await _state(database, missed)
    assert call.callback_done_at is not None
    # ...then detection says it was a machine: back on the list, the task reopened, the try kept as voicemail.
    await _hook(client, placed, "amd", {"CallSid": "CAchild", "AnsweredBy": "machine_start"})
    call, tasks, tries = await _state(database, missed)
    assert call.callback_done_at is None and any(t.status == "open" for t in tasks)
    assert [(e.payload["result"], e.payload.get("undone")) for e in tries] == [("voicemail", False)]
    await _cleanup(database)

    # The other way: 20 s with no verdict is a short call (a try), then detection says a person: called back.
    missed, placed = await _connected(client, database, owner)
    await _hook(client, placed, "dialed", {"CallSid": placed.sid, "DialCallStatus": "completed", "DialCallDuration": "20"})
    assert (await _state(database, missed))[0].callback_done_at is None
    await _hook(client, placed, "amd", {"CallSid": "CAchild", "AnsweredBy": "human"})
    call, tasks, tries = await _state(database, missed)
    assert call.callback_done_at is not None and all(t.status == "done" for t in tasks)
    assert [e.payload["result"] for e in tries] == ["reached"]
    # Detection that can't tell ("unknown") falls back to the length of the call, and changes nothing here.
    assert bridge.result_of("completed", 95, "unknown") == "spoke" and bridge.result_of("completed", 20, "unknown") == "short"
    assert bridge.result_of("no-answer", 0, "human") == "no_answer" and bridge.result_of("completed", 5, "fax") == "voicemail"
    await _cleanup(database)
