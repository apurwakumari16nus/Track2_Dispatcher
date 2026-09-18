import json

import pytest

from faithfulness import check


@pytest.fixture
def record():
    return {"candidates": [{"workshop_id": "W2", "total_days": 2.5,
        "days_to_spare": -3, "eta_date": "2026-04-09", "total_cost": 1200.0,
        "cost_per_piece": 0.75, "expected_defect_rate": 0.05}],
        "ineligible": [{"workshop_id": "W8", "reason": "batch of 400 exceeds 300-piece cap"}],
        "tool_outputs": {"queue": {"queue_after": 4.25}},
        "timestamp": "2099-01-01", "reason_chosen": "Invented saving 99999",
        "constraints_applied": {"raw_text": "cost 88888"}}


def test_numbers_dates_money_rates_ids_and_queue_are_supported(record):
    text = "W2: 2.50 days; spare -3 days; ETA 2026-04-09; $1,200.00; per piece .75; defects 5%; queue 4.25. W8 cap 300."
    result = check(text, record)
    assert result["passed"] and result["unmatched"] == []
    assert "$1,200.00" in result["numbers_in_text"]
    assert "2026-04-09" in result["numbers_in_text"]


@pytest.mark.parametrize("claim", ["99999", "88888", "2099-01-01", "2026-04-10", "W9", "3", "2", "2026", "2.51", "50%"])
def test_invented_numbers_and_metadata_do_not_authorize_claims(record, claim):
    result = check(f"Claim {claim}", record)
    assert not result["passed"] and result["unmatched"] == [claim]


def test_dates_atomic_and_english_dates_normalized(record):
    assert check("April 9, 2026", record)["passed"]
    assert check("9 Apr 2026", record)["passed"]
    assert not check("April 10, 2026", record)["passed"]
    assert not check("Apr 9", record)["passed"]
    assert check("09/04/2026", {"candidates": [{"a": 9, "b": 4, "c": 2026}]})["unmatched"] == ["09/04/2026"]


def test_signed_scientific_numbers_and_booleans():
    record = {"tool_outputs": {"small": 0.00001, "negative": -4, "allowed": True}}
    assert check("1e-5 and −4", record)["passed"]
    assert not check("1", record)["passed"]
    assert not check("4", record)["passed"]


def test_no_numbers_is_vacuously_supported_and_json_input_works(record):
    assert check("Please confirm the order.", record) == {"passed": True, "numbers_in_text": [], "unmatched": []}
    assert check("$1200", json.dumps(record))["passed"]


def test_real_number_with_wrong_meaning_is_outside_numeric_check_scope(record):
    # This deliberately passes: membership is not decision/semantic correctness.
    assert check("The defect probability is 1200.", record)["passed"]
