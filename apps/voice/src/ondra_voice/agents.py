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
import re
from collections.abc import AsyncIterable

from livekit.agents import Agent, FlushSentinel, ModelSettings, RunContext, function_tool, llm
from livekit.agents.llm import ToolError
from ondra_core.agent.prompt import STABLE, build_system
from ondra_core.agent.tools import TOOL_SPECS

from .desk import CallDesk
from .guard import guarded

log = logging.getLogger("ondra.voice")

VOICE_RULES = """\
This is a live phone call. Everything you write is spoken aloud by a voice, once, to someone holding a phone to \
their ear. They can't re-read it, skim it or see anything. These rules override anything above about writing, \
texting or message length.

How to sound
- Talk the way a good person at the dealership's front desk talks: short, plain sentences, with contractions \
("we've got", "you're all set"). Most replies are one or two sentences. Three is a long one.
- Answer in the first few words ("Yes, we've got two."), then add what they need. At most one question, at the end.
- One piece of information per sentence. A listener can hold about one number at a time, so a sentence carrying a \
car, a mileage and a price loses them. When you name a car, say the year, the model and the price, and stop. \
Mileage, trim, colour and features wait until they ask, or until that detail is the reason the car fits what they \
said they want.
- Name cars the way people do on the phone. Once you both know it's a Honda CR-V, it's "the 2023" or "the CR-V", \
not "the 2023 Honda CR-V EX-L" each time. Use the trim only to tell two of the same model apart, or if they ask.
- Mileage is fine rounded ("about 23,000 miles"). A price never is: say exactly the listed price.
- Say each thing once in the whole call. Don't repeat their words back to them, don't recap what you already \
told them, and don't describe your own steps ("I've noted that", "I'll mark it as urgent", "I've recorded your \
details"). They only need the result.
- Skip call-centre phrases: "I'd be happy to", "Certainly", "Absolutely", "Is there anything else I can help you \
with?". A plain "Sure" or "Got it" is fine now and then, not on every reply.
- No lists, markdown, symbols or links, and nothing like "as you can see" or "below".

To show the rhythm (an illustration, not wording to copy): written style would be "We have two Honda CR-Vs. The \
first is a 2023 CR-V EX-L with about 23,500 miles, listed at $25,100." Spoken, that's "Yes, we've got two. \
There's a 2023 at $25,100, and a 2024 at $29,800. Want to hear about either one?"

Numbers, names and times
- Write prices with digits and a dollar sign ($31,900): the voice reads them aloud correctly, and the checks on \
what you say need the digits. Say times the way people do ("nine on Saturday morning", "half past two"), never \
"9:00 AM".
- Use first names for staff ("with Maria"). Never read out ids, slot ids or stock numbers, unless they ask for \
the stock number.
- If you didn't catch something (a name, a number, a model), ask them to say it again. Never guess at it. Just \
ask ("Which CR-V was that?"), without apologising: save "sorry" for when something has actually gone wrong for them.

Looking things up
- Before a tool that takes a moment, say a few words first in the same reply ("Let me check."), then call it. \
Never say you'll check without calling the tool in that same reply.
- When more than three cars fit, a stock search gives you the best two and how many it found. Name those two, \
ask what matters most to them, and offer to text the full list. With two or three, name each one, short. Never \
read out a longer list.
- When several times are open, offer at most two ("I've got nine or ten thirty"), and say there are more if there \
are. Don't describe the whole schedule.
- Text the caller only when they've asked for a text ("text me those") or said yes when you offered ("Can I text \
you the details at this number?"). Either is their consent: call text_details right away, without asking again.

Booking
- If they pick a time you offered ("nine works"), that's their yes: book it. When they answer with a time, match \
it to the slot whose time they said, never to its position in the list. If you're working out the day or time \
yourself from something vaguer, say it back and get a yes before you book, because a wrong booking by voice is \
worse than one extra question.
- For service, the make is enough to book ("my BMW"). Don't hold a booking up for the year or model, and ask \
for the time and wait-or-loaner together as one question.
- If you offered two times and they say yes without picking one ("yeah, that works"), ask which: "Two, or half \
past?" Don't choose for them.
- If the day they asked for is today and the time has passed, say so plainly, and ask if they meant next week.
- Only say something is booked, moved or cancelled after the tool succeeds. Then confirm it in one short \
sentence: the day, the time and who they'll see. Anything else they need (leaving the car, a loaner) goes in a \
second sentence.

Passing things to the team
- When something has to go to a person (a discount, a trade-in value, a delivery date), call handoff first, then \
tell them once, in one sentence, who will call them back. The call isn't over: carry on with whatever else they \
wanted. Don't say goodbye or thank them for calling because you handed something off.

Being an AI
- If they ask whether you're a person or a bot, say plainly you're the dealership's AI assistant, and offer to \
connect them with a person.

Ending the call
- The caller decides when the call is over. Say goodbye only when they've said they're done ("that's all", \
"thanks, bye"). Then say one short goodbye and call end_call in the same reply. Until then, never say "thanks for \
calling" or "goodbye"."""


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
# Said the moment the caller finishes, when what they asked needs a lookup: no wait for the model to start talking.
QUICK_FILLERS = ["Sure, let me check.", "One sec, let me take a look.", "Okay, let me look that up.",
                 "Let me see what we have.", "Give me a second to check."]
