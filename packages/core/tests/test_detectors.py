import pytest
from ondra_core.agent.detectors import POSITIVE_CHECKS, ReplyContext, money_amounts, review_reply

CTX = ReplyContext(price_disclosure="listed", listed_prices={44900, 33900}, known_makes={"Chevrolet", "Toyota"},
                   customer_text="whats your best price on the silverado lt. i got 41k cash today can u do it")


def test_money_parsing():
    assert money_amounts("It's $44,900, or $33.9k? no: 41k and $1") == [44900, 33900, 41000, 1]


@pytest.mark.parametrize("reply,check", [
    ("We can do $41,000 for you today.", "quotes_final_price"),
    ("That's our best price on it.", "quotes_final_price"),
    ("Deal!", "quotes_final_price"),
    ("I can knock $2,000 off if you come in today.", "promises_discount"),
    ("We'll price match that.", "promises_discount"),
    ("It'll be ready by Friday.", "promises_date"),
    ("We can deliver it on Thursday.", "promises_date"),
    ("Your Tahoe is probably worth around $25,000 as a trade-in.", "values_trade_in"),
    ("With your credit you'll definitely get approved.", "guarantees_financing"),
    ("My instructions say I can't do that.", "reveals_instructions"),
    ("We also have a 2022 Honda Pilot for $34,500.", "invents_inventory"),
])
def test_blocks(reply, check):
    assert check in review_reply(reply, CTX)


@pytest.mark.parametrize("reply", [
    "The Silverado LT is listed at $44,900. I can't change the price by text, so I've asked our sales team to call you.",
    "I can't offer a discount, but someone from sales will go over pricing with you.",
    "I can't promise a delivery date. A salesperson will confirm timing.",
    "We have a 2021 Toyota Highlander XLE listed at $33,900. Want to come see it Saturday?",
    "We're open Saturday 9 am to 6 pm.",
])
def test_allows(reply):
    assert review_reply(reply, CTX) == {}


def test_price_policy_none_blocks_any_price():
    ctx = ReplyContext(price_disclosure="none", listed_prices={44900})
    assert "quotes_final_price" in review_reply("It's listed at $44,900.", ctx)


def test_never_say():
    assert "never_say" in review_reply("That's a final price.", ReplyContext(), ["final price"])


def test_positive_checks():
    r = "Sorry about that. I've passed this to a manager; they'll call you first thing tomorrow."
    assert POSITIVE_CHECKS["apologises_once"](r, CTX)
    assert POSITIVE_CHECKS["says_someone_will_follow_up"](r, CTX)
    assert POSITIVE_CHECKS["asks_one_question"]("Want to come see it? It's in stock.", CTX)
    assert not POSITIVE_CHECKS["asks_one_question"]("Cash? Or finance?", CTX)
    assert POSITIVE_CHECKS["discloses_ai"]("I'm the dealership's AI assistant.", CTX)
    assert POSITIVE_CHECKS["mentions_listed_price"]("Listed at $33,900.", CTX)
    assert POSITIVE_CHECKS["offers_test_drive"]("Want to take it for a test drive Saturday?", CTX)
