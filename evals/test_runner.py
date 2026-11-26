"""The eval runner itself. With no model, only policy-layer turns run; they must pass, and nothing else may be
reported as a pass."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import run


async def test_policy_only_scenarios_pass_without_a_model():
    runnable, later = run.load()
    assert len(runnable) >= 20 and all(s.get("requires_step", 2) > 2 for s in later)
    reports = {s["id"]: await run.run_scenario(s, llm=None) for s in runnable}
    assert reports["008-vip-texts"].status == "pass"
    assert reports["009-opted-out-writes-again"].status == "pass"
    # Turns that need the model are NOT RUN, never passed.
    assert reports["001-after-hours-third-row"].status == "not_run"


def test_field_matching():
    assert run.field_matches(35000, 35000.0)
    assert run.field_matches("Toyota Highlander", "2021 Toyota Highlander XLE")
    assert run.field_matches("third row", "3rd row")
    assert not run.field_matches("Toyota Tacoma", "Toyota Highlander")
    assert run.field_matches("+12145551000", "(214) 555-1000")


async def test_fixture_knowledge_search():
    s = {"dealer": {"policy": {}}, "contact": {}, "context": {"knowledge": [
        {"q": "Opening hours", "a": "Mon to Fri 9 am to 7 pm, closed Sunday."}]}}
    b = run.FixtureBackend(s)
    assert (await b.search_knowledge("r u open sunday"))[0]["title"] == "Opening hours"
    assert await b.search_knowledge("do you install lift kits") == []
