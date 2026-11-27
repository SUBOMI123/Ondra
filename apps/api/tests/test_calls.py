"""Calls: routing before anyone speaks, missed calls under the consent rule, summaries, and the calls API."""

import uuid

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import calls
from ondra_core.models import Call, Event, Job, MetricDay, Task, Tenant, User
from sqlalchemy import delete, select, text, update

from .conftest import login

DEALER = "+12145550100"
NEW_CALLERS = ("+14695550142", "+12145559998")  # callers these tests create; removed after each test


@pytest.fixture(autouse=True)
async def _remove_new_callers(database):
    yield
    async with tenant_session(database["a"]) as db:
        await db.execute(text("DELETE FROM contacts WHERE display_name = ANY(:n)"), {"n": list(NEW_CALLERS)})


async def _phone_of(tenant_id, name):
    async with tenant_session(tenant_id) as db:
        return (await db.execute(text(
            "SELECT i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id AND i.kind = 'phone' "
            "WHERE c.display_name = :n"), {"n": name})).scalar_one()


def _sid():
    return f"CA{uuid.uuid4().hex}"


async def test_regular_caller_goes_to_the_ai_and_the_call_is_recorded_once(database):
    phone = await _phone_of(database["a"], "Ben Carter")
    sid = _sid()
    plan = await calls.start_call(from_number=phone, to_number=DEALER, provider_call_sid=sid)
    assert plan.route == "ai" and plan.known and plan.caller_name == "Ben Carter" and not plan.is_vip
    again = await calls.start_call(from_number=phone, to_number=DEALER, provider_call_sid=sid)
    assert again.call_id == plan.call_id  # the provider retried: same call
    async with tenant_session(database["a"]) as db:
        call = await db.get(Call, plan.call_id)
        assert call.direction == "inbound" and call.from_number == phone and call.conversation_id == plan.conversation_id


async def test_vip_calls_ring_the_owner_and_never_reach_the_ai(database):
    phone = await _phone_of(database["a"], "Robert Hale")
    plan = await calls.start_call(from_number=phone, to_number=DEALER, provider_call_sid=_sid())
    async with tenant_session(database["a"]) as db:
        owner = (await db.execute(select(User).where(User.role == "owner"))).scalar_one()
    assert plan.route == "ring_owner" and plan.is_vip and plan.ring_number == owner.phone


async def test_unknown_dealer_number_is_ignored_and_voice_off_rings_the_team(database):
    assert await calls.start_call(from_number="+12145559999", to_number="+19995550000", provider_call_sid=_sid()) is None
    async with tenant_session(database["a"]) as db:
        t = (await db.execute(select(Tenant))).scalar_one()
        t.settings = {**(t.settings or {}), "voice_ai": False}
    plan = await calls.start_call(from_number="+12145559998", to_number=DEALER, provider_call_sid=_sid())
    assert plan.route == "ring_team" and plan.ring_number
    async with tenant_session(database["a"]) as db:
        t = (await db.execute(select(Tenant))).scalar_one()
        t.settings = {k: v for k, v in (t.settings or {}).items() if k != "voice_ai"}


async def test_missed_call_texts_back_only_with_recorded_consent(database):
    channels.mock("sms").outbox.clear()
    # Seeded contact with a recorded SMS opt-in: text-back plus a call-back task.
    phone = await _phone_of(database["a"], "Ethan Walker")
    plan = await calls.start_call(from_number=phone, to_number=DEALER, provider_call_sid=_sid())
    await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="no answer")
    await worker.run_once()
    assert len(channels.mock("sms").outbox) == 1 and "Sorry we missed your call" in channels.mock("sms").outbox[0].body

    # A new caller with no recorded consent: no automated text, only a task for a person.
    stranger = "+14695550142"
    plan2 = await calls.start_call(from_number=stranger, to_number=DEALER, provider_call_sid=_sid())
    await calls.finish_call(plan2.tenant_id, plan2.call_id, handled_by="missed", outcome="no answer")
    await worker.run_once()
    assert len(channels.mock("sms").outbox) == 1
    async with tenant_session(database["a"]) as db:
        tasks = (await db.execute(select(Task).where(Task.contact_id.in_([plan.contact_id, plan2.contact_id])))).scalars().all()
        assert len(tasks) == 2 and all("Call" in t.title for t in tasks)
        skipped = (await db.execute(select(Event).where(Event.type == "call.text_back_skipped"))).scalars().all()
        assert any(e.payload["call_id"] == str(plan2.call_id) for e in skipped)
        await db.execute(update(Task).where(Task.id.in_([t.id for t in tasks])).values(status="done"))


