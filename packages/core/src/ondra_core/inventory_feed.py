"""Reading a dealer's inventory file (BUILD_PLAN.md §8: CSV/XML feed import, dedupe by VIN). No database here.

Feeds come from many vendors with many column names, so headers are matched by meaning ("Stock #", "StockNumber"
and "stock_no" are all the stock number). A row that can't be used is reported with its line and the reason, never
silently dropped, and never guessed at: a car with a wrong price is worse than a car that's missing.

`plan()` compares a parsed file with what the dealer has and says what would change. A feed is the whole lot, so
cars it no longer lists are marked sold, unless the file looks cut short (then nothing is marked, and it says so).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024

# Meaning -> header spellings seen in dealer feeds (compared lowercased, with punctuation and spaces removed).
_HEADERS = {
    "vin": ("vin", "vehiclevin", "vinnumber"),
    "stock": ("stock", "stocknumber", "stockno", "stocknum", "stockid", "stk", "stock#"),
    "year": ("year", "modelyear", "yr"),
    "make": ("make", "manufacturer", "brand"),
    "model": ("model", "modelname"),
    "trim": ("trim", "series", "trimlevel", "style"),
    "price": ("price", "internetprice", "sellingprice", "saleprice", "askingprice", "listprice", "ourprice", "retailprice"),
    "mileage": ("mileage", "miles", "odometer", "odometerreading", "kms"),
    "status": ("status", "availability", "vehiclestatus", "inventorystatus"),
    "photos": ("photos", "photourls", "photourl", "images", "imageurls", "imagelist", "imageurl", "pictures"),
    "color": ("color", "exteriorcolor", "extcolor", "exteriorcolour", "colour"),
    "body": ("body", "bodystyle", "bodytype", "vehicletype"),
    "seats": ("seats", "seating", "passengers", "seatingcapacity"),
}
_BY_SPELLING = {s: field_name for field_name, spellings in _HEADERS.items() for s in spellings}
_STATUS = {"available": "available", "instock": "available", "in stock": "available", "active": "available", "live": "available",
           "hold": "hold", "onhold": "hold", "on hold": "hold", "pending": "hold", "salepending": "hold", "sale pending": "hold",
           "deposit": "hold", "reserved": "hold", "sold": "sold", "delivered": "sold", "wholesale": "sold"}
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")  # 17 characters, never I, O or Q
_XML_ITEM = ("vehicle", "listing", "item", "car", "unit", "ad")


def _key(header: str) -> str | None:
    return _BY_SPELLING.get(re.sub(r"[^a-z0-9#]", "", (header or "").lower()))


@dataclass(frozen=True)
class Car:
    stock: str
    vin: str | None
    year: int
    make: str
    model: str
    trim: str | None = None
    price: float | None = None
    mileage: int | None = None
    status: str | None = None  # None: the file doesn't say, so an existing car keeps its status
    photos: tuple[str, ...] = ()
    extra: tuple[tuple[str, str | int], ...] = ()  # color, body, seats: kept on `raw`, where search reads them


@dataclass
class Parsed:
    cars: list[Car] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)  # {"line": 7, "why": "No year"}
    duplicates: int = 0
    columns: dict[str, str] = field(default_factory=dict)  # meaning -> the header it was read from
    unknown_columns: list[str] = field(default_factory=list)
    error: str | None = None  # the whole file can't be read


def _number(value: str) -> float | None:
    s = re.sub(r"[^\d.]", "", value or "")
    try:
        return float(s) if s and s != "." else None
    except ValueError:
        return None


def _car(row: dict[str, str], line: int, out: Parsed) -> Car | None:
    def bad(why: str) -> None:
        out.skipped.append({"line": line, "why": why})

    get = lambda k: (row.get(k) or "").strip()
    vin = get("vin").upper().replace(" ", "") or None
    if vin and not _VIN.match(vin):
        return bad(f"VIN '{vin[:20]}' isn't a 17-character VIN")
    stock = get("stock") or (vin[-8:] if vin else "")
    if not stock:
        return bad("No stock number or VIN")
    if len(stock) > 40:
        return bad("Stock number is longer than 40 characters")
    year = _number(get("year"))
    this_year = datetime.now().year
    if year is None or not 1950 <= int(year) <= this_year + 2:
        return bad(f"Year '{get('year')[:10]}' isn't a model year" if get("year") else "No year")
    if not get("make") or not get("model"):
        return bad("No make or model")
    price = _number(get("price")) if get("price") else None
    if get("price") and price is None:
        return bad(f"Price '{get('price')[:20]}' isn't a number")
    if price is not None and (price <= 0 or price > 5_000_000):
        price = None  # "$0" and "call for price" placeholders mean no price, which the AI treats as "ask sales"
    mileage = _number(get("mileage")) if get("mileage") else None
    if get("mileage") and (mileage is None or mileage > 2_000_000):
        return bad(f"Mileage '{get('mileage')[:20]}' isn't a number")
    status = None
    if get("status"):
        status = _STATUS.get(get("status").lower()) or _STATUS.get(re.sub(r"[^a-z]", "", get("status").lower()))
        if status is None:
            return bad(f"Status '{get('status')[:20]}' isn't one of available, on hold or sold")
    photos = tuple(u for u in re.split(r"[|,;\s]+", get("photos")) if u.lower().startswith("https://"))[:20]
    extra: list[tuple[str, str | int]] = [(k, get(k)) for k in ("color", "body") if get(k)]
    if _number(get("seats")):
        extra.append(("seats", int(_number(get("seats")))))
    return Car(stock=stock, vin=vin, year=int(year), make=get("make")[:60], model=get("model")[:60], trim=get("trim")[:80] or None,
               price=price, mileage=int(mileage) if mileage is not None else None, status=status, photos=photos, extra=tuple(extra))


def _finish(out: Parsed, rows: list[tuple[int, dict[str, str]]]) -> Parsed:
    if not {"year", "make", "model"} <= set(out.columns) or not ({"vin", "stock"} & set(out.columns)):
        out.error = ("This file needs columns for year, make and model, and a stock number or VIN. "
                     f"Found: {', '.join(sorted(out.columns.values())) or 'none we recognise'}.")
        return out
    if len(rows) > MAX_ROWS:
        out.error = f"This file has {len(rows)} vehicles; the limit is {MAX_ROWS}."
        return out
    seen: dict[str, int] = {}
    for line, row in rows:
        car = _car(row, line, out)
        if car is None:
            continue
        ident = car.vin or f"stock:{car.stock.lower()}"
        if ident in seen:  # the same car twice: the later line wins
            out.cars[seen[ident]] = car
            out.duplicates += 1
        else:
            seen[ident] = len(out.cars)
            out.cars.append(car)
    return out


def parse_csv(text: str) -> Parsed:
    out = Parsed()
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text.lstrip("﻿")), dialect)
    try:
        headers = next(reader)
    except StopIteration:
        out.error = "This file is empty."
        return out
    names: list[str | None] = []
    for h in headers:
        k = _key(h)
        if k and k not in out.columns:
            out.columns[k] = h.strip()
            names.append(k)
        else:
            names.append(None)
            if h.strip() and not k:
                out.unknown_columns.append(h.strip())
    rows = []
    for i, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        rows.append((i, {n: v for n, v in zip(names, values, strict=False) if n}))
    return _finish(out, rows)


def parse_xml(text: str) -> Parsed:
    """A list of vehicle elements, each with child elements (or attributes) named like the CSV headers."""
    out = Parsed()
    if "<!DOCTYPE" in text[:2000].upper() or "<!ENTITY" in text.upper():
        out.error = "This XML file declares a document type, which isn't accepted. Export it without one."  # no entity tricks
        return out
    try:
        root = ElementTree.fromstring(text.lstrip("﻿"))
    except ElementTree.ParseError as e:
        out.error = f"This isn't well-formed XML ({e})."
        return out
    local = lambda tag: tag.rsplit("}", 1)[-1].lower()
    items = [el for el in root.iter() if local(el.tag) in _XML_ITEM and len(el)]
    if not items:
        out.error = "No vehicles found in this XML file (expected repeated <vehicle> or <listing> elements)."
        return out
    rows = []
    for i, el in enumerate(items, start=1):
        row: dict[str, str] = {}
        for name, value in [*el.attrib.items(), *((local(c.tag), (c.text or "")) for c in el)]:
            k = _key(name)
            if k:
                row[k] = f"{row[k]}|{value}" if k == "photos" and k in row else value
                out.columns.setdefault(k, name)
        rows.append((i, row))
    return _finish(out, rows)


def parse(text: str, filename: str = "") -> Parsed:
    if len(text.encode("utf-8", "ignore")) > MAX_BYTES:
        out = Parsed()
        out.error = "This file is larger than 5 MB."
        return out
    looks_xml = text.lstrip("﻿ \n\r\t").startswith("<")
    return parse_xml(text) if looks_xml or filename.lower().endswith(".xml") else parse_csv(text)


# --- what would change -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Existing:
    id: str
    stock: str
    vin: str | None
    status: str
    from_feed: bool  # it came from a feed before (not typed in by hand), so a feed may mark it sold
    fingerprint: tuple  # the fields a feed sets, to tell "updated" from "unchanged"
    photos: tuple[str, ...] = ()
    extra: tuple[tuple[str, str | int], ...] = ()  # color, body, seats already on file


def fingerprint(year, make, model, trim, price, mileage, status) -> tuple:
    return (year, make, model, trim or None, float(price) if price is not None else None, mileage, status)


@dataclass
class Plan:
    create: list[Car] = field(default_factory=list)
    update: list[tuple[str, Car]] = field(default_factory=list)  # (existing id, new values)
    unchanged: int = 0
    mark_sold: list[str] = field(default_factory=list)  # existing ids no longer in the feed
    partial: bool = False  # the file lists far fewer cars than before: nothing is marked sold


def plan(existing: list[Existing], cars: list[Car], *, whole_lot: bool = True) -> Plan:
    out = Plan()
    by_vin = {e.vin: e for e in existing if e.vin}
    by_stock = {e.stock.lower(): e for e in existing}
    matched: set[str] = set()
    for car in cars:
        e = (by_vin.get(car.vin) if car.vin else None) or by_stock.get(car.stock.lower())
        if e is None:
            out.create.append(car)
            continue
        matched.add(e.id)
        status = car.status or e.status  # a file with no status column leaves a car on hold on hold
        new = fingerprint(car.year, car.make, car.model, car.trim, car.price, car.mileage, status)
        # Photos and details only count as a change when the file brings them and they differ: a file without a
        # photo column doesn't wipe the photos, and one without seats doesn't "update" every car.
        same_photos = not car.photos or car.photos == e.photos
        same_extra = set(car.extra) <= set(e.extra)
        if new == e.fingerprint and e.stock == car.stock and e.vin == car.vin and same_photos and same_extra:
            out.unchanged += 1
        else:
            out.update.append((e.id, car))
    if whole_lot:
        missing = [e for e in existing if e.from_feed and e.id not in matched and e.status != "sold"]
        from_feed = sum(1 for e in existing if e.from_feed and e.status != "sold")
        # A feed cut short mid-export would otherwise mark most of the lot sold and the AI would turn buyers away.
        if from_feed >= 10 and len(missing) > from_feed / 2:
            out.partial = True
        else:
            out.mark_sold = [e.id for e in missing]
    return out
