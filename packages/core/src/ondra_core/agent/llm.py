"""The model interface. The orchestrator talks to `LLM`; `AnthropicLLM` is the real one, `ScriptedLLM` is a test
double that replays a fixed script (for plumbing tests only; it is never used to produce eval results)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    stop_reason: str  # end_turn | tool_use | max_tokens | refusal | ...
    text: str
    tool_calls: list[ToolCall]
    raw_content: list[Any]  # exactly what to send back as the assistant turn (keeps thinking blocks intact)
    model: str = ""
    usage: dict = field(default_factory=dict)


class LLM(Protocol):
    async def create(self, *, system: list[dict], messages: list[dict], tools: list[dict]) -> LLMResponse: ...


class AnthropicLLM:
    """Claude via the official SDK.

    - Adaptive thinking at a configurable effort (low by default: these are short chat replies and the reply has to
      land within seconds).
    - Server-side refusal fallback on, so a safety decline is retried on a fallback model inside the same call.
    - Forced tool choice isn't available on current models, so tool use is `auto` and steered by the prompt.
    """

    def __init__(self, *, api_key: str, model: str, effort: str = "low", base_url: str | None = None,
                 max_tokens: int = 8000, timeout_s: float = 30.0, http_client: Any = None,
                 thinking: str = "adaptive") -> None:
        import anthropic

        # Pass base_url explicitly so a stray ANTHROPIC_BASE_URL in the environment can't redirect traffic.
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, base_url=base_url or "https://api.anthropic.com", timeout=timeout_s, max_retries=2,
            **({"http_client": http_client} if http_client is not None else {}),
        )
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.thinking = thinking  # "adaptive", or "disabled" for one-word jobs like topic classification

    async def create(self, *, system: list[dict], messages: list[dict], tools: list[dict]) -> LLMResponse:
        resp = await self._client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            tools=tools,
            thinking={"type": self.thinking},
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        }
        return LLMResponse(resp.stop_reason or "", text, calls, list(resp.content), resp.model, usage)


class ScriptedLLM:
    """Replays scripted responses in order. Each item is either a string (a final text reply) or a list of
    (tool_name, input) pairs to call."""

    def __init__(self, script: list[str | list[tuple[str, dict]]]) -> None:
        self.script = list(script)
        self.requests: list[dict] = []

    async def create(self, *, system: list[dict], messages: list[dict], tools: list[dict]) -> LLMResponse:
        self.requests.append({"system": system, "messages": [dict(m) for m in messages], "tools": tools})
        if not self.script:
            raise RuntimeError("ScriptedLLM ran out of script")
        step = self.script.pop(0)
        if isinstance(step, str):
            return LLMResponse("end_turn", step, [], [{"type": "text", "text": step}], "scripted")
        calls = [ToolCall(f"toolu_{len(self.requests)}_{i}", n, a) for i, (n, a) in enumerate(step)]
        raw = [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in calls]
        return LLMResponse("tool_use", "", calls, raw, "scripted")
