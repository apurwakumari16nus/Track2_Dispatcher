"""Exercise simulator compatibility, auditable scores and decision constraints."""

import copy
import json
from dataclasses import asdict, replace
from datetime import date

import pytest
import yaml

from allocator import Allocator, DecisionRecord
from heuristic import earliest_finish
from objectives import ObjectiveConfig, PRESETS, load_config, score_candidate, score_terms
from simulate import Simulator, eligible_workshops, load_workshops
from tools import ShockMonitor


@pytest.fixture
def workshops():
    source = load_workshops()
    return {
        "W1": replace(source["W1"], capacity=100, lead_days=1, defect_rate=0.2, cost=1.0),
        "W2": replace(source["W2"], capacity=100, lead_days=1, defect_rate=0.01, cost=2.0),
    }


@pytest.fixture
def queues():
    return {"W1": 0.0, "W2": 5.0}


@pytest.fixture
def batch():
    # W1 needs 2 days and finishes Apr 3; W2 needs 7 and finishes Apr 8.
    return {
        "order_id": "TEST-001", "category": "TOPS", "pieces": 100,
        "sent_date": date(2026, 4, 1), "due_date": date(2026, 4, 5),
    }


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("shock", [False, True])
def test_allocator_runs_simulator_without_illegal_choices_and_logs_json(preset, shock):
    sim = Simulator(shock=shock)
    allocator = Allocator(PRESETS[preset])
    records = []

    def policy(batch, workshops, queues):
        chosen = allocator(batch, workshops, queues)
        assert chosen in {w.workshop_id for w in eligible_workshops(batch, workshops)}
        records.append(asdict(allocator.last_decision))
        return chosen

    outcomes = sim.run(policy, name=preset)

    assert len(outcomes) == len(records) == len(sim.batches)
    assert sum(allocator.pieces_by_workshop.values()) == sum(b["pieces"] for b in sim.batches)
    assert json.loads(json.dumps(records, allow_nan=False)) == records
    assert all(record["objective_name"] == preset for record in records)


def test_score_terms_and_weighting_match_hand_calculation(workshops):
    cand = {
        "workshop_id": "W1", "days_to_spare": -30, "total_days": 30.0,
        "expected_defect_rate": 0.1, "cost_per_piece": 1.0,
    }
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 0.0, 0)
    monitor.observe({"W1": 4.0}, 0)
    state = {
        "workshops": workshops,
        "pieces_by_workshop": {"W1": 25, "W2": 75},
        "shock_monitor": monitor,
    }
    before = copy.deepcopy((cand, workshops, state["pieces_by_workshop"], monitor.__dict__))

    # Half-saturation at 30 days; quarter share; flagged robustness is 0.85.
    assert score_terms(cand, state) == pytest.approx({
        "lateness": 0.505, "defect": 0.1, "fairness": 0.25,
        "robustness": 0.85, "cost": 0.5,
    })
    all_weights = ObjectiveConfig(1, 1, 1, 1, 1)
    assert score_candidate(cand, all_weights, state) == pytest.approx(2.205)
    # Hybrid preset 0.9 lateness + 0.1 fairness: 0.9 * 0.505 + 0.1 * 0.25.
    assert score_candidate(cand, PRESETS["hybrid_lateness_fairness"], state) == pytest.approx(0.4795)
    assert (cand, workshops, state["pieces_by_workshop"], monitor.__dict__) == before