async def test_missed_vip_call_alerts_the_owner_and_sends_no_text(database):
    channels.mock("sms").outbox.clear()
    phone = await _phone_of(database["a"], "Robert Hale")
    plan = await calls.start_call(from_number=phone, to_number=DEALER, provider_call_sid=_sid())
    await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="owner didn't answer")
    await worker.run_once()
    assert channels.mock("sms").outbox == []
    async with tenant_session(database["a"]) as db:
        task = (await db.execute(select(Task).where(Task.contact_id == plan.contact_id, Task.title.like("%(VIP)%"))
                                 .order_by(Task.created_at.desc()))).scalars().first()
        assert task.urgency == "high"
        task.status = "done"


async def test_answered_call_gets_a_summary_but_never_for_a_vip(database):
    phone = await _phone_of(database["a"], "Grace Kim")
    plan = await calls.start_call(from_number=phone, to_number=DEALER, provider_call_sid=_sid())
    transcript = [{"who": "agent", "text": "Prestige Motors, this is Ondra."},
                  {"who": "caller", "text": "I'd like to book an oil change for my Camry on Tuesday."}]
    await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="ai", outcome="booked",
                            transcript=transcript, metrics={"summary": {"turns": 3, "avg_ms": 820}})
    async with tenant_session(database["a"]) as db:
        job = (await db.execute(select(Job).where(Job.kind == "call_summary", Job.payload["call_id"].astext == str(plan.call_id)))).scalar_one()
    await worker.run_once()
    async with tenant_session(database["a"]) as db:
        call = await db.get(Call, plan.call_id)
        assert call.summary and "oil change" in call.summary.lower() and (await db.get(Job, job.id)).status == "done"
        assert call.recording_url is None and call.metrics["summary"]["avg_ms"] == 820

    vip = await _phone_of(database["a"], "Robert Hale")
    plan2 = await calls.start_call(from_number=vip, to_number=DEALER, provider_call_sid=_sid())
    await calls.finish_call(plan2.tenant_id, plan2.call_id, handled_by="owner", outcome="talked",
                            transcript=[{"who": "caller", "text": "It's Robert."}])
    async with tenant_session(database["a"]) as db:
        assert (await db.execute(select(Job).where(Job.kind == "call_summary", Job.payload["call_id"].astext == str(plan2.call_id)))).first() is None


async def test_calls_api_hides_vips_from_sales_and_records_call_backs(client, database):
    for name, handled in (("Robert Hale", "owner"), ("Ben Carter", "missed")):
        plan = await calls.start_call(from_number=await _phone_of(database["a"], name), to_number=DEALER, provider_call_sid=_sid())
        await calls.finish_call(plan.tenant_id, plan.call_id, handled_by=handled, outcome="test")
    await worker.run_once()  # send the text-back now, so no queued job leaks into other tests
    owner, sales = await login(client, "owner@prestigemotors.example"), await login(client, "daniel@prestigemotors.example")
    items = (await client.get("/calls", headers=owner)).json()["items"]
    assert any(c["contact"] and c["contact"]["is_vip"] for c in items)
    assert not any(c["contact"] and c["contact"]["is_vip"] for c in (await client.get("/calls", headers=sales)).json()["items"])
    vip_call = next(c for c in items if c["contact"] and c["contact"]["is_vip"])
    assert vip_call["summary"] is None
    assert (await client.get(f"/calls/{vip_call['id']}", headers=sales)).status_code == 404
    missed = next(c for c in items if c["needs_callback"] and c["contact"] and not c["contact"]["is_vip"])
    r = await client.post(f"/calls/{missed['id']}/called-back", headers=sales)
    assert r.status_code == 200 and r.json()["needs_callback"] is False
    detail = (await client.get(f"/calls/{items[0]['id']}", headers=owner)).json()
    assert "transcript" in detail and "latency" in detail
    # Calls show in the client's thread and timeline; a VIP's carries no summary.
    conv = (await client.get(f"/conversations/{vip_call['conversation_id']}", headers=owner)).json()
    assert conv["calls"] and all(c["summary"] is None for c in conv["calls"])
    tl = (await client.get(f"/contacts/{missed['contact']['id']}/timeline", headers=owner)).json()["items"]
    assert any(i["kind"] == "call" and i["handled_by"] == "missed" for i in tl)



