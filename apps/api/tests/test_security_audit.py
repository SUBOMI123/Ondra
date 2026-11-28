"""Fixes from the security audit (2026-11-28), each tested as the attack it stops."""

import base64
import json
import uuid

import pytest
from ondra_api import worker
from ondra_api.config import Settings
from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.seed import DEALER_EMAIL
from ondra_api.services import bridge, inbound
from ondra_api.services.agent_tools import DbToolBackend
from ondra_core.channels.base import SignatureError, WebhookRequest
from ondra_core.channels.postmark import PostmarkAdapter as PostmarkEmail
from ondra_core.channels.twilio_sms import TwilioSmsAdapter as TwilioSms
from ondra_core.channels.whatsapp import WhatsAppCloudAdapter as WhatsAppCloud
from ondra_core.models import Contact, ContactIdentity, Conversation, Deal, Event
from sqlalchemy import select, text

from .conftest import login

SIG = {"x-mock-signature": "mock-secret"}


# --- 1. A number or email the customer types is a claim, not an identity ----------------------------------------

async def test_claiming_someone_elses_number_gets_their_repair_orders_nothing(database):
    """The seeded customer +12145551001 has a repair order. An attacker texting from their own number says it's
    theirs: it is kept on the deal for staff, but never attached to the contact, so nothing of the victim's leaks
    and no message is ever sent to it."""
    t = database["a"]
    attacker = f"+1469555{uuid.uuid4().int % 10000:04d}"
    async with tenant_session(t) as db:
        c = Contact(display_name=attacker, preferred_channel="sms")
        db.add(c)
        await db.flush()
        db.add(ContactIdentity(contact_id=c.id, kind="phone", value=attacker))
        conv = Conversation(contact_id=c.id, channel="sms", ai_mode="auto")
        db.add(conv)
        await db.flush()
        backend = DbToolBackend(db, contact=c, conversation=conv, price_disclosure="listed", open_now=True)
        await backend.update_lead_fields({"phone": "+12145551001", "email": "victim@example.com"})
        idents = (await db.execute(select(ContactIdentity.value).where(ContactIdentity.contact_id == c.id))).scalars().all()
        assert idents == [attacker]
        deal = (await db.execute(select(Deal).where(Deal.contact_id == c.id))).scalar_one()
        assert deal.vehicle_of_interest["phone_given"] == "+12145551001"
        out = await backend.get_repair_order_status()
        assert out["found"] is False and "RO-55120" not in json.dumps(out)
        await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": c.id})


# --- 2. A forged START never undoes a STOP --------------------------------------------------------------------

async def _post(client, channel, frm, body, to):
    payload = {"id": f"m-{uuid.uuid4().hex[:10]}", "from": frm, "to": to, "text": body}
    r = await client.post(f"/webhooks/mock/{channel}", content=json.dumps(payload), headers=SIG)
    await worker.run_once()
    assert r.status_code == 200
    return r


async def test_start_by_email_doesnt_lift_a_texted_stop(client, database, monkeypatch):
    monkeypatch.setattr(inbound, "llm_factory", lambda: None)
    t = database["a"]
    phone = f"+1469555{uuid.uuid4().int % 10000:04d}"
    email = f"cust-{uuid.uuid4().hex[:8]}@example.com"
    async with tenant_session(t) as db:
        c = Contact(display_name="Ade Bello", preferred_channel="sms")
        db.add(c)
        await db.flush()
        db.add_all([ContactIdentity(contact_id=c.id, kind="phone", value=phone),
                    ContactIdentity(contact_id=c.id, kind="email", value=email)])
        cid = c.id
    try:
        await _post(client, "sms", phone, "STOP", "+12145550100")
        # Anyone can put the customer's address in an email's From line.
        await _post(client, "email", email, "START", DEALER_EMAIL)
        async with tenant_session(t) as db:
            assert await inbound.contact_opted_out(db, cid)
            ignored = (await db.execute(select(Event).where(Event.type == "consent.opt_in_ignored",
                                                            Event.payload["contact_id"].astext == str(cid)))).scalars().all()
            assert ignored
        # START from the number that sent STOP does lift it.
        await _post(client, "sms", phone, "START", "+12145550100")
        async with tenant_session(t) as db:
            assert not await inbound.contact_opted_out(db, cid)
    finally:
        async with tenant_session(t) as db:
            await db.execute(text("DELETE FROM contacts WHERE id = :c"), {"c": cid})


