"""Ondra on the phone: one agent on the shared tools.

Built the way LiveKit's examples build voice agents: a thin `Agent`, with the rules held elsewhere (`desk.CallDesk`,
the shared tool layer, and `guard`). Tools are the text agent's own `TOOL_SPECS`, registered as raw-schema LiveKit
tools, so both channels run identical code.

One agent, not the plan's receptionist routing to sales and service agents (§4.2 step 4): measured with the real
model, each switch cost a full extra model round (about 2.5 s of silence) and the agent announced it as if
transferring the caller. One agent with all ten tools handled a caller switching from buying to service without
any switch. See docs/DECISIONS.md (2026-11-26, voice).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterable

from livekit.agents import Agent, FlushSentinel, ModelSettings, RunContext, function_tool, llm
from livekit.agents.llm import ToolError
from ondra_core.agent.prompt import STABLE, build_system
from ondra_core.agent.tools import TOOL_SPECS

from .desk import CallDesk
from .guard import guarded

log = logging.getLogger("ondra.voice")

VOICE_RULES = """\
This is a live phone call, not a text conversation. These rules override anything above about writing, texting \
or message length.
- Talk like a person at the dealership: one or two short sentences at a time, one question at a time. No lists, \
markdown, symbols or links.
- Write prices with digits and a dollar sign ($31,900) and times as people say them ("ten on Saturday morning"). \
The voice reads prices aloud naturally, and the checks on what you say need the digits. Never read out ids, slot \
ids or stock numbers unless they ask for the stock number.
- Before a tool that takes a moment, say a few words first in the same reply ("Let me check what we have."), then \
call it. Never say you'll check without calling the tool in that same reply.
- Only say something is booked, moved or cancelled after the tool succeeds. On the phone, read the day, time and \
who they'll see back and get a yes before you book: a wrong booking by voice is worse than one extra question.
- When several cars or times fit, mention the best one or two, then ask. Never read out a whole list.
- The caller can't see anything. Never say "as you can see" or "below".
- If you didn't catch something (a name, a number, a model), ask them to say it again. Never guess at it.
- If they ask whether you're a person or a bot, say plainly you're the dealership's AI assistant, and offer to \
connect them with a person.
- When they're done, say a short goodbye and call end_call in the same reply."""


TRANSFER_RULES = """\
- To put the caller through to a person now, call transfer_to_person. Use it when they ask for a person, or when \
a person is needed and the dealership is open. If the dealership is closed, or the transfer doesn't connect, use \
handoff instead and tell them who will call them back."""


def instructions(desk: CallDesk) -> str:
    dealer_lines = build_system(desk.dealer, "phone", desk.customer, desk.contact_context)[1]["text"]
    sections = [STABLE, VOICE_RULES, TRANSFER_RULES, dealer_lines]
    return "\n\n".join(sections)


def greeting(desk: CallDesk) -> str:
    """Fixed words, said before the model runs: instant, and always includes the disclosures the dealer needs."""
    parts = [f"Thanks for calling {desk.dealer.name}."]
    if desk.dealer.disclose_upfront:
        parts.append("I'm the dealership's AI assistant.")
    if desk.plan.disclose_recording:
        parts.append("This call may be recorded.")
    parts.append("How can I help you today?")
    return " ".join(parts)


def shared_tool(spec: dict) -> llm.RawFunctionTool:
    """A tool from the shared layer, as a LiveKit raw-schema tool. Errors become a tool error the model can act
    on, never a stack trace read aloud."""
    name = spec["name"]

    async def call(raw_arguments: dict, context: RunContext[CallDesk]) -> str:
        desk = context.userdata
        try:
            out = await desk.run(name, raw_arguments)
        except Exception as e:
            log.exception("tool %s failed with %s", name, json.dumps(raw_arguments, default=str)[:500])
            desk.tool_problems.append({"tool": name, "crashed": f"{type(e).__name__}: {str(e)[:300]}"})
            raise ToolError("That didn't work. Don't retry it: tell the caller someone from the team will follow "
                            "up, and call handoff.") from e
        if isinstance(out, dict) and out.get("error"):
            log.warning("tool %s refused: %s", name, out["error"])
            desk.tool_problems.append({"tool": name, "refused": str(out["error"])[:300]})
        # LiveKit's Anthropic formatting sends a tool result that is a JSON array as content blocks, so a list of
        # cars would be rejected by the API. Wrap lists in an object.
        return json.dumps({"results": out} if isinstance(out, list) else out, default=str)

    return function_tool(call, raw_schema={"name": name, "description": spec["description"],
                                           "parameters": spec["input_schema"]})


