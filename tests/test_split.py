from copy import deepcopy
from dataclasses import replace
from datetime import date
from itertools import combinations

import pytest

from simulate import load_workshops
from tools import candidates, estimate_split

TODAY = date(2026, 4, 1)


@pytest.fixture
def case():
    source = load_workshops()
    shops = {wid: replace(source[wid], capacity=100, lead_days=2, max_batch=None) for wid in ("W1", "W2")}
    batch = {"order_id": "TEST", "category": "TOPS", "pieces": 1000, "due_date": date(2026, 5, 1), "sent_date": TODAY}
    return batch, shops, {"W1": 0.0, "W2": 0.0}


def test_parallel_split_by_hand_includes_both_leads_without_adding_elapsed_times(case):
    batch, shops, queues = case
    before = deepcopy(case)
    result = estimate_split(*case, TODAY)
    assert [part["pieces"] for part in result["parts"]] == [500, 500]
    assert [part["lead_days"] for part in result["parts"]] == [2, 2]
    assert result["total_days"] == 7 and result["single"]["total_days"] == 12
    assert result["eta_date"] == "2026-04-08" and result["days_saved"] == 5
    assert result["total_cost"] == 500 * shops["W1"].cost + 500 * shops["W2"].cost
    assert result["faster"] and result["earlier_eta"]
    assert case == before


def test_split_can_be_slower_when_other_shop_is_busy(case):
    batch, shops, queues = case
    queues["W2"] = 30
    result = estimate_split(*case, TODAY)
    assert not result["faster"] and result["days_saved"] < 0


def test_caps_allow_split_when_no_whole_batch_shop_is_eligible(case):
    batch, shops, queues = case
    shops.update({wid: replace(w, max_batch=600) for wid, w in shops.items()})
    result = estimate_split(*case, TODAY)
    assert result["available"] and result["single"] is None
    assert sum(part["pieces"] for part in result["parts"]) == 1000
    assert all(0 < part["pieces"] <= 600 for part in result["parts"])
    batch["pieces"] = 1300
    assert not estimate_split(*case, TODAY)["available"]


def test_exclusions_suspension_category_and_single_piece(case):
    batch, shops, queues = case
    assert not estimate_split(*case, TODAY, exclude=["SteadyHands"])["available"]
    shops["W2"] = replace(shops["W2"], status="SUSPENDED")
    assert not estimate_split(*case, TODAY)["available"]
    shops["W2"] = replace(shops["W2"], status="ACTIVE", makes={"ACCESSORIES"})
    assert not estimate_split(*case, TODAY)["available"]
    batch["pieces"] = 1
    assert not estimate_split(*case, TODAY)["available"]


def test_optimizer_matches_exhaustive_legal_integer_search(case):
    batch, shops, queues = case
    source = load_workshops()
    shops["W3"] = replace(source["W3"], capacity=7, lead_days=2, max_batch=11)
    shops["W1"] = replace(shops["W1"], capacity=3, max_batch=13)
    shops["W2"] = replace(shops["W2"], capacity=11, lead_days=1, max_batch=19)
    queues.update(W1=0.5, W2=4.25, W3=1)
    for pieces in range(2, 36):
        batch["pieces"] = pieces
        brute = []
        for a, b in combinations(shops, 2):
            for x in range(1, pieces):
                left = candidates({**batch, "pieces": x}, {a: shops[a]}, queues, TODAY)
                right = candidates({**batch, "pieces": pieces-x}, {b: shops[b]}, queues, TODAY)
                if left and right:
                    brute.append(max(left[0]["total_days"], right[0]["total_days"]))
        result = estimate_split(*case, TODAY)
        assert result["available"] == bool(brute)
        if brute:
            assert result["total_days"] == pytest.approx(min(brute))
