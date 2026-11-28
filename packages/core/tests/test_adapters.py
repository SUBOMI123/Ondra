import base64
import hashlib
import hmac
import json

import pytest
from ondra_core.channels.base import InboundMessage, SignatureError, StatusUpdate, WebhookRequest
from ondra_core.channels.identity import normalize_email, normalize_phone
from ondra_core.channels.postmark import PostmarkAdapter
from ondra_core.channels.twilio_sms import TwilioSmsAdapter, twilio_signature
from ondra_core.channels.whatsapp import WhatsAppCloudAdapter


def req(body=b"", headers=None, form=None, url="https://api.example/webhooks", query=None):
    return WebhookRequest("POST", url, headers or {}, query or {}, body, form or {})


def test_normalize():
    assert normalize_phone("(214) 555-0101") == "+12145550101"
    assert normalize_phone("16505551234") == "+16505551234"
    assert normalize_phone("whatsapp:+447700900123") == "+447700900123"
    assert normalize_email('"Sarah King" <Sarah.King@Example.com>') == "sarah.king@example.com"


def test_twilio_signature_matches_docs_example():
    # The worked example in Twilio's "Webhooks security" docs.
    params = {"CallSid": "CA1234567890ABCDE", "Caller": "+14158675310", "Digits": "1234",
              "From": "+14158675310", "To": "+18005551212"}
    assert twilio_signature("12345", "https://example.com/myapp.php?foo=1&bar=2", params) == "L/OH5YylLD5NRKLltdqwSvS0BnU="


def test_twilio_parse_and_verify():
    a = TwilioSmsAdapter(account_sid="AC1", auth_token="tok")
    form = {"MessageSid": "SM1", "From": "+12145550101", "To": "+12145550100", "Body": "hi", "NumMedia": "0"}
    url = "https://api.example/webhooks/twilio/sms"
    good = req(form=form, url=url, headers={"x-twilio-signature": twilio_signature("tok", url, form)})
    a.verify_signature(good)
    with pytest.raises(SignatureError):
        a.verify_signature(req(form=form | {"Body": "tampered"}, url=url, headers=good.headers))
    [m] = a.parse_webhook(good)
    assert isinstance(m, InboundMessage) and m.provider_message_id == "SM1" and m.body == "hi"


WA_EXAMPLE = {  # Meta's documented inbound text example
    "object": "whatsapp_business_account",
    "entry": [{"id": "102290129340398", "changes": [{"value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550783881", "phone_number_id": "106540352242922"},
        "contacts": [{"profile": {"name": "Sheena Nelson"}, "wa_id": "16505551234", "user_id": "US.1349"}],
        "messages": [{"from": "16505551234", "from_user_id": "US.1349", "id": "wamid.HBgL", "timestamp": "1749416383",
                      "type": "text", "text": {"body": "Does it come in another color?"}}],
        "statuses": [{"id": "wamid.OUT", "status": "delivered", "timestamp": "1750263773"}],
    }, "field": "messages"}]}],
}


def test_whatsapp_parse_verify_and_handshake():
    a = WhatsAppCloudAdapter(access_token="t", app_secret="sec", verify_token="vt", phone_number_id="1065")
    body = json.dumps(WA_EXAMPLE).encode()
    sig = "sha256=" + hmac.new(b"sec", body, hashlib.sha256).hexdigest()
    r = req(body, {"x-hub-signature-256": sig})
    a.verify_signature(r)
    with pytest.raises(SignatureError):
        a.verify_signature(req(body + b" ", {"x-hub-signature-256": sig}))
    msg, status = a.parse_webhook(r)
    assert msg.from_address == "+16505551234" and msg.to_address == "+15550783881"
    assert msg.sender_name == "Sheena Nelson" and msg.body.startswith("Does it")
    assert isinstance(status, StatusUpdate) and status.status == "delivered"
    assert a.verify_subscription({"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"}) == "42"
    assert a.verify_subscription({"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"}) is None


def test_postmark_parse_and_basic_auth():
    a = PostmarkAdapter(server_token="s", webhook_user="u", webhook_password="p")
    body = json.dumps({
        "From": "sarah@example.com", "FromName": "Sarah King", "FromFull": {"Email": "Sarah@Example.com"},
        "To": "sales@prestige-motors.example", "OriginalRecipient": "sales@prestige-motors.example",
        "Subject": "Highlander", "MessageID": "883953f4", "TextBody": "Is it available?\n\n> quoted",
        "StrippedTextReply": "Is it available?", "Headers": [{"Name": "Message-ID", "Value": "<abc@mail>"}],
    }).encode()
    auth = "Basic " + base64.b64encode(b"u:p").decode()
    a.verify_signature(req(body, {"authorization": auth}))
    with pytest.raises(SignatureError):
        a.verify_signature(req(body, {"authorization": "Basic " + base64.b64encode(b"u:x").decode()}))
    [m] = a.parse_webhook(req(body))
    assert m.from_address == "sarah@example.com" and m.body == "Is it available?" and m.in_reply_to == "<abc@mail>"


