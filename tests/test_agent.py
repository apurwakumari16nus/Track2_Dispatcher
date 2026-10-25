"""Offline agent integration, including every inbox line and persistent state."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

import agent
import faithfulness
import intake
from objectives import PRESETS
from simulate import load_workshops

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 4, 1)


@pytest.fixture
def data():
    shops = load_workshops()
    return pd.read_csv(ROOT / "data/orders.csv"), shops, {wid: w.queue0 for wid, w in shops.items()}


@pytest.fixture
def parsed(monkeypatch):
    def install(**overrides):
        request = intake.ParsedRequest(request_id="R30", sender="Mei", raw_text="request",
            order_id="ORD-099", customer="Northwind Apparel", product="Polo shirt", category="TOPS",
            pieces=100, due_date=date(2026, 6, 1))
        for key, value in overrides.items():
            setattr(request, key, value)
        monkeypatch.setattr(intake, "parse_request", lambda *args: deepcopy(request))
        return request
    return install


def test_all_thirty_inbox_lines_produce_faithful_serializable_responses(data, monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    lines = [line for line in (ROOT / "data/dispatch_requests.txt").read_text().splitlines() if line.startswith("R")]
    def extraction(prompt, message):
        payload = {**fixture["defaults"], **fixture["requests"][message.split()[0]]}
        return intake.LLMReply(json.dumps(payload), {"model": "synthetic-fixture"})
    monkeypatch.setattr(intake, "_call_llm", extraction)
    assert len(lines) == 30
    session = agent.Agent(PRESETS["lateness"])
    for line in lines:
        result = session.handle(line, TODAY, *data)
        assert result.faithfulness["passed"], line
        assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()
        assert json.loads(result.decision_record_json) == result.decision_record
        if result.parsed_request.behaviour in {"clarify", "decline"}:
            assert result.decision_record["chosen_workshop"] is None
            assert not result.allocation_committed
        if result.already_late:
            assert result.explanation_text.startswith("ALREADY LATE")


def test_clarification_lists_verified_options_without_allocating(data, parsed, monkeypatch):
    parsed(behaviour="clarify", order_id=None, candidate_order_ids=["ORD-099", "ORD-066"])
    monkeypatch.setattr(agent.Allocator, "decide", lambda *a, **kw: pytest.fail("must not allocate"))
    result = agent.handle("request", TODAY, *data, PRESETS["lateness"])
    for expected in ("ORD-099", "ORD-066", "Polo shirt", "1500", "1000"):
        assert expected in result.explanation_text
    assert len(result.decision_record["tool_outputs"]["order_options"]) == 2
    assert result.faithfulness["passed"]


@pytest.mark.parametrize("topic,needed", [("allocation_history", "historical dispatch records"),
    ("customer_quote", "customer sales quotation"), ("worker_names", "worker roster")])
def test_decline_names_missing_data(topic, needed, data, parsed, monkeypatch):
    parsed(behaviour="decline", question_topic=topic, is_question_only=True, reason="no such data")
    monkeypatch.setattr(agent.Allocator, "decide", lambda *a, **kw: pytest.fail("must not allocate"))
    result = agent.handle("request", TODAY, *data, PRESETS["lateness"])
    assert needed in result.explanation_text
    assert "do not hold" in result.explanation_text


def test_refusal_offers_eligible_alternative_without_counting_it(data, parsed):
    parsed(behaviour="refuse", suggested_workshop="W8", pieces=400, excluded_workshops=["W1"])
    session = agent.Agent(PRESETS["lateness"])
    before = deepcopy(session.allocator.__dict__)
    result = session.handle("request", TODAY, *data)
    assert "batch of 400 exceeds 300-piece cap" in result.explanation_text
    assert result.decision_record["chosen_workshop"] not in {None, "W1", "W7", "W8"}
    assert result.decision_record["constraints_applied"]["exclude"] == ["W1", "W8"]
    assert result.parsed_request.behaviour == "refuse" and not result.allocation_committed
    assert session.allocator.pieces_by_workshop == before["pieces_by_workshop"]
    assert session.allocator.shock_monitor.__dict__ == before["shock_monitor"].__dict__


def test_refusal_with_unconfirmed_date_does_not_invent_alternative(data, parsed):
    parsed(behaviour="refuse", suggested_workshop="W7", due_date=None, date_not_confirmed=True)
    result = agent.handle("request", TODAY, *data, PRESETS["lateness"])
    assert "suspended" in result.explanation_text and "confirmed new deadline" in result.explanation_text
    assert result.decision_record["chosen_workshop"] is None


@pytest.mark.parametrize("preference,objective", [("fastest", "lateness"),
    ("cheapest", "cheapest_on_time"), ("lowest_defect", "defect")])
def test_preference_overrides_and_exclusions(preference, objective, data, parsed):
    parsed(preference=preference, excluded_workshops=["W1", "W2"])
    session = agent.Agent(PRESETS["fairness"])
    result = session.handle("request", TODAY, *data)
    assert result.decision_record["objective_name"] == objective
    assert result.decision_record["chosen_workshop"] not in {"W1", "W2", "W7"}
    # Cheapest and lowest defect must both still make the date (quality without lateness).
    assert result.decision_record["constraints_applied"]["must_make_date"] is (preference in ("cheapest", "lowest_defect"))
    assert session.allocator.config == PRESETS["fairness"]
    assert sum(session.allocator.pieces_by_workshop.values()) == 100


def test_cheapest_only_selects_on_time_candidate(data, parsed):
    orders, original, _ = data
    shops = {"W1": replace(original["W1"], capacity=100, lead_days=0, cost=1),
             "W2": replace(original["W2"], capacity=100, lead_days=0, cost=4)}
    parsed(preference="cheapest", due_date=date(2026, 4, 3))
    result = agent.handle("request", TODAY, orders, shops, {"W1": 10, "W2": 0}, PRESETS["lateness"])
    assert result.decision_record["chosen_workshop"] == "W2"
    assert result.decision_record["constraints_applied"]["date_constraint_satisfied"]


def test_none_makes_date_warns_and_does_not_commit_fallback(data, parsed):
    parsed(due_date=TODAY, already_late=True, preference="cheapest", split_allowed=True)
    session = agent.Agent(PRESETS["lateness"])
    result = session.handle("request", TODAY, *data)
    assert result.awkward_case == "none_makes_date" and result.already_late
    assert result.decision_record["chosen_workshop"] is not None
    assert "AWKWARD CASE: none_makes_date" in result.explanation_text
    assert "Accept lateness explicitly" in result.explanation_text
    assert not result.allocation_committed and session.allocator.pieces_by_workshop == {}
    assert "splitting is not implemented" not in result.decision_record_json


def test_all_excluded_escalates(data, parsed):
    parsed(excluded_workshops=list(data[1]), split_allowed=True)
    result = agent.handle("request", TODAY, *data, PRESETS["lateness"])
    assert result.awkward_case == "no_eligible"
    assert result.decision_record["chosen_workshop"] is None
    assert not result.decision_record["tool_outputs"]["split"]["available"]


def test_session_history_survives_calls_and_split_preview_counts_batch_only_once(data, parsed):
    orders, source, _ = data
    shops = {wid: replace(source[wid], capacity=100, lead_days=1) for wid in ("W1", "W2")}
    queues = {"W1": 0.0, "W2": 0.0}
    parsed(split_allowed=True)
    session = agent.Agent(PRESETS["fairness"])
    inputs = deepcopy((orders, shops, queues))
    first = session.handle("request", TODAY, orders, shops, queues)
    second = session.handle("request", TODAY, orders, shops, queues)
    assert first.decision_record["chosen_workshop"] != second.decision_record["chosen_workshop"]
    assert sum(session.allocator.pieces_by_workshop.values()) == 200
    assert first.decision_record["tool_outputs"]["split"]["faster"]
    assert "no split has been committed" in first.explanation_text
    pd.testing.assert_frame_equal(orders, inputs[0])
    assert (shops, queues) == inputs[1:]


def test_faithfulness_failure_cannot_commit_state(data, parsed, monkeypatch):
    parsed()
    session = agent.Agent(PRESETS["lateness"])
    original = agent._choice_text
    monkeypatch.setattr(agent, "_choice_text", lambda *a, **kw: original(*a, **kw) + " Guaranteed savings 987654321.")
    with pytest.raises(ValueError, match="unsupported numbers"):
        session.handle("request", TODAY, *data)
    assert session.allocator.pieces_by_workshop == {}


def test_constraint_authorship_survives_response(data, parsed):
    statements = [{"text": "Boss says nothing new to QuickStitch", "imposed_by": "Boss", "relayed_by": "Ravi"}]
    parsed(sender="Ravi", excluded_workshops=["W1"], constraints=statements)
    result = agent.handle("request", TODAY, *data, PRESETS["lateness"])
    assert result.decision_record["constraints_applied"]["statements"] == statements


def test_date_conflict_is_shown_and_backed_by_evidence(data, parsed):
    parsed(due_date=date(2026, 6, 1), date_conflict={"message_due": "2026-06-01", "file_due": "2026-04-05"})
    result = agent.Agent(PRESETS["lateness"]).handle("request", TODAY, *data)
    assert "DATE CHECK" in result.explanation_text and "2026-04-05" in result.explanation_text
    assert result.decision_record["tool_outputs"]["date_check"]["file_due"] == "2026-04-05"
    assert result.faithfulness["passed"]