async def test_the_inbox_has_one_thread_per_client_across_channels(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    rows = (await client.get("/conversations", headers=owner)).json()["items"]
    names = [r["contact"]["name"] for r in rows]
    assert len(names) == len(set(names))  # nobody twice
    row = {r["contact"]["name"]: r for r in rows}
    # Ondra answered Grace's call: her thread is in Ondra's view, previewing the call.
    assert row["Grace Kim"]["bucket"] == "ondra" and row["Grace Kim"]["last_message"]["kind"] == "call"
    # Jordan texted (opted out) and then called: one thread, the most specific reason a person is needed.
    assert row["Jordan Price"]["reason"] == "Call Jordan back" and set(row["Jordan Price"]["channels"]) == {"sms", "phone"}
    # Robert, a VIP: his waiting text outranks the call that reached the owner.
    assert row["Robert Hale"]["reason"] == "VIP waiting for you" and row["Robert Hale"]["bucket"] == "needs"

    # Jordan's thread holds his texts and his call; replies go where he last wrote; take over covers both channels.
    d = (await client.get(f"/conversations/{row['Jordan Price']['id']}", headers=owner)).json()
    sms = next(c["id"] for c in d["channels"] if c["channel"] == "sms")
    assert {m["channel"] for m in d["messages"]} == {"sms"} and d["calls"] and d["reply_to"] == sms
    await client.post(f"/conversations/{row['Jordan Price']['id']}/takeover", headers=owner)
    d = (await client.get(f"/conversations/{sms}", headers=owner)).json()
    assert d["ai_mode"] == "off" and all(c["ai_mode"] == "off" for c in d["channels"])
    await client.post(f"/conversations/{sms}/handback", headers=owner)
    d = (await client.get(f"/conversations/{sms}", headers=owner)).json()
    assert all(c["ai_mode"] == "auto" for c in d["channels"])


async def test_missed_calls_say_why_no_text_was_sent(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    jordan = next(c for c in (await client.get("/calls", headers=owner)).json()["items"]
                  if c["contact"] and c["contact"]["name"] == "Jordan Price")
    assert jordan["needs_callback"] and jordan["text_back"] == {"sent": False, "reason": "opted out"}
    assert jordan["line"] == "Missed call"


async def test_a_call_never_stays_live_forever(client, database):
    plan = await calls.start_call(from_number="+12145551003", to_number=DEALER, provider_call_sid=_sid())
    owner = await login(client, "owner@prestigemotors.example")
    live = next(c for c in (await client.get("/calls", headers=owner)).json()["items"] if c["id"] == str(plan.call_id))
    assert live["live"] and live["line"] == "On a call now"
    async with tenant_session(database["a"]) as db:
        await db.execute(update(Call).where(Call.id == plan.call_id).values(started_at=text("now() - interval '3 hours'")))
    stale = next(c for c in (await client.get("/calls", headers=owner)).json()["items"] if c["id"] == str(plan.call_id))
    assert not stale["live"]


async def test_the_inbox_is_newest_activity_first_across_messages_and_calls(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    stamps = [r["last_message"]["at"] for r in (await client.get("/conversations", headers=owner)).json()["items"]
              if r["last_message"]["at"]]
    assert stamps == sorted(stamps, reverse=True)


async def test_a_caller_who_rings_again_is_one_call_back_one_task_and_one_text(client, database):
    channels.mock("sms").outbox.clear()
    stranger = NEW_CALLERS[1]
    for _ in range(3):
        plan = await calls.start_call(from_number=stranger, to_number=DEALER, provider_call_sid=_sid())
        await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="no answer")
    await worker.run_once()
    async with tenant_session(database["a"]) as db:
        tasks = (await db.execute(select(Task).where(Task.contact_id == plan.contact_id))).scalars().all()
        assert len(tasks) == 1 and tasks[0].title.endswith("(called 3 times)") and tasks[0].urgency == "high"
    owner = await login(client, "owner@prestigemotors.example")
    body = (await client.get("/calls?show=missed", headers=owner)).json()
    mine = [c for c in body["items"] if c["from_number"] == stranger]
    assert len(mine) == 1 and mine[0]["rings"] == 3 and mine[0]["callback_by"]
    assert all(c["handled_by"] == "missed" for c in body["items"]) and body["counts"]["missed"] >= 1
    assert {"all", "missed", "ondra", "people"} <= set(body["counts"])

    today = (await client.get("/today", headers=owner)).json()["needs"]
    assert today["callbacks"]["count"] >= 1 and not any(stranger in o["title"] for o in today["overdue"] + today["hot"])

    # Rang back, voicemail: noted, still waiting. The first try is what Today's time-to-call-back measures.
    r = (await client.post(f"/calls/{mine[0]['id']}/called-back", json={"result": "left_message"}, headers=owner)).json()
    assert r["needs_callback"] and r["attempts"][0]["by"]
    async with tenant_session(database["a"]) as db:
        tries = (await db.execute(select(Event).where(Event.type == "callback.first_try",
                                                      Event.payload["contact_id"].astext == str(plan.contact_id)))).scalars().all()
        assert len(tries) == 1 and tries[0].payload["result"] == "left_message" and tries[0].payload["rings"] == 3
    # Reached: all three calls and the task are done, with who did it.
    r = (await client.post(f"/calls/{mine[0]['id']}/called-back", json={"result": "reached"}, headers=owner)).json()
    assert not r["needs_callback"] and r["called_back"]["by"]
    after = (await client.get("/calls", headers=owner)).json()["items"]
    assert [c for c in after if c["from_number"] == stranger and c["needs_callback"]] == []
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Task, tasks[0].id)).status == "done"
    async with tenant_session(database["a"]) as db:  # reaching them after a voicemail isn't a second first try
        assert len((await db.execute(select(Event).where(Event.type == "callback.first_try",
                                                         Event.payload["contact_id"].astext == str(plan.contact_id)))).all()) == 1
    assert (await client.get("/analytics", params={"days": 1}, headers=owner)).json()["totals"]["callbacks"] >= 1
    # Undo puts all of it back.
    r = (await client.post(f"/calls/{mine[0]['id']}/reopen", headers=owner)).json()
    assert r["needs_callback"]
    again = [c for c in (await client.get("/calls?show=missed", headers=owner)).json()["items"] if c["from_number"] == stranger]
    assert len(again) == 1 and again[0]["rings"] == 3
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Task, tasks[0].id)).status == "open"

    # Finishing the call-back task on Tasks clears the call-back list too.
    await client.patch(f"/tasks/{tasks[0].id}", json={"status": "done"}, headers=owner)
    assert not any(c["from_number"] == stranger and c["needs_callback"] for c in (await client.get("/calls", headers=owner)).json()["items"])
    # Only missed calls take a call-back.
    answered = next(c for c in after if c["handled_by"] == "ai")
    assert (await client.post(f"/calls/{answered['id']}/called-back", headers=owner)).status_code == 409


