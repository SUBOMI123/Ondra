"""The dealership's logo in the sidebar: admins set it, everyone reads it, only real images under the size limit."""

import base64

from ondra_api.db import tenant_session
from ondra_core.models import Tenant
from sqlalchemy import select, update

from .conftest import login

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200).decode()


async def test_admins_set_the_logo_everyone_sees_it(client, database):
    admin, sales = await login(client, "owner@prestigemotors.example"), await login(client, "daniel@prestigemotors.example")
    async with tenant_session(database["a"]) as db:
        before = dict((await db.execute(select(Tenant))).scalar_one().settings or {})
    try:
        assert (await client.put("/settings/branding", json={"logo": PNG}, headers=sales)).status_code == 403
        got = (await client.put("/settings/branding", json={"logo": PNG, "logo_dark": PNG}, headers=admin)).json()
        assert got["logo"] == PNG and got["logo_dark"] == PNG and got["name"] == "Prestige Motors"
        assert (await client.get("/settings/branding", headers=sales)).json()["logo"] == PNG
        # Not an image, a script dressed as one, or too big: refused with the reason.
        assert (await client.put("/settings/branding", json={"logo": "data:text/html;base64,PGh0bWw+"}, headers=admin)).status_code == 422
        assert (await client.put("/settings/branding", json={"logo": "https://example.com/logo.png"}, headers=admin)).status_code == 422
        big = "data:image/png;base64," + base64.b64encode(b"\x00" * 400_000).decode()
        r = await client.put("/settings/branding", json={"logo": big}, headers=admin)
        assert r.status_code == 422 and "KB" in r.json()["detail"]
        # Removing the logo removes the dark-mode version with it.
        assert (await client.put("/settings/branding", json={"logo": None, "logo_dark": PNG}, headers=admin)).json() == {
            "name": "Prestige Motors", "logo": None, "logo_dark": None}
    finally:
        async with tenant_session(database["a"]) as db:
            await db.execute(update(Tenant).values(settings=before))
