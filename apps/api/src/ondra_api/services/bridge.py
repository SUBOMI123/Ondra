"""Calling a missed caller back through the dealership's line (a "bridge" call).

The salesperson taps "Call through Ondra". Ondra rings *their* phone first; when they pick up and press 1, it dials
the customer and joins the two. The customer sees the number they originally rang, never the salesperson's own.
Every leg is logged, and the result counts as the call-back (Today's time to call back) without anyone ticking it.

    leg 1  POST Calls.json  To=salesperson, From=dealer number, Twiml=<Gather numDigits=1> "press 1 to call Carmen"
           (press 1, so a call that lands in the salesperson's own voicemail never dials the customer into it)
    press  /connect: Digits=1 -> <Dial callerId=dealer number action=/dialed timeout=30><Number>customer</Number>
    amd    /amd: Twilio's answering-machine detection on the customer's leg says who picked up: human, machine, fax
    end    /dialed: how the customer's leg ended. With both, settle() decides:
           a person picked up -> spoke to them (marked called back, task finished);
           their voicemail picked up -> a try (they stay on the list);
           no verdict (detection timed out or never came) -> 60 s or more connected = spoke, shorter = a short call;
           busy / no-answer / failed -> a try that didn't connect.
           The verdict and the end can arrive in either order; a late verdict corrects the result already recorded.
    leg 1  /status: the salesperson didn't pick up, or hung up before pressing 1 -> nothing is recorded as a try

Checked against Twilio's docs on 2026-11-27 (voice/api/call-resource, voice/twiml/dial, voice/twiml/gather):
- POST /2010-04-01/Accounts/{AccountSid}/Calls.json, form-encoded: To, From ("a Twilio number or a Verified outgoing
  caller id for your account"), Twiml (inline, max 4000 characters; ignored if Url is also sent), StatusCallback,
  StatusCallbackEvent (initiated, ringing, answered, completed; one parameter per event), Timeout (default 60, max
  600; Twilio adds ~5 s). Call status values: queued, ringing, in-progress, canceled, completed, busy, no-answer, failed.
- <Dial> callerId: "Any incoming phone number you have purchased from Twilio. Any phone number you have verified with
  Twilio." timeout default 30 (5 to 600). The action URL gets DialCallStatus (completed, answered, busy, no-answer,
  failed, canceled), DialCallSid, DialCallDuration, DialBridged.
- <Gather> numDigits, timeout (default 5), action; the action request carries Digits. On timeout with no input it
  continues to the next verb.
- Webhook signature: same scheme as SMS (ondra_core.channels.twilio_sms.twilio_signature).
- voice/twiml/number + voice/answering-machine-detection: <Number> takes machineDetection (Enable | DetectMessageEnd),
  machineDetectionTimeout (3 to 60, default 30) and amdStatusCallback; AnsweredBy is human, machine_start, fax or
  unknown with Enable. "Enable" returns as soon as the called party is identified (we don't leave messages).
TODO(verify) on the first real call: whether <Number> detection holds the bridge until it decides (the page doesn't
say; the timeout is kept at 5 s so the worst case is a short pause), and that the amdStatusCallback request carries
CallSid and AnsweredBy as the API's AsyncAmdStatusCallback does.
TODO(verify): verifying a dealer's own (non-Twilio) number as an outgoing caller ID is done once at onboarding in the
Twilio console or its OutgoingCallerIds API; the API flow wasn't on the page fetched, so it isn't automated here.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol
from xml.sax.saxutils import escape, quoteattr

import httpx
from ondra_core.channels.twilio_sms import twilio_signature

from ondra_api.config import get_settings

log = logging.getLogger("ondra.bridge")

SPOKE_SECONDS = 60  # a connected call this long was a conversation; shorter is most likely their voicemail
RING_YOU_SECONDS = 25  # how long Ondra rings the salesperson before giving up
RING_THEM_SECONDS = 30  # how long the customer's phone rings
AMD_TIMEOUT_SECONDS = 5  # answering-machine detection gives up after this and says "unknown"


class BridgeError(Exception):
    """The call couldn't be placed; the message says why in words a salesperson understands."""