async def test_undoing_a_call_back_takes_it_off_todays_time_to_call_back(client, database):
    stranger = NEW_CALLERS[0]
    plan = await calls.start_call(from_number=stranger, to_number=DEALER, provider_call_sid=_sid())
    await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="no answer")
    await worker.run_once()
    owner = await login(client, "owner@prestigemotors.example")
    before = (await client.get("/analytics", params={"days": 1}, headers=owner)).json()["totals"]["callbacks"]
    await client.post(f"/calls/{plan.call_id}/called-back", json={"result": "reached"}, headers=owner)
    async with tenant_session(database["a"]) as db:  # today's numbers are cached for 5 minutes; skip the wait
        await db.execute(delete(MetricDay))
    assert (await client.get("/analytics", params={"days": 1}, headers=owner)).json()["totals"]["callbacks"] == before + 1
    await client.post(f"/calls/{plan.call_id}/reopen", headers=owner)
    assert (await client.get("/analytics", params={"days": 1}, headers=owner)).json()["totals"]["callbacks"] == before
    trace = (await client.get("/analytics/trace", params={"metric": "callbacks", "days": 1}, headers=owner))
    assert trace.status_code == 200
    await client.post(f"/calls/{plan.call_id}/called-back", json={"result": "reached"}, headers=owner)
    t = (await client.get("/analytics/trace", params={"metric": "callbacks", "days": 1}, headers=owner)).json()
    assert t["events"][0]["detail"]["by"] == "Samuel Adeyemi" and t["events"][0]["who"] == stranger
