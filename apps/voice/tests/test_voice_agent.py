"""The voice agent on LiveKit's AgentSession, in text mode, with a scripted model and the real database.

What's proven here: the call is routed before anyone speaks (a VIP never reaches the AI), the agent runs the shared
tools against the dealer's data, intent changes hand the call to the right agent, every spoken sentence is checked
before it's said, and the call record keeps the transcript and per-turn latency. What isn't: audio, speech
recognition, the voice and real latency, which need a real call (Step 5e).
"""

from __future__ import annotations

import uuid

import pytest
from conftest import ScriptedLLM, Step, last_tool_output
from livekit.agents import AgentSession
from ondra_api.db import tenant_session
from ondra_api.services import calls
from ondra_core.agent.detectors import ReplyContext
from ondra_core.models import Call, Task, User
from ondra_voice import agents, guard, worker
from ondra_voice.desk import CallDesk, turn_metrics_from
from sqlalchemy import select, text

DEALER = "+12145550100"


async def _phone_of(tenant_id, name):
    async with tenant_session(tenant_id) as db:
        return (await db.execute(text(
            "SELECT i.value FROM contacts c JOIN contact_identities i ON i.contact_id = c.id AND i.kind = 'phone' "
            "WHERE c.display_name = :n"), {"n": name})).scalar_one()


async def _plan(database, name):
    return await calls.start_call(from_number=await _phone_of(database["a"], name), to_number=DEALER,
                                  provider_call_sid=f"CA{uuid.uuid4().hex}")


# --- the spoken-sentence check ---------------------------------------------------------------------------------

async def _say(chunks, ctx, never_say=()):
    async def stream():
        for c in chunks:
            yield c

    hits = []
    out = "".join([s async for s in guard.guarded(stream(), ctx, list(never_say), lambda s, p: hits.append(p))])
    return out.strip(), hits


async def test_sentences_are_checked_before_they_are_spoken():
    ctx = ReplyContext(price_disclosure="listed", listed_prices={31900})
    out, hits = await _say(["We have a CR-V ", "listed at $31,9", "00. Want to see it?"], ctx)
    assert out == "We have a CR-V listed at $31,900. Want to see it?" and not hits

    out, hits = await _say(["Sure. ", "I can do $29,000 out the door", " for you. And I'll throw in mats."], ctx)
    assert out.startswith("Sure. " + guard.SAFE_LINE) and "29,000" not in out and hits
    # A second failing sentence in the same reply doesn't repeat the safe line.
    out, _ = await _say(["I can do $29,000. ", "We'll have it delivered by Friday."], ctx)
    assert out == guard.SAFE_LINE

    out, hits = await _say(["Ask about our Platinum Plan."], ctx, never_say=["Platinum Plan"])
    assert out == guard.SAFE_LINE and hits == [["never_say"]]


def test_the_voice_agent_runs_the_same_tools_as_text(database):
    from ondra_core.agent.tools import TOOL_NAMES

    names = {t.info.name for t in agents.shared_tools()}
    assert names == set(TOOL_NAMES)


# --- routing before anyone speaks ------------------------------------------------------------------------------

async def test_a_vip_is_put_through_to_the_owner_and_the_ai_never_starts(database):
    plan = await _plan(database, "Robert Hale")
    assert plan.route == "ring_owner"
    dialled = []

    async def transfer(to):
        dialled.append(to)

    await worker.ring_someone(plan, transfer)
    async with tenant_session(database["a"]) as db:
        owner = (await db.execute(select(User).where(User.role == "owner"))).scalar_one()
        call = await db.get(Call, plan.call_id)
    assert dialled == [f"tel:{owner.phone}"] and call.handled_by == "owner" and call.transcript == []


async def test_a_vip_transfer_that_fails_becomes_an_urgent_owner_task(database):
    plan = await _plan(database, "Robert Hale")

    async def transfer(to):
        raise RuntimeError("busy")

    await worker.ring_someone(plan, transfer)
    async with tenant_session(database["a"]) as db:
        call = await db.get(Call, plan.call_id)
        task = (await db.execute(select(Task).where(Task.contact_id == plan.contact_id, Task.status == "open")
                                 .order_by(Task.created_at.desc()))).scalars().first()
        assert call.handled_by == "missed" and task.urgency == "high" and "(VIP)" in task.title
        task.status = "done"


# --- the agent on a call ---------------------------------------------------------------------------------------

