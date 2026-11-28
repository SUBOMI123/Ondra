from ondra_core.agent.llm import ScriptedLLM
from ondra_core.agent.orchestrator import Turn, run_turn
from ondra_core.agent.prompt import CustomerFacts, DealerFacts

HIGHLANDER = {"stock": "T21-1037", "year": 2021, "make": "Toyota", "model": "Highlander", "price": 33900}


class FakeBackend:
    def __init__(self):
        self.calls = []

    async def get_contact_context(self):
        return {}

    async def search_inventory(self, **f):
        self.calls.append(("search_inventory", f))
        return [HIGHLANDER]

    async def get_vehicle(self, stock_or_vin):
        return HIGHLANDER

    async def search_knowledge(self, query):
        return []

    async def update_lead_fields(self, fields):
        self.calls.append(("update_lead_fields", fields))
        return {"saved": sorted(fields)}

    async def handoff(self, reason, brief, urgency, target_role):
        self.calls.append(("handoff", reason))
        return {"task_id": "t1", "tell_customer": "I've passed this to our sales team."}


DEALER = DealerFacts(name="Prestige Motors", local_time="Tue 10:48 pm", open_now=False)


async def turn(script):
    backend = FakeBackend()
    llm = ScriptedLLM(script)
    res = await run_turn(llm=llm, backend=backend, dealer=DEALER, customer=CustomerFacts(known=False), channel="sms",
                         history=[Turn("customer", "is the white highlander still there? budget 35k")])
    return res, backend, llm


async def test_tools_then_reply():
    res, backend, llm = await turn([
        [("search_inventory", {"query": "highlander"}), ("update_lead_fields", {"fields": {"budget_max": 35000}})],
        "Yes, the 2021 Highlander XLE is here, listed at $33,900. Want to come see it?",
    ])
    assert res.tools_called == ["search_inventory", "update_lead_fields"]
    assert res.reply.startswith("Yes") and not res.blocked and res.model_calls == 2
    # Tool results go back in one user message, and the stable prompt block is marked for caching.
    assert llm.requests[1]["messages"][-1]["content"][0]["type"] == "tool_result"
    assert llm.requests[0]["system"][0]["cache_control"] == {"type": "ephemeral"}


async def test_rule_breaking_draft_is_rewritten_not_sent():
    res, _, llm = await turn([
        [("search_inventory", {})],
        "I can knock $2,000 off for you.",
        "It's listed at $33,900. I can't change the price by text; our sales team can talk it through.",
    ])
    assert "promises_discount" in res.blocked and res.rewritten and "knock" not in res.reply
    assert llm.requests[2]["messages"][-1]["role"] == "system"


async def test_two_bad_drafts_fall_back_to_a_person():
    res, backend, _ = await turn([[("search_inventory", {})], "We can do $30,000.", "Fine, $31,000 it is."])
    assert res.fallback == "failed_checks"
    assert ("handoff", "pricing") in backend.calls
    assert "$" not in res.reply


async def test_invented_car_is_blocked():
    res, _, _ = await turn([[("search_inventory", {})], "We have a 2022 Honda Pilot too.", "We have the Highlander."])
    assert "invents_inventory" in res.blocked and res.reply == "We have the Highlander."


def test_disclosure_is_when_asked_unless_the_dealer_turns_on_upfront():
    from ondra_core.agent.prompt import build_system

    default = build_system(DEALER, "sms", CustomerFacts(known=False))
    assert "Never say or imply you're a person" in default[0]["text"]
    assert "first reply" not in default[1]["text"]
    upfront = DealerFacts(name="X", local_time="Tue 10:48 pm", open_now=False, disclose_upfront=True)
    assert "first reply in this conversation, say you're the dealership's AI assistant" in build_system(
        upfront, "sms", CustomerFacts(known=False))[1]["text"]


async def test_reply_written_alongside_the_final_handoff_saves_a_round_trip():
    from ondra_core.agent.llm import LLMResponse, ToolCall

    class OneShot:
        def __init__(self):
            self.calls = 0

        async def create(self, *, system, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse("tool_use", "", [ToolCall("t1", "search_inventory", {})],
                                   [{"type": "tool_use", "id": "t1", "name": "search_inventory", "input": {}}])
            text = "It's listed at $33,900. I've passed your offer to our sales team; they'll be in touch when we open."
            calls = [ToolCall("t2", "handoff", {"reason": "pricing", "brief": "b", "urgency": "high", "target_role": "sales"})]
            return LLMResponse("tool_use", text, calls, [{"type": "text", "text": text},
                                                          {"type": "tool_use", "id": "t2", "name": "handoff", "input": calls[0].input}])

    llm, backend = OneShot(), FakeBackend()
    res = await run_turn(llm=llm, backend=backend, dealer=DEALER, customer=CustomerFacts(known=False), channel="sms",
                         history=[Turn("customer", "can you do 30k on the highlander")])
    assert llm.calls == 2 and res.model_calls == 2
    assert res.handoff["target_role"] == "sales" and res.reply.startswith("It's listed at $33,900")


async def test_reply_alongside_a_lookup_is_not_used_because_it_hasnt_seen_the_results():
    res, _, llm = await turn([
        [("search_inventory", {})],
        "Yes, the Highlander is here at $33,900.",
    ])
    assert res.model_calls == 2  # the lookup's text (if any) is ignored; the reply came after the results
