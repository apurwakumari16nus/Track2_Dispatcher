"""Choose the lateness/fairness hybrid weights with a pre-declared rule.

Sweeps the fairness share f over 0.0, 0.1, ... 1.0 with w_lateness = 1 - f and
w_fairness = f (the 0-1 scaled terms in objectives.py), using the unchanged
shared simulator, normal and --shock, averaged over paired seeds. No LLM calls.

SELECTION RULE (written before the first run; do not edit after seeing results):
  Using the NORMAL runs on the TUNING seeds only, a fairness share f is eligible when
    1. % late <= (% late at f = 0, lateness only) + TOLERANCE_PP percentage points,
    2. % late <= random's % late, and
    3. max share <= random's max share (the hybrid must beat random on both).
  Choose the eligible f with the lowest max share (ties: the smaller f).
  TOLERANCE_PP is 5.0: we accept about six extra late batches in 120 for a more even
  spread of work. Other tolerances are shown only as a sensitivity check.

HONESTY NOTE: separate seeds change only the defect draws and which workshop closes.
The 120 orders are the same ones used in development, so this is NOT an unseen-data
test. Choose f on the tuning seeds, then report the chosen f on the course seeds
(5105-5114) with --fixed-fairness, and say so.

Usage:
  python eval/run_hybrid_sweep.py --seed 6105 --output-dir eval/hybrid_sweep/tuning
  python eval/run_hybrid_sweep.py --seed 5105 --fixed-fairness 0.3 \
         --output-dir eval/hybrid_sweep/reporting
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "harness"), str(PROJECT_ROOT / "eval")]

from allocator import Allocator
from objectives import ObjectiveConfig
from run_simulator import BASELINES, METRICS, markdown_table, summarize_outcomes
from simulate import Simulator

TOLERANCE_PP = 5.0
GRID = [round(i / 10, 1) for i in range(11)]
SHOWN = ["pct_late", "late_days", "max_share", "pct_defect_pieces", "total_cost"]


def hybrid_config(fairness: float) -> ObjectiveConfig:
    return ObjectiveConfig(w_lateness=round(1 - fairness, 6), w_fairness=fairness,
                           name=f"hybrid_f{fairness:.1f}")


def run_sweep(seed: int, seeds: int, grid: list[float]) -> pd.DataFrame:
    rows = []
    for current in range(seed, seed + seeds):
        for shock in (False, True):
            sim = Simulator(shock=shock, seed=current)
            for name in ("random_choice", "earliest_finish"):
                out = sim.run(BASELINES[name], name=name)
                rows.append({"seed": current, "shock": shock, "policy": name,
                             "fairness": None, **summarize_outcomes(out)})
            for f in grid:
                config = hybrid_config(f)
                out = sim.run(Allocator(config), name=config.name)  # fresh allocator per run
                rows.append({"seed": current, "shock": shock, "policy": "hybrid",
                             "fairness": f, **summarize_outcomes(out)})
    return pd.DataFrame(rows)


def average(trials: pd.DataFrame) -> pd.DataFrame:
    keyed = trials.assign(fairness=trials["fairness"].fillna(-1))
    mean = keyed.groupby(["shock", "policy", "fairness"], sort=False)[METRICS].mean().reset_index()
    mean["fairness"] = mean["fairness"].where(mean["fairness"] >= 0)
    return mean


def pick(mean: pd.DataFrame, tolerance: float) -> float | None:
    normal = mean[~mean["shock"]]
    rnd = normal[normal["policy"] == "random_choice"].iloc[0]
    hyb = normal[normal["policy"] == "hybrid"].sort_values("fairness")
    base = hyb[hyb["fairness"] == 0.0].iloc[0]["pct_late"]
    ok = hyb[(hyb["pct_late"] <= base + tolerance) & (hyb["pct_late"] <= rnd["pct_late"])
             & (hyb["max_share"] <= rnd["max_share"])]
    if ok.empty:
        return None
    return float(ok.sort_values(["max_share", "fairness"]).iloc[0]["fairness"])


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=6105, help="first of the paired seeds")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--fixed-fairness", type=float, default=None,
                        help="report this f only (no selection), e.g. on the course seeds")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "eval" / "hybrid_sweep")
    args = parser.parse_args(argv)

    grid = GRID if args.fixed_fairness is None else sorted({0.0, 1.0, round(args.fixed_fairness, 1)})
    trials = run_sweep(args.seed, args.seeds, grid)
    mean = average(trials)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trials.to_csv(args.output_dir / "sweep_trials.csv", index=False)
    mean.to_csv(args.output_dir / "sweep_summary.csv", index=False)

    lines = [f"# Hybrid weight sweep: seeds {args.seed}-{args.seed + args.seeds - 1}", ""]
    for shock in (False, True):
        part = mean[mean["shock"] == shock].copy()
        part["setting"] = [("random" if p == "random_choice" else "earliest finish" if p == "earliest_finish"
                            else f"lateness {1 - f:.1f} / fairness {f:.1f}") for p, f in zip(part["policy"], part["fairness"])]
        lines += [f"## {'Shock' if shock else 'Normal'} (mean over seeds)", "",
                  markdown_table(part[["setting", *SHOWN]], 2), ""]
    if args.fixed_fairness is None:
        chosen = pick(mean, TOLERANCE_PP)
        lines += ["## Selection (rule fixed in advance)", "",
                  f"Tolerance {TOLERANCE_PP} pp over lateness-only: **chosen fairness share = {chosen}**", "",
                  "Sensitivity of the rule to the tolerance:", ""]
        for tol in (2.0, 3.0, 5.0, 8.0, 10.0, 15.0):
            lines.append(f"- tolerance {tol:>4.1f} pp: fairness share {pick(mean, tol)}")
        lines.append("")
    text = "\n".join(lines)
    (args.output_dir / "sweep_summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
