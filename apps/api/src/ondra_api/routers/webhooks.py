"""Provider webhooks. Each one checks the request is authentic, parses it into normalised events, stores each
message once, and answers fast; the AI turn runs after the response (providers retry slow webhooks).

    POST /webhooks/mock/{channel}        local development and tests (no accounts needed)
    GET  /webhooks/whatsapp              Meta's subscription handshake
    POST /webhooks/whatsapp              WhatsApp Cloud API (FEATURE_WHATSAPP)
    POST /webhooks/twilio/sms            Twilio Messaging (FEATURE_SMS)
    POST /webhooks/postmark/inbound      Postmark inbound email (FEATURE_EMAIL)
    POST /webhooks/voice/bridge/{tenant}/{call}/{step}
                                         a call-back through the dealer's line (services/bridge.py): Twilio, or the mock
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request, Response
from ondra_core.channels.base import (
    ChannelAdapter,
    InboundMessage,
    SignatureError,
    StatusUpdate,
    WebhookRequest,
)

from ondra_api.channels import CHANNELS, mock, real
from ondra_api.config import get_settings
from ondra_api.db import tenant_session
from ondra_api.services import bridge, inbound

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


async def _process(adapter: ChannelAdapter, req: WebhookRequest) -> dict:
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
        inline = get_settings().agent_inline
        # Normally the AI turn is queued as a durable job in the same transaction (the worker runs it). Inline mode
        # runs it before answering, for local debugging and tests.
        res = await inbound.ingest(ev, queue_agent=not inline)
        if res.status == "duplicate":
            duplicates += 1
            continue
        stored += res.status == "stored"
        if res.run_ai and inline:
            await inbound.run_agent(res.tenant_id, res.conversation_id, res.message_id, res.draft)
    return {"stored": stored, "duplicates": duplicates}


@router.post("/mock/{channel}")
async def mock_webhook(channel: str, request: Request) -> dict:
    if channel not in CHANNELS:
        raise HTTPException(404)
    return await _process(mock(channel), await _request(request))


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
async def whatsapp_webhook(request: Request) -> dict:
    return await _process(_enabled("whatsapp"), await _request(request))


@router.post("/twilio/sms")
async def twilio_webhook(request: Request) -> Response:
    await _process(_enabled("sms"), await _request(request))
    # Twilio expects TwiML. An empty response means "don't reply here"; replies go out through the REST API.
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="text/xml")


@router.post("/postmark/inbound")
async def postmark_webhook(request: Request) -> dict:
    return await _process(_enabled("email"), await _request(request))


def _twiml(body: str) -> Response:
    return Response(body, media_type="text/xml")


@router.post("/voice/bridge/{tenant_id}/{call_id}/{step}")
async def bridge_webhook(tenant_id: uuid.UUID, call_id: uuid.UUID, step: Literal["connect", "dialed", "status"],
                         request: Request) -> Response:
    """Each step of a call-back: the salesperson pressed (or didn't press) 1, the customer's leg ended, or the
    salesperson's leg changed state. Signed like every Twilio webhook; the URL names the dealer and the call."""
    from ondra_core.models import Call, Event

    from ondra_api.services.calls import first_try, mark_called_back, waiting_calls

    req = await _request(request)
    if not bridge.verify(req.url, req.form, req.headers.get("x-twilio-signature", "")):
        raise HTTPException(403, "bad signature")
    f = req.form
    async with tenant_session(tenant_id) as db:
        out = await db.get(Call, call_id)
        b = dict(((out.metrics or {}).get("bridge") or {}) if out else {})
        if out is None or out.direction != "outbound" or not b:
            return _twiml(bridge.hang_up())

        def save(**changes) -> None:
            out.metrics = {**(out.metrics or {}), "bridge": {**b, **changes}}

        if step == "connect":
            if f.get("Digits") != "1":
                save(state="not_connected")
                return _twiml(bridge.hang_up("Nobody was called. Goodbye."))
            save(state="dialing_them")
            return _twiml(bridge.dial_customer(bridge.webhook_base(tenant_id, call_id), out.from_number, out.to_number))

        if step == "dialed":
            if b.get("result"):  # Twilio retried; already recorded
                return _twiml(bridge.hang_up())
            seconds = int(f.get("DialCallDuration") or 0)
            result = bridge.result_of(f.get("DialCallStatus", ""), seconds)
            out.duration_s, out.ended_at, out.outcome = seconds, bridge.now(), result
            save(state="ended", result=result, dial_status=f.get("DialCallStatus"))
            missed = await db.get(Call, uuid.UUID(b["for_call"]))
            by = uuid.UUID(b["user_id"])
            if missed is not None and missed.callback_done_at is None:
                if result == "spoke":
                    # They talked: the call-back is done, the task finished, and it counts on Today, untouched.
                    await mark_called_back(db, missed, by)
                else:
                    # A try that didn't reach them (or only their voicemail): noted, and they stay on the list.
                    await first_try(db, await waiting_calls(db, missed), by, result)
                    attempt = {"by": str(by), "at": bridge.now().isoformat(), "how": result, "seconds": seconds}
                    missed.metrics = {**(missed.metrics or {}),
                                      "callback_attempts": [*(missed.metrics or {}).get("callback_attempts", []), attempt]}
            db.add(Event(type="call.bridge_ended", payload={"call_id": str(out.id), "result": result, "seconds": seconds}))
            return _twiml(bridge.hang_up())

        # status: the salesperson's own leg
        status = f.get("CallStatus", "")
        if status == "in-progress" and b.get("state") == "ringing_you":
            save(state="asked")
        elif status in ("no-answer", "busy", "failed", "canceled") or (status == "completed" and b.get("state") in ("ringing_you", "asked")):
            out.ended_at = out.ended_at or bridge.now()
            if b.get("state") in ("ringing_you", "asked", "dialing_them"):
                save(state="you_missed" if status != "completed" else "not_connected")
        elif status == "completed":
            out.ended_at = out.ended_at or bridge.now()
        return Response(status_code=204)
