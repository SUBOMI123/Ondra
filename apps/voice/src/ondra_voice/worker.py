"""The voice worker: `python -m ondra_voice.worker dev` (or `start` in production).

A call arrives from the dealer's number over a SIP trunk into a LiveKit room, and LiveKit dispatches this agent
(`agent_name="ondra-voice"`; the dispatch rule names it, see docs/VOICE.md). Then:

1. Before anyone speaks: `start_call` finds the dealer and caller and picks the route (services/calls.py).
2. VIP, or voice AI off: a cold transfer to the owner's or team's phone. The AI never says a word.
3. Otherwise: Ondra answers, on the shared tools, with each spoken sentence checked (agents.py, guard.py).
4. When the call ends: transcript, per-turn latency and outcome are stored, and the summary job is queued.

Models come from the environment so they can be swapped for the STT bake-off and the latency tests (see
.env.example: VOICE_STT_MODEL, VOICE_LLM_MODEL, VOICE_TTS_*). The skeleton follows LiveKit's examples:
`AgentServer`, `@server.rtc_session`, `cli.run_app`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from livekit import api, rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    STTContextOptions,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.agents.beta.tools import EndCallTool

# Model and voice plugins load when the worker starts (LiveKit needs plugins registered on the main thread). Loading
# them during a call added about 0.7 s to the first reply, seen in the first real call's logs.
from livekit.plugins import anthropic, elevenlabs
from ondra_api.config import get_settings
from ondra_api.services.calls import CallPlan, finish_call, start_call

from .agents import OndraAgent, greeting
from .desk import CallDesk, turn_metrics_from

log = logging.getLogger("ondra.voice")
AGENT_NAME = "ondra-voice"

server = AgentServer()


def sip_facts(p: rtc.RemoteParticipant) -> tuple[str, str, str]:
    """Caller, dialled number and a call id, from LiveKit's SIP participant attributes."""
    a = p.attributes
    return (a.get("sip.phoneNumber", ""), a.get("sip.trunkPhoneNumber", ""),
            a.get("sip.twilio.callSid") or a.get("sip.callID") or p.sid)


async def ring_someone(plan: CallPlan, transfer: Callable[[str], Awaitable[None]]) -> None:
    """VIP or voice AI off: hand the call to a person without the AI speaking. If there's nobody to ring or the
    transfer fails, it's a missed call (a VIP's alerts the owner; others get a call-back task)."""
    handled_by = "owner" if plan.route == "ring_owner" else "staff"
    if not plan.ring_number:
        await finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="nobody to ring")
        return
    try:
        await transfer(f"tel:{plan.ring_number}")
    except Exception:
        log.exception("transfer failed")
        await finish_call(plan.tenant_id, plan.call_id, handled_by="missed", outcome="transfer failed")
        return
    # TODO(verify): whether the person picked up is only known from the carrier's call status after a cold
    # transfer (Twilio status callback). Until that's wired in Step 5e, a transferred call is recorded as handed
    # over, not as answered.
    await finish_call(plan.tenant_id, plan.call_id, handled_by=handled_by, outcome="transferred",
                      transferred_to_user_id=plan.ring_user_id)


def build_session(desk: CallDesk) -> AgentSession[CallDesk]:
    s = get_settings()
    stt_model = os.getenv("VOICE_STT_MODEL", "deepgram/nova-3")
    tts_provider = os.getenv("VOICE_TTS_PROVIDER", "inference")
    if tts_provider == "elevenlabs":
        voice = {"voice_id": v} if (v := os.getenv("VOICE_TTS_VOICE")) else {}  # blank: ElevenLabs' default voice
        model = os.getenv("VOICE_TTS_MODEL") or "eleven_flash_v2_5"
        tts = elevenlabs.TTS(model=model if model.startswith("eleven_") else "eleven_flash_v2_5", **voice)
    else:
        tts = inference.TTS(model=os.getenv("VOICE_TTS_MODEL", "cartesia/sonic-3"), voice=os.getenv("VOICE_TTS_VOICE") or None)
    return AgentSession[CallDesk](
        userdata=desk,
        stt=inference.STT(model=stt_model, language="en"),
        # Phone audio mangles names ("Honda CR-V" came through as "hunger series" on the first real call): tell the
        # recogniser the dealership's name and the makes and models in stock.
        stt_context_options=STTContextOptions(keyterms=desk.vocabulary or [desk.dealer.name]),
        llm=anthropic.LLM(model=os.getenv("VOICE_LLM_MODEL") or s.model_fast, api_key=s.anthropic_api_key,
                          base_url=s.anthropic_api_base, caching="ephemeral", max_tokens=600),
        tts=tts,
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            interruption={"mode": "adaptive"},
            preemptive_generation={"enabled": True},
        ),
        tools=[end_call_tool()],
    )


def end_call_tool() -> EndCallTool:
    """Hang up after the reply that calls it. No end instructions: with them LiveKit has the model reply again after
    the tool, and callers heard "Thanks for calling" twice on the first real call. The voice rules already make the
    model say goodbye in the same reply that ends the call."""
    return EndCallTool(end_instructions=None)


def record_conversation(session: AgentSession, desk: CallDesk) -> None:
    @session.on("conversation_item_added")
    def _item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if getattr(item, "type", None) != "message" or item.role not in ("user", "assistant"):
            return
        desk.heard("caller" if item.role == "user" else "agent", item.text_content or "")
        if item.role == "assistant" and item.metrics:
            desk.turn_metrics.append(turn_metrics_from(dict(item.metrics)))


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    caller = await ctx.wait_for_participant(kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP)
    from_number, to_number, call_sid = sip_facts(caller)
    ctx.log_context_fields = {"room": ctx.room.name}

    plan = await start_call(from_number=from_number, to_number=to_number, provider_call_sid=call_sid)
    if plan is None:
        ctx.delete_room()
        return

    if plan.route != "ai":
        async def transfer(to: str) -> None:
            await ctx.api.sip.transfer_sip_participant(api.TransferSIPParticipantRequest(
                room_name=ctx.room.name, participant_identity=caller.identity, transfer_to=to, play_dialtone=True))

        await ring_someone(plan, transfer)
        ctx.delete_room()
        return

    desk = await CallDesk.open(plan)
    session = build_session(desk)
    record_conversation(session, desk)
    done = asyncio.Event()

    async def finish() -> None:
        await desk.settle()  # a follow-up task the spoken check promised is created before the call is stored
        await finish_call(
            plan.tenant_id, plan.call_id, handled_by="staff" if desk.transferred_to else "ai",
            outcome="transferred" if desk.transferred_to else "handled", transcript=desk.transcript,
            metrics=desk.metrics(), transferred_to_user_id=desk.transferred_to.user_id if desk.transferred_to else None,
        )
        done.set()

    @session.on("close")
    def _close(_ev) -> None:
        asyncio.create_task(finish())
        if not desk.transferred_to:
            ctx.delete_room()  # after a warm transfer the caller and the person stay in the room

    async def _wait_for_finish() -> None:
        await asyncio.wait_for(done.wait(), timeout=10)

    ctx.add_shutdown_callback(_wait_for_finish)
    await session.start(agent=OndraAgent(desk), room=ctx.room,
                        room_options=room_io.RoomOptions(delete_room_on_close=False))
    session.say(greeting(desk), allow_interruptions=False)


def main() -> None:
    cli.run_app(server)


if __name__ == "__main__":
    main()