def shared_tools() -> list[llm.RawFunctionTool]:
    return [shared_tool(s) for s in TOOL_SPECS]


FILLER = "One moment. "
# Tools that take a moment and lead to a second model reply; bookkeeping (update_lead_fields) and hanging up don't.
_SLOW_TOOLS = {"check_availability", "book_appointment", "reschedule_or_cancel", "search_inventory", "get_vehicle",
               "search_knowledge", "get_contact_context"}


def _needs_filler(chunks: list[llm.ChatChunk]) -> bool:
    return any(c.delta and any(t.name in _SLOW_TOOLS for t in c.delta.tool_calls or []) for c in chunks)


class OndraAgent(Agent):
    def __init__(self, desk: CallDesk) -> None:
        self._desk = desk
        super().__init__(instructions=instructions(desk), tools=shared_tools())

    async def llm_node(self, chat_ctx: llm.ChatContext, tools: list[llm.Tool],
                       model_settings: ModelSettings) -> AsyncIterable[llm.ChatChunk | str | FlushSentinel]:
        """The default model step, with every spoken sentence checked first (see `guard`). Tool calls pass
        straight through; only text the caller would hear is held back."""
        desk = self._desk
        # What the caller has said, from the history this reply answers: always complete, unlike the transcript
        # events, which can arrive after the reply starts. Without it the checks took the caller's own car ("my
        # 2021 BMW 330i") for a car Ondra made up, replaced the sentence, and handed the call off (first real call).
        desk.checks.customer_text = "\n".join(
            m.text_content or "" for m in chat_ctx.items if getattr(m, "type", None) == "message" and m.role == "user")

        def blocked(sentence: str, problems: list[str]) -> None:
            desk.blocked.extend(problems)
            log.warning("spoken sentence replaced: %s", ",".join(problems))
            desk.follow_up_on_block(problems)

        async def text_only() -> AsyncIterable[str]:
            async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
                if isinstance(chunk, str):
                    yield chunk
                elif isinstance(chunk, llm.ChatChunk):
                    if chunk.delta and chunk.delta.content:
                        yield chunk.delta.content
                    if chunk.delta and chunk.delta.tool_calls:
                        # Tool calls go straight through, after the text checked so far.
                        pending_calls.append(llm.ChatChunk(id=chunk.id, delta=llm.ChoiceDelta(
                            role="assistant", tool_calls=chunk.delta.tool_calls)))
                    if chunk.usage:
                        pending_calls.append(llm.ChatChunk(id=chunk.id, usage=chunk.usage))

        pending_calls: list[llm.ChatChunk] = []
        spoke = False
        async for sentence in guarded(text_only(), desk.checks, desk.dealer.never_say, blocked):
            spoke = True
            yield sentence
            while pending_calls:
                yield pending_calls.pop(0)
        if pending_calls and not spoke and _needs_filler(pending_calls):
            # A lookup or booking with nothing said first: say something now rather than leave the caller in
            # silence while the tool runs and the model answers again.
            yield FILLER
        while pending_calls:
            yield pending_calls.pop(0)

    @function_tool
    async def transfer_to_person(self, context: RunContext[CallDesk], team: str, brief: str) -> str:
        """Put the caller through to a person at the dealership now, briefing them first. Ask the caller before you
        call this.

        Args:
            team: "sales", "service" or "manager" (for complaints).
            brief: One or two sentences the person needs before they pick up: who's calling and what they want.
        """
        desk = context.userdata
        if not desk.dealer.open_now:
            return "The dealership is closed, so nobody can pick up. Call handoff instead and tell them when we'll call."
        target = await desk.transfer_target(team if team in ("sales", "service", "manager") else "sales")
        trunk = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK")
        if target is None or not trunk:
            return "Nobody can be put through right now. Call handoff instead and tell them who will call them back."
        from livekit.agents.beta.workflows import WarmTransferTask

        await self.session.say("One moment, I'll put you through.", allow_interruptions=False)
        try:
            await WarmTransferTask(sip_call_to=target.phone, sip_trunk_id=trunk, chat_ctx=self.chat_ctx,
                                   ringing_timeout=25.0,
                                   extra_instructions=f"What the caller needs: {brief}")
        except ToolError:
            return f"{target.name} didn't pick up. Tell the caller, then call handoff so {target.name} calls them back."
        desk.transferred_to = target
        await self.session.say(f"You're through to {target.name.split()[0]}. Thanks for calling.",
                               allow_interruptions=False)
        self.session.shutdown()
        return "transferred"

