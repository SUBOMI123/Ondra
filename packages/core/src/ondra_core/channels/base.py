"""The channel adapter interface (BUILD_PLAN.md §8).

Every channel (WhatsApp, SMS, email, and later Instagram) turns a provider webhook into `InboundEvent`s and sends an
`OutboundMessage`. Everything above this layer sees only these types, so a new provider means a new adapter and
nothing else. Each adapter has a mock (`MockAdapter`) so the system runs with no real accounts.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


class Feature(enum.StrEnum):
    TEXT = "text"
    MEDIA = "media"
    TEMPLATES = "templates"  # business-initiated messages need a pre-approved template (WhatsApp)
    SERVICE_WINDOW = "service_window"  # free-form replies only within 24h of the customer's last message
    THREADING = "threading"  # replies can thread (email)
    DELIVERY_STATUS = "delivery_status"


@dataclass(frozen=True)
class WebhookRequest:
    """What an adapter needs from an HTTP request. Built by the API so adapters don't depend on a web framework."""

    method: str
    url: str  # full public URL the provider called, as the provider saw it (needed for Twilio signatures)
    headers: dict[str, str]  # lowercase keys
    query: dict[str, str]
    body: bytes
    form: dict[str, str] = field(default_factory=dict)  # parsed application/x-www-form-urlencoded body, if any


@dataclass(frozen=True)
class InboundMessage:
    """A message from a customer, normalised across channels."""

    channel: str  # whatsapp | sms | email
    provider: str  # whatsapp_cloud | twilio | postmark | mock
    provider_message_id: str  # idempotency key: the same id is never processed twice
    from_address: str  # E.164 phone, or lowercased email
    to_address: str  # the dealer's number/address it was sent to; used to find the tenant
    body: str
    received_at: datetime
    sender_name: str | None = None
    subject: str | None = None
    in_reply_to: str | None = None
    attachments: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class StatusUpdate:
    """Delivery receipt for a message Ondra sent."""

    provider: str
    provider_message_id: str
    status: str  # sent | delivered | read | failed


InboundEvent = InboundMessage | StatusUpdate


@dataclass(frozen=True)
class OutboundMessage:
    channel: str
    to_address: str
    from_address: str
    body: str
    subject: str | None = None
    in_reply_to: str | None = None
    # WhatsApp only. `buttons`: up to three quick replies, [{"id": "approve:<id>", "title": "Approve"}], inside the
    # 24-hour window. `template`: {"name": "...", "language": "en_US", "params": ["...", ...]} for a message that
    # starts a conversation outside it; `body` is then what the template renders to, for our own record.
    buttons: list[dict] | None = None
    template: dict | None = None


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None


class SignatureError(Exception):
    """The webhook didn't come from the provider. The API answers 403 and processes nothing."""


@runtime_checkable
class ChannelAdapter(Protocol):
    provider: str
    channel: str

    def verify_signature(self, request: WebhookRequest) -> None:
        """Raise SignatureError unless the request is authentic."""

    def parse_webhook(self, request: WebhookRequest) -> list[InboundEvent]: ...

    async def send(self, message: OutboundMessage) -> ProviderResult: ...

    def supports(self, feature: Feature) -> bool: ...
