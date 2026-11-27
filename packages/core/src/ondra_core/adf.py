"""ADF 1.0 (Auto-lead Data Format): the XML lead that dealer CRMs read from an email (BUILD_PLAN.md §8).

What was verified, and how (2026-11-27; the spec's own site, adfxml.info, wasn't reachable from the build machine):
- Element names, attributes and CHILD ORDER come from a copy of the ADF 1.0 DTD read in full
  (github.com/carmelosantana/sendadf, docs/adf-1.0.dtd). DTD sequences are ordered, so order matters:
    prospect: id*, requestdate, vehicle+, customer, vendor, provider?
    vehicle:  id*, year, make, model, vin?, stock?, trim?, ..., odometer?, ..., price?, ..., finance?, comments?
    customer: contact, id*, timeframe?, comments?
    contact:  name+, email?, phone*, address?
    vendor:   id*, vendorname, url?, contact
    provider: id*, name, service?, url?, email?, phone?, contact?
  year, make and model are required inside vehicle; vendorname and contact inside vendor.
- The processing instruction `<?adf version="1.0"?>` and ISO 8601 request dates with an offset are from the same
  project's output and from search snippets of the spec, not from the spec itself.
- TODO(verify): how each CRM wants the email (plain-text body that is only the XML is the spec's simple mode and
  the common case; some CRMs want an attachment or a particular subject). Confirm with each pilot dealer's CRM.

`build()` writes the XML; `problems()` checks a document against the rules above, so tests can call a lead "valid"
without a validating parser (the DTD copy has transcription defects and won't load in one).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr


@dataclass(frozen=True)
class Vehicle:
    year: int | None = None
    make: str = ""
    model: str = ""
    vin: str | None = None
    stock: str | None = None
    trim: str | None = None
    odometer: int | None = None
    price: float | None = None  # the listed price, sent as type="asking"
    interest: str = "buy"  # buy | lease | sell | trade-in | test-drive
    status: str = "used"  # new | used
    comments: str | None = None  # what they asked for, when it isn't one car in stock


@dataclass(frozen=True)
class Lead:
    id: str
    requested_at: datetime  # timezone-aware
    vendor: str  # the dealership
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    vehicle: Vehicle = field(default_factory=Vehicle)
    comments: str | None = None
    timeframe: str | None = None
    finance_method: str | None = None  # cash | finance | lease
    budget_max: float | None = None
    vendor_email: str | None = None
    provider: str = "Ondra"
    service: str = "AI assistant"
    resend: bool = False


def _el(tag: str, text: object | None, **attrs: str) -> str:
    a = "".join(f" {k}={quoteattr(v)}" for k, v in attrs.items() if v)
    return f"<{tag}{a}>{escape('' if text is None else str(text))}</{tag}>"


def build(lead: Lead) -> str:
    if lead.requested_at.tzinfo is None:
        raise ValueError("requested_at must carry a time zone (ADF dates are ISO 8601 with an offset)")
    v = lead.vehicle
    veh = [_el("year", v.year), _el("make", v.make), _el("model", v.model)]  # required, in this order, even if empty
    if v.vin:
        veh.append(_el("vin", v.vin))
    if v.stock:
        veh.append(_el("stock", v.stock))
    if v.trim:
        veh.append(_el("trim", v.trim))
    if v.odometer is not None:
        veh.append(_el("odometer", v.odometer, status="original", units="mi"))
    if v.price is not None:
        veh.append(_el("price", f"{v.price:.0f}", type="asking", currency="USD"))
    if lead.finance_method in ("cash", "finance", "lease"):
        amount = _el("amount", f"{lead.budget_max:.0f}" if lead.budget_max else "0", type="total", limit="maximum", currency="USD")
        veh.append(f"<finance>{_el('method', lead.finance_method)}{amount}</finance>")
    if v.comments:
        veh.append(_el("comments", v.comments))

    names = []
    if lead.first_name:
        names.append(_el("name", lead.first_name, part="first"))
    if lead.last_name:
        names.append(_el("name", lead.last_name, part="last"))
    if not names:
        names.append(_el("name", lead.full_name or "Unknown", part="full"))
    contact = names
    if lead.email:
        contact.append(_el("email", lead.email))
    if lead.phone:
        contact.append(_el("phone", lead.phone, type="voice", time="nopreference"))
    customer = [f"<contact>{''.join(contact)}</contact>"]
    if lead.timeframe:
        customer.append(f"<timeframe>{_el('description', lead.timeframe)}</timeframe>")
    if lead.comments:
        customer.append(_el("comments", lead.comments))

    vendor_contact = [_el("name", lead.vendor, part="full", type="business")]
    if lead.vendor_email:
        vendor_contact.append(_el("email", lead.vendor_email))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?adf version="1.0"?>',
        "<adf>",
        f'<prospect status="{"resend" if lead.resend else "new"}">',
        _el("id", lead.id, sequence="1", source=lead.provider),
        _el("requestdate", lead.requested_at.replace(microsecond=0).isoformat()),
        f"<vehicle interest={quoteattr(v.interest)} status={quoteattr(v.status)}>{''.join(veh)}</vehicle>",
        f"<customer>{''.join(customer)}</customer>",
        f"<vendor>{_el('vendorname', lead.vendor)}<contact>{''.join(vendor_contact)}</contact></vendor>",
        f"<provider>{_el('name', lead.provider, part='full', type='business')}{_el('service', lead.service)}</provider>",
        "</prospect>",
        "</adf>",
    ]
    return "\n".join(lines) + "\n"


# --- checking a document against the DTD's order and required parts ------------------------------------------------

_ORDER = {
    "prospect": ["id", "requestdate", "vehicle", "customer", "vendor", "provider"],
    "vehicle": ["id", "year", "make", "model", "vin", "stock", "trim", "doors", "bodystyle", "transmission", "odometer",
                "colorcombination", "imagetag", "price", "pricecomments", "option", "finance", "comments"],
    "customer": ["contact", "id", "timeframe", "comments"],
    "contact": ["name", "email", "phone", "address"],
    "vendor": ["id", "vendorname", "url", "contact"],
    "provider": ["id", "name", "service", "url", "email", "phone", "contact"],
    "finance": ["method", "amount", "balance"],
}
_REQUIRED = {"prospect": ["requestdate", "vehicle", "customer", "vendor"], "vehicle": ["year", "make", "model"],
             "customer": ["contact"], "contact": ["name"], "vendor": ["vendorname", "contact"], "provider": ["name"],
             "finance": ["method", "amount"]}
_ENUMS = {("prospect", "status"): {"new", "resend"}, ("vehicle", "interest"): {"buy", "lease", "sell", "trade-in", "test-drive"},
          ("vehicle", "status"): {"new", "used"}, ("name", "part"): {"surname", "first", "middle", "last", "full"},
          ("name", "type"): {"business", "individual"}, ("phone", "type"): {"voice", "fax", "cellphone", "pager"},
          ("phone", "time"): {"morning", "afternoon", "evening", "nopreference", "day"},
          ("price", "type"): {"quote", "offer", "msrp", "invoice", "call", "appraisal", "asking"},
          ("odometer", "units"): {"km", "mi"}, ("odometer", "status"): {"unknown", "rolledover", "replaced", "original"},
          ("amount", "type"): {"downpayment", "monthly", "total"}, ("amount", "limit"): {"maximum", "minimum", "exact"}}


def problems(xml: str) -> list[str]:
    """Why this isn't a valid ADF 1.0 lead, by the rules in this module's docstring. Empty: it is."""
    out: list[str] = []
    if '<?adf version="1.0"?>' not in xml.split("<adf", 1)[0]:
        out.append('missing the <?adf version="1.0"?> processing instruction before <adf>')
    try:
        root = ET.fromstring(xml.encode())
    except ET.ParseError as e:
        return [f"not well-formed XML: {e}"]
    if root.tag != "adf" or not root.findall("prospect"):
        return [*out, "root must be <adf> with at least one <prospect>"]

    def check(el: ET.Element) -> None:
        order = _ORDER.get(el.tag)
        kids = [c.tag for c in el]
        if order is not None:
            unknown = [k for k in kids if k not in order]
            if unknown:
                out.append(f"<{el.tag}> can't contain <{unknown[0]}>")
            positions = [order.index(k) for k in kids if k in order]
            if positions != sorted(positions):
                out.append(f"children of <{el.tag}> are out of order: {', '.join(kids)}")
            for need in _REQUIRED.get(el.tag, []):
                if need not in kids:
                    out.append(f"<{el.tag}> is missing <{need}>")
        for (tag, attr), allowed in _ENUMS.items():
            if el.tag == tag and attr in el.attrib and el.attrib[attr] not in allowed:
                out.append(f'<{tag} {attr}="{el.attrib[attr]}"> isn\'t one of {sorted(allowed)}')
        for c in el:
            check(c)

    for prospect in root:
        check(prospect)
        date = prospect.findtext("requestdate") or ""
        try:
            if datetime.fromisoformat(date).tzinfo is None:
                out.append("requestdate has no UTC offset")
        except ValueError:
            out.append(f"requestdate '{date}' isn't ISO 8601")
        contact = prospect.find("customer/contact")
        if contact is not None and contact.find("email") is None and contact.find("phone") is None:
            out.append("the customer has no email or phone")
    return out
