from datetime import UTC, datetime, timedelta

import jwt

from .conftest import login


async def test_sign_in_and_me(client):
    h = await login(client, "owner@prestigemotors.example")
    r = await client.get("/me", headers=h)
    assert r.status_code == 200
    assert r.json()["tenant_name"] == "Prestige Motors" and r.json()["role"] == "owner"


async def test_wrong_password_and_unknown_email_look_the_same(client):
    a = await client.post("/auth/login", json={"email": "owner@prestigemotors.example", "password": "nope"})
    b = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


async def test_requests_without_a_valid_token_are_rejected(client):
    assert (await client.get("/contacts")).status_code == 401
    forged = jwt.encode({"sub": "x", "tid": "y", "typ": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)},
                        "wrong-secret-" + "y" * 32, algorithm="HS256")
    assert (await client.get("/contacts", headers={"Authorization": f"Bearer {forged}"})).status_code == 401


async def test_refresh_rotates_and_old_token_stops_working(client):
    await login(client, "daniel@prestigemotors.example")
    old = client.cookies.get("ondra_refresh")
    r = await client.post("/auth/refresh")
    assert r.status_code == 200 and client.cookies.get("ondra_refresh") != old
    client.cookies.set("ondra_refresh", old, path="/auth")
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_logout_revokes_the_session(client):
    await login(client, "maria@prestigemotors.example")
    token = client.cookies.get("ondra_refresh")
    assert (await client.post("/auth/logout")).status_code == 204
    client.cookies.set("ondra_refresh", token, path="/auth")
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_seeded_data_is_visible_to_its_dealership(client):
    h = await login(client, "owner@prestigemotors.example")
    assert (await client.get("/vehicles", headers=h)).json()["total"] == 50
    assert (await client.get("/contacts", headers=h)).json()["total"] == 30
    assert (await client.get("/users", headers=h)).json()["total"] == 5


async def test_another_dealership_sees_only_its_own_data(client):
    h = await login(client, "owner@lonestar.example")
    contacts = (await client.get("/contacts", headers=h)).json()
    assert [c["display_name"] for c in contacts["items"]] == ["Only In Tenant B"]
    assert (await client.get("/vehicles", headers=h)).json()["total"] == 1


async def test_vips_are_hidden_from_sales_but_visible_to_the_owner(client):
    owner = (await client.get("/contacts?limit=200", headers=await login(client, "owner@prestigemotors.example"))).json()
    sales = (await client.get("/contacts?limit=200", headers=await login(client, "daniel@prestigemotors.example"))).json()
    owner_vips = {c["display_name"] for c in owner["items"] if c["is_vip"]}
    assert owner_vips == {"Robert Hale", "Tunde Bakare"}
    assert not any(c["is_vip"] for c in sales["items"])
    assert sales["total"] == owner["total"] - 2


async def test_roles_are_enforced_server_side(client):
    sales = await login(client, "daniel@prestigemotors.example")
    admin = await login(client, "admin@prestigemotors.example")
    assert (await client.get("/users", headers=sales)).status_code == 403
    assert (await client.get("/users", headers=admin)).status_code == 200


async def test_vehicle_search_matches_every_word(client):
    h = await login(client, "daniel@prestigemotors.example")
    tahoes = (await client.get("/vehicles?q=tahoe&limit=200", headers=h)).json()
    assert tahoes["total"] > 0 and all(v["model"] == "Tahoe" for v in tahoes["items"])
    narrowed = (await client.get(f"/vehicles?q=tahoe {tahoes['items'][0]['year']}&limit=200", headers=h)).json()
    assert 0 < narrowed["total"] <= tahoes["total"]
    assert (await client.get("/vehicles?q=lamborghini", headers=h)).json()["total"] == 0
