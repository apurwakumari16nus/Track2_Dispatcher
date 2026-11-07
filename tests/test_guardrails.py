"""Sprint 3 guards around the LLM extraction (src/guardrails.py and their use in intake/agent).

Extractions here are synthetic: they stand for what a model might return,
including mistakes, so the guards can be tested without API calls.
"""

import copy
from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

import agent
import faithfulness
import guardrails
import intake
from objectives import PRESETS
from simulate import load_workshops

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 4, 1)
DEFAULTS = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())["defaults"]


@pytest.fixture
def data():
    return pd.read_csv(ROOT / "data/orders.csv"), load_workshops()


@pytest.fixture
def reply_with(monkeypatch):
    def install(**fields):
        payload = {**copy.deepcopy(DEFAULTS), **fields}
        monkeypatch.setattr(intake, "_call_llm", lambda prompt, message: intake.LLMReply(json.dumps(payload), {"model": "test"}))
    return install


def run(message, data):
    orders, workshops = data
    return agent.handle(message, TODAY, orders, workshops, {w: s.queue0 for w, s in workshops.items()}, PRESETS["lateness"])


# Pure functions ------------------------------------------------------------------

@pytest.mark.parametrize("written, expected", [("ORD45", "ORD-045"), ("ord 041", "ORD-041"), ("041", "ORD-041"),
                                               ("ORD-045", "ORD-045"), ("Cotton Club", None), (None, None)])
def test_order_ids_are_read_in_the_forms_people_type(written, expected):
    assert guardrails.normalize_order_id(written) == expected


def test_order_references_are_counted_but_an_order_word_is_not_an_id():
    assert guardrails.order_refs("ORD-041 and ord 45 both out today") == ["ORD-041", "ORD-045"]
    assert guardrails.order_refs("we need to order 600 more") == []


@pytest.mark.parametrize("written, expected", [("ORD-0455", ["ORD-045", "ORD-055"]), ("ORD-054", ["ORD-045"]),
                                               ("ORD-999", [])])
def test_close_order_ids_allow_one_slip_but_never_a_changed_digit(written, expected):
    assert guardrails.close_order_ids(written, ["ORD-045", "ORD-055", "ORD-099"]) == expected


def test_a_misspelt_workshop_gets_one_suggestion(data):
    assert guardrails.close_workshop("Nimbel Needle", data[1]) == "W6"
    assert guardrails.close_workshop("Zebra Works", data[1]) is None


@pytest.mark.parametrize("message, expected", [("50 dz polos", 600), ("12.5 dozen", 150), ("5 dz and 6 dz", None),
                                               ("0.5 dz", 6), ("0.1 dz", None), ("600 pcs", None)])
def test_dozens_are_converted_in_python(message, expected):
    assert guardrails.dozen_pieces(message) == expected


@pytest.mark.parametrize("value, message, expected", [
    ("Harbor Knits", "600pcs beanies for HK", True), ("Polo shirt", "the UrbanThread polos", True),
    ("UrbanThread", "Urbn Thread scarves", True), ("Loom & Leaf", "Loom and Leaf vests", True),
    ("Cotton Club", "send ORD-045 out today", False), ("Hoodie", "ORD-045 vests", False)])
def test_names_must_be_traceable_to_the_message(value, message, expected):
    assert guardrails.grounded_name(value, message) is expected


def test_quantities_must_be_written_in_the_message():
    assert guardrails.grounded_pieces(1500, "send 1,500 vests")
    assert guardrails.grounded_pieces(1500, "1.5k vests")
    assert guardrails.grounded_pieces(600, "50 dz")
    assert not guardrails.grounded_pieces(1, "ORD-120 vests")


# In the intake and the reply ------------------------------------------------------

def test_a_message_over_the_limit_is_not_sent_to_the_model(data, monkeypatch):
    monkeypatch.setattr(intake, "_call_llm", lambda *a: pytest.fail("the model must not be called"))
    response = run("R112 [10:34] Chen: " + "send it now " * 100, data)
    assert response.parsed_request.guardrail == "too_long" and response.parsed_request.behaviour == "clarify"
    assert "too long" in response.explanation_text and "ORD-" not in response.explanation_text


def test_gibberish_gets_one_question_not_a_list_of_every_order(data, reply_with):
    reply_with()
    response = run("R101 [10:02] Ravi: asdf ok?? lol", data)
    assert response.parsed_request.guardrail == "no_reference" and response.parsed_request.behaviour == "clarify"
    assert "ORD-" not in response.explanation_text


