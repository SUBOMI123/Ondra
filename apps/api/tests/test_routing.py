"""Step 6 acceptance: rules route test messages correctly across 10 scenarios (there are 12 here).

Each scenario is a real message through the webhook, the job queue and Postgres. The model is scripted (routing
never depends on what the model writes); the topic comes from the words, as it does when no model is configured.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import inbound
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import Contact, Conversation, Event, Job, Policy, RoutingRule, Task, Tenant, User
from sqlalchemy import delete, select, text, update

DEALER = "+12145550100"
SIG = {"x-mock-signature": "mock-secret"}
ALWAYS = {}  # no hours set: always on shift
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def off_now(tz: str = "America/Chicago") -> dict:
    """Working hours that don't include now: one shift, three days from today."""
    day = (datetime.now(UTC).astimezone(ZoneInfo(tz)) + timedelta(days=3)).weekday()
    return {_DAYS[day]: ["09:00", "17:00"]}


def on_now(tz: str) -> dict:
    return {_DAYS[datetime.now(UTC).astimezone(ZoneInfo(tz)).weekday()]: ["00:00", "23:59"]}


@pytest.fixture
async def floor(database, monkeypatch):
    """The dealership for a routing scenario: everyone always on shift, a second sales rep (Ana), AI sending for
    real, no rules. Everything is put back afterwards."""
    t = database["a"]
    holder = {}
    started = datetime.now(UTC)
    monkeypatch.setattr(inbound, "llm_factory", lambda: holder.get("llm"))
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    async with tenant_session(t) as db:
        before = (await db.execute(select(Tenant.business_hours))).scalar_one()
        draft_before = (await db.execute(select(Policy.draft_mode))).scalar_one()
        await db.execute(update(Policy).values(draft_mode=False))
        await db.execute(update(User).values(work_hours=ALWAYS, last_assigned_at=None, max_open_tasks=None))
        ana = User(email=f"ana-{uuid.uuid4().hex[:8]}@prestigemotors.example", name="Ana Ruiz", role="sales", work_hours=ALWAYS,
                   password_hash="joined")
        db.add(ana)
        await db.flush()
        people = {u.name.split()[0]: u.id for u in (await db.execute(select(User).where(User.active.is_(True)))).scalars()}
        # Daniel joined first, so with nobody assigned yet it's his turn, then Ana's.
        await db.execute(update(User).where(User.id == ana.id).values(created_at=datetime.now(UTC)))

    created: list[str] = []  # numbers of customers these scenarios invented, removed afterwards

    class Floor:
        tenant = t

        def __init__(self) -> None:
            self.who = people
            self.names = {v: k for k, v in people.items()}

        def script(self, *steps):
            holder["llm"] = ScriptedLLM(list(steps))
            return holder["llm"]

        async def rule(self, name, priority, conditions, action, active=True):
            async with tenant_session(t) as db:
                db.add(RoutingRule(name=name, priority=priority, conditions=conditions, action=action, active=active))

        async def set(self, who, **fields):
            async with tenant_session(t) as db:
                await db.execute(update(User).where(User.id == people[who]).values(**fields))

        async def hours(self, hours):
            async with tenant_session(t) as db:
                await db.execute(update(Tenant).values(business_hours=hours))

        def prompt(self) -> str:
            """What the AI was told about this dealer on its last turn (who's in, among other things)."""
            return " ".join(b["text"] for b in holder["llm"].requests[0]["system"])

        async def message(self, body, *, channel="whatsapp", frm=None, handoff=None):
            """A customer writes in. `handoff` is what the (scripted) AI does with it: (reason, target_role)."""
            if frm is None:
                frm = f"+1469555{uuid.uuid4().int % 9000 + 1000}"
                created.append(frm)
            if handoff:
                self.script([("handoff", {"reason": handoff[0], "brief": "They want a person.", "urgency": "normal",
                                          "target_role": handoff[1]})], "Passing you to the team.")
            payload = {"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": DEALER, "text": body}
            r = await client_post(channel, payload)
            assert r.status_code == 200, r.text
            await worker.run_once()
            async with tenant_session(t) as db:
                contact = (await db.execute(text(
                    "SELECT contact_id FROM contact_identities WHERE value = :v LIMIT 1"), {"v": frm})).scalar_one()
                task = (await db.execute(select(Task).where(Task.contact_id == contact).order_by(Task.created_at.desc()).limit(1))).scalar_one_or_none()
                conv = (await db.execute(select(Conversation).where(Conversation.contact_id == contact).limit(1))).scalar_one()
                out = (await db.execute(text("""SELECT body, is_draft, status FROM messages WHERE conversation_id = :c
                                                 AND direction = 'outbound' ORDER BY created_at DESC LIMIT 1"""), {"c": conv.id})).one_or_none()
                return Got(frm, self.names.get(task.assignee_user_id) if task else None, task, conv.topic, out,
                           self.names.get(conv.assigned_user_id))

    client_post = None

    async def _post(channel, payload):
        import httpx
        from ondra_api.main import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            return await c.post(f"/webhooks/mock/{channel}", content=json.dumps(payload), headers=SIG)

    client_post = _post
    yield Floor()
    async with tenant_session(t) as db:
        await db.execute(delete(RoutingRule))
        invented = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = ANY(:v)"), {"v": created})).scalars().all()
        await db.execute(delete(Task).where(Task.contact_id.in_(invented) | (Task.assignee_user_id == people["Ana"])))
        await db.execute(delete(Task).where(Task.created_at > started, Task.source.in_(("ai_handoff", "rule"))))
        await db.execute(delete(Contact).where(Contact.id.in_(invented)))  # their conversations and messages go too
        await db.execute(update(Conversation).where(Conversation.assigned_user_id == people["Ana"]).values(assigned_user_id=None))
        await db.execute(delete(User).where(User.id == people["Ana"]))
        await db.execute(update(User).values(work_hours=None, timezone=None, last_assigned_at=None, max_open_tasks=None))
        await db.execute(update(Tenant).values(business_hours=before))
        await db.execute(update(Policy).values(draft_mode=draft_before))


