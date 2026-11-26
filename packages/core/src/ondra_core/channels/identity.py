"""Normalising customer addresses so the same person is recognised on every channel."""

import re

_NON_DIGITS = re.compile(r"\D")


def normalize_phone(raw: str, default_country_code: str = "1") -> str:
    """Return E.164 (+15551234567). Bare 10-digit numbers get the tenant's default country code (US by default).

    TODO(verify): use a full numbering-plan library (e.g. phonenumbers) once non-US dealers go live; this handles
    US numbers and numbers that already carry a country code.
    """
    raw = raw.strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw[9:]
    digits = _NON_DIGITS.sub("", raw)
    if not digits:
        raise ValueError(f"not a phone number: {raw!r}")
    if raw.startswith(("+", "00")):
        return "+" + (digits[2:] if raw.startswith("00") else digits)
    if len(digits) == 10:
        return f"+{default_country_code}{digits}"
    return "+" + digits  # WhatsApp sends international numbers without the +


def normalize_email(raw: str) -> str:
    raw = raw.strip()
    if "<" in raw and raw.endswith(">"):  # "Sarah King <sarah@example.com>"
        raw = raw[raw.rindex("<") + 1 : -1]
    return raw.strip().lower()


def identity_kind(channel: str) -> str:
    """Which contact_identities.kind a channel's sender address is stored under."""
    return {"sms": "phone", "phone": "phone", "whatsapp": "whatsapp", "email": "email"}[channel]