# --- 3 and 4. Webhooks with no secret, and the mock webhook on a public site --------------------------------------

def _req(headers=None, body=b"{}", form=None):
    return WebhookRequest("POST", "https://api.example.com/webhooks/x", headers or {}, {}, body, form or {})


def test_real_adapters_refuse_when_their_secret_is_empty():
    wa = WhatsAppCloud(access_token="t", app_secret="", verify_token="", phone_number_id="1")
    import hashlib
    import hmac
    forged = "sha256=" + hmac.new(b"", b"{}", hashlib.sha256).hexdigest()
    with pytest.raises(SignatureError):
        wa.verify_signature(_req({"x-hub-signature-256": forged}))
    assert wa.verify_subscription({"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "x"}) is None
    from ondra_core.channels.twilio_sms import twilio_signature
    tw = TwilioSms(account_sid="AC1", auth_token="")
    with pytest.raises(SignatureError):
        tw.verify_signature(_req({"x-twilio-signature": twilio_signature("", "https://api.example.com/webhooks/x", {})}))
    pm = PostmarkEmail(server_token="t", webhook_user="", webhook_password="")
    with pytest.raises(SignatureError):
        pm.verify_signature(_req({"authorization": "Basic " + base64.b64encode(b":").decode()}))
    pm = PostmarkEmail(server_token="t", webhook_user="u", webhook_password="p")
    with pytest.raises(SignatureError):  # non-ASCII is a rejection, not a 500
        pm.verify_signature(_req({"authorization": "Basic " + base64.b64encode("ü:p".encode()).decode()}))


def test_a_public_site_wont_start_with_a_channel_on_and_its_secret_empty():
    s = Settings(app_base_url="https://app.useondra.com", jwt_secret="x" * 48, mock_webhook_secret="y" * 32,
                 auth_provider="clerk", feature_email=True, feature_whatsapp=True, whatsapp_app_secret="s",
                 whatsapp_verify_token="", postmark_inbound_user="", postmark_inbound_password="")
    problems = " ".join(s.public_site_problems())
    assert "FEATURE_EMAIL" in problems and "WHATSAPP_VERIFY_TOKEN" in problems and "WHATSAPP_APP_SECRET" not in problems


async def test_the_mock_webhook_and_mock_voice_key_are_off_on_a_public_site(client, monkeypatch):
    public = Settings(app_base_url="https://app.useondra.com", jwt_secret="x" * 48, mock_webhook_secret="mock-secret")
    from ondra_api.routers import webhooks
    monkeypatch.setattr(webhooks, "get_settings", lambda: public)
    payload = {"id": "m-x", "from": "+12145550101", "to": "+12145550100", "text": "hi"}
    r = await client.post("/webhooks/mock/sms", content=json.dumps(payload), headers=SIG)
    assert r.status_code == 404
    monkeypatch.setattr(bridge, "get_settings", lambda: public)
    from ondra_core.channels.twilio_sms import twilio_signature
    url, form = "https://api.useondra.com/webhooks/voice/vip/start", {"CallSid": "CA1"}
    assert bridge.verify(url, form, twilio_signature("mock-secret", url, form)) is False
    # With the VIP desk on, Twilio's own auth token is the key (it was the mock secret before).
    vip = Settings(app_base_url="https://app.useondra.com", feature_vip_desk=True, twilio_auth_token="real-token")
    monkeypatch.setattr(bridge, "get_settings", lambda: vip)
    assert bridge.verify(url, form, twilio_signature("real-token", url, form)) is True
    assert bridge.verify(url, form, twilio_signature("mock-secret", url, form)) is False


# --- 7. Password guessing is throttled -------------------------------------------------------------------------

async def test_repeated_wrong_passwords_are_throttled(client, database):
    email = f"guess-{uuid.uuid4().hex[:6]}@prestigemotors.example"
    try:
        for _ in range(5):
            r = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
            assert r.status_code == 401
        r = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert r.status_code == 429
        # A real account: two misses, then the right password clears its count.
        real = "daniel@prestigemotors.example"
        for _ in range(2):
            assert (await client.post("/auth/login", json={"email": real, "password": "nope-nope"})).status_code == 401
        await login(client, real)
        async with no_tenant_session() as db:
            left = (await db.execute(text("SELECT count(*) FROM login_attempts WHERE email = :e"), {"e": real})).scalar()
        assert left == 0
    finally:
        async with no_tenant_session() as db:
            await db.execute(text("DELETE FROM login_attempts"))