class Got:
    def __init__(self, frm, to, task, topic, out, contact_owner):
        self.frm, self.to, self.task, self.topic, self.out, self.contact_owner = frm, to, task, topic, out, contact_owner


async def test_1_sales_leads_take_turns_and_a_customer_keeps_their_rep(floor):
    first = await floor.message("Is the Highlander still available? Can I talk to someone?", handoff=("asked_for_person", "sales"))
    second = await floor.message("How much is the F-150? I'd like a person.", handoff=("pricing", "sales"))
    third = await floor.message("Looking for a used car under 20k", handoff=("vehicle_request", "sales"))
    assert [first.to, second.to, third.to] == ["Daniel", "Ana", "Daniel"]  # round-robin
    assert first.topic == "sales" and first.contact_owner == "Daniel"
    # The second customer writes again. It's Ana's turn anyway? No: it's Ana's customer, so Ana, even out of turn.
    again = await floor.message("Any discount on that F-150?", frm=second.frm, handoff=("discount", "sales"))
    again2 = await floor.message("And what about my trade-in?", frm=second.frm, handoff=("trade_in", "sales"))
    assert (again.to, again2.to) == ("Ana", "Ana")
    assert "sales: in now" in floor.prompt()  # so the AI may say "shortly"


async def test_2_service_goes_to_service(floor):
    got = await floor.message("My check engine light is on, can someone call me?", handoff=("asked_for_person", "service"))
    assert (got.to, got.topic) == ("Maria", "service")


async def test_3_a_complaint_rule_sends_it_to_the_manager_and_alerts(floor):
    await floor.rule("Complaints to the manager", 10, {"topic": ["complaint"]}, {"assign_role": "manager", "alert": True})
    # The model asks for sales; the rule wins because the handoff's reason is a complaint.
    got = await floor.message("This is unacceptable. I want a refund.", handoff=("complaint", "sales"))
    assert (got.to, got.task.urgency) == ("Grace", "high")
    async with tenant_session(floor.tenant) as db:
        alerts = (await db.execute(select(Event).where(Event.type == "alert.created",
                                                       Event.payload["task_id"].astext == str(got.task.id)))).scalars().all()
        decided = (await db.execute(select(Event).where(Event.type == "routing.decided",
                                                        Event.payload["user_id"].astext == str(floor.who["Grace"]))
                                    .order_by(Event.occurred_at.desc()).limit(1))).scalar_one()
    assert len(alerts) == 1 and decided.payload["rule"] == "Complaints to the manager"


