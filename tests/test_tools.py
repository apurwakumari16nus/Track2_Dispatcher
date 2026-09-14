"""Check allocation estimates against the harness rules and hand calculations."""

import copy
import json
import random
from dataclasses import replace
from datetime import date

import pytest

from simulate import eligible_workshops, load_batches, load_workshops
from tools import (
    candidates,
    check_eligibility,
    estimate_cost,
    estimate_eta,
    overload_probe,
    queue_check,
)


@pytest.fixture
def workshops():
    return load_workshops()


@pytest.fixture
def queues(workshops):
    return {workshop_id: workshop.queue0 for workshop_id, workshop in workshops.items()}


@pytest.fixture
def batch():
    return {
        "order_id": "HAND-CHECK",
        "category": "TOPS",
        "pieces": 340,
        "sent_date": date(2026, 4, 1),
        "due_date": date(2026, 4, 10),
    }


@pytest.mark.parametrize(
    "batch", random.Random(5105).sample(load_batches(), 10), ids=lambda batch: batch["order_id"]
)
def test_eligibility_matches_simulator_for_random_orders(batch, workshops):
    results = check_eligibility(batch, workshops)

    assert len(results) == len(workshops)
    assert {result["workshop_id"] for result in results} == set(workshops)
    assert {result["workshop_id"] for result in results if result["eligible"]} == {
        workshop.workshop_id for workshop in eligible_workshops(batch, workshops)
    }
    assert all(result["reason"] == "ok" for result in results if result["eligible"])


def test_oldmill_is_never_eligible(workshops):
    for batch in load_batches():
        result = next(
            result for result in check_eligibility(batch, workshops)
            if result["workshop_id"] == "W7"
        )
        assert result == {
            "workshop_id": "W7", "name": "OldMill", "eligible": False, "reason": "suspended"
        }


@pytest.mark.parametrize("pieces", [301, 340, 1200, 10000])
def test_freshstart_rejects_batches_over_300(batch, workshops, pieces):
    batch["pieces"] = pieces
    result = next(
        result for result in check_eligibility(batch, workshops)
        if result["workshop_id"] == "W8"
    )

    assert result == {
        "workshop_id": "W8", "name": "FreshStart", "eligible": False,
        "reason": f"batch of {pieces} exceeds 300-piece cap",
    }


def test_freshstart_accepts_exactly_300_tops(batch, workshops):
    batch["pieces"] = 300
    result = next(
        result for result in check_eligibility(batch, workshops)
        if result["workshop_id"] == "W8"
    )

    assert result["eligible"] is True
    assert result["reason"] == "ok"


def test_little_loom_cannot_make_tops(batch, workshops):
    result = next(
        result for result in check_eligibility(batch, workshops)
        if result["workshop_id"] == "W4"
    )

    assert result == {
        "workshop_id": "W4", "name": "Little Loom", "eligible": False,
        "reason": "cannot make TOPS",
    }


def test_eligibility_reason_follows_simulator_rule_order(batch, workshops):
    # FreshStart violates both category and size constraints; category wins.
    batch["category"] = "ACCESSORIES"
    results = {result["workshop_id"]: result for result in check_eligibility(batch, workshops)}

    assert results["W8"]["reason"] == "cannot make ACCESSORIES"
    assert results["W7"]["reason"] == "suspended"


@pytest.mark.parametrize("iso_dates", [False, True])
def test_eta_matches_hand_calculation(batch, workshops, queues, iso_dates):
    today = date(2026, 4, 1)
    if iso_dates:
        today = today.isoformat()
        batch["due_date"] = batch["due_date"].isoformat()

    # SteadyHands: 340 / 170 = 2 processing days; 2.5 + 2 + 2 = 6.5.
    # Python round(6.5) = 6, giving April 7 and three days before April 10.
    assert estimate_eta(batch, "W2", workshops, queues, today) == {
        "workshop_id": "W2",
        "queue_days": 2.5,
        "processing_days": 2.0,
        "lead_days": 2,
        "total_days": 6.5,
        "eta_date": "2026-04-07",
        "due_date": "2026-04-10",
        "days_to_spare": 3,
        "expected_defect_rate": 0.03,
    }


def test_eta_rounds_half_to_even_and_reports_lateness(batch, workshops, queues):
    queues["W2"] = 3.5
    batch["due_date"] = date(2026, 4, 8)

    result = estimate_eta(batch, "W2", workshops, queues, date(2026, 4, 1))

    # 3.5 + 2 + 2 = 7.5, rounded to eight days; one day late.
    assert result["total_days"] == 7.5
    assert result["eta_date"] == "2026-04-09"
    assert result["days_to_spare"] == -1


