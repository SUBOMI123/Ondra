"""Tasks: mine and everyone's, create with a deadline, complete, reassign; VIP tasks stay private; a new due time
can escalate again. The client timeline merges messages and tasks, newest first."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ondra_api import worker
from ondra_api.db import tenant_session
from ondra_core.models import Contact, Task, User

from .conftest import login

OWNER, SALES, MANAGER = "owner@prestigemotors.example", "daniel@prestigemotors.example", "manager@prestigemotors.example"


async def test_create_complete_and_reassign(client, database):
    sales = await login(client, SALES)
    async with tenant_session(database["a"]) as db:
        contact_id = (await db.execute(select(Contact.id).where(Contact.is_vip.is_(False)).limit(1))).scalar_one()
        manager_id = (await db.execute(select(User.id).where(User.role == "manager"))).scalar_one()
    r = await client.post("/tasks", headers=sales, json={"title": "Send trade-in photos to Grace", "contact_id": str(contact_id),
                                                         "urgency": "high"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["assignee"]["name"] == "Daniel Okafor" and t["due_at"] and t["overdue"] is False
    mine = (await client.get("/tasks?scope=mine", headers=sales)).json()["items"]
    assert any(x["id"] == t["id"] for x in mine)

    r = await client.patch(f"/tasks/{t['id']}", headers=sales, json={"assignee_user_id": str(manager_id)})
    assert r.json()["assignee"]["name"] == "Grace Thompson"
    assert not any(x["id"] == t["id"] for x in (await client.get("/tasks?scope=mine", headers=sales)).json()["items"])
    assert (await client.patch(f"/tasks/{t['id']}", headers=sales, json={"status": "done"})).json()["status"] == "done"
    done = (await client.get("/tasks?scope=all&status=done", headers=sales)).json()["items"]
    assert any(x["id"] == t["id"] for x in done)


async def test_vip_tasks_are_private_to_people_who_can_see_vips(client, database):
    owner, sales = await login(client, OWNER), await login(client, SALES)
    async with tenant_session(database["a"]) as db:
        vip_id = (await db.execute(select(Contact.id).where(Contact.display_name == "Robert Hale"))).scalar_one()
    t = (await client.post("/tasks", headers=owner, json={"title": "Call Robert about the Range Rover", "contact_id": str(vip_id)})).json()
    assert not any(x["id"] == t["id"] for x in (await client.get("/tasks?scope=all", headers=sales)).json()["items"])
    assert (await client.patch(f"/tasks/{t['id']}", headers=sales, json={"status": "done"})).status_code == 404
    await client.patch(f"/tasks/{t['id']}", headers=owner, json={"status": "done"})


async def test_a_new_due_time_can_escalate_again(client, database):
    manager = await login(client, MANAGER)
    t = (await client.post("/tasks", headers=manager, json={"title": "Follow up on Tahoe", "urgency": "low",
                                                           "due_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()})).json()
    await worker.sweep()
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Task, t["id"])).escalated_at is not None
    later = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    await client.patch(f"/tasks/{t['id']}", headers=manager, json={"due_at": later})
    await worker.sweep()
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Task, t["id"])).escalated_at is not None  # escalated again after the new deadline passed
    await client.patch(f"/tasks/{t['id']}", headers=manager, json={"status": "done"})


async def test_timeline_merges_messages_and_tasks_newest_first(client, database):
    owner = await login(client, OWNER)
    from ondra_core.models import Conversation, Message

    async with tenant_session(database["a"]) as db:
        cid = (await db.execute(select(Contact.id).where(Contact.is_vip.is_(False)).order_by(Contact.display_name.desc())
                                .limit(1))).scalar_one()
        conv = Conversation(contact_id=cid, channel="sms", ai_mode="auto")
        db.add(conv)
        await db.flush()
        db.add(Message(conversation_id=conv.id, direction="inbound", author_type="customer", body="hi", status="received"))
    await client.post("/tasks", headers=owner, json={"title": "Timeline check", "contact_id": str(cid)})
    items = (await client.get(f"/contacts/{cid}/timeline", headers=owner)).json()["items"]
    kinds = {i["kind"] for i in items}
    assert {"message", "task"} <= kinds
    assert [i["at"] for i in items] == sorted((i["at"] for i in items), reverse=True)
    assert items[0]["kind"] == "task" and items[0]["title"] == "Timeline check"


async def test_the_team_board_lists_everyone_who_takes_work_and_moves_tasks_between_them(client, database):
    owner = await login(client, "owner@prestigemotors.example")
    board = (await client.get("/tasks?scope=all", headers=owner)).json()
    people = {p["name"]: p for p in board["people"]}
    assert {"Daniel Okafor", "Samuel Adeyemi", "Grace Thompson"} <= set(people)
    assert all(p["role"] != "admin" for p in board["people"])  # admins set things up; they don't take tasks
    assert "people" not in (await client.get("/tasks?scope=mine", headers=owner)).json()
    t = (await client.post("/tasks", headers=owner, json={"title": "Check the trade-in on the Rogue"})).json()
    moved = (await client.patch(f"/tasks/{t['id']}", headers=owner, json={"assignee_user_id": people["Grace Thompson"]["id"]})).json()
    assert moved["assignee"]["name"] == "Grace Thompson"
    await client.patch(f"/tasks/{t['id']}", headers=owner, json={"status": "cancelled"})
