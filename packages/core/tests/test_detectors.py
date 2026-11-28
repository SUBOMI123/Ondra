import pytest
from ondra_core.agent.detectors import (
    POSITIVE_CHECKS,
    ReplyContext,
    money_amounts,
    promises_discount,
    quotes_final_price,
    review_reply,
)

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


def test_spanish_visit_invitation_counts_as_offering_a_test_drive():
    r = "Si quiere verla o probarla, con gusto la esperamos. ¿Qué día le queda bien para venir?"
    assert POSITIVE_CHECKS["offers_test_drive"](r, CTX)


def test_confirms_booking_details_needs_the_booked_day_and_time():
    from ondra_core.agent.detectors import confirms_booking_details

    ctx = ReplyContext(booked=["Sat 10:00 am"], today="Tue")
    assert confirms_booking_details("You're booked for Saturday at 10 am with Daniel.", ctx)
    assert confirms_booking_details("All set: Sat 10:00 am.", ctx)
    assert not confirms_booking_details("You're all set, see you then!", ctx)
    assert not confirms_booking_details("You're booked for Saturday.", ctx)
    tomorrow = ReplyContext(booked=["Wed 7:30 am, Bay 3"], today="Tue")
    assert confirms_booking_details("Booked for tomorrow at 7:30 am in Bay 3, with a loaner.", tomorrow)
    assert not confirms_booking_details("Booked for tomorrow at 7 am.", tomorrow)


@pytest.mark.parametrize("sentence,blocked", [
    # From a real call: passing a discount request to sales was replaced mid-reply.
    ("Your test drive is booked for Friday at 9 with Daniel. I've also passed your discount question to sales.", False),
    ("I've passed your request for $500 off to our sales team, and they'll call you.", False),
    ("I can't offer a discount myself, but I've passed your $500 off request to sales.", False),
    ("I'll ask a manager whether a discount is possible.", False),
    ("Drop it off Saturday at nine.", False),
    ("It's listed at $27,600.", False),
    # Promises, including the way people say them on the phone.
    ("I can take $500 off for you today.", True),
    ("Sure, we can do five hundred off.", True),
    ("I can knock a grand off if you buy today.", True),
    ("We can give you a discount and I'll let sales know.", True),
    ("I can do $500 off and I'll pass it to sales to finalize.", True),
])
def test_discount_and_price_checks_on_spoken_replies(sentence, blocked):
    ctx = ReplyContext(price_disclosure="listed", listed_prices={27600},
                       customer_text="Can you do five hundred off if I come in today?")
    assert bool(review_reply(sentence, ctx)) is blocked


@pytest.mark.parametrize("sentence,blocked", [
    ("Done, both CR-Vs are on their way to your phone now.", False),  # from a call, after texting the caller
    ("Your oil change is done on the lift in about an hour.", False),
    ("Your car will be ready on Friday.", True),
    ("We'll have it delivered by the 5th.", True),
    ("It'll be finished tomorrow afternoon.", True),
    ("I promise it ships by next week.", True),
    ("Shipping to Lagos arrives before December.", True),
])
def test_delivery_date_promises(sentence, blocked):
    assert bool(review_reply(sentence, ReplyContext())) is blocked


@pytest.mark.parametrize("said, amounts", [
    ("What do you have in SUVs under thirty grand?", [30000]),
    ("my budget is about 25 thousand", [25000]),
    ("around twenty five thousand five hundred", [25500]),
    ("thirty-five k tops", [35000]),
    ("it has forty thousand miles on it", []),  # mileage isn't money
    ("three works for me", []),
    ("Can you do five hundred off if I come in today?", [500]),
    ("knock a grand off", [1000]),
    ("seven hundred fifty down", [750]),
    ("it's done five hundred miles", []),
])
def test_amounts_as_a_caller_says_them(said, amounts):
    from ondra_core.agent.detectors import spoken_amounts
    assert spoken_amounts(said) == amounts


def test_a_callers_spoken_budget_said_back_is_not_a_quote():
    # A test call: "under thirty grand" -> "We have five SUVs under $30,000." was replaced with the safe line.
    ctx = ReplyContext(price_disclosure="listed", listed_prices={25100}, customer_text="What SUVs do you have under thirty grand?")
    assert not review_reply("We have five SUVs under $30,000.", ctx)
    assert "quotes_final_price" in review_reply("We can do $30,000 on it.", ctx)  # still a quote
    assert "quotes_final_price" in review_reply("We have five SUVs under $28,000.", ctx)  # not their number


def test_a_callers_spoken_ask_said_back_in_a_referral_is_not_a_quote():
    ctx = ReplyContext(price_disclosure="listed", listed_prices={25100}, customer_text="Can you do five hundred off if I come in today?")
    assert not review_reply("Our sales team will get back to you shortly about the $500.", ctx)
    assert review_reply("Sure, we can do $500 off.", ctx)


# --- security audit, 2026-11-28: a "not" elsewhere in the sentence used to excuse a commitment ---------------------

@pytest.mark.parametrize("reply", [
    "Not a problem, we can do $25,000.",
    "$25,000 is fine.",
    "Deal, $25,000 it is.",
    "We will let it go for twenty-five thousand.",
    "Not a problem, I can give you a discount.",
])
def test_a_negation_elsewhere_doesnt_excuse_a_commitment(reply):
    ctx = ReplyContext(price_disclosure="none", customer_text="Can you do $25,000?")
    assert quotes_final_price(reply, ctx) or promises_discount(reply, ctx)


@pytest.mark.parametrize("reply", [
    "I can't confirm $25,000, someone from sales will call you.",
    "I can't offer a discount, but sales can talk it through.",
    "I can't do that price.",
    "No problem, I can book you a test drive Saturday at 10.",
    "Both are under your $25,000 budget.",
])
def test_refusals_and_echoes_still_pass(reply):
    ctx = ReplyContext(price_disclosure="none", customer_text="Can you do $25,000?")
    assert not quotes_final_price(reply, ctx) and not promises_discount(reply, ctx)