def test_queue_check_uses_live_queue(workshops, queues):
    queues["W1"] = 9.25

    assert queue_check("W1", workshops, queues) == {
        "workshop_id": "W1", "queue_days": 9.25, "capacity_per_day": 300, "lead_days": 1
    }


def test_cost_matches_hand_calculation(batch, workshops):
    assert estimate_cost(batch, "W2", workshops) == {
        "workshop_id": "W2", "cost_per_piece": 1.3, "total_cost": 442.0
    }


def test_overload_adds_processing_but_not_transport_to_queue(batch, workshops, queues):
    batch["pieces"] = 600
    queues["W1"] = 3.25

    assert overload_probe(batch, "W1", workshops, queues) == {
        "workshop_id": "W1", "queue_before": 3.25, "queue_after": 5.25,
        "delay_added_to_next_batch_days": 2.0,
    }


def test_candidates_merge_details_and_sort_eligible_workshops(batch, workshops, queues):
    batch["pieces"] = 200
    today = date(2026, 4, 1)
    results = candidates(batch, workshops, queues, today)

    assert [result["workshop_id"] for result in results] == ["W6", "W8", "W1", "W2", "W5", "W3"]
    eligibility = {result["workshop_id"]: result for result in check_eligibility(batch, workshops)}
    for result in results:
        workshop_id = result["workshop_id"]
        assert result == {
            **eligibility[workshop_id],
            **estimate_eta(batch, workshop_id, workshops, queues, today),
            **estimate_cost(batch, workshop_id, workshops),
        }


def test_candidates_exclude_names_and_ids_case_insensitively(batch, workshops, queues):
    batch["pieces"] = 200
    results = candidates(
        batch, workshops, queues, "2026-04-01", exclude=[" nimble NEEDLE ", " w8 "]
    )

    assert [result["workshop_id"] for result in results] == ["W1", "W2", "W5", "W3"]


def test_candidates_preserve_workshop_order_for_equal_times(batch, workshops):
    tied = {
        "W2": replace(workshops["W2"], capacity=100, lead_days=2),
        "W1": replace(workshops["W1"], capacity=100, lead_days=2),
    }
    results = candidates(batch, tied, {"W1": 0.0, "W2": 0.0}, "2026-04-01")

    assert [result["workshop_id"] for result in results] == ["W2", "W1"]


def test_candidates_return_empty_when_no_workshop_is_eligible(batch, workshops, queues):
    batch["category"] = "UNSUPPORTED"

    assert candidates(batch, workshops, queues, "2026-04-01") == []


def test_all_tools_are_json_serializable_and_leave_inputs_unchanged(batch, workshops, queues):
    exclude = ["W3"]
    before = copy.deepcopy((batch, workshops, queues, exclude))
    results = [
        check_eligibility(batch, workshops),
        queue_check("W2", workshops, queues),
        estimate_eta(batch, "W2", workshops, queues, date(2026, 4, 1)),
        estimate_cost(batch, "W2", workshops),
        overload_probe(batch, "W2", workshops, queues),
        candidates(batch, workshops, queues, date(2026, 4, 1), exclude),
    ]

    assert json.loads(json.dumps(results)) == results
    assert (batch, workshops, queues, exclude) == before


@pytest.mark.parametrize("tool", [queue_check, estimate_eta, estimate_cost, overload_probe])
def test_unknown_workshop_raises_key_error(tool, batch, workshops, queues):
    with pytest.raises(KeyError):
        if tool is queue_check:
            tool("UNKNOWN", workshops, queues)
        elif tool is estimate_cost:
            tool(batch, "UNKNOWN", workshops)
        elif tool is estimate_eta:
            tool(batch, "UNKNOWN", workshops, queues, "2026-04-01")
        else:
            tool(batch, "UNKNOWN", workshops, queues)


@pytest.mark.parametrize("tool", [queue_check, estimate_eta, overload_probe])
def test_missing_live_queue_raises_instead_of_using_starting_queue(tool, batch, workshops):
    with pytest.raises(KeyError):
        if tool is queue_check:
            tool("W2", workshops, {})
        elif tool is estimate_eta:
            tool(batch, "W2", workshops, {}, "2026-04-01")
        else:
            tool(batch, "W2", workshops, {})


@pytest.mark.parametrize("tool", [estimate_eta, overload_probe])
def test_zero_capacity_raises_zero_division_error(tool, batch, workshops, queues):
    workshops["W2"] = replace(workshops["W2"], capacity=0)

    with pytest.raises(ZeroDivisionError):
        if tool is estimate_eta:
            tool(batch, "W2", workshops, queues, "2026-04-01")
        else:
            tool(batch, "W2", workshops, queues)
