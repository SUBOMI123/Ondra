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
    # Speech recognition is told the dealership's name and the stock it may hear about.
    assert desk.vocabulary[0] == "Prestige Motors" and {"loaner", "Honda", "CR-V"} <= set(desk.vocabulary)


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
        result.expect.skip_next_event_if(type="message")  # "One moment." while it books
        result.expect.next_event().is_function_call(name="book_appointment")
        result.expect.next_event().is_function_call_output()
        assert result.expect.next_event().is_message(role="assistant").event().item.text_content == "You're booked."
    assert desk.tools_called == ["check_availability", "book_appointment"]
    # The model only ever saw short slot names; the calendar got the real id.
    assert slot["id"] == "slot1" and len(desk.slot_aliases["slot1"]) > 100


async def test_the_call_record_keeps_the_transcript_and_latency(database):
    plan = await _plan(database, "Ben Carter")
    desk = await CallDesk.open(plan)
    desk.heard("agent", "Thanks for calling Prestige Motors. How can I help you today?")
    desk.heard("caller", "What time do you close Saturday?")
    desk.turn_metrics += [turn_metrics_from({"e2e_latency": 0.82, "llm_node_ttft": 0.41, "tts_node_ttfb": 0.12}),
                          turn_metrics_from({"e2e_latency": 1.31, "llm_node_ttft": 0.9})]
    m = desk.metrics()
    assert m["summary"] == {"turns": 2, "avg_ms": 1065, "p90_ms": 1310, "over_1s": 1, "tools": [], "blocked": [],
                            "tool_problems": []}
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