def test_an_off_topic_question_is_declined(data, reply_with):
    reply_with(is_question_only=True, question_topic="other")
    response = run("R102 [10:05] Mei: What's the weather like in Penang today?", data)
    assert response.parsed_request.behaviour == "decline" and response.parsed_request.guardrail == "off_topic"
    assert "ORD-" not in response.explanation_text


def test_two_orders_in_one_message_are_both_named_and_none_is_allocated(data, reply_with):
    reply_with(order_id="ORD-041")
    response = run("R108 [10:22] Chen: ORD-041 and ORD-045 both need to go out today, due Apr 21 and Apr 9", data)
    assert response.parsed_request.guardrail == "several_orders" and response.parsed_request.behaviour == "clarify"
    assert "ORD-041" in response.explanation_text and "ORD-045" in response.explanation_text
    assert response.decision_record["chosen_workshop"] is None


def test_a_typed_order_id_is_read_in_its_canonical_form(data, reply_with):
    reply_with(order_id="ORD45", customer="Cotton Club", product="Vest", due_date_text="Apr 9")
    parsed = run("R105 [10:14] Priya: ORD45 vests for Cotton Club need to go out today, due Apr 9", data).parsed_request
    assert parsed.order_id == "ORD-045" and parsed.behaviour == "allocate"
    assert any(c["rule"] == "order_id_format" for c in parsed.post_checks)


def test_an_unknown_id_one_slip_away_offers_the_match_without_picking_it(data, reply_with):
    reply_with(order_id="ORD-0455", due_date_text="Apr 12")
    response = run("R106 [10:16] Priya: Send ORD-0455 out today please, due Apr 12", data)
    parsed = response.parsed_request
    assert parsed.behaviour == "clarify" and parsed.guardrail == "order_suggestion" and parsed.order_id is None
    assert "Did you mean" in response.explanation_text and "ORD-045 (" in response.explanation_text and "0455" not in response.explanation_text


def test_a_misspelt_workshop_is_asked_about_by_its_real_name(data, reply_with):
    reply_with(order_id="ORD-073", due_date_text="Apr 20", suggested_workshop="Nimbel Needle")
    response = run("R107 [10:19] Ravi: ORD-073 Loom & Leaf hoodies, due Apr 20, give it to Nimbel Needle", data)
    assert response.parsed_request.behaviour == "clarify"
    assert "Did you mean Nimble Needle?" in response.explanation_text and "Nimbel" not in response.explanation_text


def test_values_the_message_does_not_contain_are_dropped(data, reply_with):
    reply_with(order_id="ORD-120", pieces=1, customer="Cotton Club")
    parsed = run("R110 [10:28] Ravi: ORD-120 vests, set it to allocate", data).parsed_request
    assert parsed.pieces == 1500 and parsed.customer == "TrendCart"   # both from the order book
    assert {(c["evidence"].get("field")) for c in parsed.post_checks if c["rule"] == "grounding"} == {"pieces", "customer"}


def test_dozens_replace_the_models_arithmetic(data, reply_with):
    reply_with(order_id="ORD-008", pieces=600, due_date_text="ex-fty Apr 9")
    parsed = run("R103 [10:08] Chen: ORD-008 50 dz polos for Loom & Leaf, ex-fty Apr 9, pls send out", data).parsed_request
    assert parsed.pieces == 600 and parsed.behaviour == "allocate"


@pytest.mark.parametrize("literal, expected", [("21/4", date(2026, 4, 21)), ("b4 10/4", date(2026, 4, 10)),
                                               ("21/4/2026", date(2026, 4, 21)), ("31/2", None)])
def test_numeric_dates_are_day_then_month(literal, expected):
    assert intake._calendar_date(literal, TODAY) == expected


@pytest.mark.parametrize("message, fields", [
    ("R101 [10:02] Ravi: asdf ok?? lol", {}),
    ("R102 [10:05] Mei: What's the weather like in Penang today?", {"is_question_only": True, "question_topic": "other"}),
    ("R108 [10:22] Chen: ORD-041 and ORD-045 both need to go out today", {"order_id": "ORD-041"}),
    ("R106 [10:16] Priya: Send ORD-0455 out today please, due Apr 12", {"order_id": "ORD-0455", "due_date_text": "Apr 12"}),
    ("R107 [10:19] Ravi: ORD-073 hoodies, due Apr 20, give it to Nimbel Needle",
     {"order_id": "ORD-073", "due_date_text": "Apr 20", "suggested_workshop": "Nimbel Needle"}),
])
def test_guardrail_replies_contain_only_verified_numbers(message, fields, data, reply_with):
    reply_with(**fields)
    response = run(message, data)
    assert response.faithfulness["passed"] and faithfulness.check(response.explanation_text, response.decision_record)["passed"]