async def test_4_a_vip_goes_to_the_owner_whatever_the_rules_say(floor):
    await floor.rule("Everything to sales", 1, {}, {"assign_role": "sales"})
    async with tenant_session(floor.tenant) as db:
        _vip, phone = (await db.execute(text("""SELECT c.id, i.value FROM contacts c JOIN contact_identities i
            ON i.contact_id = c.id AND i.kind = 'phone' WHERE c.is_vip LIMIT 1"""))).one()
    llm = floor.script("should never be used")
    got = await floor.message("Call me about the Escalade.", frm=phone)
    assert got.to == "Samuel" and got.out is None and llm.requests == []  # the owner; no AI reply or draft
    async with tenant_session(floor.tenant) as db:
        job = (await db.execute(select(Job).where(Job.kind == "vip_realert", Job.payload["task_id"].astext == str(got.task.id)))).scalar_one()
        assert job.run_at > datetime.now(UTC) + timedelta(minutes=5)
    # Ten minutes on and still open: the owner is alerted again. Once it's done, no more.
    assert await inbound.vip_realert(floor.tenant, job.payload) is True
    async with tenant_session(floor.tenant) as db:
        await db.execute(update(Task).where(Task.id == got.task.id).values(status="done"))
    assert await inbound.vip_realert(floor.tenant, {"task_id": str(got.task.id), "n": 2}) is False


async def test_5_a_rule_can_name_a_person_for_one_channel(floor):
    await floor.rule("Finance on WhatsApp to Chris", 10, {"topic": ["finance"], "channel": ["whatsapp"]},
                     {"assign_user_id": str(floor.who["Chris"])})
    wa = await floor.message("What APR can I get on a loan?", channel="whatsapp", handoff=("financing", "sales"))
    sms = await floor.message("What APR can I get on a loan?", channel="sms", handoff=("financing", "sales"))
    assert (wa.to, wa.topic) == ("Chris", "finance")
    assert sms.to in ("Daniel", "Ana")  # same question by text: the rule doesn't apply, sales takes it


async def test_6_a_rule_can_keep_the_ai_out_of_a_topic(floor):
    await floor.rule("Shipping: people only", 10, {"topic": ["shipping"]}, {"assign_role": "manager", "ai": "off"})
    llm = floor.script("should never be used")
    got = await floor.message("Can you ship a Lexus to Lagos?")
    assert llm.requests == [] and got.out is None  # the AI never ran and nothing was sent
    assert (got.to, got.task.source, got.topic) == ("Grace", "rule", "shipping")
    assert "keeps Ondra out" in got.task.brief


async def test_7_someone_at_their_limit_is_skipped(floor):
    async with tenant_session(floor.tenant) as db:
        open_now = (await db.execute(text("SELECT count(*) FROM tasks WHERE assignee_user_id = :u AND status IN ('open','in_progress')"),
                                     {"u": floor.who["Daniel"]})).scalar()
    await floor.set("Daniel", max_open_tasks=max(open_now, 1))
    if open_now == 0:
        await floor.message("Is the Camry available? A person please.", handoff=("asked_for_person", "sales"))  # fills Daniel
        await floor.set("Ana", last_assigned_at=datetime.now(UTC))  # make it Daniel's turn again
    got = await floor.message("Do you have a Tahoe in stock? Call me.", handoff=("asked_for_person", "sales"))
    assert got.to == "Ana"  # Daniel's turn, but he's full


async def test_8_nobody_in_queues_it_and_the_customer_is_told(floor):
    await floor.set("Daniel", work_hours=off_now())
    await floor.set("Ana", work_hours=off_now())
    got = await floor.message("How much is the Silverado? Can someone call me?", handoff=("pricing", "sales"))
    assert got.to in ("Daniel", "Ana")  # queued for whoever is in next, not bounced to a manager
    assert "sales: nobody in until" in floor.prompt()  # so the AI says when, not "shortly"
    # And when the AI's own words can't be used, the fallback line says the same.
    floor.script([("search_inventory", {})], [("search_inventory", {})], [("search_inventory", {})],
                 [("search_inventory", {})], [("search_inventory", {})], [("search_inventory", {})])
    stuck = await floor.message("Do you have a Silverado? I keep asking.")
    assert stuck.to in ("Daniel", "Ana") and "when we open" in stuck.out.body and "shortly" not in stuck.out.body


