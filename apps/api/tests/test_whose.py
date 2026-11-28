"""Whose work each screen shows (docs/PLAN.md item 6). Inbox, Calls, Calendar, Tasks and Deals take the same
Mine / Everyone switch; "mine" follows what's listed (services/whose.py), and VIPs stay hidden from people who may not
see them whichever is chosen."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ondra_api.db import tenant_session
from ondra_core.models import Appointment, AppointmentType, Call, Contact, Conversation, Deal, User
from sqlalchemy import select, update

from .conftest import login

ADMIN, SALES, OTHER = "owner@prestigemotors.example", "daniel@prestigemotors.example", "maria@prestigemotors.example"


async def _user(db, email):
    return (await db.execute(select(User).where(User.email == email))).scalar_one()


async def test_mine_is_your_clients_deals_and_appointments_and_everyone_is_the_dealership(client, database):
    t = database["a"]
    now = datetime.now(UTC)
    async with tenant_session(t) as db:
        daniel, maria = await _user(db, SALES), await _user(db, OTHER)
        ours = (await db.execute(select(Contact).where(Contact.is_vip.is_(False)).order_by(Contact.display_name).limit(2))).scalars().all()
        mine_c, theirs_c = ours
        # Daniel is given Mine's conversation and deal; Maria gets the other client's.
        convs = (await db.execute(select(Conversation).where(Conversation.contact_id.in_([c.id for c in ours])))).scalars().all()
        before = {c.id: c.assigned_user_id for c in convs}
        for c in convs:
            c.assigned_user_id = daniel.id if c.contact_id == mine_c.id else maria.id
        deals = (await db.execute(select(Deal).where(Deal.contact_id.in_([c.id for c in ours])))).scalars().all()
        deals_before = {d.id: d.owner_user_id for d in deals}
        for d in deals:
            d.owner_user_id = daniel.id if d.contact_id == mine_c.id else maria.id
        if not any(d.contact_id == mine_c.id for d in deals):
            db.add(Deal(contact_id=mine_c.id, type="sales", stage="new", owner_user_id=daniel.id))
        kind = (await db.execute(select(AppointmentType).limit(1))).scalar_one()
        soon = now.replace(minute=0, second=0, microsecond=0) + timedelta(days=3, hours=1)
        a1 = Appointment(contact_id=mine_c.id, appointment_type_id=kind.id, starts_at=soon, ends_at=soon + timedelta(minutes=30),
                         assigned_user_id=daniel.id, status="booked", source="staff")
        a2 = Appointment(contact_id=theirs_c.id, appointment_type_id=kind.id, starts_at=soon, ends_at=soon + timedelta(minutes=30),
                         assigned_user_id=maria.id, status="booked", source="staff")
        call_mine = Call(contact_id=mine_c.id, direction="inbound", handled_by="missed", started_at=now - timedelta(minutes=5))
        call_theirs = Call(contact_id=theirs_c.id, direction="inbound", handled_by="ai", started_at=now - timedelta(minutes=6))
        db.add_all([a1, a2, call_mine, call_theirs])
        await db.flush()
        made = (a1.id, a2.id, call_mine.id, call_theirs.id)
        ids = (str(mine_c.id), str(theirs_c.id), str(daniel.id))
    sales = await login(client, SALES)
    try:
        # Inbox
        inbox = lambda w: client.get("/conversations", params={"whose": w}, headers=sales)  # noqa: E731
        mine = {i["contact"]["id"] for i in (await inbox("mine")).json()["items"]}
        everyone = {i["contact"]["id"] for i in (await inbox("everyone")).json()["items"]}
        assert ids[0] in mine and ids[1] not in mine and ids[1] in everyone and mine <= everyone
        # Calls
        calls = lambda w: client.get("/calls", params={"whose": w}, headers=sales)  # noqa: E731
        mine = {str(i["id"]) for i in (await calls("mine")).json()["items"]}
        everyone = {str(i["id"]) for i in (await calls("everyone")).json()["items"]}
        assert str(made[2]) in mine and str(made[3]) not in mine and str(made[3]) in everyone
        # Deals: every deal under Mine is Daniel's
        board = (await client.get("/deals", params={"whose": "mine"}, headers=sales)).json()
        mine_deals = [d for s in board["stages"] for d in s["deals"]]
        assert mine_deals and all(d["owner_id"] == ids[2] for d in mine_deals) and any(d["contact_id"] == ids[0] for d in mine_deals)
        all_deals = [d for s in (await client.get("/deals", headers=sales)).json()["stages"] for d in s["deals"]]
        assert any(d["contact_id"] == ids[1] for d in all_deals)
        # Calendar: only appointments with Daniel, in his own lane
        day = soon.astimezone(ZoneInfo("America/Chicago")).date().isoformat()  # the dealership's day
        cal = (await client.get("/calendar", params={"date": day, "whose": "mine"}, headers=sales)).json()
        assert {a["id"] for a in cal["appointments"]} >= {str(made[0])} and str(made[1]) not in {a["id"] for a in cal["appointments"]}
        assert all(a["assigned_user_id"] == ids[2] for a in cal["appointments"])
        assert [lane["id"] for lane in cal["lanes"] if lane["kind"] == "person"] == [ids[2]]
        full = (await client.get("/calendar", params={"date": day}, headers=sales)).json()
        assert str(made[1]) in {a["id"] for a in full["appointments"]}
    finally:
        async with tenant_session(t) as db:
            for i in made[:2]:
                await db.execute(Appointment.__table__.delete().where(Appointment.id == i))
            for i in made[2:]:
                await db.execute(Call.__table__.delete().where(Call.id == i))
            for cid, uid in before.items():
                await db.execute(update(Conversation).where(Conversation.id == cid).values(assigned_user_id=uid))
            for did, uid in deals_before.items():
                await db.execute(update(Deal).where(Deal.id == did).values(owner_user_id=uid))
            await db.execute(Deal.__table__.delete().where(Deal.contact_id == mine_c.id, Deal.id.notin_(list(deals_before) or [mine_c.id])))


async def test_vips_stay_hidden_from_a_salesperson_on_everyone_too(client, database):
    sales, admin = await login(client, SALES), await login(client, ADMIN)
    async with tenant_session(database["a"]) as db:
        daniel = await _user(db, SALES)
        vips = {str(c.id) for c in (await db.execute(select(Contact).where(Contact.is_vip.is_(True)))).scalars()
                if c.vip_owner_user_id != daniel.id}
    assert vips
    for path, pick in (("/conversations", lambda r: {i["contact"]["id"] for i in r["items"]}),
                       ("/deals", lambda r: {d["contact_id"] for s in r["stages"] for d in s["deals"]}),
                       ("/calls", lambda r: {i["contact"]["id"] for i in r["items"] if i.get("contact")})):
        for w in ("mine", "everyone"):
            assert not (pick((await client.get(path, params={"whose": w}, headers=sales)).json()) & vips), (path, w)
    seen = {i["contact"]["id"] for i in (await client.get("/conversations", params={"whose": "everyone"}, headers=admin)).json()["items"]}
    assert seen & vips  # an admin sees them


async def test_an_unknown_choice_is_refused(client, database):
    sales = await login(client, SALES)
    assert (await client.get("/conversations", params={"whose": "team"}, headers=sales)).status_code == 422


async def test_today_is_your_own_for_a_salesperson_and_shows_who_is_behind_to_an_admin(client, database):
    t = database["a"]
    now = datetime.now(UTC)
    async with tenant_session(t) as db:
        daniel, maria = await _user(db, SALES), await _user(db, OTHER)
        c = (await db.execute(select(Contact).where(Contact.is_vip.is_(False)).limit(1))).scalar_one()
        kind = (await db.execute(select(AppointmentType).limit(1))).scalar_one()
        # Today, an hour from now in the dealership's day (or the start of the day just past if it's late).
        at = max(now + timedelta(minutes=30), now)
        chi_end = datetime.combine(at.astimezone(ZoneInfo("America/Chicago")).date(), datetime.max.time(), ZoneInfo("America/Chicago"))
        at = min(at, chi_end - timedelta(minutes=31))
        theirs = Appointment(contact_id=c.id, appointment_type_id=kind.id, starts_at=at, ends_at=at + timedelta(minutes=30),
                             assigned_user_id=maria.id, status="booked", source="staff")
        db.add(theirs)
        await db.flush()
        made = theirs.id
    try:
        sales, admin = await login(client, SALES), await login(client, ADMIN)
        mine = (await client.get("/today", headers=sales)).json()
        assert str(made) not in {a["id"] for a in mine["appointments"]} and mine["team"] == []
        everyone = (await client.get("/today", headers=admin)).json()
        assert str(made) in {a["id"] for a in everyone["appointments"]}
        # Seeded overdue tasks belong to Daniel: he's on the admin's "who's behind" list.
        behind = {p["name"]: p for p in everyone["team"]}
        assert behind and all(p["overdue"] + p["callbacks"] > 0 for p in everyone["team"])
        assert daniel.name in behind
    finally:
        async with tenant_session(t) as db:
            await db.execute(Appointment.__table__.delete().where(Appointment.id == made))
