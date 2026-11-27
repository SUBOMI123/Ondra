"""Step 9 acceptance: every number on the dashboard is traceable to events, and matches a hand-calculated fixture.

The fixture is the one in packages/core/tests/test_metrics.py (worked out by hand in its docstring), loaded into the
events table of a dealership with nothing else in that week."""

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from ondra_api.db import tenant_session
from ondra_api.services import metrics
from ondra_core.models import Contact, Deal, Event, MetricDay
from sqlalchemy import delete, select, text, update

from tests.conftest import login

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "core" / "tests"))
from test_metrics import FIXTURE

WEEK = {"to": "2026-11-25", "days": 3}


@pytest.fixture
async def week(database):
    """The hand-worked week, as events in dealership B (Lone Star), which has no other events that week."""
    t = database["b"]
    async with tenant_session(t) as db:
        assert (await db.execute(text("SELECT count(*) FROM events WHERE type = ANY(:t)"), {"t": ["lead.captured", "deal.stage_changed"]})).scalar() == 0
        for e in FIXTURE:
            db.add(Event(type=e.type, payload=e.payload, occurred_at=e.at))
    yield t
    async with tenant_session(t) as db:
        await db.execute(delete(Event).where(Event.occurred_at >= datetime(2026, 11, 20, tzinfo=UTC), Event.occurred_at < datetime(2026, 11, 27, tzinfo=UTC)))
        await db.execute(delete(MetricDay))


async def test_the_dashboard_matches_the_hand_calculated_fixture(client, week):
    """Step 9 acceptance."""
    owner = await login(client, "owner@lonestar.example")
    r = await client.get("/analytics", params=WEEK, headers=owner)
    assert r.status_code == 200, r.text
    got = r.json()
    t = got["totals"]
    assert (got["from"], got["to"], got["timezone"]) == ("2026-11-23", "2026-11-25", "America/Chicago")
    assert (t["leads"], t["leads_by_ai"], t["leads_after_hours"]) == (3, 2, 1)
    assert t["leads_by_channel"] == {"whatsapp": 1, "sms": 1, "email": 1}
    assert (t["responses"], t["responses_by_ai"], t["responses_by_team"]) == (5, 3, 2)
    assert (t["median_first_response_seconds"], t["median_first_response_seconds_ai"]) == (40, 30)
    assert (t["follow_ups_sent"], t["appointments_booked"], t["appointments_booked_by_ai"], t["appointments_showed"], t["appointments_no_show"]) == (1, 2, 1, 1, 1)
    assert (t["calls"], t["calls_by_ai"], t["calls_missed"]) == (3, 1, 1) and t["handled_by"] == {"ai": 4, "team": 3}
    assert got["pipeline"] == {"by_stage": {"new": 1, "qualified": 0, "appointment": 0, "negotiating": 1, "lost": 1}, "in_play": 2, "in_play_by_ai": 1}
    # The 11:30 pm lead is Monday's (the dealership's day), not Tuesday's (UTC's).
    assert [(d["day"], d["leads"]) for d in got["series"]] == [("2026-11-23", 2), ("2026-11-24", 1), ("2026-11-25", 0)]
    assert got["previous"]["leads"] == 0  # the three days before were empty
    assert got["people"] == [{"user_id": "dan", "name": "Someone who has left", "first_replies": 2, "median_first_response_seconds": 1200}]

    # Each day was rolled up from its events, and the rollup can be thrown away and rebuilt to the same numbers.
    async with tenant_session(week) as db:
        rows = {r.day: r for r in (await db.execute(select(MetricDay).where(MetricDay.day >= date(2026, 11, 23)))).scalars()}
        assert [rows[date(2026, 11, d)].events for d in (23, 24, 25)] == [8, 9, 7]  # the eighth on the 25th isn't a dashboard event
        await db.execute(delete(MetricDay))
    assert (await client.get("/analytics", params=WEEK, headers=owner)).json()["totals"] == t


