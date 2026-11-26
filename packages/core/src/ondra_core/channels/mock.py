"""A mock adapter for any channel, so the whole system runs locally with no provider accounts.

Webhook body (JSON):
    {"id": "m-1", "from": "+12145550101", "to": "+12145550100", "text": "hi", "name": "Sarah", "subject": null}

Signature: header `x-mock-signature` must equal the shared secret (default "mock-secret"). That isn't real
security; it exists so the signature-checking path is exercised in tests the same way as real providers.
Sent messages are kept in `outbox` for tests and the dev UI.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

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
from ondra_core.channels.identity import normalize_email, normalize_phone


class MockAdapter:
    provider = "mock"

    def __init__(self, channel: str, secret: str = "mock-secret") -> None:
        self.channel = channel
        self.secret = secret
        self.outbox: list[OutboundMessage] = []
        self.fail_next = False

    def _addr(self, raw: str) -> str:
        return normalize_email(raw) if self.channel == "email" else normalize_phone(raw)

    def verify_signature(self, request: WebhookRequest) -> None:
        if request.headers.get("x-mock-signature") != self.secret:
            raise SignatureError("bad mock signature")

    def parse_webhook(self, request: WebhookRequest) -> list[InboundEvent]:
        data = json.loads(request.body or b"{}")
        items = data if isinstance(data, list) else [data]
        events: list[InboundEvent] = []
        for item in items:
            if "status" in item:
                events.append(StatusUpdate(self.provider, str(item["id"]), item["status"]))
                continue
            events.append(
                InboundMessage(
                    channel=self.channel,
                    provider=self.provider,
                    provider_message_id=str(item["id"]),
                    from_address=self._addr(item["from"]),
                    to_address=self._addr(item["to"]),
                    body=item.get("text", ""),
                    received_at=datetime.now(UTC),
                    sender_name=item.get("name"),
                    subject=item.get("subject"),
                )
            )
        return events

    async def send(self, message: OutboundMessage) -> ProviderResult:
        if self.fail_next:
            self.fail_next = False
            return ProviderResult(ok=False, error="mock failure")
        self.outbox.append(message)
        return ProviderResult(ok=True, provider_message_id=f"mock-out-{uuid.uuid4().hex[:12]}")

    def supports(self, feature: Feature) -> bool:
        return feature in {Feature.TEXT, Feature.DELIVERY_STATUS} | (
            {Feature.THREADING} if self.channel == "email" else set()
        )
