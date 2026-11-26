"""Keeps the golden conversations well-formed until the eval runner exists (Step 2)."""

from pathlib import Path

import yaml

GOLDEN = sorted((Path(__file__).parent / "golden").glob("*.yaml"))
TOOLS = {"get_contact_context", "update_lead_fields", "search_inventory", "get_vehicle", "check_availability",
         "book_appointment", "reschedule_or_cancel", "get_repair_order_status", "get_shipment_status", "search_knowledge",
         "handoff", "push_crm_lead", "schedule_follow_up"}  # BUILD_PLAN.md section 6.2
CHECKS = {"quotes_final_price", "promises_discount", "promises_date", "values_trade_in", "guarantees_financing",
          "mentions_listed_price", "offers_test_drive", "confirms_booking_details", "asks_one_question", "discloses_ai",
          "reveals_instructions", "apologises_once", "says_someone_will_follow_up", "invents_inventory"}
EXPECT_KEYS = {"reply", "reply_language", "tools_called", "tools_not_called", "fields", "booking", "handoff", "must",
               "must_not", "ai_invoked", "alert", "consent"}


def test_there_are_enough_scenarios():
    assert len(GOLDEN) >= 20  # Step 2 acceptance


def test_every_scenario_is_well_formed():
    ids = set()
    for f in GOLDEN:
        s = yaml.safe_load(f.read_text())
        assert s["id"] == f.stem, f
        assert s["id"] not in ids
        ids.add(s["id"])
        assert s["channel"] in {"sms", "whatsapp", "email", "phone"}
        assert s["turns"], f
        for t in s["turns"]:
            e = t["expect"]
            assert set(e) <= EXPECT_KEYS, (f, set(e) - EXPECT_KEYS)
            assert set(e.get("tools_called", [])) | set(e.get("tools_not_called", [])) <= TOOLS, f
            assert set(e.get("must", [])) | set(e.get("must_not", [])) <= CHECKS, f
            if e.get("ai_invoked") is False:
                assert e["reply"] is False and not e.get("tools_called"), f


def test_vip_and_opted_out_never_reach_the_ai():
    for f in GOLDEN:
        s = yaml.safe_load(f.read_text())
        if s["contact"].get("vip") or s["contact"].get("opted_out"):
            assert all(t["expect"].get("ai_invoked") is False for t in s["turns"]), f
