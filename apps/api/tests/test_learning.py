"""The learning loop. Includes the Step 6 acceptance check: an unanswered question, answered once by the dealer, is
used by the AI on the next identical question."""

import json
import uuid

import pytest
from ondra_api import channels, worker
from ondra_api.db import tenant_session
from ondra_api.services import inbound
from ondra_core.agent.llm import ScriptedLLM
from ondra_core.models import Contact, KnowledgeDoc, KnowledgeGap, MessageRating, Policy, Task
from sqlalchemy import delete, select, text, update

from tests.conftest import login

DEALER = "+12145550100"
SIG = {"x-mock-signature": "mock-secret"}
ANSWER = "Yes. We ship to Tema port in Ghana through our freight partner; it takes about five weeks."
DONT_KNOW = [[("search_knowledge", {"query": "Do you ship cars to Ghana?"})],
             [("handoff", {"reason": "unknown_answer", "brief": "Asks if we ship to Ghana.", "urgency": "normal", "target_role": "sales"})],
             "I don't have that to hand. I've passed it to our sales team."]


@pytest.fixture
async def shop(client, database, monkeypatch):
    t = database["a"]
    holder = {}
    monkeypatch.setattr(inbound, "llm_factory", lambda: holder.get("llm"))
    for ch in channels.CHANNELS:
        channels.mock(ch).outbox.clear()
    created: list[str] = []
    async with tenant_session(t) as db:
        draft_before = (await db.execute(select(Policy.draft_mode))).scalar_one()
        await db.execute(update(Policy).values(draft_mode=False))
        docs_before = set((await db.execute(select(KnowledgeDoc.id))).scalars())

    class Shop:
        tenant = t

        async def asks(self, body, script, *, frm=None, draft=False):
            if frm is None:
                frm = f"+1832555{uuid.uuid4().int % 9000 + 1000}"
                created.append(frm)
            holder["llm"] = ScriptedLLM(list(script))
            r = await client.post("/webhooks/mock/sms", headers=SIG,
                                  content=json.dumps({"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": DEALER, "text": body}))
            assert r.status_code == 200, r.text
            await worker.run_once()
            return frm, holder["llm"]

    yield Shop()
    async with tenant_session(t) as db:
        invented = (await db.execute(text("SELECT contact_id FROM contact_identities WHERE value = ANY(:v)"), {"v": created})).scalars().all()
        await db.execute(delete(Task).where(Task.contact_id.in_(invented)))
        await db.execute(delete(Contact).where(Contact.id.in_(invented)))
        await db.execute(delete(KnowledgeGap))
        await db.execute(delete(MessageRating))
        await db.execute(delete(KnowledgeDoc).where(KnowledgeDoc.id.notin_(docs_before)))
        await db.execute(text("DELETE FROM events WHERE type IN ('draft.edited', 'reply.rated')"))
        await db.execute(update(Policy).values(draft_mode=draft_before))


async def test_an_unanswered_question_answered_once_is_used_next_time(client, shop):
    """Step 6 acceptance."""
    manager = await login(client, "manager@prestigemotors.example")
    sales = await login(client, "daniel@prestigemotors.example")
    await shop.asks("Hi, do you ship cars to Ghana?", DONT_KNOW)
    await shop.asks("do you guys ship to ghana", DONT_KNOW)  # a second customer, same question
    got = (await client.get("/knowledge", headers=sales)).json()
    [gap] = got["unanswered"]
    assert (gap["question"], gap["times"], gap["asked"]) == ("do you ship cars to ghana", 2, "do you guys ship to ghana")
    assert got["can_edit"] is False  # sales can read the list; a manager answers

    body = {"question": "Do you ship cars to Ghana?", "answer": ANSWER}
    assert (await client.post(f"/knowledge/unanswered/{gap['id']}/answer", json=body, headers=sales)).status_code == 403
    r = await client.post(f"/knowledge/unanswered/{gap['id']}/answer", json=body, headers=manager)
    assert r.status_code == 201, r.text
    after = (await client.get("/knowledge", headers=sales)).json()
    assert after["unanswered"] == [] and after["answers"][0]["answer"] == ANSWER

    # The next customer asks the identical question: the search now returns the dealer's answer, and Ondra uses it.
    _, llm = await shop.asks("Do you ship cars to Ghana?", [[("search_knowledge", {"query": "Do you ship cars to Ghana?"})],
                                                            "Yes, we ship to Tema port in Ghana. It takes about five weeks."])
    assert ANSWER in json.dumps(llm.requests[1]["messages"])  # what the model was handed before it wrote
    assert "Tema" in channels.mock("sms").outbox[-1].body
    assert (await client.get("/knowledge", headers=sales)).json()["unanswered"] == []  # and no new gap
    # Answering twice isn't possible; the question has left the list.
    assert (await client.post(f"/knowledge/unanswered/{gap['id']}/answer", json=body, headers=manager)).status_code == 404


