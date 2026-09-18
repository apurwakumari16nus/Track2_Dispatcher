"""Check metric fidelity, complete comparisons, and the runnable evaluation bundle."""

from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import sys

import pandas as pd

from objectives import PRESETS, ObjectiveConfig
from simulate import Simulator

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_simulator", ROOT / "eval/run_simulator.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_metrics_match_hand_calculation_and_report_output():
    # Descending durations expose the distinction from interpolated p90. Pieces
    # deliberately differ: W2's piece share is 95%, but its batch share is 50%.
    outcomes = [{"turnaround": float(10 - i), "late": i < 3, "defective": i < 2,
                 "cost": float(i + 1), "pieces": 910 if i == 9 else 10,
                 "workshop": "W1" if i < 5 else "W2"} for i in range(10)]
    metrics = runner.summarize_outcomes(outcomes)
    assert metrics == {"mean_days": 5.5, "p90_days": 10.0, "pct_late": 30.0,
                       "pct_defect": 20.0, "total_cost": 55.0, "max_share": 95.0}
    sim = Simulator()
    sim.results = {"hand_case": outcomes}
    captured = io.StringIO()
    with redirect_stdout(captured):
        sim.report()
    line = (f"{'hand_case':<16}{metrics['mean_days']:>10.1f}{metrics['p90_days']:>10.1f}"
            f"{metrics['pct_late']:>7.0f}%{metrics['pct_defect']:>9.0f}%"
            f"{metrics['total_cost']:>12,.0f}{metrics['max_share']:>10.0f}%")
    assert captured.getvalue().splitlines()[-1] == line


def test_mean_uses_sorted_python_sum_and_retains_unrounded_rates():
    outcomes = [{"turnaround": value, "late": i == 0, "defective": i == 0,
                 "cost": 1.0, "pieces": 1, "workshop": "W1"}
                for i, value in enumerate([1e16, 1.0, 1.0])]
    result = runner.summarize_outcomes(outcomes)
    assert result["mean_days"] == sum([1.0, 1.0, 1e16]) / 3
    assert result["pct_late"] == result["pct_defect"] == 100 / 3


def test_matrix_uses_every_preset_fresh_state_and_matches_real_report(monkeypatch):
    # A newly added preset must be discovered automatically, without a hardcoded
    # policy list or reused state. Compare formatted metrics to the real harness.
    monkeypatch.setitem(PRESETS, "new_preset", ObjectiveConfig(w_lateness=1, name="new_preset"))
    original_run = Simulator.run
    reports = {}

    def capture_report(self, policy, name):
        out = original_run(self, policy, name)
        captured = io.StringIO()
        with redirect_stdout(captured):
            self.report()
        reports[(self.shock, name)] = captured.getvalue().splitlines()[-1]
        return out

    monkeypatch.setattr(Simulator, "run", capture_report)
    first = runner.run_evaluation()
    assert list(first.columns) == runner.COLUMNS
    assert len(first) == 2 * (4 + len(PRESETS))
    assert not first.isna().any().any()
    assert not first.duplicated(["policy", "objective", "shock"]).any()
    for shock in (False, True):
        group = first[first["shock"] == shock]
        assert set(group[group["policy"] == "allocator"]["objective"]) == set(PRESETS)
        assert set(group[group["objective"] == "none"]["policy"]) == set(runner.BASELINES)
    for row in first.to_dict("records"):
        name = runner.label(row)
        line = (f"{name:<16}{row['mean_days']:>10.1f}{row['p90_days']:>10.1f}"
                f"{row['pct_late']:>7.0f}%{row['pct_defect']:>9.0f}%"
                f"{row['total_cost']:>12,.0f}{row['max_share']:>10.0f}%")
        assert reports[(row["shock"], name)] == line
    pd.testing.assert_frame_equal(first, runner.run_evaluation())


def test_report_enumerates_each_win_and_preserves_ties():
    rows = []
    for policy, objective, mean, cost in [
        ("random_choice", "none", 5, 50), ("earliest_finish", "none", 3, 70),
        ("allocator", "fast", 3, 80), ("allocator", "cheap", 10, 50),
    ]:
        rows.append({"policy": policy, "objective": objective, "shock": False,
                     **dict.fromkeys(runner.METRICS, 5.0), "mean_days": float(mean),
                     "total_cost": float(cost)})
    frame = pd.DataFrame(rows)
    winners, wins, ties = runner.comparison_tables(frame)
    assert set(wins[["metric", "baseline_or_heuristic", "allocator_objective"]]
               .itertuples(index=False, name=None)) == {
        ("mean_days", "random_choice", "cheap"), ("mean_days", "earliest_finish", "cheap"),
        ("total_cost", "random_choice", "fast"), ("total_cost", "earliest_finish", "fast"),
    }
    assert set(wins["improvement"]) == {5, 7, 30, 10}
    best_mean = winners[winners["metric"] == "mean_days"].iloc[0]
    assert best_mean["best_policy_or_objective"] == "earliest_finish, allocator:fast"
    assert best_mean["best_value"] == 3
    assert len(ties) == 22  # five unchanged metrics (including fairness), plus two ties
    # A difference hidden by two-decimal display rounding must still be a win.
    frame.loc[0, "pct_late"] = 4.9999
    _, wins, _ = runner.comparison_tables(frame)
    assert len(wins[wins["metric"] == "pct_late"]) == 2
    assert runner.tied(1.0, 1.0 + 1e-14)
    assert not runner.tied(1.0, 1.0001)
    frame.loc[2, "max_share"] = 7.0
    frame.loc[3, "max_share"] = 9.0
    winners, wins, _ = runner.comparison_tables(frame)
    fairness_wins = wins[wins["metric"] == "fairness"]
    assert len(fairness_wins) == 4
    assert set(fairness_wins["improvement"]) == {2, 4}
    assert winners[winners["metric"] == "fairness"].iloc[0]["best_value"] == 95


def test_cli_from_other_directory_writes_csv_report_and_matplotlib_charts(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "eval/run_simulator.py"), "--output-dir", str(tmp_path / "bundle")],
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    destination = tmp_path / "bundle"
    csv = pd.read_csv(destination / "results.csv", keep_default_na=False)
    pd.testing.assert_frame_equal(csv, runner.run_evaluation(), check_exact=False, rtol=1e-14)
    assert "| policy | objective | shock |" in completed.stdout
    report = (destination / "baseline_wins.md").read_text()
    assert report in completed.stdout
    assert "earliest_finish ties allocator preset(s) **lateness** on all six metrics" in report
    assert "### Normal:" in report and "### Shock:" in report
    assert "Input and implementation fingerprints" in report
    from PIL import Image
    for name in ["lateness_by_policy.png", "tradeoff_lateness_vs_cost.png", "tradeoff_lateness_vs_fairness.png"]:
        with Image.open(destination / "charts" / name) as image:
            image.verify()
        assert (destination / "charts" / name).stat().st_size > 10000