def test_cost_scale_includes_ineligible_workshops_and_handles_zero_prices(workshops):
    workshops["W7"] = replace(workshops["W1"], workshop_id="W7", status="SUSPENDED", cost=4.0)
    cand = {
        "workshop_id": "W1", "days_to_spare": 3, "total_days": 2.0,
        "expected_defect_rate": 0.2, "cost_per_piece": 1.0,
    }
    state = {"workshops": workshops}
    config = ObjectiveConfig(w_cost=1)
    assert score_candidate(cand, config, state) == 0.25

    state["workshops"] = {wid: replace(w, cost=0.0) for wid, w in workshops.items()}
    cand["cost_per_piece"] = 0.0
    assert score_candidate(cand, config, state) == 0.0


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".yml"])
def test_load_config_from_inspectable_file(tmp_path, suffix):
    path = tmp_path / f"my_hybrid{suffix}"
    path.write_text(
        '{"w_lateness": 0.7, "w_fairness": 0.3}' if suffix == ".json"
        else "w_lateness: 0.7\nw_fairness: 0.3\n",
        encoding="utf-8",
    )

    assert load_config(path) == ObjectiveConfig(
        w_lateness=0.7, w_fairness=0.3, name="my_hybrid"
    )


def test_load_config_preserves_explicit_name(tmp_path):
    path = tmp_path / "objective.json"
    path.write_text(json.dumps(asdict(PRESETS["defect"])), encoding="utf-8")
    assert load_config(path) == PRESETS["defect"]


@pytest.mark.parametrize("contents", ['{"w_latness": 1}', '[]', '{"w_cost": -1}'])
def test_invalid_config_file_is_rejected(tmp_path, contents):
    path = tmp_path / "bad.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_yaml_loader_rejects_python_object_tags(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("!!python/tuple [1, 2]", encoding="utf-8")
    with pytest.raises(yaml.constructor.ConstructorError):
        load_config(path)


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True, "high"])
def test_invalid_weights_are_rejected(value):
    with pytest.raises(ValueError, match="w_lateness"):
        ObjectiveConfig(w_lateness=value)


def test_zero_weight_config_falls_back_to_speed(batch, workshops, queues):
    allocator = Allocator(ObjectiveConfig())
    assert allocator(batch, workshops, queues) == "W1"
    assert all(cand["score"] == 0.0 for cand in allocator.last_decision.candidates)


def test_date_constraint_overrides_defect_preference_but_retains_all_candidates(batch, workshops, queues):
    unconstrained = Allocator(PRESETS["defect"]).decide(batch, workshops, queues, "2026-04-01")
    constrained = Allocator(PRESETS["defect"]).decide(
        batch, workshops, queues, "2026-04-01", must_make_date=True
    )

    assert unconstrained.chosen_workshop == "W2"
    assert unconstrained.awkward_case is None  # W1 can make the date.
    assert constrained.chosen_workshop == "W1"
    assert constrained.constraints_applied["date_constraint_satisfied"] is True
    assert {row["workshop_id"] for row in constrained.candidates} == {"W1", "W2"}
    assert constrained.candidates[0]["workshop_id"] == "W2"  # Lowest score, but late.


@pytest.mark.parametrize("must_make_date", [False, True])
def test_all_late_chooses_least_late_even_when_objective_prefers_another(batch, workshops, queues, must_make_date):
    batch["due_date"] = date(2026, 4, 2)
    record = Allocator(PRESETS["defect"]).decide(
        batch, workshops, queues, batch["sent_date"], must_make_date=must_make_date
    )

    assert record.awkward_case == "none_makes_date"
    assert record.chosen_workshop == "W1"
    assert record.constraints_applied["date_constraint_satisfied"] is False
    assert record.options[0] == {"action": "accept_lateness", "workshop_id": "W1", "days_late": 1}
    assert record.options[1]["action"] == "consider_split"
    assert "Least-late fallback" in record.reason_chosen
    assert json.loads(json.dumps(record.to_dict(), allow_nan=False)) == asdict(record)