async def test_answers_can_be_added_changed_ignored_and_never_cross_dealerships(client, database, shop):
    owner = await login(client, "owner@prestigemotors.example")
    other = await login(client, "owner@lonestar.example")
    await shop.asks("Is your mechanic married?", [[("search_knowledge", {"query": "is the mechanic married"})],
                                                 [("handoff", {"reason": "unknown_answer", "brief": "Odd question.", "urgency": "low", "target_role": "sales"})],
                                                 "I can't help with that one."])
    [gap] = (await client.get("/knowledge", headers=owner)).json()["unanswered"]
    assert (await client.get("/knowledge", headers=other)).json()["unanswered"] == []  # not another dealer's
    assert (await client.post(f"/knowledge/unanswered/{gap['id']}/answer", json={"question": "Anything", "answer": "Whatever"}, headers=other)).status_code == 404
    assert (await client.post(f"/knowledge/unanswered/{gap['id']}/ignore", headers=owner)).status_code == 204
    got = (await client.get("/knowledge", headers=owner)).json()
    assert got["unanswered"] == [] and got["ignored"] == 1
    assert (await client.post(f"/knowledge/unanswered/{gap['id']}/reopen", headers=owner)).status_code == 204
    assert len((await client.get("/knowledge", headers=owner)).json()["unanswered"]) == 1

    made = (await client.post("/knowledge/answers", json={"question": "Do you offer paint protection film?", "answer": "Yes, from $900."}, headers=owner)).json()
    async with tenant_session(shop.tenant) as db:
        from ondra_api.services import knowledge

        assert any("paint protection" in d["title"].lower() for d in await knowledge.search(db, "paint protection film"))
    changed = (await client.put(f"/knowledge/answers/{made['id']}", headers=owner,
                                json={"question": "Do you offer paint protection film?", "answer": "Yes, ask service for a quote."})).json()
    assert changed["answer"] == "Yes, ask service for a quote."
    async with tenant_session(shop.tenant) as db:
        hit = next(d for d in await knowledge.search(db, "paint protection film") if "paint" in d["title"].lower())
        assert hit["answer"] == "Yes, ask service for a quote."  # re-embedded with the new words
    async with tenant_session(database["b"]) as db:
        assert not any("paint" in d["title"].lower() for d in await knowledge.search(db, "paint protection film"))
    assert (await client.post("/knowledge/answers", json={"question": "   ", "answer": "ok then"}, headers=owner)).status_code == 422
    assert (await client.delete(f"/knowledge/answers/{made['id']}", headers=owner)).status_code == 204
    assert (await client.delete(f"/knowledge/answers/{made['id']}", headers=other)).status_code == 404


async def test_people_rate_ondras_replies_and_corrections_are_listed(client, shop):
    sales = await login(client, "daniel@prestigemotors.example")
    manager = await login(client, "manager@prestigemotors.example")
    frm, _ = await shop.asks("What time do you close today?", ["We close at 9 pm."])
    async with tenant_session(shop.tenant) as db:
        rows = (await db.execute(text("""SELECT m.id, m.author_type, m.conversation_id FROM messages m JOIN conversations c ON c.id = m.conversation_id
            JOIN contact_identities i ON i.contact_id = c.contact_id WHERE i.value = :v ORDER BY m.created_at"""), {"v": frm})).all()
    theirs, ondras = rows[0], rows[1]
    assert (await client.put(f"/messages/{theirs.id}/rating", json={"rating": "good"}, headers=sales)).status_code == 404  # only Ondra's
    r = await client.put(f"/messages/{ondras.id}/rating", json={"rating": "wrong", "note": "We close at 7 on weekdays."}, headers=sales)
    assert r.status_code == 200 and r.json()["rating"] == "wrong"
    assert (await client.put(f"/messages/{ondras.id}/rating", json={"rating": "brilliant"}, headers=sales)).status_code == 422
    detail = (await client.get(f"/conversations/{ondras.conversation_id}", headers=sales)).json()
    assert [m["rating"] for m in detail["messages"]] == [None, "wrong"]

    assert (await client.get("/knowledge/corrections", headers=sales)).status_code == 403
    got = (await client.get("/knowledge/corrections", headers=manager)).json()
    [rated] = got["rated"]
    assert (rated["rating"], rated["note"], rated["reply"], rated["customer_said"], rated["by"]) == (
        "wrong", "We close at 7 on weekdays.", "We close at 9 pm.", "What time do you close today?", "Daniel Okafor")
    # Changing your mind replaces the rating; clearing removes it.
    await client.put(f"/messages/{ondras.id}/rating", json={"rating": "good"}, headers=manager)
    got = (await client.get("/knowledge/corrections", headers=manager)).json()
    assert got["rated"] == [] and got["good"] == 1
    assert (await client.delete(f"/messages/{ondras.id}/rating", headers=sales)).status_code == 204

    # A draft a person changed before sending shows up as a correction: what Ondra wrote, what was sent instead.
    async with tenant_session(shop.tenant) as db:
        await db.execute(update(Policy).values(draft_mode=True))
    frm2, _ = await shop.asks("Do you have loaners?", ["Yes, always."])
    async with tenant_session(shop.tenant) as db:
        draft = (await db.execute(text("""SELECT m.id FROM messages m JOIN conversations c ON c.id = m.conversation_id
            JOIN contact_identities i ON i.contact_id = c.contact_id WHERE i.value = :v AND m.is_draft"""), {"v": frm2})).scalar_one()
    r = await client.post(f"/messages/{draft}/approve", json={"body": "Yes, if you book one ahead."}, headers=sales)
    assert r.status_code == 200, r.text
    [edit] = (await client.get("/knowledge/corrections", headers=manager)).json()["edits"]
    assert (edit["before"], edit["after"]) == ("Yes, always.", "Yes, if you book one ahead.")