async def test_every_number_is_traceable_to_its_events(client, week):
    owner = await login(client, "owner@lonestar.example")
    totals = (await client.get("/analytics", params=WEEK, headers=owner)).json()["totals"]
    labels = (await client.get("/analytics", params=WEEK, headers=owner)).json()["labels"]
    async with tenant_session(week) as db:
        ids = set(str(i) for i in (await db.execute(select(Event.id))).scalars())
    for name in labels:  # every count on the dashboard
        tr = (await client.get("/analytics/trace", params={**WEEK, "metric": name}, headers=owner)).json()
        assert tr["count"] == totals[name] == len(tr["events"]), name
        assert all(e["event_id"] in ids for e in tr["events"]), name
    after_hours = (await client.get("/analytics/trace", params={**WEEK, "metric": "leads_after_hours"}, headers=owner)).json()
    [ev] = after_hours["events"]
    assert (ev["type"], ev["detail"]) == ("lead.captured", {"channel": "sms", "by": "ai", "after_hours": True})
    assert (await client.get("/analytics/trace", params={**WEEK, "metric": "made_up"}, headers=owner)).status_code == 404
    # Another dealership sees none of it.
    other = await login(client, "owner@prestigemotors.example")
    theirs = (await client.get("/analytics/trace", params={**WEEK, "metric": "leads_after_hours"}, headers=other)).json()
    assert all(e["event_id"] not in ids for e in theirs["events"])


async def test_real_work_writes_the_events_and_a_stage_change_moves_the_pipeline(client, database):
    """The events aren't only in fixtures: an AI-captured lead, its reply and a stage change show up as they happen."""
    import json
    import uuid

    from ondra_api import channels, worker
    from ondra_api.services import inbound
    from ondra_core.agent.llm import ScriptedLLM
    from ondra_core.models import Policy, Task
    from sqlalchemy import update

    t = database["a"]
    owner = await login(client, "owner@prestigemotors.example")
    before = (await client.get("/analytics", params={"days": 1}, headers=owner)).json()
    async with tenant_session(t) as db:
        draft_before = (await db.execute(select(Policy.draft_mode))).scalar_one()
        await db.execute(update(Policy).values(draft_mode=False))
    frm = f"+1512555{uuid.uuid4().int % 9000 + 1000}"
    inbound.llm_factory, keep = (lambda: ScriptedLLM([[("update_lead_fields", {"fields": {"vehicle_interest": "Tahoe"}})], "Yes, we have Tahoes."])), inbound.llm_factory
    try:
        r = await client.post("/webhooks/mock/sms", headers={"x-mock-signature": "mock-secret"},
                              content=json.dumps({"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": "+12145550100", "text": "Do you have a Tahoe?"}))
        assert r.status_code == 200
        await worker.run_once()
    finally:
        inbound.llm_factory = keep
    assert channels.mock("sms").outbox[-1].body == "Yes, we have Tahoes."
    async with tenant_session(t) as db:
        await db.execute(delete(MetricDay))  # skip the few-minute cache
        cid = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = :v"), {"v": frm})).scalar_one()
        deal = (await db.execute(select(Deal).where(Deal.contact_id == cid))).scalar_one()
    after = (await client.get("/analytics", params={"days": 1}, headers=owner)).json()
    for k in ("leads", "leads_by_ai", "responses", "responses_by_ai", "messages_in"):
        assert after["totals"][k] == before["totals"][k] + 1, k
    assert after["pipeline"]["in_play_by_ai"] == before["pipeline"]["in_play_by_ai"] + 1
    lead = (await client.get("/analytics/trace", params={"days": 1, "metric": "leads_by_ai"}, headers=owner)).json()["events"][0]
    assert lead["who"] == frm and lead["detail"]["channel"] == "sms" and lead["backfilled"] is False

    sales = await login(client, "daniel@prestigemotors.example")
    moved = (await client.patch(f"/deals/{deal.id}", json={"stage": "won"}, headers=sales)).json()
    assert {k: moved[k] for k in ("id", "stage", "changed")} == {"id": str(deal.id), "stage": "won", "changed": True}
    assert (await client.patch(f"/deals/{deal.id}", json={"stage": "won"}, headers=sales)).json()["changed"] is False
    assert (await client.patch(f"/deals/{deal.id}", json={"stage": "sold-ish"}, headers=sales)).status_code == 422
    end = (await client.get("/analytics", params={"days": 1}, headers=owner)).json()
    assert end["pipeline"]["in_play_by_ai"] == before["pipeline"]["in_play_by_ai"] and end["pipeline"]["by_stage"].get("won", 0) >= 1
    async with tenant_session(t) as db:
        await db.execute(delete(Task).where(Task.contact_id == cid))
        await db.execute(delete(Event).where(Event.payload["deal_id"].astext == str(deal.id)))
        await db.execute(delete(Event).where(Event.type == "response.sent", Event.occurred_at > datetime.now(UTC) - timedelta(minutes=2)))
        await db.execute(text("DELETE FROM events WHERE type = 'message.received' AND occurred_at > now() - interval '2 minutes'"))
        await db.execute(delete(Contact).where(Contact.id == cid))
        await db.execute(delete(MetricDay))
        await db.execute(text("DELETE FROM jobs WHERE kind IN ('follow_up', 'crm_push') AND created_at > now() - interval '2 minutes'"))
        await db.execute(update(Policy).values(draft_mode=draft_before))