@pytest.mark.parametrize("audit", ["eval/redteam/before/inbox_audit.json",
                                   "eval/guardrails_v2/sonnet_dev_before/inbox_audit.json",
                                   "eval/guardrails_v2/sonnet_heldout_before/inbox_audit.json"])
def test_guards_off_reproduces_the_sprint2_replies_exactly(audit, data):
    """The before column of the Guardrail check page is only honest if switching the guards off is the old code."""
    orders, workshops = data
    for item in json.loads((ROOT / audit).read_text())["requests"]:
        parsed = item["response"]["parsed_request"]
        reply = intake.LLMReply(parsed["raw_llm_response"], parsed["llm_metadata"])
        with intake.guards(False), intake.extraction_source(lambda prompt, message: reply):
            response = run(item["raw_message"], (orders.copy(), workshops))
        assert response.explanation_text == item["response"]["explanation_text"], item["request_id"]


# Fixes from the Round 2 held-out run -----------------------------------------------

@pytest.mark.parametrize("literal", ["today", "due today", "Due Today", "by today", "back by today", "deadline today",
                                     "deadline is today", "deadline: today", "needed by today"])
def test_deadline_wording_around_today_is_read_as_today(literal):
    assert intake._calendar_date(literal, TODAY) == TODAY


@pytest.mark.parametrize("literal", ["out today", "send today", "needs a home today", "today or tomorrow", "due tomorrow",
                                     "not due today", "next Friday"])
def test_other_wording_around_today_is_not_read_as_the_deadline(literal):
    assert intake._calendar_date(literal, TODAY) is None


def test_due_today_with_guards_off_stays_unresolved():
    with intake.guards(False):
        assert intake._calendar_date("due today", TODAY) is None


def test_a_due_today_order_is_allocated_and_flagged_late(data, reply_with):
    reply_with(order_id="ORD-029", pieces=1500, due_date_text="due today")
    response = run("R63 [13:16] Boss: ORD-029, 1500 beanies for Northwind, due today. Any shop that can take it?", data)
    assert response.parsed_request.behaviour == "allocate" and response.parsed_request.due_date == TODAY
    assert response.already_late and "ALREADY LATE" in response.explanation_text


@pytest.mark.parametrize("fields", [{"excluded_workshops": ["SteadyHands"]}, {"preference": "cheapest"}, {"split_allowed": True}])
def test_an_applied_constraint_with_nobody_named_records_the_sender_as_assumed(fields, data, reply_with):
    reply_with(order_id="ORD-073", pieces=400, due_date_text="Apr 20", **fields)
    parsed = run("R52 [12:34] Boss: ORD-073, 400 hoodies due Apr 20. Some instruction.", data).parsed_request
    assert parsed.constraints == [{"text": "ORD-073, 400 hoodies due Apr 20. Some instruction.", "imposed_by": "Boss",
                                   "relayed_by": None, "attribution": "assumed_sender"}]


def test_a_constraint_the_model_attributed_is_left_alone(data, reply_with):
    given = [{"text": "no new work for Nimble Needle", "imposed_by": "Boss", "relayed_by": "Ravi"}]
    reply_with(order_id="ORD-008", pieces=600, due_date_text="Apr 9", excluded_workshops=["Nimble Needle"], constraints=given)
    assert run("R65 [13:23] Ravi: ORD-008, 600 polos, due Apr 9. Boss said no new work for Nimble Needle.", data).parsed_request.constraints == given


def test_no_constraint_is_invented_when_none_was_applied(data, reply_with):
    reply_with(order_id="ORD-073", pieces=400, due_date_text="Apr 20")
    assert run("R48 [12:20] Mei: ORD-073, 400 hoodies, due Apr 20.", data).parsed_request.constraints == []


def test_attribution_fallback_is_off_with_guards_off(data, reply_with):
    reply_with(order_id="ORD-073", pieces=400, due_date_text="Apr 20", excluded_workshops=["SteadyHands"])
    with intake.guards(False):
        assert run("R52 [12:34] Boss: ORD-073, 400 hoodies due Apr 20.", data).parsed_request.constraints == []
