"""WhatsApp Cloud API adapter (Meta). Behind the WHATSAPP_ENABLED flag; the mock adapter is used otherwise.

Checked against Meta's docs on 2026-11-26:
- webhooks/getting-started: GET verification with hub.mode / hub.verify_token / hub.challenge; POST payloads signed
  in `X-Hub-Signature-256: sha256=<sig>` "using the payload and your app's App Secret"; retries for up to 36h, so
  deduplicate.
- messages webhook reference: entry[].changes[].value.{metadata, contacts, messages, statuses}.
- messages/text-messages: POST https://graph.facebook.com/<version>/<phone_number_id>/messages, Bearer token,
  response id at messages[0].id, body max 4096 chars.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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

MAX_BODY = 4096


class WhatsAppCloudAdapter:
    provider = "whatsapp_cloud"
    channel = "whatsapp"

    def __init__(self, *, access_token: str, app_secret: str, verify_token: str, phone_number_id: str,
                 api_version: str = "v27.0", base_url: str = "https://graph.facebook.com",
                 client: httpx.AsyncClient | None = None) -> None:
        self.access_token = access_token
        self.app_secret = app_secret
        self.verify_token = verify_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self.base_url = base_url.rstrip("/")
        self._client = client

    # GET handshake when the webhook is registered in the Meta app dashboard.
    def verify_subscription(self, query: dict[str, str]) -> str | None:
        if query.get("hub.mode") == "subscribe" and hmac.compare_digest(
            query.get("hub.verify_token", ""), self.verify_token
        ):
            return query.get("hub.challenge", "")
        return None

    def verify_signature(self, request: WebhookRequest) -> None:
        header = request.headers.get("x-hub-signature-256", "")
        if not header.startswith("sha256="):
            raise SignatureError("missing X-Hub-Signature-256")
        # TODO(verify): the docs say "SHA256 signature using the payload and your app's App Secret" without naming
        # HMAC or hex; HMAC-SHA256 over the raw body, hex-encoded, is the documented sample apps' behaviour.
        expected = hmac.new(self.app_secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, header[7:]):
            raise SignatureError("bad X-Hub-Signature-256")

    def parse_webhook(self, request: WebhookRequest) -> list[InboundEvent]:
        data = json.loads(request.body or b"{}")
        events: list[InboundEvent] = []
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                to = value.get("metadata", {}).get("display_phone_number", "")
                names = {}
                for c in value.get("contacts", []):
                    key = c.get("wa_id") or c.get("user_id")
                    names[key] = (c.get("profile") or {}).get("name")
                for m in value.get("messages", []):
                    # Users with a WhatsApp username may have no phone number; then only the BSUID is sent.
                    # TODO(verify): store the BSUID as its own identity kind when contact_identities supports it.
                    sender = m.get("from") or m.get("from_user_id", "")
                    from_addr = normalize_phone(sender) if m.get("from") else sender
                    body = (m.get("text") or {}).get("body", "") if m.get("type") == "text" else ""
                    attachments = [] if m.get("type") == "text" else [{"type": m.get("type"), "raw": m.get(m.get("type", ""), {})}]
                    events.append(InboundMessage(
                        channel=self.channel,
                        provider=self.provider,
                        provider_message_id=m["id"],
                        from_address=from_addr,
                        to_address=normalize_phone(to) if to else "",
                        body=body,
                        received_at=datetime.fromtimestamp(int(m.get("timestamp", "0")), UTC),
                        sender_name=names.get(m.get("from")) or names.get(m.get("from_user_id")),
                        attachments=attachments,
                    ))
                for s in value.get("statuses", []):
                    events.append(StatusUpdate(self.provider, s["id"], s.get("status", "")))
        return events

    async def send(self, message: OutboundMessage) -> ProviderResult:
        url = f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.to_address,
            "type": "text",
            "text": {"preview_url": False, "body": message.body[:MAX_BODY]},
        }
        client = self._client or httpx.AsyncClient(timeout=10)
        try:
            r = await client.post(url, json=payload, headers={"Authorization": f"Bearer {self.access_token}"})
        except httpx.HTTPError as exc:
            return ProviderResult(ok=False, error=f"network: {type(exc).__name__}")
        finally:
            if self._client is None:
                await client.aclose()
        if r.status_code >= 400:
            return ProviderResult(ok=False, error=f"http {r.status_code}: {r.text[:300]}")
        return ProviderResult(ok=True, provider_message_id=r.json()["messages"][0]["id"])

    def supports(self, feature: Feature) -> bool:
        return feature in {Feature.TEXT, Feature.MEDIA, Feature.TEMPLATES, Feature.SERVICE_WINDOW, Feature.DELIVERY_STATUS}