@dataclass
class PlacedCall:
    to: str
    from_: str
    twiml: str
    status_callback: str
    sid: str


class Dialer(Protocol):
    provider: str
    auth_token: str

    async def place(self, *, to: str, from_: str, twiml: str, status_callback: str) -> str: ...


class TwilioDialer:
    provider = "twilio"

    def __init__(self, *, account_sid: str, auth_token: str, base_url: str = "https://api.twilio.com",
                 client: httpx.AsyncClient | None = None) -> None:
        self.account_sid, self.auth_token, self.base_url, self._client = account_sid, auth_token, base_url.rstrip("/"), client

    async def place(self, *, to: str, from_: str, twiml: str, status_callback: str) -> str:
        # StatusCallbackEvent repeats, one parameter per event; httpx encodes a list value that way.
        data = {"To": to, "From": from_, "Twiml": twiml, "StatusCallback": status_callback,
                "StatusCallbackEvent": ["answered", "completed"], "Timeout": str(RING_YOU_SECONDS)}
        client = self._client or httpx.AsyncClient(timeout=15)
        try:
            r = await client.post(f"{self.base_url}/2010-04-01/Accounts/{self.account_sid}/Calls.json", data=data,
                                  auth=(self.account_sid, self.auth_token))
        finally:
            if self._client is None:
                await client.aclose()
        if r.status_code >= 400:
            log.warning("twilio call create failed: %s %s", r.status_code, r.text[:300])
            raise BridgeError("The phone line didn't accept the call. Try again, or call from your phone.")
        return r.json()["sid"]


@dataclass
class MockDialer:
    """Records the calls it's asked to place. With `autoplay`, it then plays a call out against our own webhooks (the
    salesperson answers and presses 1; detection reports `answered_by`; the call lasts 95 s), so the whole flow can be
    seen locally."""

    auth_token: str
    autoplay: bool = False
    answered_by: str = "human"
    provider: str = "mock"
    placed: list[PlacedCall] = field(default_factory=list)

    async def place(self, *, to: str, from_: str, twiml: str, status_callback: str) -> str:
        sid = f"CAmock{uuid.uuid4().hex[:26]}"
        self.placed.append(PlacedCall(to, from_, twiml, status_callback, sid))
        if self.autoplay:
            asyncio.get_running_loop().create_task(self._play(status_callback.rsplit("/", 1)[0], sid))
        return sid

    async def _play(self, base: str, sid: str) -> None:
        steps = [("status", {"CallSid": sid, "CallStatus": "in-progress"}), ("connect", {"CallSid": sid, "Digits": "1"}),
                 ("amd", {"CallSid": f"{sid}x", "AnsweredBy": self.answered_by, "MachineDetectionDuration": "1800"}),
                 ("dialed", {"CallSid": sid, "DialCallStatus": "completed", "DialCallDuration": "95", "DialCallSid": f"{sid}x"}),
                 ("status", {"CallSid": sid, "CallStatus": "completed", "CallDuration": "110"})]
        async with httpx.AsyncClient(timeout=10) as client:
            for step, form in steps:
                await asyncio.sleep(1.5)
                url = f"{base}/{step}"
                try:
                    await client.post(url, data=form, headers={"X-Twilio-Signature": twilio_signature(self.auth_token, url, form)})
                except httpx.HTTPError:
                    log.exception("mock bridge step %s failed", step)
                    return


@lru_cache
def dialer() -> Dialer:
    s = get_settings()
    if s.feature_call_bridge:
        return TwilioDialer(account_sid=s.twilio_account_sid, auth_token=s.twilio_auth_token)
    return MockDialer(auth_token=s.mock_webhook_secret, autoplay=s.mock_bridge_autoplay, answered_by=s.mock_bridge_answered_by)


def verify(url: str, form: dict[str, str], signature: str) -> bool:
    expected = twilio_signature(dialer().auth_token, url, form)
    return bool(signature) and hmac.compare_digest(signature, expected)


