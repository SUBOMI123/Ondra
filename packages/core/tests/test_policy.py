import pytest
from ondra_core.agent.policy import InboundFacts, classify_consent, evaluate_inbound, may_send_outbound


def facts(**kw):
    base = dict(channel="sms", body="is the civic still there", contact_is_vip=False, contact_opted_out=False,
                conversation_ai_mode="auto", tenant_draft_mode=False)
    return InboundFacts(**(base | kw))


@pytest.mark.parametrize("body", ["STOP", "stop", " Stop. ", "UNSUBSCRIBE", "stopall", "End", "please stop texting me",
                                  "Don't text me again", "take me off your list"])
def test_opt_out_words(body):
    assert classify_consent(body) == "opt_out"


@pytest.mark.parametrize("body", ["can I stop by saturday?", "the end of the month works", "yes", "stop sign is broken",
                                  "is the civic still there"])
def test_not_opt_out(body):
    assert classify_consent(body) is None


def test_vip_never_reaches_ai_and_alerts_owner():
    d = evaluate_inbound(facts(contact_is_vip=True))
    assert not d.run_ai and d.reason == "vip"
    assert d.alert.to == "owner" and d.alert.urgency == "high"


def test_vip_in_draft_mode_still_gets_no_draft():
    d = evaluate_inbound(facts(contact_is_vip=True, tenant_draft_mode=True, conversation_ai_mode="draft"))
    assert not d.run_ai and not d.draft


def test_stop_opts_out_everywhere_even_for_vip():
    d = evaluate_inbound(facts(body="STOP", contact_is_vip=True))
    assert not d.run_ai and d.consent_change == "opted_out_all_channels" and d.alert is None


def test_opted_out_contact_gets_no_ai_but_a_person_is_told():
    d = evaluate_inbound(facts(contact_opted_out=True))
    assert not d.run_ai and d.reason == "opted_out" and d.alert is not None


def test_start_opts_back_in_without_ai_reply():
    d = evaluate_inbound(facts(body="START", contact_opted_out=True))
    assert not d.run_ai and d.consent_change == "opted_in"


def test_ai_off_and_draft_mode():
    assert evaluate_inbound(facts(conversation_ai_mode="off")).run_ai is False
    d = evaluate_inbound(facts(tenant_draft_mode=True))
    assert d.run_ai and d.draft
    assert evaluate_inbound(facts()).draft is False


def test_outbound_gate():
    assert may_send_outbound(contact_is_vip=False, contact_opted_out=True, author_type="user") == (False, "opted_out")
    assert may_send_outbound(contact_is_vip=True, contact_opted_out=False, author_type="ai") == (False, "vip")
    assert may_send_outbound(contact_is_vip=True, contact_opted_out=False, author_type="user")[0] is True
