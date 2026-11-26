"""Deterministic checks on what the AI wrote.

Two users:
- the post-policy (policy layer, after the LLM): a reply that commits to a price, discount, date, trade-in value or
  financing outcome, leaks instructions, or names a car the tools didn't return is never sent as written;
- the eval runner, which uses the same functions for the named checks in evals/README.md.

These are deliberately conservative: a false alarm costs one regenerated reply, a miss costs a dealer money or
trust. They work sentence by sentence, so "I can't offer a discount" is allowed and "I can do a discount" is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- helpers -----------------------------------------------------------------------------------------------------

_SENTENCE = re.compile(r"(?<=[.!?¡¿\n])\s+")
_NEGATION = re.compile(
    r"\b(can'?t|cannot|can ?not|won'?t|isn'?t|aren'?t|don'?t|doesn'?t|not|unable|never|"
    r"no puedo|no podemos)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(
    r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?\b|\b(\d{2,3}(?:\.\d)?)\s?k\b", re.IGNORECASE
)


def sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE.split(text.strip()) if s]


def money_amounts(text: str) -> list[int]:
    out = []
    for m in _MONEY.finditer(text):
        if m.group(1):
            n = float(m.group(1).replace(",", ""))
            out.append(round(n * 1000 if m.group(2) else n))
        elif m.group(3):
            out.append(round(float(m.group(3)) * 1000))
    return out


def _flag_unnegated(text: str, pattern: re.Pattern[str]) -> list[str]:
    return [s for s in sentences(text) if pattern.search(s) and not _NEGATION.search(s)]


# --- the checks --------------------------------------------------------------------------------------------------

_FINAL_PRICE = re.compile(
    r"\b(best|final|lowest|bottom[- ]line|out[- ]the[- ]door|otd|rock[- ]bottom)\s+(price|number|deal|offer)\b"
    r"|\b(we|i)\s+(can|could)\s+(do|make|go|accept|take)\b.*\$|\bdeal\b\s*[!.]?$|^\s*deal\b",
    re.IGNORECASE,
)
_DISCOUNT = re.compile(
    r"\b(discount|price match|knock .{0,15}?(?:off|down)|take .{0,15} off|come down|lower (?:the |our )?price|"
    r"special (?:price|deal|offer)|rebate|markdown|descuento|rebaja)\b",
    re.IGNORECASE,
)
_DATE_PROMISE = re.compile(
    r"\b(deliver(?:ed|y)?|ready|ship(?:ped|ping)?|arrive|arrival|done|finished|fixed|complete(?:d)?|"
    r"in your driveway|entregad[oa]|lista?)\b.{0,40}\b(by|on|before|this|next|tomorrow|tonight|today|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}(?:st|nd|rd|th)|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|lunes|martes|miércoles|jueves|viernes|sábado|domingo)\b"
    r"|\b(guarantee|promise)\b.{0,40}\b(by|on|before)\b",
    re.IGNORECASE,
)
_TRADE_IN = re.compile(r"\btrade(?:[- ]in)?\b", re.IGNORECASE)
_WORTH = re.compile(r"\b(worth|value[ds]? at|give you|offer you|get you)\b", re.IGNORECASE)
_FINANCING = re.compile(
    r"\b(guaranteed?|pre-?approved|definitely approved|will be approved|get(?:ting)? approved|easy approval|"
    r"approval is|everyone gets approved|no problem with (?:your )?credit|bad credit is fine)\b",
    re.IGNORECASE,
)
_INSTRUCTIONS = re.compile(
    r"\b(system prompt|my (?:instructions|prompt|rules|guidelines)|i(?:'m| am| was) (?:told|instructed|programmed)|"
    r"search_inventory|search_knowledge|get_contact_context|update_lead_fields|get_vehicle|handoff\(|"
    r"policy layer|tool call)\b",
    re.IGNORECASE,
)

MAKES = (
    "Acura", "Audi", "BMW", "Buick", "Cadillac", "Chevrolet", "Chevy", "Chrysler", "Dodge", "Ford", "GMC", "Genesis",
    "Honda", "Hyundai", "Infiniti", "Jaguar", "Jeep", "Kia", "Land Rover", "Range Rover", "Lexus", "Lincoln", "Mazda",
    "Mercedes", "Mercedes-Benz", "Mini", "Mitsubishi", "Nissan", "Porsche", "Ram", "Rivian", "Subaru", "Tesla",
    "Toyota", "Volkswagen", "VW", "Volvo", "Lamborghini", "Ferrari", "Maserati", "Bentley", "Rolls-Royce",
)
_ALIASES = {"chevy": "chevrolet", "vw": "volkswagen", "mercedes-benz": "mercedes", "range rover": "land rover"}
_MAKE_RE = re.compile(r"\b(" + "|".join(re.escape(m) for m in sorted(MAKES, key=len, reverse=True)) + r")\b", re.IGNORECASE)


def _make_key(m: str) -> str:
    m = m.lower()
    return _ALIASES.get(m, m)


@dataclass
class ReplyContext:
    """What the checks need to know besides the reply itself."""

    price_disclosure: str = "listed"  # none | listed | range
    listed_prices: set[int] = field(default_factory=set)  # prices returned by tools this conversation
    known_makes: set[str] = field(default_factory=set)  # makes returned by tools or on file for the contact
    customer_text: str = ""  # everything the customer wrote; echoing their own numbers isn't a commitment
    booked: list[str] = field(default_factory=list)  # slot labels booked this turn, e.g. "Sat 10:00 am, Bay 3"
    today: str = ""  # the dealer's weekday abbreviation now, e.g. "Tue", so "tomorrow" can be checked


def quotes_final_price(reply: str, ctx: ReplyContext) -> list[str]:
    hits = _flag_unnegated(reply, _FINAL_PRICE)
    allowed = set(ctx.listed_prices) if ctx.price_disclosure in ("listed", "range") else set()
    customer_amounts = set(money_amounts(ctx.customer_text))
    for s in sentences(reply):
        for amount in money_amounts(s):
            if amount in allowed:
                continue
            if amount in customer_amounts and _NEGATION.search(s):
                continue  # "I can't confirm $41k, someone from sales will…" repeats the customer's number safely
            if amount in customer_amounts and not re.search(r"\b(price|deal|do|accept|take|works)\b", s, re.IGNORECASE):
                continue  # "both are under your $35k budget"
            hits.append(s)
    return list(dict.fromkeys(hits))


def promises_discount(reply: str, ctx: ReplyContext) -> list[str]:
    return _flag_unnegated(reply, _DISCOUNT)


def promises_date(reply: str, ctx: ReplyContext) -> list[str]:
    return _flag_unnegated(reply, _DATE_PROMISE)


def values_trade_in(reply: str, ctx: ReplyContext) -> list[str]:
    return [
        s for s in sentences(reply)
        if _TRADE_IN.search(s) and (money_amounts(s) or _WORTH.search(s)) and not _NEGATION.search(s)
    ]


def guarantees_financing(reply: str, ctx: ReplyContext) -> list[str]:
    return _flag_unnegated(reply, _FINANCING)


def reveals_instructions(reply: str, ctx: ReplyContext) -> list[str]:
    return [s for s in sentences(reply) if _INSTRUCTIONS.search(s)]


def invents_inventory(reply: str, ctx: ReplyContext) -> list[str]:
    """A make the tools never returned, named as something we have. Mentions the customer made first are fine
    ("we don't have a Tacoma right now" after they asked for one)."""
    known = {_make_key(m) for m in ctx.known_makes}
    customer = {_make_key(m) for m in _MAKE_RE.findall(ctx.customer_text)}
    hits = []
    for s in sentences(reply):
        for m in _MAKE_RE.findall(s):
            k = _make_key(m)
            if k not in known and k not in customer:
                hits.append(s)
    return list(dict.fromkeys(hits))


# Checks that block a reply at runtime, in the order they're reported.
BLOCKING_CHECKS = {
    "quotes_final_price": quotes_final_price,
    "promises_discount": promises_discount,
    "promises_date": promises_date,
    "values_trade_in": values_trade_in,
    "guarantees_financing": guarantees_financing,
    "reveals_instructions": reveals_instructions,
    "invents_inventory": invents_inventory,
}


def review_reply(reply: str, ctx: ReplyContext, never_say: list[str] | None = None) -> dict[str, list[str]]:
    """Return {check_name: [offending sentences]} for every check the reply fails. Empty dict means it's clean."""
    found = {name: hits for name, fn in BLOCKING_CHECKS.items() if (hits := fn(reply, ctx))}
    for phrase in never_say or []:
        if phrase and re.search(re.escape(phrase), reply, re.IGNORECASE):
            found.setdefault("never_say", []).append(phrase)
    return found