def webhook_base(tenant_id: uuid.UUID, call_id: uuid.UUID) -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/webhooks/voice/bridge/{tenant_id}/{call_id}"


# --- TwiML --------------------------------------------------------------------------------------------------------

def _say(text: str) -> str:
    return f"<Say>{escape(text)}</Say>"


def ask_to_connect(base: str, customer: str) -> str:
    """What the salesperson hears on picking up. Nothing pressed: goodbye, and the customer is never dialed."""
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather numDigits="1" timeout="8" action={quoteattr(base + "/connect")}>'
            f"{_say(f'Call back {customer} from Ondra. Press 1 to connect.')}</Gather>"
            f"{_say('Nothing was pressed, so nobody was called. Goodbye.')}</Response>")


def dial_customer(base: str, caller_id: str, number: str) -> str:
    """Dial them, and find out whether a person or their voicemail picked up (reported to /amd)."""
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Dial callerId={quoteattr(caller_id)} timeout="{RING_THEM_SECONDS}" action={quoteattr(base + "/dialed")}>'
            f'<Number machineDetection="Enable" machineDetectionTimeout="{AMD_TIMEOUT_SECONDS}" '
            f'amdStatusCallback={quoteattr(base + "/amd")}>{escape(number)}</Number></Dial></Response>')


def hang_up(text: str | None = None) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{_say(text) if text else ""}<Hangup/></Response>'


def result_of(dial_status: str, seconds: int, answered_by: str | None = None) -> str:
    """spoke | voicemail | short (no verdict, under a minute: probably voicemail) | no_answer"""
    if dial_status not in ("completed", "answered"):
        return "no_answer"
    if answered_by == "human":
        return "spoke"
    if answered_by and (answered_by.startswith("machine") or answered_by == "fax"):
        return "voicemail"
    return "spoke" if seconds >= SPOKE_SECONDS else "short"


async def settle(db, out, missed, b: dict) -> dict:
    """Record what a call-back came to, from what's known so far (the end of the call, and detection's verdict if it
    has come). Safe to call again as either arrives: it moves the missed call from one outcome to another (marked
    called back, or a try that didn't reach them) and keeps Today's first try in step. Returns the new bridge state."""
    from ondra_core.models import Event

    from ondra_api.services.calls import first_try, mark_called_back, reopen_called_back, waiting_calls

    if not b.get("dial_status"):  # the verdict came first; wait for the end of the call
        return b
    new = result_of(b["dial_status"], int(b.get("seconds") or 0), b.get("answered_by"))
    old = b.get("result")
    if new == old:
        return b
    b = {**b, "result": new}
    by = uuid.UUID(b["user_id"])
    if missed is None:
        return b

    async def retag_try(result: str) -> None:
        if b.get("first_try"):
            e = await db.get(Event, uuid.UUID(b["first_try"]))
            if e is not None:
                e.payload = {**e.payload, "result": result, "undone": False}

    def note_try(how: str) -> None:
        tries = [a for a in (missed.metrics or {}).get("callback_attempts", []) if a.get("bridge") != str(out.id)]
        tries.append({"by": str(by), "at": now().isoformat(), "how": how, "seconds": b.get("seconds"), "bridge": str(out.id)})
        missed.metrics = {**(missed.metrics or {}), "callback_attempts": tries}

    if new == "spoke":
        if missed.callback_done_at is None:
            stamp = await mark_called_back(db, missed, by)
            b["marked"] = True
            b["first_try"] = b.get("first_try") or stamp.get("first_try")
            await retag_try("reached")
        note_try("spoke")
    else:
        if old == "spoke" and b.get("marked"):
            # A late verdict: it was their voicemail after all. Back on the list; the try still counts.
            await reopen_called_back(db, missed, try_was=new)
            b["marked"] = False
        elif missed.callback_done_at is None and not b.get("first_try"):
            e = await first_try(db, await waiting_calls(db, missed), by, new)
            if e is not None:
                b["first_try"] = str(e.id)
        await retag_try(new)
        note_try(new)
    return b


def now() -> datetime:
    return datetime.now(UTC)
