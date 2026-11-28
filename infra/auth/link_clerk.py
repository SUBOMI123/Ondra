"""Connect an Ondra dealership to Clerk (sign-in), and invite its owner. Safe to run again.

    uv run python infra/auth/link_clerk.py --dealer "Prestige Motors" --owner-email you@yourdealership.com

- Creates the dealership's Clerk Organization if it has none, and stores its id on the dealership (tenants.clerk_org_id).
- With --owner-email: sets that email on the dealership's owner in Ondra and has Clerk email them an invitation
  (Organization admin). When they accept and sign in, Ondra links their Clerk account by that verified email.
  Owners must then turn on two-step sign-in (CLERK_MFA_ROLES).

Needs CLERK_SECRET_KEY (or, in Ondra's cloud build environment, the proxy adds it) and the database URLs.
"""

from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import select, text

os.environ.setdefault("CLERK_SECRET_KEY", "proxy-injected")

from ondra_api import clerk
from ondra_api.config import get_settings
from ondra_api.db import tenant_session
from ondra_core.models import Tenant, User


async def main(dealer: str, owner_email: str | None) -> None:
    # Finding a dealership by name crosses tenants, so it uses the owner role (as migrations do); the rest of the
    # work happens inside that dealership's tenant-scoped session.
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(get_settings().migrations_database_url)
    async with engine.connect() as conn:
        tenant_id = (await conn.execute(text("SELECT id FROM tenants WHERE name = :n"), {"n": dealer})).scalar()
    await engine.dispose()
    if tenant_id is None:
        raise SystemExit(f"No dealership called {dealer!r}.")
    c = clerk.client()
    async with tenant_session(tenant_id) as db:
        t = (await db.execute(select(Tenant))).scalar_one()
        if not t.clerk_org_id:
            t.clerk_org_id = await asyncio.to_thread(c.create_organization, t.name)
            print(f"clerk: created organization {t.clerk_org_id[:10]}… for {t.name}")
        else:
            print(f"clerk: {t.name} is already organization {t.clerk_org_id[:10]}…")
        org = t.clerk_org_id
        if owner_email:
            owner = (await db.execute(select(User).where(User.role == "owner", User.active.is_(True))
                                      .order_by(User.created_at).limit(1))).scalar_one()
            if owner.clerk_user_id:
                print("clerk: the owner is already linked to a Clerk account; nothing to invite")
                return
            owner.email = owner_email.strip().lower()
            await db.flush()
            url = f"{get_settings().app_base_url.rstrip('/')}/invite"
            await asyncio.to_thread(c.invite, org, owner.email, "org:admin", url)
            print(f"clerk: invitation emailed to the owner ({owner.name}); it opens {url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dealer", required=True)
    ap.add_argument("--owner-email")
    a = ap.parse_args()
    asyncio.run(main(a.dealer, a.owner_email))