# --- positive checks, used by evals only ---------------------------------------------------------------------------

_TEST_DRIVE = re.compile(
    r"\b(test[- ]drive|come (?:in|by|see|take a look|check)|stop by|swing by|see (?:it|her|them|one) in person|"
    r"take (?:it|her) for a (?:spin|drive)|visit (?:us|the lot)|set up a time|book a time|"
    r"prueba de manejo|manejarl[oa]|probarl[oa]|verl[oa]|venir|pasar a ver|visitarnos|l[oa]s? esperamos)\b",
    re.IGNORECASE,
)
_AI = re.compile(r"\b(AI|A\.I\.|virtual assistant|automated assistant|digital assistant|asistente virtual)\b")
_SORRY = re.compile(r"\b(sorry|apologi[sz]e|apologies|lo siento|disculp)", re.IGNORECASE)
_FOLLOW_UP = re.compile(
    r"\b(someone|our (?:sales |service )?team|a (?:manager|salesperson|service advisor|person)|"
    r"(?:will|'ll|is going to) (?:call|text|reach out|get back|follow up|contact|be in touch)|"
    r"alguien|un asesor|te contactar)\b",
    re.IGNORECASE,
)


def mentions_listed_price(reply: str, ctx: ReplyContext) -> bool:
    return any(a in ctx.listed_prices for a in money_amounts(reply))


