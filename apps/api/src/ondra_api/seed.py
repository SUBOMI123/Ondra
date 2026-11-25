"""Seed one example dealership: 1 tenant, 5 users, 50 vehicles, 30 contacts (BUILD_PLAN.md §12, Step 1).

    python -m ondra_api.seed            # add the example dealership
    python -m ondra_api.seed --if-empty # only if no tenant exists yet (used by docker compose)

Runs as the owner role (MIGRATIONS_DATABASE_URL) and sets tenant_id explicitly on every row. Everything here is
example data: 555 phone numbers, example.com emails. Every seeded user's password is DEV_PASSWORD.
"""

import asyncio
import random
import sys
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ondra_api.config import get_settings
from ondra_api.security import hash_password
from ondra_core.models import Consent, Contact, ContactIdentity, Policy, Tenant, User, Vehicle

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
            for i in range(30):
                name = f"{FIRST[i]} {LAST[i]}"
                vip = name in ("Robert Hale", "Tunde Bakare")
                c = Contact(tenant_id=t, display_name=name, is_vip=vip, vip_owner_user_id=owner.id if vip else None,
                            preferred_channel=channels[i % 4], language="es" if FIRST[i] in ("Carmen", "Sofia") else "en",
                            tags=["vip"] if vip else rng.sample(["sales", "service", "trade-in", "financing", "repeat"], 1))
                db.add(c)
                await db.flush()
                phone = f"+1214555{1000 + i:04d}"
                db.add(ContactIdentity(tenant_id=t, contact_id=c.id, kind="phone", value=phone, verified=True))
                db.add(ContactIdentity(tenant_id=t, contact_id=c.id, kind="email",
                                       value=f"{FIRST[i].lower()}.{LAST[i].lower()}@example.com"))
                if c.preferred_channel == "whatsapp":
                    db.add(ContactIdentity(tenant_id=t, contact_id=c.id, kind="whatsapp", value=phone))
                db.add(Consent(tenant_id=t, contact_id=c.id, channel="sms", purpose="transactional",
                               status="opted_out" if name == "Jordan Price" else "opted_in", source="seed"))
            print(f"seed: Prestige Motors ({t}) with 5 users, 50 vehicles, 30 contacts. Password: {DEV_PASSWORD}")
            return t
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(if_empty="--if-empty" in sys.argv))
