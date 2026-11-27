"""Reading inventory files and deciding what changes."""

from ondra_core.inventory_feed import Car, Existing, fingerprint, parse, plan

CSV = """Stock #,VIN,Year,Make,Model,Trim,Internet Price,Miles,Status,Photo URLs,Exterior Color,Body Style
H23-1148,2HKRS4H7XPH400001,2023,Honda,CR-V,EX-L,"$25,100.00","23,512",In Stock,https://img.example/a.jpg|https://img.example/b.jpg,Blue,SUV
T21-0007,5TDKDRAH5MS000002,2021,Toyota,Highlander,XLE,31900,41200,Sale Pending,,Silver,SUV
,1FTFW1E50LFA00003,2020,Ford,F-150,Platinum,28800,46500,,,,Truck
BAD-1,NOTAVIN,2020,Ford,Escape,,19000,30000,,,,
BAD-2,,20,Kia,Soul,,9000,80000,,,,
BAD-3,,2019,Kia,Soul,,cheap,80000,,,,
"""


def test_csv_headers_are_matched_by_meaning_and_values_cleaned():
    p = parse(CSV, "feed.csv")
    assert p.error is None and len(p.cars) == 3
    crv, highlander, f150 = p.cars
    assert crv == Car(stock="H23-1148", vin="2HKRS4H7XPH400001", year=2023, make="Honda", model="CR-V", trim="EX-L", price=25100.0,
                      mileage=23512, status="available", photos=("https://img.example/a.jpg", "https://img.example/b.jpg"),
                      extra=(("color", "Blue"), ("body", "SUV")))
    assert highlander.status == "hold" and f150.status is None
    assert f150.stock == "LFA00003"  # no stock number: the last 8 of the VIN
    assert p.columns["price"] == "Internet Price" and p.columns["stock"] == "Stock #"


def test_bad_rows_are_reported_with_their_line_never_guessed_at():
    p = parse(CSV)
    assert p.skipped == [{"line": 5, "why": "VIN 'NOTAVIN' isn't a 17-character VIN"},
                         {"line": 6, "why": "Year '20' isn't a model year"},
                         {"line": 7, "why": "Price 'cheap' isn't a number"}]


def test_a_file_without_the_needed_columns_is_refused_whole():
    p = parse("Name,Phone\nSarah,555\n")
    assert p.cars == [] and "year, make and model" in p.error
    assert parse("").error == "This file is empty."
    assert "larger than 5 MB" in parse("x" * (5 * 1024 * 1024 + 1)).error


def test_semicolons_tabs_a_bom_and_duplicates():
    p = parse("﻿stock;year;make;model;price\nA1;2020;Kia;Soul;9000\nA1;2020;Kia;Soul;9500\n")
    assert [c.price for c in p.cars] == [9500.0] and p.duplicates == 1  # the later line wins
    assert len(parse("VIN\tYear\tMake\tModel\n2HKRS4H7XPH400001\t2023\tHonda\tCR-V\n").cars) == 1


def test_zero_price_means_no_price():
    [car] = parse("stock,year,make,model,price\nA1,2020,Kia,Soul,$0\n").cars
    assert car.price is None  # "call for price": the AI then says sales will confirm it


def test_xml_feeds():
    xml = """<?xml version="1.0"?><inventory><vehicle><stock>H23-1148</stock><vin>2HKRS4H7XPH400001</vin><year>2023</year>
      <make>Honda</make><model>CR-V</model><price>25100</price><image>x</image><imageurl>https://img.example/a.jpg</imageurl>
      <imageurl>https://img.example/b.jpg</imageurl></vehicle>
      <vehicle stock="T1" year="2021" make="Toyota" model="Camry" price="19900"/></inventory>"""
    p = parse(xml)
    assert p.error is None and [c.stock for c in p.cars] == ["H23-1148"]  # the attribute-only one has no children
    assert p.cars[0].photos == ("https://img.example/a.jpg", "https://img.example/b.jpg")
    assert "document type" in parse('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><inventory/>').error
    assert "well-formed" in parse("<inventory><vehicle>").error


def existing(id_, stock, vin, status="available", from_feed=True, price=25100.0):
    return Existing(id_, stock, vin, status, from_feed, fingerprint(2023, "Honda", "CR-V", None, price, None, status), extra=(("seats", 5),))


def car(stock, vin, price=25100.0, status=None):
    return Car(stock=stock, vin=vin, year=2023, make="Honda", model="CR-V", price=price, status=status)


def test_plan_matches_by_vin_first_then_stock():
    have = [existing("1", "OLD-STOCK", "2HKRS4H7XPH400001"), existing("2", "S2", None), existing("3", "S3", None, status="hold")]
    p = plan(have, [car("NEW-STOCK", "2HKRS4H7XPH400001"),  # same VIN, restocked under a new number: an update, not a second car
                    car("s2", None, price=24000.0), car("S3", None), car("S9", None)])
    assert [i for i, _ in p.update] == ["1", "2"] and p.unchanged == 1  # S3 stays on hold: the file has no status
    assert [c.stock for c in p.create] == ["S9"] and p.mark_sold == []


def test_cars_missing_from_the_feed_are_marked_sold_but_only_feed_cars():
    have = [existing("1", "S1", None), existing("2", "S2", None), existing("3", "HAND", None, from_feed=False)]
    p = plan(have, [car("S1", None)])
    assert p.mark_sold == ["2"]  # the hand-entered car isn't the feed's to remove
    assert plan(have, [car("S1", None)], whole_lot=False).mark_sold == []  # a manual upload of a few cars


def test_a_feed_cut_short_marks_nothing_sold():
    have = [existing(str(i), f"S{i}", None) for i in range(20)]
    p = plan(have, [car("S0", None), car("S1", None)])
    assert p.partial is True and p.mark_sold == []
    assert plan(have, [car(f"S{i}", None) for i in range(12)]).mark_sold == [str(i) for i in range(12, 20)]  # 8 of 20 gone is normal
