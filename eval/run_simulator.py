"""Reproduce the simulator evaluation matrix and report baseline wins honestly.

Run from any directory: python /path/to/Track2_dispatch/eval/run_simulator.py
Default outputs are beside this file. Defaults to ten paired seeds. Use --seed, --seeds and --output-dir for separate
experiments. CSV percentages are 0..100, and retain unrounded metric values.
Baseline/heuristic rows have objective='none'; our rows have policy='allocator'
and the corresponding PRESETS key. No LLM calls or simulator modifications.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import math
import json
import os
from pathlib import Path
import sys
import tempfile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "harness")]

from allocator import Allocator
from heuristic import earliest_finish
from objectives import PRESETS
from simulate import Simulator, random_choice, greedy_biggest, cheapest


BASELINES = {
    "random_choice": random_choice,
    "greedy_biggest": greedy_biggest,
    "cheapest": cheapest,
    "earliest_finish": earliest_finish,
}
METRIC_NAMES = {
    "mean_days": "mean days", "p90_days": "p90 days", "pct_late": "% late",
    "late_days": "late days", "pct_defect": "% defect", "pct_defect_pieces": "% def pcs",
    "total_cost": "cost", "max_share": "max share",
}
METRICS = list(METRIC_NAMES)
COLUMNS = ["policy", "objective", "shock", *METRICS]


def summarize_outcomes(out: list[dict]) -> dict[str, float]:
    """Rename the official v3 metrics; do not duplicate or reinterpret arithmetic.

    late_days averages positive lateness over ALL batches (on-time = zero).
    pct_defect_pieces weights defective batches by their full piece counts.
    p90 is the harness's sorted order statistic, not an interpolated quantile.
    """
    official = Simulator.metrics(out)
    return {column: official[name] for column, name in METRIC_NAMES.items()}


def run_trials(seed: int = 5105, seeds: int = 10) -> pd.DataFrame:
    """One independent, default-mode run per policy, condition, and paired seed.

    Construct stateful allocators inside the innermost loop. The harness's
    average_over_seeds helper reuses supplied callables and cannot reset them.
    Never pass a target or closure dates into an allocation policy.
    """
    if seeds < 1:
        raise ValueError("seeds must be a positive count")
    rows = []
    for current_seed in range(seed, seed + seeds):
        for shock in (False, True):
            sim = Simulator(shock=shock, seed=current_seed)
            policies = [(name, "none", policy) for name, policy in BASELINES.items()]
            policies += [("allocator", name, Allocator(config)) for name, config in PRESETS.items()]
            for policy_name, objective, policy in policies:
                name = f"allocator:{objective}" if policy_name == "allocator" else policy_name
                outcomes = sim.run(policy, name=name)
                rows.append({"seed": current_seed, "policy": policy_name,
                             "objective": objective, "shock": shock,
                             **summarize_outcomes(outcomes)})
    result = pd.DataFrame(rows, columns=["seed", *COLUMNS])
    result.attrs.update(seed=seed, seeds=seeds, stages=False, batch_count=len(sim.batches),
                        total_pieces=sum(b["pieces"] for b in sim.batches))
    return result


def average_trials(trials: pd.DataFrame) -> pd.DataFrame:
    """Arithmetic mean of each per-run metric, never a pooled-outcome percentile."""
    result = trials.groupby(["policy", "objective", "shock"], sort=False)[METRICS].mean().reset_index()
    result.attrs.update(trials.attrs)
    return result[COLUMNS]


def run_evaluation(seed: int = 5105, seeds: int = 10) -> pd.DataFrame:
    """Return twenty averaged rows; run_trials retains all individual runs."""
    return average_trials(run_trials(seed, seeds))


def paired_changes(trials: pd.DataFrame) -> pd.DataFrame:
    """Shock minus normal for matching seeds/policies; positive means worse."""
    keys = ["seed", "policy", "objective"]
    paired = trials[trials.shock].merge(trials[~trials.shock], on=keys,
                                       suffixes=("_shock", "_normal"), validate="one_to_one")
    result = paired[keys].copy()
    for metric in METRICS:
        result["delta_" + metric] = paired[metric + "_shock"] - paired[metric + "_normal"]
    return result


def objective_checks(results: pd.DataFrame) -> pd.DataFrame:
    """Track v4 criteria against EACH comparator; guardrails use random_choice.

    Lateness/robustness: no worse on both required measures, strictly better on
    at least one. Fairness: smaller share, or tied share with lower lateness.
    Defects: strictly lower piece-weighted exposure. Defect/fairness guardrails
    apply within the scenario; robustness checks normal-run lateness. Hybrid
    results stay in the metric tables: no invented course rule for a hybrid.
    """
    rows = []
    normal = results[~results.shock].set_index(["policy", "objective"])
    shocked = results[results.shock].set_index(["policy", "objective"])
    def no_worse(a, b):
        return a < b or tied(a, b)
    for objective in ("lateness", "defect", "fairness", "robustness"):
        for scenario in (("paired change",) if objective == "robustness" else ("normal", "shock")):
            group = shocked if scenario == "shock" else normal
            if ("allocator", objective) not in group.index:
                continue
            own = group.loc[("allocator", objective)]
            guard = objective == "lateness" or no_worse(own.pct_late, group.loc[("random_choice", "none"), "pct_late"])
            for baseline in BASELINES:
                other = group.loc[(baseline, "none")]
                if objective == "robustness":
                    a = [shocked.loc[("allocator", objective), m] - own[m] for m in ("pct_late", "late_days")]
                    b = [shocked.loc[(baseline, "none"), m] - other[m] for m in ("pct_late", "late_days")]
                elif objective == "lateness":
                    a, b = [own[m] for m in ("pct_late", "late_days")], [other[m] for m in ("pct_late", "late_days")]
                elif objective == "defect":
                    a, b = [own.pct_defect_pieces], [other.pct_defect_pieces]
                else:
                    a, b = [own.max_share], [other.max_share]
                metric_win = all(no_worse(x, y) for x, y in zip(a, b)) and any(x < y and not tied(x, y) for x, y in zip(a, b))
                if objective == "fairness" and tied(a[0], b[0]):
                    metric_win = own.pct_late < other.pct_late and not tied(own.pct_late, other.pct_late)
                rows.append({"objective": objective, "scenario": scenario, "comparator": baseline,
                             "guardrail_passed": bool(guard), "required_metric_win": bool(metric_win),
                             "qualifying_win": bool(guard and metric_win)})
    return pd.DataFrame(rows)


def label(row) -> str:
    return f"allocator:{row['objective']}" if row["policy"] == "allocator" else row["policy"]


def markdown_table(frame: pd.DataFrame, precision: int = 2) -> str:
    """Render Markdown without adding pandas.to_markdown's optional tabulate dependency."""
    def cell(value):
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:,.{precision}f}" if precision == 2 else f"{value:.10g}"
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    lines = ["| " + " | ".join(map(str, frame.columns)) + " |",
             "| " + " | ".join("---" for _ in frame.columns) + " |"]
    lines.extend("| " + " | ".join(cell(v) for v in row) + " |"
                 for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def tied(a: float, b: float) -> bool:
    """Ignore only floating-point noise, not differences hidden by display rounding."""
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def comparison_tables(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """All metric winners, every strict comparator win over every preset, and ties.

    Comparisons stay within a shock scenario. All original metrics minimise;
    fairness=100-max_share maximises. A positive improvement means the comparator
    is better, in days, model cost units, or percentage points as appropriate.
    """
    frame = results.assign(fairness=100 - results["max_share"])
    winners, wins, ties = [], [], []
    for shock, group in frame.groupby("shock", sort=True):
        baselines = group[group["policy"].isin(BASELINES)].to_dict("records")
        ours = group[group["policy"] == "allocator"].to_dict("records")
        for metric in [*METRICS, "fairness"]:
            larger = metric == "fairness"
            best = group[metric].max() if larger else group[metric].min()
            names = [label(row) for row in group.to_dict("records") if tied(row[metric], best)]
            winners.append({"shock": bool(shock), "metric": metric,
                            "best_value": float(best), "best_policy_or_objective": ", ".join(names)})
            for baseline in baselines:
                for own in ours:
                    b, a = baseline[metric], own[metric]
                    entry = {"shock": bool(shock), "metric": metric,
                             "baseline_or_heuristic": baseline["policy"], "baseline_value": b,
                             "allocator_objective": own["objective"], "allocator_value": a}
                    if tied(a, b):
                        ties.append(entry)
                    elif (larger and b > a) or (not larger and b < a):
                        wins.append({**entry, "improvement": b - a if larger else a - b})
    comparison_columns = ["shock", "metric", "baseline_or_heuristic", "baseline_value",
                          "allocator_objective", "allocator_value"]
    return (pd.DataFrame(winners),
            pd.DataFrame(wins, columns=[*comparison_columns, "improvement"]),
            pd.DataFrame(ties, columns=comparison_columns))


def baseline_report(results: pd.DataFrame, seed: int) -> str:
    winners, wins, ties = comparison_tables(results)
    lines = [
        "# Simulator evaluation: winners, baseline wins, and ties", "",
        f"Mean over **{results.attrs.get('seeds', 1)} paired seeds**, starting at **{seed}**. "
        "Each policy uses the same orders and matching normal/shock seeds; stages mode is off.",
        f"Batches per run: **{results.attrs.get('batch_count', 'unknown')}**; "
        f"pieces per run: **{results.attrs.get('total_pieces', 'unknown')}**.", "",
        "All eight simulator metrics use the official `Simulator.metrics()` arithmetic. "
        "CSV values are unrounded. Percentages use 0-100; `objective=none` identifies "
        "a supplied baseline or the earliest-finish heuristic. Every allocator preset "
        "starts with fresh history and a fresh shock monitor.", "",
        "Lower is better for mean_days, p90_days, pct_late, late_days, pct_defect, pct_defect_pieces, total_cost, "
        "and max_share. Derived fairness is `100 - max_share`, so higher is better. "
        "It measures concentration of pieces, not equality relative to workshop capacity. "
        "Fairness wins duplicate max_share wins and are not independent evidence.", "",
        "Comparisons use unrounded values within each scenario. Values equal within "
        "relative/absolute tolerance 1e-12 are ties, never wins. Report values use up "
        "to ten significant digits. Improvement is in days, model cost units, or "
        "percentage points, not a relative percentage reduction.", "",
        "## Best policy for every metric (including all ties)", "",
        markdown_table(winners, precision=10), "",
        "## Every case where a baseline or heuristic beats an allocator preset", "",
        "Each row is one strict pairwise win. All four comparison policies are checked "
        "against every preset for every metric; no losing allocator setting is omitted.", "",
    ]
    for shock in (False, True):
        subset = wins[wins["shock"] == shock]
        lines += [f"### {'Shock' if shock else 'Normal'}: {len(subset)} strict metric comparisons", "",
                  markdown_table(subset.drop(columns="shock"), precision=10) if len(subset) else "No strict baseline wins.", ""]
    lines += ["## Ties between comparison policies and allocator presets", "",
              markdown_table(ties, precision=10) if len(ties) else "No ties.", "",
              "## What the strong heuristic adds to the interpretation", ""]
    for shock in (False, True):
        group = results[results["shock"] == shock]
        heuristic = group[group["policy"] == "earliest_finish"].iloc[0]
        equal = [row["objective"] for row in group[group["policy"] == "allocator"].to_dict("records")
                 if all(tied(row[m], heuristic[m]) for m in METRICS)]
        lines.append(f"- {'Shock' if shock else 'Normal'}: " + (
            f"earliest_finish ties allocator preset(s) **{', '.join(equal)}** on all eight metrics. "
            "These results do not show those settings beating the simple earliest-finish heuristic."
            if equal else "no allocator preset ties earliest_finish on all eight metrics; see the per-metric comparisons above."))
    lines += ["", "The allocator additionally supports configurable preferences, exclusions, "
              "decision evidence, and queue-anomaly monitoring. Those capabilities do not "
              "establish a scheduling improvement over a tied or better heuristic. "
              "Avoiding a suspect workshop in shock_trace.py is not itself proof of "
              "better aggregate turnaround.", "",
              "## Scope and reproducibility", "",
              "These are averages of per-run metrics over paired seeds, not a held-out natural-language "
              "evaluation or a statistical confidence claim. These supplied orders and "
              "seed 5105 have been used during development; report that use honestly. "
              "Additional seeds alone do not make these orders unseen. The final "
              "Evaluation.pdf still needs the chat evaluation and individual failure analysis.", "",
              "The v3 harness uses a separate random stream for target selection; paired "
              "normal/shock runs use matching defect draws. Different choices can still "
              "produce different defect outcomes because workshop risks differ. The "
              "evaluator never passes the hidden target or closure dates to the allocator.", "",
              "The p90 is `sorted_days[int(0.9 * n)]`, not an interpolated percentile. "
              "pct_late and pct_defect count batches; late_days averages lateness over all batches; pct_defect_pieces counts pieces in defective batches; max_share counts pieces. A lower "
              "unit-cost policy may win on spending while losing on delivery. There is "
              "no declared overall winner across conflicting metrics.", "",
              f"Reproduce: `python eval/run_simulator.py --seed {seed} --seeds {results.attrs.get('seeds', 1)}`. Use "
              "`--output-dir eval/seed_OTHER` to preserve separate experiments.", "",
              "### Objective settings used", ""]
    # Display the same paired mean changes that the CSV exposes. With matching
    # seeds, mean(shock-normal) equals mean(shock)-mean(normal).
    normal = results[~results.shock].set_index(["policy", "objective"])
    shocked = results[results.shock].set_index(["policy", "objective"])
    deltas = (shocked[["pct_late", "late_days"]] - normal[["pct_late", "late_days"]]).rename(
        columns={"pct_late": "delta_pct_late", "late_days": "delta_late_days"}).reset_index()
    lines[-2:-2] = ["### Mean paired shock changes", "",
        "Shock minus normal over matching seeds. Positive means worse; percentage "
        "changes are percentage points. A negative change can reflect rerouting, "
        "not a generally beneficial closure.", "", markdown_table(deltas, precision=10), ""]
    checks = objective_checks(results)
    lines[-2:-2] = [
        "### Course objective criteria and guardrails", "",
        "Lateness uses both pct_late and late_days. Defects use pct_defect_pieces. "
        "Fairness uses max_share (a share tie can win with improved lateness). "
        "Robustness uses shock-minus-normal pct_late and late_days. Defect and fairness "
        "must not have higher pct_late than random in that scenario; robustness must "
        "not have higher normal pct_late than random. A qualifying win needs the "
        "required metric improvement AND its guardrail. Ties are not strict wins. "
        "Hybrid presets have no invented pass rule and remain fully reported above.", "",
        markdown_table(checks), "",
        "### Queue-anomaly limitation", "",
        "The official harness immediately adds future closure delay to an affected "
        "queue. In the default robustness trace, the monitor flags W2 on day 26, "
        "before closure starts on day 30. This is a response to a simulated queue "
        "anomaly, not evidence of realistic advance detection. Rework can also "
        "trigger flags. Preserve the official harness and disclose this caveat.", "",
    ]
    lines += [markdown_table(pd.DataFrame([{"preset": key, **asdict(config)}
                                           for key, config in PRESETS.items()]), precision=10), "",
              "### Input and implementation fingerprints (SHA-256)", ""]
    for relative in ["data/orders.csv", "data/workshops.csv", "harness/simulate.py",
                     "src/tools.py", "src/objectives.py", "src/allocator.py", "src/heuristic.py"]:
        digest = hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()
        lines.append(f"- `{relative}`: `{digest}`")
    return "\n".join(lines) + "\n"


def make_charts(results: pd.DataFrame, directory: Path, seed: int) -> None:
    """Matplotlib only; separate scatter panels avoid pooling normal and shock runs.

    One point per policy/objective in each panel. Coincident points are not moved:
    their numeric labels are grouped, so tied policies remain visible in the key.
    """
    # Use a writable cache and a display-free backend, including on headless CI.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "track2-dispatch-mpl"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import StrMethodFormatter

    directory.mkdir(parents=True, exist_ok=True)
    normal = results[~results["shock"]].reset_index(drop=True)
    shock = results[results["shock"]].reset_index(drop=True)
    labels = [label(row) for row in normal.to_dict("records")]
    seed_label = f"mean of {results.attrs.get('seeds', 1)} seeds ({seed} onward)"
    count = len(labels)
    numbers = range(1, count + 1)
    palette = [plt.get_cmap("tab20")(i % 20) for i in range(count)]
    key = [f"{i}: {name}" for i, name in zip(numbers, labels)]
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "savefig.facecolor": "white"}):
        fig, ax = plt.subplots(figsize=(15, 8))
        positions = list(range(count))
        for values, offset, color, title in [(normal, -.2, "#247A92", "Normal"),
                                             (shock, .2, "#D27C32", "Shock")]:
            bars = ax.bar([x + offset for x in positions], values["pct_late"], .38, label=title, color=color)
            ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
        ax.set(xticks=positions, xticklabels=list(numbers), ylim=(0, 108),
               xlabel="Policy / objective number (key below)", ylabel="Late batches (%)",
               title=f"Lateness by policy: normal versus shock | {seed_label}")
        ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True); ax.legend(loc="upper left")
        fig.text(.07, .025, "\n".join(key[:(count + 1)//2]), fontsize=9, va="bottom")
        fig.text(.53, .025, "\n".join(key[(count + 1)//2:]), fontsize=9, va="bottom")
        fig.subplots_adjust(bottom=.27, left=.07, right=.98, top=.91)
        fig.savefig(directory / "lateness_by_policy.png", dpi=180)
        plt.close(fig)

        for metric, filename, ylabel, title in [
            ("total_cost", "tradeoff_lateness_vs_cost.png", "Total cost (simulator units; lower is better)", "Lateness versus cost"),
            ("fairness", "tradeoff_lateness_vs_fairness.png", "Fairness = 100 - max_share (higher is better)", "Lateness versus fairness"),
        ]:
            fig, axes = plt.subplots(1, 2, figsize=(16, 9), sharex=True, sharey=True)
            for ax, values, scenario in zip(axes, (normal, shock), ("Normal", "Shock")):
                coincident = {}
                for i, row in enumerate(values.to_dict("records")):
                    x = row["pct_late"]
                    y = 100 - row["max_share"] if metric == "fairness" else row[metric]
                    ax.scatter(x, y, color=palette[i], s=85, edgecolors="white", linewidth=.8, zorder=3)
                    coincident.setdefault((x, y), []).append(str(i + 1))
                y_values = [y for _, y in coincident]
                y_span = 100 if metric == "fairness" else max(max(y_values) - min(y_values), 1)
                annotated = []
                for (x, y), ids in coincident.items():
                    nearby = any(abs(x - px) < 5 and abs(y - py) < .045 * y_span
                                 for px, py in annotated)
                    # Move only the label for nearby points; keep measured coordinates exact.
                    ax.annotate(", ".join(ids), (x, y), xytext=(-9, -16) if nearby else (6, 7),
                                textcoords="offset points", ha="right" if nearby else "left",
                                arrowprops={"arrowstyle": "-", "color": "#666666", "lw": .6} if nearby else None,
                                fontsize=8, bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": .5})
                    annotated.append((x, y))
                ax.set(title=scenario, xlabel="Late batches (%; lower is better)", xlim=(-4, 106))
                ax.grid(alpha=.2);ax.margins(y=.18)
            axes[0].set_ylabel(ylabel)
            if metric == "total_cost":
                axes[0].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            else:
                axes[0].set_ylim(0, 104)
            fig.suptitle(f"{title} | {seed_label}", fontsize=16, y=.96)
            fig.text(.5, .905, "One point per policy/objective per scenario. Grouped numbers mark exact overlaps; no jitter.", ha="center", fontsize=10)
            handles = [Line2D([], [], marker="o", linestyle="", color=c, markersize=7) for c in palette]
            fig.legend(handles, key, loc="lower center", bbox_to_anchor=(.5, .025), ncol=2, frameon=False, fontsize=9)
            fig.subplots_adjust(bottom=.28, top=.85, left=.08, right=.98, wspace=.13)
            fig.savefig(directory / filename, dpi=180)
            plt.close(fig)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=5105)
    parser.add_argument("--seeds", type=int, default=10, help="Positive number of paired seeds, starting at --seed")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "eval")
    args = parser.parse_args(argv)
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    trials = run_trials(args.seed, args.seeds)
    results = average_trials(trials)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output_dir / "results.csv", index=False)
    trials.to_csv(args.output_dir / "results_per_seed.csv", index=False)
    changes = paired_changes(trials)
    changes.to_csv(args.output_dir / "shock_changes_per_seed.csv", index=False)
    changes.groupby(["policy", "objective"], sort=False).mean(numeric_only=True).drop(columns="seed").reset_index().to_csv(
        args.output_dir / "shock_changes.csv", index=False)
    objective_checks(results).to_csv(args.output_dir / "objective_checks.csv", index=False)
    metadata = {**trials.attrs, "seed_values": list(range(args.seed, args.seed + args.seeds)),
                "aggregation": "arithmetic mean of per-run metrics; paired shock minus normal",
                "metric_mapping": METRIC_NAMES,
                "queue_snapshot": "workshops.csv reused as January 1 starting queue for replay",
                "source_hashes": {str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [PROJECT_ROOT / f for f in ("data/orders.csv", "data/workshops.csv", "harness/simulate.py",
                        "src/tools.py", "src/objectives.py", "src/allocator.py", "src/heuristic.py", "eval/run_simulator.py")]}}
    (args.output_dir / "simulator_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    report = baseline_report(results, args.seed)
    (args.output_dir / "baseline_wins.md").write_text(report, encoding="utf-8")
    make_charts(results, args.output_dir / "charts", args.seed)
    print(f"# Simulator results (mean of {args.seeds} paired seeds starting at {args.seed})\n")
    print(markdown_table(results))
    print("\n" + report)
    print(f"Saved CSV, baseline report, and three charts in {args.output_dir}.", file=sys.stderr)


if __name__ == "__main__":
    main()