def test_whatsapp_sends_a_template_buttons_or_text_in_metas_documented_shape():
    from ondra_core.channels.base import OutboundMessage

    base = {"channel": "whatsapp", "to_address": "+12145550100", "from_address": "+12145550199", "body": "Good morning Sam."}
    tpl = WhatsAppCloudAdapter.content(OutboundMessage(**base, template={"name": "ondra_morning_briefing", "language": "en_US", "params": ["Sam", 3]}))
    assert tpl == {"type": "template", "template": {"name": "ondra_morning_briefing", "language": {"code": "en_US"}, "components": [
        {"type": "body", "parameters": [{"type": "text", "text": "Sam"}, {"type": "text", "text": "3"}]}]}}
    buttons = [{"id": "approve:1", "title": "Approve"}, {"id": "skip:1", "title": "A title that is far too long"}, {"id": "c", "title": "C"}, {"id": "d", "title": "D"}]
    inter = WhatsAppCloudAdapter.content(OutboundMessage(**base, buttons=buttons))["interactive"]
    assert inter["type"] == "button" and inter["body"] == {"text": "Good morning Sam."}
    assert [b["reply"] for b in inter["action"]["buttons"]] == [{"id": "approve:1", "title": "Approve"},
                                                               {"id": "skip:1", "title": "A title that is far "}, {"id": "c", "title": "C"}]  # 3 at most, 20 chars
    assert WhatsAppCloudAdapter.content(OutboundMessage(**base))["type"] == "text"


def test_whatsapp_parses_voice_notes_and_button_taps():
    a = WhatsAppCloudAdapter(access_token="t", app_secret="sec", verify_token="vt", phone_number_id="1065")

    def msg(extra: dict) -> bytes:
        return json.dumps({"entry": [{"changes": [{"value": {"metadata": {"display_phone_number": "12145550199"}, "messages": [
            {"from": "12145550100", "id": "wamid.X", "timestamp": "1714510003", **extra}]}}]}]}).encode()

    def parse(extra: dict):
        from ondra_core.channels.base import WebhookRequest

        [ev] = a.parse_webhook(WebhookRequest("POST", "https://x", {}, {}, msg(extra), {}))
        return ev

    voice = parse({"type": "audio", "audio": {"mime_type": "audio/ogg; codecs=opus", "sha256": "h", "id": "MEDIA1", "voice": True}})
    assert voice.body == "" and voice.attachments == [{"type": "audio", "raw": {"mime_type": "audio/ogg; codecs=opus", "sha256": "h", "id": "MEDIA1", "voice": True}}]
    tap = parse({"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "approve:1", "title": "Approve"}}})
    assert tap.attachments[0]["raw"]["button_reply"]["id"] == "approve:1"
    quick = parse({"type": "button", "button": {"payload": "approve:1", "text": "Approve"}})
    assert quick.attachments == [{"type": "button", "raw": {"payload": "approve:1", "text": "Approve"}}]


async def test_whatsapp_fetches_media_in_two_requests_and_refuses_oversize():
    import httpx

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers.get("authorization")))
        if request.url.path.endswith("/MEDIA1"):
            return httpx.Response(200, json={"url": "https://lookaside.example/file", "mime_type": "audio/ogg; codecs=opus", "file_size": "5"})
        if request.url.path.endswith("/BIG"):
            return httpx.Response(200, json={"url": "https://lookaside.example/big", "mime_type": "audio/ogg", "file_size": str(17 * 1024 * 1024)})
        return httpx.Response(200, content=b"OggS!")

    a = WhatsAppCloudAdapter(access_token="tok", app_secret="s", verify_token="v", phone_number_id="1065",
                             client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await a.fetch_media("MEDIA1") == (b"OggS!", "audio/ogg; codecs=opus")
    assert [h for _, h in seen] == ["Bearer tok", "Bearer tok"] and seen[1][0] == "https://lookaside.example/file"
    with pytest.raises(ValueError, match="16 MB"):
        await a.fetch_media("BIG")