def test_no_eligible_returns_escalation_and_does_not_allocate(batch, workshops, queues):
    batch["category"] = "UNSUPPORTED"
    allocator = Allocator(PRESETS["lateness"])
    allocator.pieces_by_workshop["W1"] = 50
    record = allocator.decide(batch, workshops, queues, batch["sent_date"])

    assert isinstance(record, DecisionRecord)
    assert record.awkward_case == "no_eligible"
    assert record.chosen_workshop is None
    assert record.candidates == []
    assert {row["reason"] for row in record.ineligible} == {"cannot make UNSUPPORTED"}
    assert record.options[0]["action"] == "escalate"
    assert allocator.pieces_by_workshop == {"W1": 50}
    assert json.loads(json.dumps(record.to_dict(), allow_nan=False)) == asdict(record)
    with pytest.raises(ValueError, match="No eligible workshop"):
        allocator(batch, workshops, queues)


def test_exclusions_by_name_and_id_can_leave_no_candidates(batch, workshops, queues):
    allocator = Allocator(PRESETS["lateness"])
    exclude = [" quickSTITCH ", " w2 "]
    record = allocator.decide(batch, workshops, queues, "2026-04-01", exclude=exclude)

    assert record.awkward_case == "no_eligible"
    assert record.ineligible == []  # Both shops meet the profile rules.
    assert record.constraints_applied["exclude"] == exclude
    assert allocator.pieces_by_workshop == {}


def test_fairness_uses_history_before_committing_the_batch_once(batch, workshops, queues):
    batch["due_date"] = date(2026, 4, 20)
    allocator = Allocator(PRESETS["fairness"])
    allocator.pieces_by_workshop.update({"W1": 900, "W2": 100})

    assert allocator(batch, workshops, queues) == "W2"
    record = allocator.last_decision
    assert allocator.pieces_by_workshop == {"W1": 900, "W2": 200}
    assert record.candidates[0]["score_terms"]["fairness"] == 0.1
    saved_record = record.to_dict()
    allocator(batch, workshops, queues)
    assert record.to_dict() == saved_record
    assert Allocator(PRESETS["fairness"]).pieces_by_workshop == {}


def test_shock_flag_steers_robustness_without_changing_eligibility(batch, workshops, queues):
    batch["due_date"] = date(2026, 4, 20)
    allocator = Allocator(PRESETS["robustness"])
    allocator.shock_monitor.record_allocation("W1", 0.0, 0)
    queues["W1"] = 4.0
    record = allocator.decide(batch, workshops, queues, batch["sent_date"])

    assert record.chosen_workshop == "W2"
    assert record.ineligible == []
    assert {row["workshop_id"] for row in record.candidates} == {"W1", "W2"}
    assert allocator.shock_monitor.is_flagged("W1")
    assert record.shock_flags[0]["workshop_id"] == "W1"
    assert record.shock_events[0]["status"] == "suspect"


def test_replays_are_identical_and_inputs_are_not_mutated(batch, workshops, queues):
    before = copy.deepcopy((batch, workshops, queues))
    first = Allocator(PRESETS["hybrid_lateness_fairness"])
    second = Allocator(PRESETS["hybrid_lateness_fairness"])

    for _ in range(3):
        left = first.decide(batch, workshops, queues, batch["sent_date"])
        right = second.decide(batch, workshops, queues, "2026-04-01")
        assert left.to_dict() == right.to_dict()
        assert left.timestamp == "2026-04-01T00:00:00"
    assert (batch, workshops, queues) == before


def test_earliest_finish_respects_all_eligibility_rules(batch, workshops, queues):
    for wid, overrides in (
        ("W7", {"status": "SUSPENDED"}),
        ("W8", {"max_batch": 50}),
        ("W4", {"makes": {"ACCESSORIES"}}),
    ):
        workshops[wid] = replace(
            workshops["W1"], workshop_id=wid, capacity=1000, lead_days=0, **overrides
        )
        queues[wid] = 0.0

    assert earliest_finish(batch, workshops, queues) == "W1"
    batch["category"] = "UNSUPPORTED"
    with pytest.raises(ValueError, match="No eligible workshop"):
        earliest_finish(batch, workshops, queues)
