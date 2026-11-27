"""Seed one example dealership: 1 tenant, 5 users, 50 vehicles, 30 contacts (BUILD_PLAN.md §12, Step 1).

    python -m ondra_api.seed            # add the example dealership
    python -m ondra_api.seed --if-empty # only if no tenant exists yet (used by docker compose)

Runs as the owner role (MIGRATIONS_DATABASE_URL) and sets tenant_id explicitly on every row. Everything here is
example data: 555 phone numbers, example.com emails. Every seeded user's password is DEV_PASSWORD.
"""

import asyncio
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ondra_core.models import (
    Appointment,
    AppointmentType,
    Call,
    ChannelAddress,
    Consent,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    Event,
    Integration,
    KnowledgeDoc,
    Message,
    Policy,
    Resource,
    Task,
    Tenant,
    User,
    Vehicle,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ondra_api.config import get_settings
from ondra_api.security import hash_password

DEV_PASSWORD = "ondra-dev-password"

USERS = [
    ("owner@prestigemotors.example", "Samuel Adeyemi", "owner", "+12145550100"),
    ("manager@prestigemotors.example", "Grace Thompson", "manager", "+12145550101"),
    ("daniel@prestigemotors.example", "Daniel Okafor", "sales", "+12145550102"),
    ("maria@prestigemotors.example", "Maria Lopez", "service", "+12145550103"),
    ("admin@prestigemotors.example", "Chris Bell", "admin", "+12145550104"),
]

# Body style and seats, as an inventory feed would provide them (search and "3-row" questions rely on it).
BODY = {
    "Silverado 1500": ("truck", 5), "F-150": ("truck", 5), "1500": ("truck", 5), "Highlander": ("SUV", 8),
    "RAV4 Hybrid": ("SUV", 5), "CR-V": ("SUV", 5), "RX 350": ("SUV", 5), "GLE 450": ("SUV", 5), "X5": ("SUV", 5),
    "Grand Cherokee L": ("SUV", 7), "Bronco": ("SUV", 5), "Model Y": ("SUV", 5), "Tahoe": ("SUV", 8), "Sport": ("SUV", 5),
}

MODELS = [
    ("Chevrolet", "Silverado 1500", ["LT", "RST", "LTZ"], 38000, 56000),
    ("Ford", "F-150", ["XLT", "Lariat", "Platinum"], 36000, 62000),
    ("Toyota", "Highlander", ["XLE", "Limited"], 31000, 46000),
    ("Toyota", "RAV4 Hybrid", ["XLE", "XSE"], 28000, 38000),
    ("Honda", "CR-V", ["EX", "EX-L", "Sport"], 26000, 36000),
    ("Lexus", "RX 350", ["Premium", "F Sport"], 36000, 52000),
    ("Mercedes-Benz", "GLE 450", ["4MATIC"], 52000, 72000),
    ("BMW", "X5", ["xDrive40i", "M60i"], 48000, 79000),
    ("Jeep", "Grand Cherokee L", ["Laredo", "Limited", "Overland"], 33000, 52000),
    ("Ford", "Bronco", ["Big Bend", "Badlands"], 36000, 55000),
    ("Ram", "1500", ["Big Horn", "Laramie"], 34000, 58000),
    ("Tesla", "Model Y", ["Long Range", "Performance"], 33000, 45000),
    ("Chevrolet", "Tahoe", ["LT", "Z71", "High Country"], 46000, 76000),
    ("Range Rover", "Sport", ["SE", "Dynamic SE"], 68000, 98000),
]

FIRST = ["Kevin", "Sarah", "Marcus", "Elena", "Jordan", "Aisha", "Tom", "Priya", "Luis", "Grace", "Darnell", "Hannah",
         "Omar", "Mei", "Victor", "Natalie", "Ben", "Rachel", "Tunde", "Carmen", "Ethan", "Fatima", "Jake", "Lena",
         "Andre", "Sofia", "Malik", "Chloe", "Ravi", "Robert"]
LAST = ["Lee", "King", "Taylor", "Ruiz", "Price", "Bello", "Nguyen", "Shah", "Romero", "Kim", "Brooks", "Weiss",
        "Haddad", "Chen", "Alvarez", "Ross", "Carter", "Green", "Bakare", "Ortiz", "Walker", "Hassan", "Miller", "Novak",
        "Jackson", "Moreno", "Wright", "Dubois", "Patel", "Hale"]


def _vin(rng: random.Random) -> str:
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "".join(rng.choice(chars) for _ in range(17))


# The dealer's phone line. A real number (set by infra/telephony/connect_line.py in .env) routes real calls here.
DEALER_PHONE = os.getenv("DEALER_PHONE") or "+12145550100"
DEALER_EMAIL = "sales@prestige-motors.example"

KNOWLEDGE = [
    ("Opening hours", ("Sales: Monday to Friday 9 am to 7 pm, Saturday 9 am to 6 pm, closed Sunday. "
     "Service: Monday to Friday 7 am to 6 pm, Saturday 8 am to 2 pm."), "hours"),
    ("Location and parking", ("4100 Lemmon Ave, Dallas, TX 75219. Free customer parking in front of the showroom."), "location"),
    ("Financing", ("We work with several banks and credit unions. A finance manager reviews every application; we "
     "can't say whether an application will be approved until it's submitted."), "financing"),
    ("Test drives", ("Test drives are available during sales hours. Bring a valid driver's license. They take about "
     "30 minutes."), "sales"),
    ("Shipping and export", ("We can arrange shipping through partner carriers. A salesperson confirms costs, "
     "documents and timing for each order."), "shipping"),
    ("Service loaners and shuttle", ("Free shuttle within 10 miles. Loaner cars for repairs over 4 hours, "
     "subject to availability."), "service"),
]


async def _seed_conversations(db, t, contacts: dict, users: dict) -> None:
    """Six example conversations, one for each state the Inbox has to show. Example data, like the rest of the seed."""
    now = datetime.now(UTC)

    def at(minutes_ago: int) -> datetime:
        return now - timedelta(minutes=minutes_ago)

    def conv(name, channel, status="open", ai_mode="auto"):
        c = Conversation(tenant_id=t, contact_id=contacts[name].id, channel=channel, status=status, ai_mode=ai_mode,
                         last_inbound_at=at(30))
        db.add(c)
        return c

    def msg(c, direction, author, body, minutes_ago, status, draft=False, user=None):
        db.add(Message(tenant_id=t, conversation_id=c.id, direction=direction, author_type=author, body=body,
                       status=status, is_draft=draft, author_user_id=user.id if user else None,
                       created_at=at(minutes_ago), provider="mock" if direction == "inbound" else None,
                       provider_message_id=f"seed-{c.channel}-{minutes_ago}-{direction}" if direction == "inbound" else None))

    # 1. A VIP waiting for the owner.
    robert = conv("Robert Hale", "sms", status="waiting_staff")
    await db.flush()
    msg(robert, "inbound", "customer", "Sam, call me when you get a minute. It's about the Range Rover for my daughter.", 95, "received")
    db.add(Task(tenant_id=t, title="Robert Hale: VIP message waiting for a personal reply", contact_id=contacts["Robert Hale"].id,
                conversation_id=robert.id, assignee_user_id=users["owner"].id, source="rule", urgency="high",
                brief="VIP message waiting for a personal reply", due_at=at(80)))

    # 2. Ondra's draft waiting for approval (draft mode).
    kevin = conv("Kevin Lee", "email", status="waiting_staff")
    await db.flush()
    msg(kevin, "inbound", "customer", "Is the gray 2022 Silverado still available? Is the price negotiable? I'd need financing.", 42, "received")
    msg(kevin, "outbound", "ai", "Hi Kevin, the 2022 Silverado 1500 LT in gray is here, listed at $44,900. I can't change "
        "the price by email, so I've asked Daniel from our sales team to go over pricing and financing with you. Would "
        "Thursday after work suit you to see it?", 41, "queued", draft=True)
    db.add(Deal(tenant_id=t, contact_id=contacts["Kevin Lee"].id, type="sales", stage="qualified", source_channel="email",
                vehicle_of_interest={"description": "2022 Chevrolet Silverado 1500 LT"}, payment_method="finance",
                owner_user_id=users["sales"].id))

    # 3. Handed to sales, and the follow-up is overdue.
    sarah = conv("Sarah King", "sms", status="waiting_staff")
    await db.flush()
    msg(sarah, "inbound", "customer", "whats the best you can do on the highlander? i have 31k cash", 190, "received")
    msg(sarah, "outbound", "ai", "The 2021 Highlander XLE is listed at $33,900. I can't negotiate by text, so I've passed "
        "your offer to our sales team; they'll call you shortly.", 189, "sent")
    db.add(Task(tenant_id=t, title="Sarah King: Talk price with Sarah", contact_id=contacts["Sarah King"].id, conversation_id=sarah.id,
                assignee_user_id=users["sales"].id, source="ai_handoff", urgency="high", due_at=at(170),
                brief="Cash buyer offering $31,000 on the 2021 Highlander XLE listed at $33,900. Ready to buy this week."))
    db.add(Deal(tenant_id=t, contact_id=contacts["Sarah King"].id, type="sales", stage="new", source_channel="sms",
                vehicle_of_interest={"description": "2021 Toyota Highlander XLE"}, budget_max=31000, payment_method="cash"))

    # 4. Handled end to end by Ondra.
    marcus = conv("Marcus Taylor", "whatsapp", status="waiting_customer")
    await db.flush()
    msg(marcus, "inbound", "customer", "are you open on sunday?", 300, "received")
    msg(marcus, "outbound", "ai", "We're closed on Sundays. Sales is open Monday to Friday 9 am to 7 pm and Saturday 9 am "
        "to 6 pm.", 299, "sent")

    # 5. Opted out: nothing can be sent.
    jordan = conv("Jordan Price", "sms", status="waiting_staff")
    await db.flush()
    msg(jordan, "inbound", "customer", "is the civic sport still for sale", 600, "received")
    msg(jordan, "outbound", "ai", "Yes, the 2021 Civic Sport is here, listed at $21,900. Want to come see it?", 599, "sent")
    msg(jordan, "inbound", "customer", "STOP", 590, "received")

    await _seed_after_hours_lead(db, t, contacts, users)


async def _seed_pipeline(db, t, contacts: dict, users: dict) -> None:
    """A sales board that looks like a working week: a deal at every stage, each with a short conversation, a
    salesperson, and what's next (a booked test drive, a task), plus one won and one lost."""
    from ondra_api.services.metrics import lead_captured

    now = datetime.now(UTC)
    local = now.astimezone(ZoneInfo("America/Chicago"))
    test_drive = (await db.execute(select(AppointmentType).where(AppointmentType.category == "test_drive"))).scalars().first()
    sales, manager = users["sales"], users["manager"]

    async def deal(name, channel, stage, owner, wants, said, *, budget=None, pay=None, trade_in=None, timeline=None,
                   by_ai=False, days_ago=2, reason=None):
        conv = Conversation(tenant_id=t, contact_id=contacts[name].id, channel=channel, status="waiting_customer",
                            ai_mode="auto", assigned_user_id=owner.id, last_inbound_at=now - timedelta(days=days_ago))
        db.add(conv)
        await db.flush()
        for i, (who, body) in enumerate(said):
            mins = days_ago * 1440 - i * 4
            db.add(Message(tenant_id=t, conversation_id=conv.id, direction="inbound" if who == "customer" else "outbound",
                           author_type=who, author_user_id=owner.id if who == "user" else None, body=body,
                           status="received" if who == "customer" else "delivered", created_at=now - timedelta(minutes=mins),
                           provider="mock" if who == "customer" else None,
                           provider_message_id=f"seed-pipe-{name}-{i}" if who == "customer" else None))
        voi = {"description": wants, **({"trade_in": trade_in} if trade_in else {})}
        d = Deal(tenant_id=t, contact_id=contacts[name].id, type="sales", stage=stage, source_channel=channel,
                 vehicle_of_interest=voi, budget_max=budget, payment_method=pay, timeline=timeline, owner_user_id=owner.id,
                 lost_reason=reason, created_at=now - timedelta(days=days_ago + 1), updated_at=now - timedelta(days=max(days_ago - 1, 0)))
        db.add(d)
        await db.flush()
        if by_ai:
            lead_captured(db, d, by="ai", after_hours=False, at=now - timedelta(days=days_ago + 1))
        return d

    andre = await deal("Andre Jackson", "sms", "appointment", sales, "2023 Honda Accord EX-L", [
        ("customer", "Hi, is the white Accord EX-L still there? I could come by tomorrow morning."),
        ("ai", ("It is, Andre: the 2023 Accord EX-L in white, listed at $29,400. I've booked you a test drive for tomorrow "
                "at 10:30 am with Daniel. Bring your Civic if you'd like a trade-in value the same day.")),
        ("customer", "Perfect, see you then"),
    ], budget=30000, pay="finance", trade_in="2016 Honda Civic LX, about 88,000 miles", timeline="this week", by_ai=True, days_ago=1)
    if test_drive is not None:
        start = (local + timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0)
        db.add(Appointment(tenant_id=t, contact_id=contacts["Andre Jackson"].id, deal_id=andre.id, appointment_type_id=test_drive.id,
                           starts_at=start, ends_at=start + timedelta(minutes=45), assigned_user_id=sales.id, status="booked",
                           blocks_until=start + timedelta(minutes=45 + test_drive.buffer_min),
                           source="ai"))
    await deal("Carmen Ortiz", "phone", "negotiating", sales, "2022 Toyota RAV4 XLE", [
        ("customer", "We liked the RAV4 on Saturday. Can you do better than $31,900 if we trade in the Rogue?"),
        ("user", "Thanks Carmen. Our used-car manager is looking at the Rogue today; I'll call you with numbers by 5."),
    ], budget=30000, pay="finance", trade_in="2018 Nissan Rogue SV", timeline="this weekend", days_ago=1)
    await deal("Darnell Brooks", "whatsapp", "qualified", manager, "Ford F-150 XLT, 2021 or newer", [
        ("customer", "Looking for an F-150 XLT, 2021 or newer, under 42k. Need tow package."),
        ("ai", ("We have two that fit, Darnell: a 2021 and a 2022 F-150 XLT, both with the tow package. I've asked Grace "
                "to send you photos and the window stickers today.")),
    ], budget=42000, pay="cash", by_ai=True, days_ago=3)
    db.add(Task(tenant_id=t, title="Darnell Brooks: Send Darnell the two F-150s", contact_id=contacts["Darnell Brooks"].id,
                assignee_user_id=manager.id, source="ai_handoff", urgency="normal", due_at=now + timedelta(hours=20),
                brief="Wants an F-150 XLT 2021+, tow package, under $42,000, paying cash. Send photos and window stickers."))
    await deal("Chloe Dubois", "email", "new", sales, "Tesla Model 3 or a similar EV", [
        ("customer", "Do you have any used EVs around $35k? Tesla Model 3 ideally."),
        ("ai", ("Hi Chloe, we have a 2021 Model 3 Long Range listed at $33,500, and a 2022 Hyundai Ioniq 5 at $34,900. "
                "Would you like to see either this week?")),
    ], budget=35000, by_ai=True, days_ago=0)
    await deal("Fatima Hassan", "sms", "won", sales, "2020 Mercedes-Benz GLC 300", [
        ("customer", "Picked it up, thank you Daniel! Love it."),
    ], pay="finance", days_ago=4)
    await deal("Ethan Walker", "email", "lost", manager, "2021 Mazda CX-5 Touring", [
        ("customer", "Thanks for your help, but we found one closer to home."),
    ], budget=26000, days_ago=6, reason="Bought elsewhere")


async def _seed_after_hours_lead(db, t, contacts: dict, users: dict) -> None:
    """6. An after-hours lead: a buyer in Lagos writes at 2 am Dallas time; Ondra answers and books sales for the
    morning. The Inbox's "After-hours leads" view shows it."""
    now = datetime.now(UTC)
    tz = ZoneInfo("America/Chicago")
    night = datetime.now(tz).replace(hour=2, minute=10, second=0, microsecond=0)
    if night > datetime.now(tz) - timedelta(minutes=30):
        night -= timedelta(days=1)
    night_ago = int((now - night.astimezone(UTC)).total_seconds() // 60)
    db.add(ContactIdentity(tenant_id=t, contact_id=contacts["Aisha Bello"].id, kind="whatsapp", value="+12145551005"))
    aisha = Conversation(tenant_id=t, contact_id=contacts["Aisha Bello"].id, channel="whatsapp", status="waiting_staff",
                         ai_mode="auto", last_inbound_at=night.astimezone(UTC))
    db.add(aisha)
    await db.flush()

    def msg(c, direction, body, minutes_ago, status):
        db.add(Message(tenant_id=t, conversation_id=c.id, direction=direction, author_type="customer" if direction == "inbound" else "ai",
                       body=body, status=status, created_at=now - timedelta(minutes=minutes_ago),
                       provider="mock" if direction == "inbound" else None,
                       provider_message_id=f"seed-whatsapp-{minutes_ago}-{direction}" if direction == "inbound" else None))

    msg(aisha, "inbound", "Good morning from Lagos. Is the Lexus RX 350 still available, and can you ship it to "
        "Nigeria?", night_ago, "received")
    msg(aisha, "outbound", "Good morning Aisha. Yes, we have the Lexus RX 350 in stock. We arrange shipping through "
        "partner carriers, and a salesperson confirms the cost, documents and timing for each order. I've asked our sales "
        "team to message you when we open at 9 am Dallas time, which is 4 pm in Lagos.", night_ago - 1, "sent")
    open_at = night.replace(hour=9, minute=30).astimezone(UTC)
    db.add(Task(tenant_id=t, title="Aisha Bello: Shipping a Lexus RX 350 to Lagos", contact_id=contacts["Aisha Bello"].id,
                conversation_id=aisha.id, assignee_user_id=users["sales"].id, source="ai_handoff", urgency="normal",
                due_at=open_at, brief="Buyer in Lagos wants the Lexus RX 350 shipped to Nigeria. Needs shipping cost, "
                "documents and timing. Prefers WhatsApp; Lagos is 7 hours ahead of Dallas in winter, 6 in summer."))
    db.add(Deal(tenant_id=t, contact_id=contacts["Aisha Bello"].id, type="sales", stage="new", source_channel="whatsapp",
                vehicle_of_interest={"description": "Lexus RX 350"}, created_at=night.astimezone(UTC)))


async def _seed_calls(db, t, contacts: dict, users: dict) -> None:
    """Example calls, one per state the Calls screen shows. Example data, like the rest of the seed."""
    now = datetime.now(UTC)

    def at(minutes_ago: int) -> datetime:
        return now - timedelta(minutes=minutes_ago)

    async def call(name, minutes_ago, secs, handled_by, outcome, **kw):
        c = contacts[name]
        conv = Conversation(tenant_id=t, contact_id=c.id, channel="phone", ai_mode="auto",
                            status=kw.pop("status", "waiting_customer"))
        db.add(conv)
        await db.flush()
        phone = (await db.execute(select(ContactIdentity.value).where(ContactIdentity.contact_id == c.id,
                                                                      ContactIdentity.kind == "phone"))).scalar_one()
        k = Call(tenant_id=t, conversation_id=conv.id, contact_id=c.id, provider_call_sid=kw.pop("sid", f"seed-{name}"), direction="inbound",
                 started_at=at(minutes_ago), ended_at=at(minutes_ago) + timedelta(seconds=secs), duration_s=secs,
                 handled_by=handled_by, outcome=outcome, from_number=phone, to_number=DEALER_PHONE, **kw)
        db.add(k)
        await db.flush()
        return conv, k

    # 1. Ondra answered and booked a service.
    await call("Grace Kim", 55, 134, "ai", "booked", transcript=[
        {"who": "agent", "text": "Thanks for calling Prestige Motors. How can I help you today?"},
        {"who": "caller", "text": "Hi, my Camry needs an oil change. Anything Saturday morning?"},
        {"who": "agent", "text": "Let me check Saturday morning."},
        {"who": "agent", "text": "I have 8:00 Saturday with Maria in Bay 1. Will you wait, need a loaner, or drop it off?"},
        {"who": "caller", "text": "I'll wait. 8 works."},
        {"who": "agent", "text": "You're booked for an oil change at 8:00 on Saturday with Maria. See you then."},
    ], summary="Grace Kim called to book an oil change for her Camry. Booked Saturday 8:00 am with Maria in Bay 1; "
               "she'll wait. Nothing else needed.",
       metrics={"summary": {"turns": 4, "avg_ms": 1240, "p90_ms": 1710, "over_1s": 3, "tools": ["check_availability",
                                                                                              "book_appointment"]}})
    # 2. A VIP: rang the owner directly; Ondra never answered.
    await call("Robert Hale", 140, 312, "owner", "transferred", transferred_to_user_id=users["owner"].id)
    # 3. Put through to sales by Ondra (warm transfer).
    await call("Ethan Walker", 230, 418, "staff", "transferred", transferred_to_user_id=users["sales"].id, transcript=[
        {"who": "agent", "text": "Thanks for calling Prestige Motors. How can I help you today?"},
        {"who": "caller", "text": "I want to talk to someone about trading in my F-150 on the Tacoma."},
        {"who": "agent", "text": "One of our sales team can go over that with you. Shall I put you through to Daniel?"},
        {"who": "caller", "text": "Yes please."},
    ], summary="Ethan Walker wants to trade in his F-150 toward the Tacoma. Put through to Daniel, who took the call.")
    # 4. Missed, and no text-back: Jordan opted out of texts, so a person calls back.
    conv, k = await call("Jordan Price", 20, 0, "missed", "no answer", status="waiting_staff")
    db.add(Event(tenant_id=t, type="call.text_back_skipped", payload={"call_id": str(k.id), "reason": "opted out"}))
    db.add(Task(tenant_id=t, title="Jordan Price: Call Jordan back", contact_id=contacts["Jordan Price"].id,
                conversation_id=conv.id, assignee_user_id=users["sales"].id, source="rule", urgency="normal",
                brief="Missed call.", due_at=at(-100)))
    # 5. Rang twice before anyone rang back: one text (the second ring doesn't text again), one task, one try so far.
    sales = str(users["sales"].id)
    conv, first_ring = await call("Carmen Ortiz", 95, 0, "missed", "no answer", status="waiting_staff")
    db.add(Event(tenant_id=t, type="call.text_back", payload={"call_id": str(first_ring.id),
                                                              "contact_id": str(contacts["Carmen Ortiz"].id)}))
    _, second = await call("Carmen Ortiz", 70, 0, "missed", "no answer", status="waiting_staff", sid="seed-Carmen Ortiz-2",
                           metrics={"callback_attempts": [{"by": sales, "at": at(40).isoformat()}]})
    db.add(Event(tenant_id=t, type="call.text_back_skipped", payload={"call_id": str(second.id), "reason": "texted recently"}))
    db.add(Task(tenant_id=t, title="Carmen Ortiz: Call Carmen back (called 2 times)", contact_id=contacts["Carmen Ortiz"].id,
                conversation_id=conv.id, assignee_user_id=users["sales"].id, source="rule", urgency="high",
                brief="Missed call.", due_at=at(-30)))
    # 6. Missed yesterday, and Daniel rang back within the hour.
    _, k = await call("Andre Jackson", 26 * 60, 0, "missed", "no answer", status="waiting_customer")
    k.callback_done_at = at(26 * 60 - 35)
    k.metrics = {"callback": {"by": sales, "at": k.callback_done_at.isoformat(), "calls": [str(k.id)], "tasks": []}}
    db.add(Event(tenant_id=t, type="call.text_back_skipped", payload={"call_id": str(k.id), "reason": "no recorded consent"}))


async def seed(if_empty: bool = False) -> uuid.UUID | None:
    engine = create_async_engine(get_settings().migrations_database_url)
    rng = random.Random(42)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db, db.begin():
            if if_empty and (await db.execute(select(func.count()).select_from(Tenant))).scalar_one() > 0:
                print("seed: a tenant already exists, skipping")
                return None
            tenant = Tenant(
                name="Prestige Motors",
                timezones=["America/Chicago"],
                business_hours={d: ["09:00", "19:00"] for d in ("mon", "tue", "wed", "thu", "fri")} | {"sat": ["09:00", "18:00"]},
                settings={"city": "Dallas, TX", "example": True},
            )
            db.add(tenant)
            await db.flush()
            t = tenant.id

            # The demo dealership's service lane answers from demo repair orders (ondra_core.dms.DEMO_ORDERS).
            db.add(Integration(tenant_id=t, kind="dms", config={"provider": "mock"}, status="ok"))

            pw = hash_password(DEV_PASSWORD)
            users = [User(tenant_id=t, email=e, name=n, role=r, phone=p, password_hash=pw) for e, n, r, p in USERS]
            db.add_all(users)
            await db.flush()
            owner = users[0]

            db.add(Policy(tenant_id=t, price_disclosure="listed", draft_mode=True,
                          never_say=["guaranteed approval", "final price"],
                          handoff_triggers=["A discount or final price", "What their trade-in is worth", "A delivery date", "A complaint"]))

            # The dealer's own number, WhatsApp and email. They use the mock adapters until a provider flag is on.
            for channel, address in (("sms", DEALER_PHONE), ("whatsapp", DEALER_PHONE), ("email", DEALER_EMAIL),
                                     ("phone", DEALER_PHONE)):
                db.add(ChannelAddress(tenant_id=t, channel=channel, address=address, provider="mock"))
            # Booking: the templates as this dealer's appointment types, three service bays and two loaners.
            from ondra_api.services.booking import DEFAULT_REMINDERS, TEMPLATES

            service_hours = {d: ["07:00", "18:00"] for d in ("mon", "tue", "wed", "thu", "fri")} | {"sat": ["08:00", "14:00"]}
            for tpl in TEMPLATES.values():
                db.add(AppointmentType(tenant_id=t, **tpl, reminder_schedule=DEFAULT_REMINDERS,
                                       bookable_hours=service_hours if tpl["category"] == "service" else {}))
            for name in ("Bay 1", "Bay 2", "Bay 3"):
                db.add(Resource(tenant_id=t, kind="service_bay", name=name))
            for name in ("Loaner 1", "Loaner 2"):
                db.add(Resource(tenant_id=t, kind="loaner", name=name))
            for title, body, category in KNOWLEDGE:
                db.add(KnowledgeDoc(tenant_id=t, title=title, body=body, category=category))

            for i in range(50):
                make, model, trims, lo, hi = MODELS[i % len(MODELS)]
                year = rng.choice([2020, 2021, 2022, 2023, 2024, 2025])
                # Priced like real stock: new near the top of the model's range, losing value with age and miles
                # (an example 2025 at zero miles was quoted below used 2022s on the first real call).
                age = 2025 - year
                mileage = 0 if age == 0 else min(rng.randint(8000, 13000) * age, 72000)
                value = hi * 0.87 ** age - mileage * 0.06 + rng.uniform(-0.03, 0.03) * hi
                price = round(max(value, lo * 0.55) / 100) * 100
                db.add(Vehicle(
                    tenant_id=t, stock_number=f"{make[:1]}{year % 100:02d}-{1000 + i * 37 % 9000:04d}", vin=_vin(rng),
                    year=year, make=make, model=model, trim=rng.choice(trims),
                    price=price, mileage=mileage,
                    status=rng.choices(["available", "hold", "sold"], [0.8, 0.12, 0.08])[0], source_feed="seed", raw={"body": BODY.get(model, ("car", 5))[0], "seats": BODY.get(model, ("car", 5))[1]},
                    # On the lot for a realistic spread: most turn within 45 days, a few sit for months.
                    created_at=datetime.now(UTC) - timedelta(days=rng.choices([rng.randint(1, 30), rng.randint(31, 60), rng.randint(61, 120)], [0.6, 0.28, 0.12])[0]),
                ))

            channels = ["sms", "email", "whatsapp", "phone"]
            by_name: dict[str, Contact] = {}
            for i in range(30):
                name = f"{FIRST[i]} {LAST[i]}"
                vip = name in ("Robert Hale", "Tunde Bakare")
                c = Contact(tenant_id=t, display_name=name, is_vip=vip, vip_owner_user_id=owner.id if vip else None,
                            preferred_channel=channels[i % 4], language="es" if FIRST[i] in ("Carmen", "Sofia") else "en",
                            tags=["vip"] if vip else rng.sample(["sales", "service", "trade-in", "financing", "repeat"], 1))
                db.add(c)
                await db.flush()
                by_name[name] = c
                phone = f"+1214555{1000 + i:04d}"
                db.add(ContactIdentity(tenant_id=t, contact_id=c.id, kind="phone", value=phone, verified=True))
                db.add(ContactIdentity(tenant_id=t, contact_id=c.id, kind="email",
                                       value=f"{FIRST[i].lower()}.{LAST[i].lower()}@example.com"))
                if c.preferred_channel == "whatsapp":
                    db.add(ContactIdentity(tenant_id=t, contact_id=c.id, kind="whatsapp", value=phone))
                db.add(Consent(tenant_id=t, contact_id=c.id, channel="sms", purpose="transactional",
                               status="opted_out" if name == "Jordan Price" else "opted_in", source="seed"))
            await db.flush()
            await db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(t)})
            from ondra_api.services.knowledge import embed_missing

            try:
                async with db.begin_nested():
                    n = await embed_missing(db)
                print(f"seed: embedded {n} knowledge answers")
            except Exception as exc:  # noqa: BLE001  answers stay; search uses full text until they're embedded
                print(f"seed: couldn't embed knowledge answers ({type(exc).__name__}); "
                      "run `python -m ondra_api.services.knowledge` later")
            await _seed_conversations(db, t, by_name, {u.role: u for u in users})
            await _seed_calls(db, t, by_name, {u.role: u for u in users})
            await _seed_pipeline(db, t, by_name, {u.role: u for u in users})
            # The seeded history gets its events, so the dashboard has numbers to show (marked as backfilled).
            from ondra_api.services.metrics import backfill

            await db.flush()
            await backfill(db)
            print(f"seed: Prestige Motors ({t}) with 5 users, 50 vehicles, 30 contacts. Password: {DEV_PASSWORD}")
            return t
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(if_empty="--if-empty" in sys.argv))