_NEEDS_LOOKUP = re.compile(
    r"\b(do you (?:have|guys have|carry)|in stock|available|any (?:\w+ ){0,3}(?:cars?|trucks?|suvs?|vans?|sedans?)|"
    r"how much|price|cost|book|schedule|appointment|reschedule|move (?:my|it|the)|cancel|times?|slots?|openings?|"
    r"what (?:time|day)|when (?:can|could|are you)|hours|open (?:on|at|till|until)|test drive|oil change|service)\b",
    re.IGNORECASE)
# The model's own "let me check" opener, dropped when a quick filler already said it this turn.
_OWN_FILLER = re.compile(r"^\s*(?:sure|okay|ok|great|got it)?[,.!]?\s*(?:let me|one (?:sec|second|moment)|give me|"
                         r"hold on|bear with me)\b[^.?!]*[.!]\s*$", re.IGNORECASE)
# Tools that take a moment and lead to a second model reply; bookkeeping (update_lead_fields) and hanging up don't.
_SLOW_TOOLS = {"check_availability", "book_appointment", "reschedule_or_cancel", "search_inventory", "get_vehicle",
               "search_knowledge", "get_contact_context"}


def _needs_filler(chunks: list[llm.ChatChunk]) -> bool:
    return any(c.delta and any(t.name in _SLOW_TOOLS for t in c.delta.tool_calls or []) for c in chunks)


class OndraAgent(Agent):
    def __init__(self, desk: CallDesk) -> None:
        self._desk = desk
        super().__init__(instructions=instructions(desk), tools=shared_tools())

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        """The caller just finished. If what they asked needs a lookup, say a short filler now, so they hear
        something within a moment instead of waiting for the model's first words (real calls: "a huge pause")."""
        desk = self._desk
        desk.filled_this_turn = False
        if _NEEDS_LOOKUP.search(new_message.text_content or "") and not desk.filled_last_turn:
            phrase = QUICK_FILLERS[desk.filler_index % len(QUICK_FILLERS)]
            desk.filler_index += 1
            desk.filled_this_turn = True
            self.session.say(phrase, add_to_chat_ctx=False)
        desk.filled_last_turn = desk.filled_this_turn  # never two turns in a row: it starts to sound canned

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
            log.warning("spoken sentence replaced (%s): %s", ",".join(problems), sentence)
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
        first = True
        async for sentence in guarded(text_only(), desk.checks, desk.dealer.never_say, blocked):
            if first and desk.filled_this_turn and _OWN_FILLER.match(sentence):
                first = False
                continue  # the caller already heard "let me check" from the quick filler
            first = False
            spoke = True
            yield sentence
            while pending_calls:
                yield pending_calls.pop(0)
        if pending_calls and not spoke and not desk.filled_this_turn and _needs_filler(pending_calls):
            # A lookup or booking with nothing said first: say something now rather than leave the caller in
            # silence while the tool runs and the model answers again.
            yield FILLER
        while pending_calls:
            yield pending_calls.pop(0)

    @function_tool
    async def text_details(self, context: RunContext[CallDesk], stock_numbers: list[str] | None = None) -> str:
        """Text the caller the cars from your last stock search, with prices, to the number they're calling from.
        Only when they asked for a text or said yes to your offer; their words are recorded as their consent.

        Args:
            stock_numbers: Only these cars, if they picked some. Leave out to send all of them.
        """
        said = next((m.text_content or "" for m in reversed(self.chat_ctx.items)
                     if getattr(m, "type", None) == "message" and m.role == "user"), "")
        return json.dumps(await context.userdata.text_details(stock_numbers, said), default=str)

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