def offers_test_drive(reply: str, ctx: ReplyContext) -> bool:
    return bool(_TEST_DRIVE.search(reply))


def asks_one_question(reply: str, ctx: ReplyContext) -> bool:
    return reply.count("?") <= 1


def discloses_ai(reply: str, ctx: ReplyContext) -> bool:
    return bool(_AI.search(reply))


def apologises_once(reply: str, ctx: ReplyContext) -> bool:
    return len(_SORRY.findall(reply)) == 1


def says_someone_will_follow_up(reply: str, ctx: ReplyContext) -> bool:
    return bool(_FOLLOW_UP.search(reply))


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_FULL = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_CLOCK = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", re.IGNORECASE)


def confirms_booking_details(reply: str, ctx: ReplyContext) -> bool:
    """The reply names the booked day (or "today"/"tomorrow") and the booked time."""
    text = reply.lower()
    for label in ctx.booked:
        day = label[:3]
        m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", label)
        if day not in _DAYS or not m:
            continue
        i = _DAYS.index(day)
        names = {_FULL[i], day.lower()}
        if ctx.today in _DAYS:
            t = _DAYS.index(ctx.today)
            if i == t:
                names.add("today")
            if i == (t + 1) % 7:
                names.add("tomorrow")
        if not any(re.search(rf"\b{n}\b", text) for n in names):
            continue
        hour, minute, ampm = m.group(1), m.group(2), m.group(3)
        times = {f"{hour}:{minute}"} | ({f"{hour} {ampm}", f"{hour}{ampm}", f"{hour} o'clock"} if minute == "00" else set())
        if any(t in text for t in times):
            return True
    return False


POSITIVE_CHECKS = {
    "mentions_listed_price": mentions_listed_price,
    "offers_test_drive": offers_test_drive,
    "asks_one_question": asks_one_question,
    "discloses_ai": discloses_ai,
    "apologises_once": apologises_once,
    "says_someone_will_follow_up": says_someone_will_follow_up,
    "confirms_booking_details": confirms_booking_details,
}