async def test_9_lagos_staff_cover_while_dallas_is_closed(floor):
    await floor.set("Daniel", work_hours=off_now(), timezone="America/Chicago")
    await floor.set("Ana", work_hours=on_now("Africa/Lagos"), timezone="Africa/Lagos")
    await floor.set("Ana", last_assigned_at=datetime.now(UTC))  # it would be Daniel's turn
    got = await floor.message("Is the Accord still for sale? I want to talk to someone.", handoff=("asked_for_person", "sales"))
    assert got.to == "Ana" and "sales: in now" in floor.prompt()


async def test_10_after_hours_a_rule_makes_the_ai_draft_only(floor):
    await floor.rule("After hours: drafts only", 10, {"hours": "closed"}, {"assign_role": "sales", "ai": "draft"})
    await floor.hours({})  # no opening hours today: closed
    floor.script("We open at 9 tomorrow.")
    closed = await floor.message("What time do you open?")
    assert closed.out.is_draft and channels.mock("whatsapp").outbox == []
    await floor.hours({d: ["00:00", "23:59"] for d in _DAYS})  # open: the rule doesn't apply, the AI sends
    floor.script("We're open until 7 tonight.")
    opened = await floor.message("What time do you close?")
    assert not opened.out.is_draft and opened.out.status == "sent"


async def test_11_the_first_matching_rule_wins_and_switched_off_rules_are_ignored(floor):
    await floor.rule("Service to the owner (off)", 1, {"topic": ["service"]}, {"assign_role": "owner"}, active=False)
    await floor.rule("Service to the manager", 5, {"topic": ["service"]}, {"assign_role": "manager"})
    await floor.rule("Everything to sales", 50, {}, {"assign_role": "sales"})
    service = await floor.message("I need my brakes looked at. Can someone call?", handoff=("asked_for_person", "service"))
    other = await floor.message("Where are you located? I'd like to speak to someone.", handoff=("asked_for_person", "manager"))
    assert service.to == "Grace"
    assert other.to in ("Daniel", "Ana")  # the catch-all, over the model asking for a manager


async def test_12_an_empty_team_falls_back_to_the_manager(floor):
    await floor.set("Maria", active=False)
    try:
        got = await floor.message("My car won't start, I need a service advisor.", handoff=("asked_for_person", "service"))
        assert got.to == "Grace"
    finally:
        await floor.set("Maria", active=True)


async def test_rules_never_cross_dealerships(database, floor):
    await floor.rule("A's rule", 1, {}, {"assign_role": "owner"})
    async with tenant_session(database["b"]) as db:
        assert (await db.execute(select(RoutingRule))).scalars().all() == []
        assert not any(u.name == "Ana Ruiz" for u in (await db.execute(select(User))).scalars())


# --- the settings API ---------------------------------------------------------------------------------------------

