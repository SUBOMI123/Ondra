"""Photos for the demo dealership's cars only (docs/PLAN.md item 8).

The seeded demo cars (source_feed "seed") had no photos, so the demo looked empty. These are openly licensed photos
from Wikimedia Commons, one per model, credited in apps/web/public/demo-cars/CREDITS.md and on screen ("Demo photo").
They are never put on a real dealer's car: a dealer's photos come only from their own inventory feed, and a car without
a feed photo shows none. Ondra never sends a demo photo to a customer either (services/agent_tools.py).
"""

from __future__ import annotations

from ondra_core.models import Vehicle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PREFIX = "/demo-cars/"

# model as seeded -> file in apps/web/public/demo-cars/. A model is listed only once its file and credit are in the
# repo; until then its demo cars stay without a photo rather than pointing at a missing image.
FILES: dict[str, str] = {}


def is_demo(url: str) -> bool:
    return url.startswith(PREFIX)


def photo_for(make: str, model: str) -> str | None:
    f = FILES.get(f"{make} {model}")
    return f"{PREFIX}{f}" if f else None


async def ensure_demo_photos(db: AsyncSession) -> int:
    """Give every seeded demo car without a photo its model's demo photo. Idempotent; touches nothing else."""
    n = 0
    for v in (await db.execute(select(Vehicle).where(Vehicle.source_feed == "seed"))).scalars():
        url = photo_for(v.make, v.model)
        if url and not v.photos:
            v.photos = [url]
            n += 1
    return n
