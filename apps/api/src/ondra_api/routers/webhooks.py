"""Provider webhooks. Each one checks the request is authentic, parses it into normalised events, stores each
message once, and answers fast; the AI turn runs after the response (providers retry slow webhooks).

    POST /webhooks/mock/{channel}        local development and tests (no accounts needed)
    GET  /webhooks/whatsapp              Meta's subscription handshake
    POST /webhooks/whatsapp              WhatsApp Cloud API (FEATURE_WHATSAPP)
    POST /webhooks/twilio/sms            Twilio Messaging (FEATURE_SMS)
    POST /webhooks/postmark/inbound      Postmark inbound email (FEATURE_EMAIL)
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from ondra_core.channels.base import (
    ChannelAdapter,
    InboundMessage,
    SignatureError,
    StatusUpdate,
    WebhookRequest,
)

from ondra_api.channels import CHANNELS, mock, real
from ondra_api.config import get_settings
from ondra_api.services import inbound

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("ondra.webhooks")


async def _request(request: Request) -> WebhookRequest:
    body = await request.body()
    form = {}
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        form = dict(parse_qsl(body.decode(), keep_blank_values=True))
    # The URL as the provider called it (behind a proxy, request.url is the internal one).
    url = get_settings().public_api_url.rstrip("/") + request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return WebhookRequest(request.method, url, {k.lower(): v for k, v in request.headers.items()},
                          dict(request.query_params), body, form)


async def _process(adapter: ChannelAdapter, req: WebhookRequest, background: BackgroundTasks) -> dict:
    try:
        adapter.verify_signature(req)
    except SignatureError as exc:
        log.warning("rejected %s webhook: %s", adapter.provider, exc)
        raise HTTPException(403, "invalid signature") from None
    try:
        events = adapter.parse_webhook(req)
    except (KeyError, ValueError) as exc:
        log.warning("unparseable %s webhook: %s", adapter.provider, exc)
        raise HTTPException(400, "unparseable payload") from None

    stored = duplicates = 0
    for ev in events:
        if isinstance(ev, StatusUpdate):
            await inbound.mark_status(ev)
            continue
        assert isinstance(ev, InboundMessage)
        res = await inbound.ingest(ev)
        if res.status == "duplicate":
            duplicates += 1
            continue
        stored += res.status == "stored"
        if res.run_ai:
            if get_settings().agent_inline:
                await inbound.run_agent(res.tenant_id, res.conversation_id, res.message_id, res.draft)
            else:
                background.add_task(inbound.run_agent, res.tenant_id, res.conversation_id, res.message_id, res.draft)
    return {"stored": stored, "duplicates": duplicates}


@router.post("/mock/{channel}")
async def mock_webhook(channel: str, request: Request, background: BackgroundTasks) -> dict:
    if channel not in CHANNELS:
        raise HTTPException(404)
    return await _process(mock(channel), await _request(request), background)


def _enabled(channel: str) -> ChannelAdapter:
    a = real(channel)
    if a is None:
        raise HTTPException(404, f"{channel} provider is not enabled")
    return a


@router.get("/whatsapp")
async def whatsapp_verify(request: Request) -> Response:
    challenge = _enabled("whatsapp").verify_subscription(dict(request.query_params))  # type: ignore[attr-defined]
    if challenge is None:
        raise HTTPException(403)
    return Response(challenge, media_type="text/plain")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks) -> dict:
    return await _process(_enabled("whatsapp"), await _request(request), background)


@router.post("/twilio/sms")
async def twilio_webhook(request: Request, background: BackgroundTasks) -> Response:
    await _process(_enabled("sms"), await _request(request), background)
    # Twilio expects TwiML. An empty response means "don't reply here"; replies go out through the REST API.
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="text/xml")


@router.post("/postmark/inbound")
async def postmark_webhook(request: Request, background: BackgroundTasks) -> dict:
    return await _process(_enabled("email"), await _request(request), background)