async def test_backfill_writes_missing_events_once_and_today_respects_roles(client, database):
    t = database["a"]
    async with tenant_session(t) as db:
        # The seed already backfilled its history. Remove those events, as if they'd never been recorded.
        await db.execute(text("DELETE FROM events WHERE (payload->>'backfilled')::bool"))
        first = await metrics.backfill(db)
        again = await metrics.backfill(db)
        assert first["lead.captured"] >= 2 and first["response.sent"] >= 1 and first["call.ended"] >= 1  # the seeded deals, replies and calls
        assert set(again.values()) == {0}  # nothing is written twice
        marked = (await db.execute(text("SELECT count(*) FROM events WHERE type = 'lead.captured' AND (payload->>'backfilled')::bool AND payload->>'by' = 'unknown'"))).scalar()
        assert marked == first["lead.captured"]
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    mine, all_ = (await client.get("/today", headers=sales)).json(), (await client.get("/today", headers=owner)).json()
    assert (mine["needs"]["scope"], all_["needs"]["scope"]) == ("mine", "everyone")
    assert all_["needs"]["vips"] and mine["needs"]["vips"] == []  # a salesperson doesn't see the owner's VIPs
    assert all_["overnight"] is None or {"from", "to", "leads", "median_first_response_seconds"} <= set(all_["overnight"])
    assert isinstance(all_["appointments"], list)
    async with tenant_session(t) as db:
        await db.execute(delete(MetricDay))


async def test_the_deals_board_shows_real_deals_and_moves_them(client, database):
    t = database["a"]
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    board = (await client.get("/deals", headers=owner)).json()
    assert [s["stage"] for s in board["stages"]] == ["new", "qualified", "appointment", "negotiating", "won", "lost"]
    by_client = {d["client"]: d for s in board["stages"] for d in s["deals"]}
    sarah, kevin = by_client["Sarah King"], by_client["Kevin Lee"]
    assert (sarah["stage"], sarah["wants"], sarah["value"], sarah["value_from"]) == ("new", "2021 Toyota Highlander XLE", 31000.0, "their budget")
    assert "Budget up to $31,000" in sarah["note"] and "Paying by cash" in sarah["note"]
    assert kevin["stage"] == "qualified" and kevin["value"] is None  # no stock number and no budget: no made-up value
    assert board["open"] == len(by_client) and board["open_without_value"] >= 1 and board["can_move"] is True
    # A salesperson doesn't see a VIP's deal, and can't move it by guessing its id.
    async with tenant_session(t) as db:
        vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True)).limit(1))).scalar_one()
        d = Deal(contact_id=vip.id, type="sales", stage="new", vehicle_of_interest={"description": "Range Rover Sport"})
        db.add(d)
        await db.flush()
        vip_deal, vip_name = d.id, vip.display_name
    theirs = {x["client"] for s in (await client.get("/deals", headers=sales)).json()["stages"] for x in s["deals"]}
    mine = {x["client"]: x for s in (await client.get("/deals", headers=owner)).json()["stages"] for x in s["deals"]}
    assert vip_name not in theirs and mine[vip_name]["vip"] is True and mine[vip_name]["by_ondra"] is False
    assert (await client.patch(f"/deals/{vip_deal}", json={"stage": "won"}, headers=sales)).status_code == 404
    # Moving a deal: the board, the stored reason and the dashboard's pipeline all follow.
    lost = (await client.patch(f"/deals/{sarah['id']}", json={"stage": "lost", "lost_reason": "Bought elsewhere"}, headers=sales)).json()
    assert lost["stage"] == "lost"
    after = {d["client"]: d for s in (await client.get("/deals", headers=owner)).json()["stages"] for d in s["deals"]}
    assert (after["Sarah King"]["stage"], after["Sarah King"]["lost_reason"]) == ("lost", "Bought elsewhere")
    pipe = (await client.get("/analytics", params={"days": 1}, headers=owner)).json()["pipeline"]
    assert pipe["by_stage"]["lost"] >= 1
    assert (await client.patch(f"/deals/{sarah['id']}", json={"stage": "new"}, headers=sales)).json()["stage"] == "new"  # back, reason cleared
    async with tenant_session(t) as db:
        assert (await db.execute(select(Deal.lost_reason).where(Deal.id == sarah["id"]))).scalar_one() is None
        await db.execute(delete(Deal).where(Deal.id == vip_deal))
        await db.execute(delete(Event).where(Event.type == "deal.stage_changed", Event.payload["deal_id"].astext == sarah["id"]))
        await db.execute(delete(MetricDay))


