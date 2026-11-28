"""Step 7 acceptance: a qualified lead produces a valid ADF/XML email, once, to the dealer's CRM address."""

import json
import uuid
from xml.etree import ElementTree as ET

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import crm, inbound
from ondra_core import adf
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import Contact, Deal, Integration, Job, Policy, Task, Vehicle
from sqlalchemy import delete, select, text, update

DEALER = "+12145550100"
SIG = {"x-mock-signature": "mock-secret"}
CRM = "leads@prestigemotors.crm.example"


@pytest.fixture
async def shop(client, database, monkeypatch):
    t = database["a"]
    holder = {}
    monkeypatch.setattr(inbound, "llm_factory", lambda: holder.get("llm"))
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    created: list[str] = []
    async with tenant_session(t) as db:
        draft_before = (await db.execute(select(Policy.draft_mode))).scalar_one()
        await db.execute(update(Policy).values(draft_mode=False))
        db.add(Integration(kind="crm_adf", config={"email": CRM, "active": True}, status="ok"))
        car = (await db.execute(select(Vehicle).where(Vehicle.status == "available", Vehicle.vin.isnot(None)).order_by(Vehicle.stock_number).limit(1))).scalar_one()
        stock = {"stock": car.stock_number, "vin": car.vin, "make": car.make, "model": car.model, "year": car.year}

    class Shop:
        tenant = t
        car = stock

        async def writes(self, body, script, frm=None):
            if frm is None:
                frm = f"+1713555{uuid.uuid4().int % 9000 + 1000}"
                created.append(frm)
            holder["llm"] = ScriptedLLM(list(script))
            r = await client.post("/webhooks/mock/sms", headers=SIG,
                                  content=json.dumps({"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": DEALER, "text": body}))
            assert r.status_code == 200, r.text
            await worker.run_once()
            return frm

        async def push_now(self) -> list[str]:
            """Run the queued CRM pushes without waiting the minute."""
            async with tenant_session(t) as db:
                jobs = (await db.execute(select(Job).where(Job.kind == "crm_push", Job.status == "queued"))).scalars().all()
                payloads = [j.payload for j in jobs]
                for j in jobs:
                    j.status = "done"
            return [await crm.push(t, p) for p in payloads]

        def crm_emails(self):
            return [m for m in channels.mock("email").outbox if m.to_address == CRM]

    yield Shop()
    async with tenant_session(t) as db:
        invented = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = ANY(:v)"), {"v": created})).scalars().all()
        await db.execute(delete(Task).where(Task.contact_id.in_(invented)))
        await db.execute(delete(Contact).where(Contact.id.in_(invented)))
        await db.execute(delete(Integration).where(Integration.kind == "crm_adf"))
        await db.execute(delete(Job).where(Job.kind == "crm_push"))
        await db.execute(update(Policy).values(draft_mode=draft_before))


