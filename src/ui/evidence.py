"""Read the committed ten-seed evaluation and language-evaluation status.

Nothing here reruns or edits an evaluation. Findings are computed from the
committed CSV/JSON files with the evaluator's own tie rule, so the UI cannot
describe a tie as a win. If the source hashes recorded by the evaluator no
longer match the code, the page says the evidence is stale.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "eval"
COMPARATORS = ["random_choice", "greedy_biggest", "cheapest", "earliest_finish"]
POLICY_LABELS = {"random_choice": "Random", "greedy_biggest": "Biggest workshop", "cheapest": "Cheapest",
                 "earliest_finish": "Earliest finish"}
OBJECTIVE_LABELS = {"lateness": "Lateness", "defect": "Quality (defects)", "fairness": "Fairness",
                    "robustness": "Robustness", "hybrid_lateness_fairness": "Hybrid: lateness and fairness",
                    "hybrid_lateness_defect": "Hybrid: lateness and quality"}
METRICS = ["mean_days", "p90_days", "pct_late", "late_days", "pct_defect", "pct_defect_pieces", "total_cost", "max_share"]


def tied(a: float, b: float) -> bool:
    import math
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def policy_label(policy: str, objective: str) -> str:
    return f"Ours: {OBJECTIVE_LABELS[objective].lower()}" if policy == "allocator" else POLICY_LABELS[policy]


def load() -> dict:
    results = pd.read_csv(EVAL / "results.csv")
    per_seed = pd.read_csv(EVAL / "results_per_seed.csv")
    checks = pd.read_csv(EVAL / "objective_checks.csv")
    shock = pd.read_csv(EVAL / "shock_changes.csv")
    metadata = json.loads((EVAL / "simulator_metadata.json").read_text(encoding="utf-8"))
    for frame in (results, per_seed):
        frame["shock"] = frame["shock"].astype(str).str.lower().eq("true")
    return {"results": results, "per_seed": per_seed, "checks": checks, "shock": shock, "metadata": metadata,
            "provenance": provenance(metadata)}


def provenance(metadata: dict) -> dict:
    """Compare the evaluator's recorded source hashes with the files on disk."""
    stale = []
    for relative, recorded in metadata.get("source_hashes", {}).items():
        path = ROOT / relative
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if current != recorded:
            stale.append(relative)
    return {"matches": not stale, "stale": stale, "checked": len(metadata.get("source_hashes", {}))}


def row(results: pd.DataFrame, policy: str, objective: str, shock: bool) -> pd.Series:
    match = results[(results.policy == policy) & (results.objective == objective) & (results.shock == shock)]
    return match.iloc[0]


def primary_table(results: pd.DataFrame, objective: str = "lateness") -> list[dict]:
    """Normal and shock lateness for the four comparison policies and ours."""
    out = []
    for policy, obj in [(p, "none") for p in COMPARATORS] + [("allocator", objective)]:
        normal, shocked = row(results, policy, obj, False), row(results, policy, obj, True)
        out.append({"policy": policy, "objective": obj, "label": policy_label(policy, obj),
                    "normal_pct_late": normal.pct_late, "normal_late_days": normal.late_days,
                    "shock_pct_late": shocked.pct_late, "shock_late_days": shocked.late_days,
                    "ours": policy == "allocator"})
    return out


def check_matrix(results: pd.DataFrame, checks: pd.DataFrame) -> list[dict]:
    """objective_checks.csv with a computed 'tie' outcome where the required metric ties."""
    required = {"lateness": ["pct_late", "late_days"], "defect": ["pct_defect_pieces"], "fairness": ["max_share"]}
    out = []
    for item in checks.to_dict("records"):
        outcome = "qualifying" if item["qualifying_win"] else "guardrail" if item["required_metric_win"] else "no_win"
        if item["objective"] in required and outcome == "no_win":
            shock = item["scenario"] == "shock"
            ours, other = row(results, "allocator", item["objective"], shock), row(results, item["comparator"], "none", shock)
            if all(tied(ours[m], other[m]) for m in required[item["objective"]]):
                outcome = "tie"
        out.append({**item, "outcome": outcome})
    return out