async def test_a_deal_opens_in_full_and_can_be_given_to_someone(client, database):
    t = database["a"]
    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    board = {d["client"]: d for s in (await client.get("/deals", headers=owner)).json()["stages"] for d in s["deals"]}
    sarah = board["Sarah King"]
    # The card says what's next and when you last spoke.
    assert sarah["last_contact_at"] and sarah["next_task"]["title"] == "Talk price with Sarah"
    d = (await client.get(f"/deals/{sarah['id']}", headers=sales)).json()
    assert (d["client"]["name"], d["wants"], d["budget_max"], d["payment_method"]) == ("Sarah King", "2021 Toyota Highlander XLE", 31000.0, "cash")
    assert any("highlander" in (m["body"] or "").lower() for m in d["messages"]) and d["conversation_id"]
    assert d["owner"]["name"] == "Daniel Okafor" and d["owner_given"] is False  # from her open task, until someone is given it
    assert {"Daniel Okafor", "Samuel Adeyemi"} <= {p["name"] for p in d["people"]}
    # Give it to the owner: stored on the deal, audited, and the stage is untouched.
    samuel = next(p for p in d["people"] if p["name"] == "Samuel Adeyemi")
    r = await client.patch(f"/deals/{sarah['id']}", json={"owner_user_id": samuel["id"]}, headers=owner)
    assert r.status_code == 200 and r.json()["stage"] == "new"
    again = (await client.get(f"/deals/{sarah['id']}", headers=owner)).json()
    assert (again["owner"]["name"], again["owner_given"]) == (samuel["name"], True)
    assert (await client.patch(f"/deals/{sarah['id']}", json={}, headers=owner)).status_code == 422
    # Moving it shows in its history, with who moved it.
    await client.patch(f"/deals/{sarah['id']}", json={"stage": "qualified"}, headers=sales)
    hist = (await client.get(f"/deals/{sarah['id']}", headers=owner)).json()["history"]
    assert (hist[-1]["from"], hist[-1]["to"], hist[-1]["by"]) == ("new", "qualified", "Daniel Okafor")
    # A VIP's deal doesn't exist for a salesperson who doesn't look after them.
    async with tenant_session(t) as db:
        vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True)).limit(1))).scalar_one()
        vd = Deal(contact_id=vip.id, type="sales", stage="new")
        db.add(vd)
        await db.flush()
        vip_deal = vd.id
    assert (await client.get(f"/deals/{vip_deal}", headers=sales)).status_code == 404
    assert (await client.get(f"/deals/{vip_deal}", headers=owner)).status_code == 200
    async with tenant_session(t) as db:
        await db.execute(delete(Deal).where(Deal.id == vip_deal))
        await db.execute(delete(Event).where(Event.type == "deal.stage_changed", Event.payload["deal_id"].astext == sarah["id"]))
        await db.execute(update(Deal).where(Deal.id == sarah["id"]).values(stage="new", owner_user_id=None))
        await db.execute(delete(MetricDay))