async def test_greeting_carries_the_dealers_disclosures(database):
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    assert agents.greeting(desk) == "Thanks for calling Prestige Motors. How can I help you today?"
    desk.dealer.disclose_upfront, desk.plan.disclose_recording = True, True
    assert "AI assistant" in agents.greeting(desk) and "may be recorded" in agents.greeting(desk)
    # The caller was looked up before the greeting, so the agent starts knowing who they are.
    assert desk.contact_context and "Ben Carter" in agents.instructions(desk)


async def test_a_caller_asking_for_a_car_hears_only_the_listed_price(database):
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))

    def quote(chat_ctx):
        car = last_tool_output(chat_ctx)["results"][0]
        return f"Yes, we have a {car['year']} {car['make']} {car['model']} listed at ${car['price']:,}. Want to come drive it?"

    model = ScriptedLLM([
        Step(text="Let me check what we have. ", calls=[("search_inventory", {"query": "CR-V"})]),
        Step(text=quote),
    ])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="Hi, do you have a Honda CR-V?")
        result.expect.skip_next_event_if(type="message")  # "Let me check what we have."
        result.expect.next_event().is_function_call(name="search_inventory")
        result.expect.next_event().is_function_call_output()
        reply = result.expect.next_event().is_message(role="assistant").event().item.text_content

    assert "CR-V" in reply and "listed at $" in reply and desk.blocked == []
    assert desk.tools_called == ["search_inventory"] and desk.checks.listed_prices


async def test_a_made_up_discount_is_never_spoken_and_is_counted(database):
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    model = ScriptedLLM([Step(text="Sure thing. I can knock five hundred off, so $500 off for you today.")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="Can you give me a discount?")
        said = result.expect.next_event().is_message(role="assistant").event().item.text_content
    assert "knock" not in said and guard.SAFE_LINE in said and "promises_discount" in desk.blocked
    # The safe line says a person will follow up, so a task for one exists before the call is stored.
    await desk.settle()
    async with tenant_session(database["a"]) as db:
        task = (await db.execute(select(Task).where(Task.contact_id == desk.plan.contact_id, Task.source == "ai_handoff",
                                                    Task.brief.like("%stopped itself%")))).scalars().one()
        assert task.status == "open" and "price" in task.title.lower()
        task.status = "done"


async def test_service_books_through_the_shared_calendar(database):
    desk = await CallDesk.open(await _plan(database, "Grace Kim"))

    slot = {}

    def first_slot(chat_ctx):
        slots = last_tool_output(chat_ctx)["slots"]
        slot["id"] = slots[0]["slot_id"]
        return f"I have {slots[0]['when']}. Does that work?"

    model = ScriptedLLM([
        Step(calls=[("check_availability", {"kind": "oil change"})]),
        Step(text=first_slot),
    ])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        await session.run(user_input="I need an oil change for my Camry.")
        model.steps = [Step(calls=[("book_appointment", {"slot_id": slot["id"], "details": {"transport": "wait"}})]),
                       Step(text=lambda c: "You're booked." if last_tool_output(c).get("booked") else "Hmm.")]
        result = await session.run(user_input="Yes, that works, I'll wait for it.")
        result.expect.next_event().is_function_call(name="book_appointment")
        result.expect.next_event().is_function_call_output()
        assert result.expect.next_event().is_message(role="assistant").event().item.text_content == "You're booked."
    assert desk.tools_called == ["check_availability", "book_appointment"]


async def test_the_call_record_keeps_the_transcript_and_latency(database):
    plan = await _plan(database, "Ben Carter")
    desk = await CallDesk.open(plan)
    desk.heard("agent", "Thanks for calling Prestige Motors. How can I help you today?")
    desk.heard("caller", "What time do you close Saturday?")
    desk.turn_metrics += [turn_metrics_from({"e2e_latency": 0.82, "llm_node_ttft": 0.41, "tts_node_ttfb": 0.12}),
                          turn_metrics_from({"e2e_latency": 1.31, "llm_node_ttft": 0.9})]
    m = desk.metrics()
    assert m["summary"] == {"turns": 2, "avg_ms": 1065, "p90_ms": 1310, "over_1s": 1, "tools": [], "blocked": []}
    assert m["turns"][0]["llm_ttft_ms"] == 410
    await calls.finish_call(plan.tenant_id, plan.call_id, handled_by="ai", outcome="handled",
                            transcript=desk.transcript, metrics=m)
    async with tenant_session(database["a"]) as db:
        call = await db.get(Call, plan.call_id)
        assert call.transcript[1] == {"who": "caller", "text": "What time do you close Saturday?"}
        assert call.metrics["summary"]["avg_ms"] == 1065


@pytest.fixture(autouse=True)
def _no_real_keys(monkeypatch):
    monkeypatch.delenv("LIVEKIT_SIP_OUTBOUND_TRUNK", raising=False)