def findings(results: pd.DataFrame, checks: pd.DataFrame) -> list[dict]:
    """Plain-language statements computed from the committed results."""
    out = []
    for shock in (False, True):
        scenario = "shock" if shock else "normal"
        ours, ef = row(results, "allocator", "lateness", shock), row(results, "earliest_finish", "none", shock)
        if all(tied(ours[m], ef[m]) for m in METRICS):
            out.append({"tone": "tie", "text": f"Lateness ties earliest finish on all eight metrics in the {scenario} runs. A tie is not a win."})
        elif ours.pct_late < ef.pct_late and not tied(ours.pct_late, ef.pct_late):
            out.append({"tone": "win", "text": f"Lateness beats earliest finish on late batches in the {scenario} runs."})
        else:
            out.append({"tone": "loss", "text": f"Earliest finish is no worse than lateness on late batches in the {scenario} runs."})
    random_beaten = all(bool(r) for r in checks[(checks.objective == "lateness") & checks.comparator.isin(COMPARATORS[:3])].qualifying_win)
    if random_beaten:
        out.append({"tone": "win", "text": "Lateness beats all three supplied baselines on % late and late days, in both scenarios."})
    defect = checks[checks.objective == "defect"]
    if len(defect) and not defect.guardrail_passed.any():
        normal = row(results, "allocator", "defect", False)
        rand = row(results, "random_choice", "none", False)
        out.append({"tone": "loss", "text": f"Quality (defects) has the lowest defect exposure ({normal.pct_defect_pieces:.1f}% of pieces) "
                                          f"but fails the lateness guardrail: {normal.pct_late:.1f}% late vs {rand.pct_late:.1f}% for random."})
    for objective in ("fairness", "robustness"):
        part = checks[checks.objective == objective]
        if len(part) and part.qualifying_win.all():
            out.append({"tone": "win", "text": f"{objective.capitalize()} qualifies against all four comparison policies on its own metric and guardrail."})
    return out


def seed_spread(per_seed: pd.DataFrame, metric: str = "pct_late") -> pd.DataFrame:
    keep = per_seed[(per_seed.policy != "allocator") | per_seed.objective.isin(["lateness", "fairness", "robustness",
                                                                                  "hybrid_lateness_fairness"])].copy()
    keep["label"] = [policy_label(p, o) for p, o in zip(keep.policy, keep.objective)]
    keep["scenario"] = keep.shock.map({False: "Normal", True: "Shock"})
    return keep[["seed", "label", "scenario", metric]]


# Language evaluation status ------------------------------------------------

def _labelled(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return int(frame.get("expected_behaviour", pd.Series(dtype=str)).str.strip().ne("").sum()), len(frame)


def behaviour_mix() -> list[tuple[str, int]]:
    """The official request mix, read from data/data_dictionary.md."""
    text = (ROOT / "data" / "data_dictionary.md").read_text(encoding="utf-8")
    section = text.split("| Kind | How many |", 1)[-1]
    rows = re.findall(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", section, re.M)
    return [(re.sub(r"\*\*", "", kind), int(n)) for kind, n in rows]


def language_status() -> dict:
    final, total = _labelled(EVAL / "labels.csv")
    r1, _ = _labelled(EVAL / "labeling" / "reviewer_1.csv")
    r2, _ = _labelled(EVAL / "labeling" / "reviewer_2.csv")
    reconciliation = EVAL / "labeling" / "reconciliation.md"
    status = "unknown"
    if reconciliation.exists():
        match = re.search(r"^Status:\s*(.+)$", reconciliation.read_text(encoding="utf-8"), re.M)
        status = match.group(1).split(".")[0].strip() if match else "unknown"
    live = EVAL / "inbox_audit.json"
    run = None
    if live.exists():
        try:
            audit = json.loads(live.read_text(encoding="utf-8"))
            run = {"mode": audit.get("mode"), "model": audit.get("model"), "requests": len(audit.get("requests", []))}
        except ValueError:
            run = {"mode": "unreadable"}
    return {"requests": total or 30, "final_labels": final, "reviewer_1": r1, "reviewer_2": r2,
            "reconciliation": status, "inbox_run": run, "mix": behaviour_mix(),
            "accuracy_reportable": final == (total or 30) and final > 0}
