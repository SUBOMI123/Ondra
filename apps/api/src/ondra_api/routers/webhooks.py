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
from ondra_api.services import bridge, inbound, vip_desk

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("ondra.webhooks")


# Providers' webhooks are small (text, metadata, media links); anything bigger is refused before it's read, since
# these endpoints take requests from anyone until the signature is checked.
MAX_BODY = 1_000_000


async def _read_capped(request: Request) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY:
        raise HTTPException(413, "too large")
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY:
            raise HTTPException(413, "too large")
    return bytes(body)


async def _request(request: Request) -> WebhookRequest:
    body = await _read_capped(request)
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
    # Local development and tests only. On a public site a mock message to a dealer's real number would land in
    # their account and the AI would answer through the real provider, guarded only by one shared secret.
    if channel not in CHANNELS or get_settings().is_public_site:
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
async def bridge_webhook(tenant_id: uuid.UUID, call_id: uuid.UUID, step: Literal["connect", "dialed", "amd", "status"],
                         request: Request) -> Response:
    """Each step of a call-back: the salesperson pressed (or didn't press) 1, the customer's leg ended, or the
    salesperson's leg changed state. Signed like every Twilio webhook; the URL names the dealer and the call."""
    from ondra_core.models import Call, Event

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

        if step in ("dialed", "amd"):
            # The end of the customer's leg and the answering-machine verdict, in whichever order they come.
            if step == "dialed":
                if b.get("dial_status"):  # Twilio retried; already recorded
                    return _twiml(bridge.hang_up())
                seconds = int(f.get("DialCallDuration") or 0)
                b = {**b, "dial_status": f.get("DialCallStatus", ""), "seconds": seconds, "state": "ended"}
                out.duration_s, out.ended_at = seconds, bridge.now()
            else:
                b = {**b, "answered_by": f.get("AnsweredBy") or "unknown"}
            missed = await db.get(Call, uuid.UUID(b["for_call"]))
            before = b.get("result")
            b = await bridge.settle(db, out, missed, b)
            out.outcome = b.get("result")
            out.metrics = {**(out.metrics or {}), "bridge": b}
            if b.get("result") != before:
                db.add(Event(type="call.bridge_result", payload={"call_id": str(out.id), "result": b.get("result"),
                                                                 "answered_by": b.get("answered_by"), "seconds": b.get("seconds")}))
            return _twiml(bridge.hang_up()) if step == "dialed" else Response(status_code=204)

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


@router.post("/voice/vip/start")
async def vip_desk_start(request: Request) -> Response:
    """A VIP's call arriving at the VIP desk (services/vip_desk.py): ring their person. Never the AI."""
    req = await _request(request)
    if not bridge.verify(req.url, req.form, req.headers.get("x-twilio-signature", "")):
        raise HTTPException(403, "bad signature")
    found = vip_desk.parse_target(req.form.get("To", ""))
    if found is None:
        return _twiml(vip_desk.goodbye("Sorry, we couldn't connect your call. Please call again."))
    return await _vip_step(*found, "start", req.form)


@router.post("/voice/vip/{tenant_id}/{call_id}/{step}")
async def vip_desk_step(tenant_id: uuid.UUID, call_id: uuid.UUID, step: Literal["dialed", "choice", "backup"], request: Request) -> Response:
    req = await _request(request)
    if not bridge.verify(req.url, req.form, req.headers.get("x-twilio-signature", "")):
        raise HTTPException(403, "bad signature")
    return await _vip_step(tenant_id, call_id, step, req.form)


async def _vip_step(tenant_id: uuid.UUID, call_id: uuid.UUID, step: str, f) -> Response:
    from ondra_core.models import Call, Contact, Tenant
    from sqlalchemy import select

    from ondra_api.services.calls import finish_call

    base = vip_desk.webhook_base(tenant_id, call_id)
    missed = False
    async with tenant_session(tenant_id) as db:
        call = await db.get(Call, call_id)
        contact = await db.get(Contact, call.contact_id) if call and call.contact_id else None
        if call is None or contact is None or not contact.is_vip:
            return _twiml(vip_desk.goodbye("Sorry, we couldn't connect your call. Please call again."))
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        conf = vip_desk.settings_of(tenant)
        person = await vip_desk.person_for(db, contact)
        backup = bool(conf["backup_number"])
        booking = bool(conf["booking_link"]) and await vip_desk.can_text(db, contact)
        desk = (call.metrics or {}).get("vip_desk") or {}

        if step == "start":
            if person is not None and not desk.get("rang"):
                await vip_desk.note(db, call, rang=str(person.id))
                return _twiml(vip_desk.ring(base, person.phone, call.to_number or ""))
            step, missed = "unanswered", not desk.get("missed")
        elif step == "dialed":
            if f.get("DialCallStatus") == "completed":
                await vip_desk.note(db, call, answered_by="person")
                answered = person.id if person else None
            else:
                step, missed = "unanswered", not desk.get("missed")
        elif step == "choice":
            digit = f.get("Digits", "")
            if digit == "1" and backup:
                await vip_desk.note(db, call, pressed="1")
                return _twiml(vip_desk.ring(base, conf["backup_number"], call.to_number or "", "backup", vip_desk.BACKUP_RING_SECONDS))
            if digit == "2" and booking:
                m = await vip_desk.send_booking_link(db, tenant, contact, conf["booking_link"])
                await vip_desk.note(db, call, pressed="2", booking_text=str(m.id))
                return _twiml(vip_desk.goodbye("We've sent you a text with the link. Goodbye."))
            await vip_desk.note(db, call, pressed=digit or None)
            return _twiml(vip_desk.goodbye())
        else:  # backup
            await vip_desk.note(db, call, backup=f.get("DialCallStatus", ""))
            return _twiml(vip_desk.goodbye("Goodbye.") if f.get("DialCallStatus") != "completed" else vip_desk.goodbye(""))

        if step == "unanswered":
            if missed:
                await vip_desk.note(db, call, missed=True)
            text = vip_desk.message(tenant, contact, person, backup=backup, booking=booking)
    if step == "dialed":  # answered by their person
        await finish_call(tenant_id, call_id, handled_by="owner", outcome="answered", transferred_to_user_id=answered)
        return _twiml(vip_desk.goodbye(""))
    if missed:  # their person is alerted now and gets a high-priority call-back task
        await finish_call(tenant_id, call_id, handled_by="missed", outcome="vip not answered")
    return _twiml(vip_desk.offer(base, text, backup or booking))
