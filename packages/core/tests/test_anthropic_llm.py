"""The real client's request and response handling, against a stub transport (no network, no key).
This proves what we send and how we read the reply; it does not prove the live API accepts it."""

import json

import httpx2
from ondra_core.agent.llm import AnthropicLLM
from ondra_core.agent.prompt import CustomerFacts, DealerFacts, build_system
from ondra_core.agent.tools import TOOL_SPECS


async def test_request_shape_and_tool_use_parsing():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "stop_reason": "tool_use", "stop_sequence": None,
            "content": [
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "tool_use", "id": "toolu_1", "name": "search_inventory", "input": {"query": "highlander"}},
            ],
            "usage": {"input_tokens": 900, "output_tokens": 40, "cache_read_input_tokens": 800},
        })

    llm = AnthropicLLM(api_key="test", model="claude-sonnet-5-5", base_url="https://api.anthropic.com",
                       http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    system = build_system(DealerFacts("Prestige Motors", "Tue 10:48 pm", False), "sms", CustomerFacts(known=False))
    resp = await llm.create(system=system, messages=[{"role": "user", "content": "highlander?"}], tools=TOOL_SPECS)

    assert seen["url"].startswith("https://api.anthropic.com/v1/messages")
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    b = seen["body"]
    assert b["model"] == "claude-sonnet-5-5" and b["thinking"] == {"type": "adaptive"}
    assert b["output_config"] == {"effort": "low"} and b["fallbacks"] == "default"
    assert "tool_choice" not in b and b["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert resp.stop_reason == "tool_use" and resp.tool_calls[0].name == "search_inventory"
    assert resp.raw_content[0].type == "thinking"  # thinking blocks are kept to send back unchanged
    assert resp.usage["cache_read_input_tokens"] == 800
