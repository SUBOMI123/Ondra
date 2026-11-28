"""Voice tests: LiveKit's AgentSession in text mode (no audio, no LiveKit server), a scripted model, and the same
test database as the API suite (`ondra_api.testing`, created once per run)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from ondra_api.testing import configure_env, ensure_test_database

configure_env()

from livekit.agents.llm import (
    LLM,
    ChatChunk,
    ChatContext,
    ChoiceDelta,
    FunctionToolCall,
    LLMStream,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS


@pytest.fixture(scope="session")
async def database():
    return await ensure_test_database()


@dataclass
class Step:
    """One model response: text to say, then tool calls. `text` may be a function of the chat so far, so a reply
    can quote what a tool really returned."""

    text: str | Callable[[ChatContext], str] = ""
    calls: list[tuple[str, dict]] = field(default_factory=list)


class ScriptedLLM(LLM):
    """Answers each model request with the next scripted step, streamed in small pieces like a real model."""

    def __init__(self, steps: list[Step]) -> None:
        super().__init__()
        self.steps = list(steps)
        self.requests: list[ChatContext] = []

    def chat(self, *, chat_ctx: ChatContext, tools=None, conn_options=DEFAULT_API_CONNECT_OPTIONS, **_: Any) -> LLMStream:
        self.requests.append(chat_ctx.copy())
        step = self.steps.pop(0) if self.steps else Step()
        return _Stream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options, step=step)


class _Stream(LLMStream):
    def __init__(self, llm: ScriptedLLM, *, step: Step, **kw: Any) -> None:
        super().__init__(llm, **kw)
        self._step = step

    async def _run(self) -> None:
        text = self._step.text(self.chat_ctx) if callable(self._step.text) else self._step.text
        for i in range(0, len(text), 4):
            self._event_ch.send_nowait(ChatChunk(id="x", delta=ChoiceDelta(role="assistant", content=text[i:i + 4])))
        if self._step.calls:
            calls = [FunctionToolCall(name=n, arguments=json.dumps(a), call_id=f"call_{uuid.uuid4().hex[:8]}")
                     for n, a in self._step.calls]
            self._event_ch.send_nowait(ChatChunk(id="x", delta=ChoiceDelta(role="assistant", tool_calls=calls)))


def last_tool_output(chat_ctx: ChatContext) -> Any:
    out = next(i for i in reversed(chat_ctx.items) if i.type == "function_call_output")
    return json.loads(out.output)