async def test_a_qualified_lead_produces_a_valid_adf_email_once(shop):
    """Step 7 acceptance."""
    car = shop.car
    lead = {"name": "Sarah King", "vehicle_interest": f"{car['year']} {car['make']} {car['model']}", "stock": car["stock"],
            "budget_max": 30000, "payment_method": "finance", "timeline": "this month", "trade_in": "2015 Silverado"}
    frm = await shop.writes(f"Hi, I'm Sarah King. Is the {car['model']} still available? Budget about 30k, financing.",
                            [[("update_lead_fields", {"fields": lead})], "Yes, it's here. Want to come see it this week?"])
    assert shop.crm_emails() == []  # queued for a minute later, so details from the same chat go together
    assert await shop.push_now() == ["sent"]
    [email] = shop.crm_emails()
    assert email.subject == "New lead from Ondra: Sarah King" and email.from_address == "sales@prestige-motors.example"
    assert adf.problems(email.body) == []  # valid ADF 1.0, and the body is the XML and nothing else
    assert email.body.startswith('<?xml version="1.0" encoding="UTF-8"?>') and email.body.rstrip().endswith("</adf>")
    p = ET.fromstring(email.body.encode()).find("prospect")
    v = p.find("vehicle")
    assert (v.findtext("year"), v.findtext("make"), v.findtext("model"), v.findtext("stock"), v.findtext("vin")) == (
        str(car["year"]), car["make"], car["model"], car["stock"], car["vin"])
    assert {n.get("part"): n.text for n in p.findall("customer/contact/name")} == {"first": "Sarah", "last": "King"}
    assert p.findtext("customer/contact/phone") == frm and v.findtext("finance/method") == "finance"
    comments = p.findtext("customer/comments")
    assert "Budget: up to $30,000." in comments and "Trade in: 2015 Silverado." in comments and "captured by Ondra" in comments
    assert p.findtext("vendor/vendorname") == "Prestige Motors"

    # More details later don't send the lead again: one lead per deal.
    await shop.writes("Also I'd pay 5k down", [[("update_lead_fields", {"fields": {"down_payment": 5000}})], "Noted."], frm=frm)
    assert await shop.push_now() == [] and len(shop.crm_emails()) == 1
    async with tenant_session(shop.tenant) as db:
        integ = (await db.execute(select(Integration).where(Integration.kind == "crm_adf"))).scalar_one()
        assert integ.status == "ok" and integ.last_sync_at is not None and integ.config["last"]["detail"] == "Lead sent."
        deal = (await db.execute(text("""SELECT d.crm_pushed_at FROM deals d JOIN contact_identities i ON i.contact_id = d.contact_id
                                          WHERE i.value = :v"""), {"v": frm})).scalar_one()
        assert deal is not None
        # Ondra opened the deal and gave it a salesperson straight away: nobody's deal is nobody's job.
        role = (await db.execute(text("""SELECT u.role FROM deals d JOIN contact_identities i ON i.contact_id = d.contact_id
                                          JOIN users u ON u.id = d.owner_user_id WHERE i.value = :v"""), {"v": frm})).scalar_one()
        assert role == "sales"


async def test_unqualified_leads_vips_and_a_switched_off_push_send_nothing(shop):
    # A question with no buying interest recorded: no lead.
    await shop.writes("What time do you close?", ["We close at 7."])
    assert await shop.push_now() == []
    # Interest in "a 3-row SUV" with no particular car still qualifies, with the description as the vehicle note.
    await shop.writes("Looking for a 3-row SUV under 35k", [[("update_lead_fields", {"fields": {"vehicle_interest": "3-row SUV under $35k", "budget_max": 35000}})], "We have a few."])
    assert await shop.push_now() == ["sent"]
    xml = shop.crm_emails()[-1].body
    assert adf.problems(xml) == [] and ET.fromstring(xml.encode()).findtext("prospect/vehicle/comments") == "3-row SUV under $35k"
    # Switched off: nothing is queued at all.
    async with tenant_session(shop.tenant) as db:
        await db.execute(update(Integration).where(Integration.kind == "crm_adf").values(config={"email": CRM, "active": False}))
    await shop.writes("Do you have a Tahoe?", [[("update_lead_fields", {"fields": {"vehicle_interest": "Tahoe"}})], "Yes."])
    assert await shop.push_now() == [] and len(shop.crm_emails()) == 1
    # A VIP's deal is never pushed, even if asked directly.
    async with tenant_session(shop.tenant) as db:
        await db.execute(update(Integration).where(Integration.kind == "crm_adf").values(config={"email": CRM, "active": True}))
        vip = (await db.execute(select(Contact).where(Contact.is_vip.is_(True)).limit(1))).scalar_one()
        d = Deal(contact_id=vip.id, type="sales", stage="new", vehicle_of_interest={"description": "Escalade"})
        db.add(d)
        await db.flush()
        assert await crm.maybe_queue(db, vip) is False
        deal_id = d.id
    assert await crm.push(shop.tenant, {"deal_id": str(deal_id)}) == "skipped: VIP"
    async with tenant_session(shop.tenant) as db:
        await db.execute(delete(Deal).where(Deal.id == deal_id))


