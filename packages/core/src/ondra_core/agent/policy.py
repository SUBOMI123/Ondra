"""The policy layer (BUILD_PLAN.md §6.3). It runs before the AI and after it.

`evaluate_inbound` decides, before any model is called, whether the AI may touch this message at all. The product
rules that must never break live here, as plain code with unit tests, not in a prompt:

- VIP contacts never get an AI reply or draft. A person is alerted instead.
- An opt-out (STOP) blocks every outbound message to that contact on every channel.
- `ai_mode=off` means no AI.

`review_reply` checks what the AI wrote before it can be sent or drafted (see detectors.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# Carrier-standard opt-out and opt-in keywords. A message that is only one of these words is a consent change.
# Matches Twilio's default list (docs: messaging/tutorials/advanced-opt-out, checked 2026-11-26). Twilio replies to these
# itself, so Ondra must never send its own confirmation.
OPT_OUT_KEYWORDS = frozenset({"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "OPTOUT", "REVOKE"})
OPT_IN_KEYWORDS = frozenset({"START", "UNSTOP"})  # Twilio: "YES" does not opt back in
# The carrier-required help keywords. Twilio's messaging service sends the registered HELP reply (Advanced Opt-Out),
# so Ondra stays quiet: an AI answer on top would be a second, unregistered reply.
HELP_KEYWORDS = frozenset({"HELP", "INFO"})

# Plain-language opt-outs that aren't keywords, e.g. "please stop texting me". These opt out too: when a customer
# asks us to stop, we stop, whatever word they used.
_OPT_OUT_PHRASES = re.compile(
    r"\b(stop|quit|don'?t|do not|never)\s+(texting|messaging|contacting|emailing|calling|text|message|contact|email)\s+me\b"
    r"|\bunsubscribe\b|\bremove me from\b|\btake me off\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Alert:
    to: str  # "owner" | a role ("sales", "service", "manager") | "assigned"
    urgency: Literal["low", "normal", "high"]
    reason: str


@dataclass(frozen=True)
class InboundFacts:
    """Everything the pre-policy needs. Built from the database by the API and from fixtures by the eval runner."""

    channel: str
    body: str
    contact_is_vip: bool
    contact_opted_out: bool  # any opt-out on any channel, for any purpose: outbound is blocked everywhere
    conversation_ai_mode: Literal["auto", "draft", "off"]
    tenant_draft_mode: bool


@dataclass(frozen=True)
class InboundDecision:
    run_ai: bool
    reason: str  # machine-readable, stored on the event: "vip", "opted_out", "opt_out_keyword", "ai_off", "ok"
    draft: bool = False  # the AI writes, a person approves before anything is sent
    alert: Alert | None = None
    consent_change: Literal["opted_out_all_channels", "opted_in"] | None = None
    notes: list[str] = field(default_factory=list)


def classify_consent(body: str) -> Literal["opt_out", "opt_in"] | None:
    word = re.sub(r"[^A-Za-z]", "", body).upper()
    if word in OPT_OUT_KEYWORDS:
        return "opt_out"
    if word in OPT_IN_KEYWORDS and body.strip().upper().rstrip(".!") in OPT_IN_KEYWORDS:
        return "opt_in"
    if _OPT_OUT_PHRASES.search(body):
        return "opt_out"
    return None


def evaluate_inbound(f: InboundFacts) -> InboundDecision:
    consent = classify_consent(f.body)

    # 1. Opt-out wins over everything, VIP included: a VIP who texts STOP is opted out too.
    if consent == "opt_out":
        return InboundDecision(False, "opt_out_keyword", consent_change="opted_out_all_channels")

    # 1b. HELP / INFO on its own: the carrier's registered help reply answers it.
    if f.channel == "sms" and f.body.strip().upper().rstrip(".!?") in HELP_KEYWORDS:
        return InboundDecision(False, "help_keyword")

    # 2. Opt back in. Recorded, but the carrier sends the confirmation; Ondra doesn't reply to the keyword itself.
    if consent == "opt_in" and f.contact_opted_out:
        return InboundDecision(False, "opt_in_keyword", consent_change="opted_in")

    # 3. VIP: no AI reply, no draft. The owner (or the VIP's handler) is alerted at once.
    if f.contact_is_vip:
        return InboundDecision(False, "vip", alert=Alert("owner", "high", "VIP message waiting for a personal reply"))

    # 4. Opted out but wrote to us: nothing automated goes out. A person decides how to respond.
    if f.contact_opted_out:
        return InboundDecision(
            False, "opted_out", alert=Alert("sales", "normal", "Opted-out contact wrote in; nothing automated was sent")
        )

    # 5. The dealer turned the AI off for this conversation.
    if f.conversation_ai_mode == "off":
        return InboundDecision(False, "ai_off", alert=Alert("assigned", "normal", "New message; Ondra is off here"))

    draft = f.tenant_draft_mode or f.conversation_ai_mode == "draft"
    return InboundDecision(True, "ok", draft=draft)


def may_send_outbound(*, contact_is_vip: bool, contact_opted_out: bool, author_type: str) -> tuple[bool, str]:
    """The last gate before anything leaves the building. Used by every send path, not just the agent."""
    if contact_opted_out:
        return False, "opted_out"
    if contact_is_vip and author_type == "ai":
        return False, "vip"
    return True, "ok"
