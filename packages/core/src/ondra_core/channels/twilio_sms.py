"""Twilio Programmable Messaging (SMS) adapter. Behind the TWILIO_SMS_ENABLED flag.

Checked against Twilio's docs on 2026-11-26:
- messaging/guides/webhook-request: form params MessageSid, AccountSid, From, To, Body, NumMedia, MediaUrl{N}...;
  "Twilio will occasionally add new parameters", so the signature covers every param received.
- usage/security: X-Twilio-Signature = base64(HMAC-SHA1(auth_token, url + sorted(key+value for POST params))),
  using the exact URL Twilio called.
- messaging/api/message-resource: POST /2010-04-01/Accounts/{AccountSid}/Messages.json with To, From or
  MessagingServiceSid, Body; response `sid`.
- messaging/tutorials/advanced-opt-out: Twilio handles STOP/START itself, replies with the confirmation, and blocks
  later sends (error 21610). The inbound still reaches the webhook, with OptOutType when a Messaging Service is used.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime

import httpx

from ondra_core.channels.base import (
    Feature,
    InboundEvent,
    InboundMessage,
    OutboundMessage,
    ProviderResult,
    SignatureError,
    StatusUpdate,
    WebhookRequest,
)
from ondra_core.channels.identity import normalize_phone


def twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    data = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


class TwilioSmsAdapter:
    provider = "twilio"
    channel = "sms"

    def __init__(self, *, account_sid: str, auth_token: str, messaging_service_sid: str | None = None,
                 base_url: str = "https://api.twilio.com", client: httpx.AsyncClient | None = None) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.messaging_service_sid = messaging_service_sid
        self.base_url = base_url.rstrip("/")
        self._client = client

    def verify_signature(self, request: WebhookRequest) -> None:
        # TODO(verify): accounts that switch to shared signing keys send X-Twilio-Webhooks-Signature-Settings and
        # may use HMAC-SHA256; only the default (auth token, HMAC-SHA1) scheme is implemented.
        if not self.auth_token:
            raise SignatureError("TWILIO_AUTH_TOKEN is not set")  # an empty HMAC key is one anyone can compute
        if "x-twilio-webhooks-signature-settings" in request.headers:
            raise SignatureError("shared-key signing isn't supported yet")
        given = request.headers.get("x-twilio-signature", "")
        expected = twilio_signature(self.auth_token, request.url, request.form)
        if not given or not hmac.compare_digest(given.encode(), expected.encode()):
            raise SignatureError("bad X-Twilio-Signature")

    def parse_webhook(self, request: WebhookRequest) -> list[InboundEvent]:
        f = request.form
        if "MessageStatus" in f and "Body" not in f:  # status callback for a message we sent
            return [StatusUpdate(self.provider, f.get("MessageSid", ""), f["MessageStatus"])]
        media = [
            {"type": f.get(f"MediaContentType{i}"), "url": f.get(f"MediaUrl{i}")}
            for i in range(int(f.get("NumMedia", "0") or 0))
        ]
        return [InboundMessage(
            channel=self.channel,
            provider=self.provider,
            provider_message_id=f["MessageSid"],
            from_address=normalize_phone(f["From"]),
            to_address=normalize_phone(f["To"]),
            body=f.get("Body", ""),
            received_at=datetime.now(UTC),
            attachments=media + ([{"type": "opt_out", "value": f["OptOutType"]}] if f.get("OptOutType") else []),
        )]

    async def send(self, message: OutboundMessage) -> ProviderResult:
        url = f"{self.base_url}/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        form = {"To": message.to_address, "Body": message.body[:1600]}
        if self.messaging_service_sid:
            form["MessagingServiceSid"] = self.messaging_service_sid
        else:
            form["From"] = message.from_address
        client = self._client or httpx.AsyncClient(timeout=10)
        try:
            # TODO(verify): the docs' examples authenticate with an API key/secret pair; AccountSid:AuthToken basic
            # auth is the long-standing alternative. Swap to an API key before production.
            r = await client.post(url, data=form, auth=(self.account_sid, self.auth_token))
        except httpx.HTTPError as exc:
            return ProviderResult(ok=False, error=f"network: {type(exc).__name__}")
        finally:
            if self._client is None:
                await client.aclose()
        if r.status_code >= 400:
            return ProviderResult(ok=False, error=f"http {r.status_code}: {r.text[:300]}")
        return ProviderResult(ok=True, provider_message_id=r.json()["sid"])

    def supports(self, feature: Feature) -> bool:
        return feature in {Feature.TEXT, Feature.MEDIA, Feature.DELIVERY_STATUS}
