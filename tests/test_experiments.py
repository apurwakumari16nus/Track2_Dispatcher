"""Dashboard evidence must agree with the original evaluation, including replays."""
import pandas as pd
import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest

from experiments import run_experiment, decision_replay
from run_simulator import run_evaluation, summarize_outcomes
from objectives import PRESETS

ROOT = Path(__file__).resolve().parents[1]


def test_experiment_matches_evaluator_and_outcomes_reconstruct_metrics():
    bundle = run_experiment(5105)
    pd.testing.assert_frame_equal(bundle["summary"], run_evaluation(5105))
    assert len(bundle["outcomes"]) == bundle["batch_count"] * len(bundle["summary"])
    for row in bundle["summary"].to_dict("records"):
        out = bundle["outcomes"]
        selected = out[(out["policy"] == row["policy"]) & (out["objective"] == row["objective"]) & (out["shock"] == row["shock"])]
        assert selected["order_id"].nunique() == bundle["batch_count"]
        for metric, value in summarize_outcomes(selected.to_dict("records")).items():
            assert row[metric] == value


@pytest.mark.parametrize("shock", [False, True])
def test_audit_replay_matches_automatic_choices(shock):
    bundle = run_experiment(42)
    for objective in PRESETS:
        decisions = decision_replay(42, objective, shock)
        outcomes = bundle["outcomes"]
        selected = outcomes[(outcomes["policy"] == "allocator") & (outcomes["objective"] == objective) & (outcomes["shock"] == shock)]
        assert {r.order_id: r.workshop for r in selected.itertuples()} == {
            order: decision["chosen_workshop"] for order, decision in decisions.items()
        }


def test_dashboard_default_seed_controls_and_page_navigation():
    app = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.radio(key="desk_page").value == "Simulation"
    assert len(app.get("vega_lite_chart")) == 5
    assert app.session_state["desk_saved"] == {}
    app.number_input(key="lab_seed").set_value(42).run()
    assert app.session_state["lab_bundle"]["seed"] == 5105
    app.button(key="lab_run").click().run()
    assert not app.exception
    assert app.session_state["lab_bundle"]["seed"] == 42
    app.selectbox(key="lab_focus").set_value("fairness").run()
    app.radio(key="lab_scenario").set_value("Shock").run()
    assert not app.exception
    app.radio(key="desk_page").set_value("Dispatch").run()
    assert not app.exception
    app.radio(key="desk_page").set_value("Simulation").run()
    assert not app.exception
    assert app.session_state["lab_bundle"]["seed"] == 42
    assert app.number_input(key="lab_seed").value == 42
    assert app.selectbox(key="lab_focus").value == "fairness"
    assert app.radio(key="lab_scenario").value == "Shock"
    assert app.session_state["desk_saved"] == {}
