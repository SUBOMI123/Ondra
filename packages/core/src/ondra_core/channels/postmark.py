"""Postmark email adapter (inbound webhook + outbound API). Behind the POSTMARK_ENABLED flag.

Checked against Postmark's docs on 2026-11-26:
- webhooks/inbound-webhook: JSON with From, FromFull, FromName, To, ToFull, Subject, MessageID (Postmark's UUID),
  TextBody, HtmlBody, StrippedTextReply, Headers[{Name,Value}], OriginalRecipient, MailboxHash, Attachments.
- webhooks-overview: "Postmark does not currently support HMAC webhook signature verification"; use HTTP Basic auth
  in the webhook URL over HTTPS. So `verify_signature` checks Basic auth credentials.
- api/email-api: POST https://api.postmarkapp.com/email with X-Postmark-Server-Token; From, To, Subject, TextBody,
  Headers, MessageStream; response MessageID.
"""

from __future__ import annotations

import base64
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
    WebhookRequest,
)
from ondra_core.channels.identity import normalize_email


class PostmarkAdapter:
    provider = "postmark"
    channel = "email"

    def __init__(self, *, server_token: str, webhook_user: str, webhook_password: str,
                 message_stream: str = "outbound", base_url: str = "https://api.postmarkapp.com",
                 client: httpx.AsyncClient | None = None) -> None:
        self.server_token = server_token
        self.webhook_user = webhook_user
        self.webhook_password = webhook_password
        self.message_stream = message_stream
        self.base_url = base_url.rstrip("/")
        self._client = client

    def verify_signature(self, request: WebhookRequest) -> None:
        if not (self.webhook_user and self.webhook_password):
            raise SignatureError("POSTMARK_INBOUND_USER and POSTMARK_INBOUND_PASSWORD are not set")
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("basic "):
            raise SignatureError("missing basic auth")
        try:
            user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
        except ValueError:
            raise SignatureError("bad basic auth") from None
        # Bytes, not str: compare_digest raises on non-ASCII str, which would be a 500 instead of a 403.
        ok_user = hmac.compare_digest(user.encode(), self.webhook_user.encode())
        ok_pw = hmac.compare_digest(pw.encode(), self.webhook_password.encode())
        if not (ok_user and ok_pw):
            raise SignatureError("bad basic auth")

    def parse_webhook(self, request: WebhookRequest) -> list[InboundEvent]:
        d = json.loads(request.body or b"{}")
        headers = {h.get("Name", "").lower(): h.get("Value", "") for h in d.get("Headers", [])}
        to = d.get("OriginalRecipient") or ((d.get("ToFull") or [{}])[0].get("Email", "")) or d.get("To", "")
        # Prefer the reply without the quoted thread; it's only filled for replies (and best effort).
        body = d.get("StrippedTextReply") or d.get("TextBody") or ""
        return [InboundMessage(
            channel=self.channel,
            provider=self.provider,
            provider_message_id=d["MessageID"],
            from_address=normalize_email((d.get("FromFull") or {}).get("Email") or d.get("From", "")),
            to_address=normalize_email(to),
            body=body.strip(),
            received_at=datetime.now(UTC),
            sender_name=d.get("FromName") or None,
            subject=d.get("Subject"),
            in_reply_to=headers.get("message-id"),  # the RFC Message-ID, to thread our reply
            attachments=[{"name": a.get("Name"), "type": a.get("ContentType")} for a in d.get("Attachments", [])],
        )]

    async def send(self, message: OutboundMessage) -> ProviderResult:
        payload: dict = {
            "From": message.from_address,
            "To": message.to_address,
            "Subject": message.subject or "Re: your message",
            "TextBody": message.body,
            "MessageStream": self.message_stream,
        }
        if message.attachments:
            # TODO(verify): Postmark's send API takes Attachments as [{Name, Content (base64), ContentType}]; the docs
            # couldn't be reached from the build machine on 2026-11-28. Check before the first real confirmation.
            payload["Attachments"] = [{"Name": a["name"], "Content": a["content_b64"], "ContentType": a["content_type"]}
                                      for a in message.attachments]
        if message.in_reply_to:
            # TODO(verify): Postmark documents custom Headers but not In-Reply-To/References specifically.
            payload["Headers"] = [
                {"Name": "In-Reply-To", "Value": message.in_reply_to},
                {"Name": "References", "Value": message.in_reply_to},
            ]
        client = self._client or httpx.AsyncClient(timeout=10)
        try:
            r = await client.post(
                f"{self.base_url}/email", json=payload,
                headers={"Accept": "application/json", "X-Postmark-Server-Token": self.server_token},
            )
        except httpx.HTTPError as exc:
            return ProviderResult(ok=False, error=f"network: {type(exc).__name__}")
        finally:
            if self._client is None:
                await client.aclose()
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code >= 400 or body.get("ErrorCode", 0) != 0:
            return ProviderResult(ok=False, error=f"http {r.status_code}: {body.get('Message', r.text[:300])}")
        return ProviderResult(ok=True, provider_message_id=body["MessageID"])

    def supports(self, feature: Feature) -> bool:
        return feature in {Feature.TEXT, Feature.MEDIA, Feature.THREADING}