async def test_rules_api_add_order_switch_preview_and_permissions(client, database, floor):
    from tests.conftest import login

    owner = await login(client, "owner@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    got = (await client.get("/routing", headers=sales)).json()
    assert got["rules"] == [] and got["can_edit"] is False and got["owner"] == "Samuel Adeyemi"
    rule = {"topics": ["complaint"], "team": "manager", "alert": True, "ai": "off"}
    assert (await client.post("/routing/rules", json=rule, headers=sales)).status_code == 403  # read-only for sales

    a = (await client.post("/routing/rules", json=rule, headers=owner)).json()
    b = (await client.post("/routing/rules", json={"team": "sales", "hours": "closed", "ai": "draft"}, headers=owner)).json()
    assert (a["position"], b["position"]) == (1, 2) and a["topics"] == ["complaint"] and a["ai"] == "off"
    # A rule must send the work somewhere, to a team or a person, not both; and only to someone who works here.
    assert (await client.post("/routing/rules", json={"topics": ["sales"]}, headers=owner)).status_code == 422
    other_dealer = await login(client, "owner@lonestar.example")
    stranger = (await client.get("/users", headers=other_dealer)).json()["items"][0]["id"]
    r = await client.post("/routing/rules", json={"user_id": stranger}, headers=owner)
    assert r.status_code == 422 and "works here" in r.json()["detail"]

    # Preview: what happens to a message right now, without sending or assigning anything.
    p = (await client.post("/routing/preview", json={"text": "This is unacceptable, I want a refund", "channel": "sms"}, headers=sales)).json()
    assert (p["topic"], p["person"], p["ai"], p["alert"], p["rule_id"]) == ("complaint", "Grace Thompson", "off", True, a["id"])
    p = (await client.post("/routing/preview", json={"text": "is the tahoe in stock?"}, headers=sales)).json()
    assert p["topic"] == "sales" and p["team"] == "sales" and p["rule_id"] is None and p["in_now"] is True

    # Order decides: move the catch-all first and the complaint now matches it instead (if the dealership is closed).
    r = await client.put("/routing/order", json={"ids": [b["id"], a["id"]]}, headers=owner)
    assert [x["id"] for x in r.json()["rules"]] == [b["id"], a["id"]]
    assert (await client.put("/routing/order", json={"ids": [a["id"]]}, headers=owner)).status_code == 409

    off = (await client.patch(f"/routing/rules/{a['id']}", json={"active": False}, headers=owner)).json()
    assert off["active"] is False
    p = (await client.post("/routing/preview", json={"text": "I want a refund, this is unacceptable"}, headers=sales)).json()
    assert p["rule_id"] != a["id"]  # switched off: no longer applies
    edited = (await client.put(f"/routing/rules/{a['id']}", json={**rule, "channels": ["email"], "active": True}, headers=owner)).json()
    assert edited["channels"] == ["email"] and edited["active"] is True
    assert (await client.delete(f"/routing/rules/{b['id']}", headers=owner)).status_code == 204
    assert [x["id"] for x in (await client.get("/routing", headers=owner)).json()["rules"]] == [a["id"]]
    assert (await client.get("/routing", headers=other_dealer)).json()["rules"] == []  # never another dealer's
    async with tenant_session(database["a"]) as db:
        actions = (await db.execute(text("SELECT action FROM audit_log WHERE action LIKE 'routing.%' ORDER BY created_at DESC LIMIT 6"))).scalars().all()
    assert {"routing.rule.add", "routing.rule.update", "routing.rule.delete", "routing.order"} <= set(actions)


async def test_a_persons_hours_and_limit_are_set_from_the_team_api(client, database, floor):
    from tests.conftest import login

    owner = await login(client, "owner@prestigemotors.example")
    daniel = str(floor.who["Daniel"])
    r = await client.patch(f"/users/{daniel}", headers=owner, json={
        "work_hours": {"mon": ["08:00", "16:00"], "tue": None}, "timezone": "Africa/Lagos", "max_open_tasks": 12})
    assert r.status_code == 200, r.text
    assert (r.json()["work_hours"], r.json()["timezone"], r.json()["max_open_tasks"]) == ({"mon": ["08:00", "16:00"]}, "Africa/Lagos", 12)
    listed = next(u for u in (await client.get("/users", headers=owner)).json()["items"] if u["id"] == daniel)
    assert (listed["work_hours"], listed["timezone"], listed["max_open_tasks"]) == ({"mon": ["08:00", "16:00"]}, "Africa/Lagos", 12)
    bad = await client.patch(f"/users/{daniel}", headers=owner, json={"work_hours": {"mon": ["18:00", "09:00"]}})
    assert bad.status_code == 422
    assert (await client.patch(f"/users/{daniel}", headers=owner, json={"work_hours": {"mon": None}})).status_code == 422
    assert (await client.patch(f"/users/{daniel}", headers=owner, json={"timezone": "Mars/Olympus"})).status_code == 422
    back = (await client.patch(f"/users/{daniel}", headers=owner, json={"work_hours": None, "max_open_tasks": None})).json()
    assert (back["work_hours"], back["timezone"], back["max_open_tasks"]) == (None, None, None)