async def test_a_failed_send_is_recorded_and_retried(shop):
    await shop.writes("Is the Camry available? I'm Ben.", [[("update_lead_fields", {"fields": {"name": "Ben Ortiz", "vehicle_interest": "Camry"}})], "Yes."])
    channels.mock("email").fail_next = True
    async with tenant_session(shop.tenant) as db:
        payload = (await db.execute(select(Job.payload).where(Job.kind == "crm_push", Job.status == "queued"))).scalar_one()
    with pytest.raises(RuntimeError, match="ADF push failed"):  # raising makes the job queue retry with backoff
        await crm.push(shop.tenant, payload)
    async with tenant_session(shop.tenant) as db:
        integ = (await db.execute(select(Integration).where(Integration.kind == "crm_adf"))).scalar_one()
        assert integ.status == "error" and integ.config["last"]["ok"] is False
    assert await crm.push(shop.tenant, payload) == "sent" and len(shop.crm_emails()) == 1
    assert await crm.push(shop.tenant, payload) == "skipped: already sent"


# --- the DMS and the repair-order tool (same step) ------------------------------------------------------------------

async def test_repair_order_status_is_answered_from_the_mock_dms(shop):
    """Step 7 acceptance: RO status answered from mock DMS. The seeded demo dealership has the mock DMS on."""
    from ondra_api.services.agent_tools import DbToolBackend
    from ondra_core.models import ContactIdentity, Conversation

    async with tenant_session(shop.tenant) as db:
        ident = (await db.execute(select(ContactIdentity).where(ContactIdentity.value == "+12145551001", ContactIdentity.kind == "phone"))).scalar_one()
        contact = await db.get(Contact, ident.contact_id)
        conv = Conversation(contact_id=contact.id, channel="sms", ai_mode="auto")
        db.add(conv)
        await db.flush()
        backend = DbToolBackend(db, contact=contact, conversation=conv, price_disclosure="listed", open_now=True)
        out = await backend.get_repair_order_status()
        assert out["found"] is True and out["repair_orders"] == [{
            "repair_order": "RO-55120", "vehicle": "2018 Honda Accord", "status": "waiting_parts",
            "what_it_means": "It's waiting on parts.", "service_advisor": "Maria"}]
        # Someone else's RO number is neither confirmed nor denied.
        other = await backend.get_repair_order_status("RO-55098")
        assert other["found"] is False and "under this customer's phone number" in other["note"]
        await db.delete(conv)

    # Through a whole turn: the customer asks, the tool result reaches the model, the reply goes out.
    frm = await shop.writes("hey is my car ready yet?", [[("get_repair_order_status", {})],
                                                        "Not yet: your Accord is waiting on parts. Maria is your advisor."], frm="+12145551001")
    assert "waiting on parts" in channels.mock("sms").outbox[-1].body
    async with tenant_session(shop.tenant) as db:
        await db.execute(text("""DELETE FROM messages WHERE created_at > now() - interval '2 minutes' AND conversation_id IN
            (SELECT c.id FROM conversations c JOIN contact_identities i ON i.contact_id = c.contact_id WHERE i.value = :v)"""), {"v": frm})


async def test_no_dms_or_a_csv_upload(shop, database):
    from ondra_api.services import dms as dms_service

    async with tenant_session(database["b"]) as db:  # the other dealership has no DMS connected
        out = await dms_service.repair_order_status(db, phones=["+12145551001"], emails=[])
        assert out["found"] is False and "isn't connected" in out["note"]
    csv = "RO,Status,Phone\n77001,Ready,2145551002\n77002,Nope,2145551003\n"
    async with tenant_session(shop.tenant) as db:
        before = dict((await dms_service.dms_integration(db)).config)
        up = await dms_service.upload_repair_orders(db, csv, "ros.csv")
        assert (up["loaded"], up["skipped_count"]) == (1, 1)
        out = await dms_service.repair_order_status(db, phones=["+12145551002"], emails=[])
        assert out["repair_orders"][0]["status"] == "ready" and out["repair_orders"][0]["repair_order"] == "77001"
        integ = await dms_service.dms_integration(db)
        assert integ.status == "warning" and integ.config["provider"] == "csv"
        integ.config, integ.status = before, "ok"  # back to the demo data
