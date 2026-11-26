"""Seed one example dealership: 1 tenant, 5 users, 50 vehicles, 30 contacts (BUILD_PLAN.md §12, Step 1).

    python -m ondra_api.seed            # add the example dealership
    python -m ondra_api.seed --if-empty # only if no tenant exists yet (used by docker compose)

Runs as the owner role (MIGRATIONS_DATABASE_URL) and sets tenant_id explicitly on every row. Everything here is
example data: 555 phone numbers, example.com emails. Every seeded user's password is DEV_PASSWORD.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import random
import sys
import uuid

from ondra_core.models import (
    ChannelAddress,
    Consent,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    KnowledgeDoc,
    Message,
    Policy,
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


DEALER_PHONE = "+12145550100"
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
    """Five example conversations, one for each state the Inbox has to show. Example data, like the rest of the seed."""
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
                vehicle_of_interest={"description": "2022 Chevrolet Silverado 1500 LT"}, payment_method="finance"))

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

            pw = hash_password(DEV_PASSWORD)
            users = [User(tenant_id=t, email=e, name=n, role=r, phone=p, password_hash=pw) for e, n, r, p in USERS]
            db.add_all(users)
            await db.flush()
            owner = users[0]

            db.add(Policy(tenant_id=t, price_disclosure="listed", draft_mode=True,
                          never_say=["guaranteed approval", "final price"],
                          handoff_triggers=["discount", "trade-in value", "delivery date", "complaint"]))

            # The dealer's own number, WhatsApp and email. They use the mock adapters until a provider flag is on.
            for channel, address in (("sms", DEALER_PHONE), ("whatsapp", DEALER_PHONE), ("email", DEALER_EMAIL)):
                db.add(ChannelAddress(tenant_id=t, channel=channel, address=address, provider="mock"))
            for title, body, category in KNOWLEDGE:
                db.add(KnowledgeDoc(tenant_id=t, title=title, body=body, category=category))

            for i in range(50):
                make, model, trims, lo, hi = MODELS[i % len(MODELS)]
                year = rng.choice([2020, 2021, 2022, 2023, 2024, 2025])
                db.add(Vehicle(
                    tenant_id=t, stock_number=f"{make[:1]}{year % 100:02d}-{1000 + i * 37 % 9000:04d}", vin=_vin(rng),
                    year=year, make=make, model=model, trim=rng.choice(trims),
                    price=round(rng.uniform(lo, hi) / 100) * 100, mileage=0 if year == 2025 else rng.randint(4000, 68000),
                    status=rng.choices(["available", "hold", "sold"], [0.8, 0.12, 0.08])[0], source_feed="seed",
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
            print(f"seed: Prestige Motors ({t}) with 5 users, 50 vehicles, 30 contacts. Password: {DEV_PASSWORD}")
            return t
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(if_empty="--if-empty" in sys.argv))