async def test_a_booking_that_fails_is_kept_on_the_call_record(database, monkeypatch):
    """Found on the first real call: a booking failed, Ondra handed off, and nothing said why. Now the call record
    says which tool failed and how, whether it refused (a bad time) or crashed."""
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    model = ScriptedLLM([Step(calls=[("book_appointment", {"slot_id": "sat-8am"})]), Step(text="Let me get someone to help.")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        await session.run(user_input="Book me Saturday at eight.")
    assert desk.tool_problems == [{"tool": "book_appointment", "refused": "That time isn't one I offered. Check availability again."}]

    real_run = desk.run

    async def crash(name, args):
        if name == "check_availability":
            raise RuntimeError("calendar unavailable")
        return await real_run(name, args)

    monkeypatch.setattr(desk, "run", crash)
    model = ScriptedLLM([Step(calls=[("check_availability", {"kind": "oil change"})]), Step(text="Someone will call you back.")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="Any oil change times?")
        out = next(e for e in result.events if e.type == "function_call_output")
        assert out.item.is_error and "handoff" in out.item.output  # the model is told what to do, not the stack trace
    assert desk.tool_problems[-1] == {"tool": "check_availability", "crashed": "RuntimeError: calendar unavailable"}
    assert desk.metrics()["summary"]["tool_problems"] == desk.tool_problems


async def test_goodbye_is_said_once(database):
    """From the first real call: "Thanks for calling" was said twice, once in the reply that ended the call and
    again because the end-call tool asked the model for another reply."""
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    model = ScriptedLLM([Step(text="Thanks for calling Prestige Motors. Have a good day.", calls=[("end_call", {})]),
                         Step(text="Thanks for calling! Goodbye.")])
    async with AgentSession(llm=model, userdata=desk, tools=[worker.end_call_tool()]) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="That's all, thanks.")
        said = [e.item.text_content for e in result.events if e.type == "message" and e.item.role == "assistant"]
    assert said == ["Thanks for calling Prestige Motors. Have a good day."]
    assert len(model.requests) == 1  # no second reply after hanging up


async def test_the_callers_own_car_is_not_mistaken_for_an_invented_one(database):
    """From the first real call: the caller said "2021 BMW 330i", Ondra repeated it, and the made-up-car check
    replaced the sentence and handed off, because it hadn't seen the caller's words yet."""
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    assert desk.checks.customer_text == ""
    model = ScriptedLLM([Step(text="Got it, your 2021 BMW 330i. I have Friday at 7:00 in the morning. Does that work?")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="Twenty twenty one BMW three thirty I. Can we do Friday morning?")
        said = result.expect.next_event().is_message(role="assistant").event().item.text_content
    assert "BMW 330i" in said and guard.SAFE_LINE not in said and desk.blocked == []
    # Naming a make nobody mentioned and the tools never returned is still stopped.
    model = ScriptedLLM([Step(text="We also have a Porsche Cayenne you'd love.")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="Anything else?")
        assert guard.SAFE_LINE in result.expect.next_event().is_message(role="assistant").event().item.text_content


async def test_a_silent_lookup_gets_a_filler_and_bookkeeping_does_not(database):
    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    model = ScriptedLLM([Step(calls=[("check_availability", {"kind": "oil change"})]), Step(text="I have Friday at 7.")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="Any oil change times?")
        said = [e.item.text_content for e in result.events if e.type == "message" and e.item.role == "assistant"]
    assert said[0].strip() == agents.FILLER.strip() and said[-1] == "I have Friday at 7."
    model = ScriptedLLM([Step(text="Got it.", calls=[("update_lead_fields", {"fields": {"vehicle_interest": "CR-V"}})]),
                         Step(text="Anything else?")])
    async with AgentSession(llm=model, userdata=desk) as session:
        await session.start(agents.OndraAgent(desk))
        result = await session.run(user_input="I want a CR-V.")
        said = [e.item.text_content for e in result.events if e.type == "message" and e.item.role == "assistant"]
    assert agents.FILLER.strip() not in " ".join(said)


async def test_voice_requests_skip_thinking_at_low_effort(monkeypatch):
    """Measured 2026-11-26 on the booking call: thinking off at low effort, median 0.61 s to first word against
    1.32 s with the model's default (thinking on, medium), every booking still right."""
    monkeypatch.delenv("VOICE_THINKING", raising=False)
    monkeypatch.delenv("VOICE_EFFORT", raising=False)
    assert worker.voice_request_settings() == {"output_config": {"effort": "low"}, "thinking": {"type": "disabled"}}


async def test_a_call_names_the_best_two_and_texts_the_rest_only_after_a_yes(database):
    """Real calls: four cars and prices read aloud were hard to follow. Now the model is given the best two and a
    count, and can text them all, but only after the caller agrees (their yes is recorded as consent)."""
    from ondra_api import channels
    from ondra_api import worker as jobs
    from ondra_core.models import Consent

    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    out = await desk.run("search_inventory", {"query": "SUV"})
    assert out["total_found"] > 2 and len(out["best"]) == 2 and len(desk.last_cars) == out["total_found"]
    assert "text_details" in out["next"]
    # Every price found counts as real for the spoken checks, not only the two named.
    assert {int(c["price"]) for c in desk.last_cars if c.get("price")} <= desk.checks.listed_prices
    cheapest = out["best"][0]
    assert cheapest["price"] == min(c["price"] for c in desk.last_cars if c.get("price"))

    assert "error" in await desk.text_details(None, "Hmm, which one is newer?")  # no yes, no text
    channels.mock("sms").outbox.clear()
    sent = await desk.text_details(None, "Yes, text me those please.")
    assert sent["sent"] and sent["cars"] == len(desk.last_cars)
    await jobs.run_once()
    text_msg = channels.mock("sms").outbox[-1]
    assert text_msg.to_address == await _phone_of(database["a"], "Ben Carter")  # the number they're calling from
    assert "Prestige Motors" in text_msg.body and cheapest["model"] in text_msg.body
    async with tenant_session(database["a"]) as db:
        consent = (await db.execute(select(Consent).where(Consent.contact_id == desk.plan.contact_id,
                                                          Consent.source == "voice_call"))).scalars().first()
        assert consent.status == "opted_in" and consent.evidence["said"].startswith("Yes")


async def test_no_text_to_a_caller_who_opted_out(database):
    from ondra_api import channels

    desk = await CallDesk.open(await _plan(database, "Jordan Price"))
    await desk.run("search_inventory", {"query": "SUV"})
    channels.mock("sms").outbox.clear()
    out = await desk.text_details(None, "Yes please.")
    assert "opted out" in out["error"] and channels.mock("sms").outbox == []


async def test_a_lookup_question_gets_a_filler_the_moment_the_caller_stops(database):
    """Real calls: "a huge pause" before lookups. The filler is said as soon as the caller finishes (LiveKit's
    end-of-turn hook, which fires on spoken turns), never two turns in a row, and the model's own "let me check" is
    dropped so the caller doesn't hear it twice."""
    from livekit.agents import llm as lk

    desk = await CallDesk.open(await _plan(database, "Ben Carter"))
    model = ScriptedLLM([
        Step(text="Let me check what we have. ", calls=[("search_inventory", {"query": "CR-V"})]),
        Step(text="We have two CR-Vs."),
    ])
    async with AgentSession(llm=model, userdata=desk) as session:
        agent = agents.OndraAgent(desk)
        await session.start(agent)
        spoken = []
        session.say = lambda text, **kw: spoken.append(text)  # type: ignore[method-assign]

        async def caller_says(text):
            await agent.on_user_turn_completed(session.history, lk.ChatMessage(role="user", content=[text]))

        await caller_says("Do you have any CR-Vs in stock?")
        assert spoken == [agents.QUICK_FILLERS[0]]
        result = await session.run(user_input="Do you have any CR-Vs in stock?")
        said = [e.item.text_content for e in result.events if e.type == "message" and e.item.role == "assistant"]
        assert "Let me check what we have." not in " ".join(said) and said[-1] == "We have two CR-Vs."

        await caller_says("And what about Saturday times?")  # a lookup again, straight after: no second filler
        assert len(spoken) == 1
        await caller_says("Thanks, that's helpful.")  # no lookup: nothing
        await caller_says("Can I book a test drive Saturday?")
        assert spoken[1] == agents.QUICK_FILLERS[1]  # a different phrase next time
