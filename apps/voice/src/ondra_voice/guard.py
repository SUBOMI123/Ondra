"""Checks what the agent is about to say, a sentence at a time, before it's spoken.

Text replies are checked whole before they're sent (`ondra_core.agent.detectors.review_reply`). A phone call can't
wait for a whole reply: the caller would hear seconds of silence. So the voice agent streams, and this sits between
the model and the voice: it holds each sentence until it's complete, runs the same blocking checks on it (final
price, discount, delivery date, trade-in value, financing, instructions, invented cars, the dealer's never-say
list), and speaks it only if it passes. A failing sentence is replaced with a safe line and a person is asked to
follow up. The cost is the time to finish one sentence, which the voice needs anyway before it can speak well.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterable, AsyncIterator, Callable

from ondra_core.agent.detectors import ReplyContext, review_reply

SAFE_LINE = "That's something one of our team needs to go over with you, and I'll make sure they do."
# A sentence ends at . ! or ? followed by a space or the end. Numbers like "$41,500.00" or "3.5" aren't ends.
_END = re.compile(r"(?<=[.!?])\s+(?=\S)")


def split_ready(buffer: str) -> tuple[list[str], str]:
    """Complete sentences in `buffer`, and what's left over."""
    parts = _END.split(buffer)
    if len(parts) == 1:
        return [], buffer
    return [p for p in parts[:-1] if p.strip()], parts[-1]


def check_sentence(sentence: str, ctx: ReplyContext, never_say: list[str]) -> list[str]:
    return sorted(review_reply(sentence, ctx, never_say))


async def guarded(text: AsyncIterable[str], ctx: ReplyContext, never_say: list[str],
                  on_block: Callable[[str, list[str]], None]) -> AsyncIterator[str]:
    """Yield the model's text a sentence at a time, replacing any sentence that fails a blocking check.
    The safe line is said once per reply even if several sentences fail."""
    buffer, replaced = "", False

    def emit(sentence: str) -> str | None:
        nonlocal replaced
        problems = check_sentence(sentence, ctx, never_say)
        if not problems:
            return sentence
        on_block(sentence, problems)
        if replaced:
            return None
        replaced = True
        return SAFE_LINE

    async for delta in text:
        buffer += delta
        ready, buffer = split_ready(buffer)
        for s in ready:
            if (out := emit(s)) is not None:
                yield out + " "
    if buffer.strip() and (out := emit(buffer)) is not None:
        yield out
