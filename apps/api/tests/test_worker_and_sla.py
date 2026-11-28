"""The job queue, the worker, response-time deadlines and escalation."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update

from ondra_api import worker
from ondra_api.db import tenant_session
from ondra_api.services.jobs import enqueue
from ondra_api.services.sla import add_business_time, business_seconds
from ondra_api.services.tasks import new_task
from ondra_core.models import Event, Job, Task, Tenant, User

SIG = {"x-mock-signature": "mock-secret"}


# --- business-hours clock -----------------------------------------------------------------------------------------

def _tenant():
    hours = {d: ["09:00", "19:00"] for d in ("mon", "tue", "wed", "thu", "fri")} | {"sat": ["09:00", "18:00"]}
    return Tenant(name="T", timezones=["America/Chicago"], business_hours=hours)


@pytest.mark.parametrize("start,minutes,expected", [
    ("2026-11-24T22:00:00-06:00", 15, "2026-11-25T09:15:00-06:00"),  # Tue 10 pm: due 15 min after Wed opens
    ("2026-11-25T10:00:00-06:00", 15, "2026-11-25T10:15:00-06:00"),  # open: plain 15 minutes
    ("2026-11-28T17:55:00-06:00", 15, "2026-11-30T09:10:00-06:00"),  # Sat 5:55 pm: 5 min Sat, closed Sun, Mon 9:10
    ("2026-11-29T12:00:00-06:00", 120, "2026-11-30T11:00:00-06:00"),  # Sunday: starts Monday
])
def test_deadlines_count_only_open_hours(start, minutes, expected):
    due = add_business_time(_tenant(), datetime.fromisoformat(start), timedelta(minutes=minutes))
    assert due == datetime.fromisoformat(expected)


def test_no_hours_means_plain_clock_time():
    t = Tenant(name="T", business_hours={})
    start = datetime(2026, 11, 24, 22, tzinfo=UTC)
    assert add_business_time(t, start, timedelta(minutes=15)) == start + timedelta(minutes=15)


@pytest.mark.parametrize("start,end,minutes", [
    ("2026-11-24T23:00:00-06:00", "2026-11-25T09:10:00-06:00", 10),  # missed at 11 pm, rung back 9:10 am: 10 open minutes
    ("2026-11-25T10:00:00-06:00", "2026-11-25T10:35:00-06:00", 35),  # open the whole time
    ("2026-11-28T17:50:00-06:00", "2026-11-30T09:05:00-06:00", 15),  # Sat 10 min before close, closed Sun, Mon 9:05
    ("2026-11-25T10:00:00-06:00", "2026-11-25T09:00:00-06:00", 0),  # end before start
])
def test_waiting_time_counts_only_open_hours(start, end, minutes):
    assert business_seconds(_tenant(), datetime.fromisoformat(start), datetime.fromisoformat(end)) == minutes * 60
    assert business_seconds(Tenant(name="T", business_hours={}), datetime(2026, 11, 24, 23, tzinfo=UTC),
                            datetime(2026, 11, 25, 1, tzinfo=UTC)) == 7200


# --- the queue ---------------------------------------------------------------------------------------------------

async def test_failed_jobs_retry_with_backoff_then_stop(database, monkeypatch):
    calls = []

    async def boom(tenant_id, payload):
        calls.append(payload)
        raise RuntimeError("provider down")

    monkeypatch.setitem(worker.HANDLERS, "test_boom", boom)
    async with tenant_session(database["a"]) as db:
        job = enqueue(db, "test_boom", {"n": 1})
        job.max_attempts = 2
        await db.flush()
        job_id = job.id

    assert await worker.run_once() >= 1
    async with tenant_session(database["a"]) as db:
        j = await db.get(Job, job_id)
        assert j.status == "queued" and j.attempts == 1 and "provider down" in j.last_error
        assert j.run_at > datetime.now(UTC)  # backed off
        j.run_at = datetime.now(UTC) - timedelta(seconds=1)  # skip the wait
    await worker.run_once()
    async with tenant_session(database["a"]) as db:
        j = await db.get(Job, job_id)
        assert j.status == "failed" and j.attempts == 2
    assert len(calls) == 2


async def test_a_job_left_running_by_a_crashed_worker_is_picked_up_again(database, monkeypatch):
    ran = []

    async def ok(tenant_id, payload):
        ran.append(payload)

    monkeypatch.setitem(worker.HANDLERS, "test_ok", ok)
    async with tenant_session(database["a"]) as db:
        job = enqueue(db, "test_ok", {"n": 2})
        await db.flush()
        job.status, job.locked_at = "running", datetime.now(UTC) - timedelta(minutes=10)
        job_id = job.id
    await worker.run_once()
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Job, job_id)).status == "done"
    assert ran == [{"n": 2}]


async def test_message_and_its_ai_turn_are_saved_together(client, database, monkeypatch):
    from ondra_api.services import inbound
    from ondra_core.agent.llm import ScriptedLLM

    async with tenant_session(database["a"]) as db:
        await db.execute(text("UPDATE policies SET draft_mode = true"))
    msg = {"id": "queue-1", "from": "+12145551001", "to": "+12145550100", "text": "any highlanders?"}
    await client.post("/webhooks/mock/sms", content=json.dumps(msg), headers=SIG)
    async with tenant_session(database["a"]) as db:
        job = (await db.execute(select(Job).where(Job.kind == "agent_turn", Job.status == "queued"))).scalars().all()
        assert len(job) == 1 and job[0].payload["draft"] is True
    monkeypatch.setattr(inbound, "llm_factory", lambda: ScriptedLLM(["We don't have one right now."]))
    await worker.run_once()
    async with tenant_session(database["a"]) as db:
        assert (await db.get(Job, job[0].id)).status == "done"


# --- escalation --------------------------------------------------------------------------------------------------

async def test_overdue_tasks_escalate_once_to_a_manager_then_owner(database):
    async with tenant_session(database["a"]) as db:
        users = {u.role: u.id for u in (await db.execute(select(User).where(User.active.is_(True)))).scalars()}
        past = datetime.now(UTC) - timedelta(minutes=5)
        sales_task = await new_task(db, title="Call Kevin back", assignee_user_id=users["sales"], urgency="normal",
                                    due_at=past)
        mgr_task = await new_task(db, title="Angry customer", assignee_user_id=users["manager"], urgency="high",
                                  due_at=past)
        future = await new_task(db, title="Not due yet", assignee_user_id=users["sales"], urgency="low")
        ids = (sales_task.id, mgr_task.id, future.id)

    assert await worker.sweep() >= 2
    assert await worker.sweep() == 0  # each task escalates once
    async with tenant_session(database["a"]) as db:
        s, m, f = [await db.get(Task, i) for i in ids]
        assert s.escalated_at and s.urgency == "high" and s.assignee_user_id == users["manager"]
        assert m.escalated_at and m.assignee_user_id == users["owner"]
        assert f.escalated_at is None and f.due_at > datetime.now(UTC)
        events = (await db.execute(select(Event).where(Event.type == "task.escalated"))).scalars().all()
        assert {e.payload["task_id"] for e in events} >= {str(s.id), str(m.id)}
        await db.execute(update(Task).where(Task.id.in_(ids)).values(status="done"))


def test_handoff_task_titles_are_actions_not_codes():
    from ondra_api.services.agent_tools import handoff_title

    assert handoff_title("pricing", "Sarah King") == "Talk price with Sarah"
    assert handoff_title("vehicle_request", "Mei Chen") == "Find a car for Mei"
    assert handoff_title("trade_in", "+12145550199") == "Value the customer's trade-in"
    assert handoff_title("something_new", "Kevin Lee") == "Follow up with Kevin"
