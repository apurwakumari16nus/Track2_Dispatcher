"""Simulation Lab view model: honest verdicts from the committed ten-seed evidence.

Every verdict here is read from eval/ (results, objective checks, shock deltas)
through ui.evidence; nothing is recomputed from a fresh simulation. The words
are fixed by outcome so the page cannot dress a tie up as a win:

    qualifying  -> Beats       (the course pass rule holds)
    tie         -> Tie         (required metric equal; a tie is not a win)
    guardrail   -> Guardrail fails (wins its own metric, breaks the lateness guardrail)
    no_win      -> No win
    hybrids     -> No course rule (reported only)
"""

from __future__ import annotations

from ui import evidence as ev

# objective -> (headline metric, label, unit format, lower is better)
METRIC = {
    "lateness": ("pct_late", "late batches", "{:.2f}%"),
    "fairness": ("max_share", "largest workshop share", "{:.1f}%"),
    "defect": ("pct_defect_pieces", "defect exposure (pieces)", "{:.1f}%"),
    "robustness": ("pct_late", "late batches", "{:.2f}%"),
    "hybrid_lateness_fairness": ("pct_late", "late batches", "{:.1f}%"),
    "hybrid_lateness_defect": ("pct_late", "late batches", "{:.1f}%"),
}
OUTCOME = {"qualifying": ("Beats", "ok"), "tie": ("Tie", "muted"), "guardrail": ("Guardrail fails", "risk"),
           "no_win": ("No win", "warn"), "none": ("No course rule", "muted")}
BASELINES = ["random_choice", "greedy_biggest", "cheapest", "earliest_finish"]
ROLE = {"random_choice": "Supplied baseline", "greedy_biggest": "Supplied baseline", "cheapest": "Supplied baseline",
        "earliest_finish": "Strong simple rule"}
NAMES = {"random_choice": "Random", "greedy_biggest": "Biggest workshop", "cheapest": "Cheapest", "earliest_finish": "Earliest finish"}


def scenario_key(objective: str, shock: bool) -> str:
    return "paired change" if objective == "robustness" else ("shock" if shock else "normal")


def outcomes(data, objective: str, shock: bool) -> dict[str, str]:
    """comparator -> outcome for this objective and scenario; empty for hybrids (no pass rule)."""
    key = scenario_key(objective, shock)
    return {r["comparator"]: r["outcome"] for r in ev.check_matrix(data["results"], data["checks"])
            if r["objective"] == objective and r["scenario"] == key}


def headline(data, objective: str, policy: str, shock: bool) -> float:
    """The objective's own number. Robustness is the shock change in late batches (points)."""
    obj = objective if policy == "allocator" else "none"
    if objective == "robustness":
        return ev.row(data["results"], policy, obj, True).pct_late - ev.row(data["results"], policy, obj, False).pct_late
    return float(ev.row(data["results"], policy, obj, shock)[METRIC[objective][0]])


def fmt_headline(objective: str, value: float) -> str:
    return f"{value:+.2f} pts" if objective == "robustness" else METRIC[objective][2].format(value)


def hero(data, objective: str, shock: bool) -> dict:
    """The primary result for one objective: ours against the strong simple rule, plus the overall verdict."""
    res = outcomes(data, objective, shock)
    card = next(c for c in ev.objective_scorecard(data["results"], data["checks"]) if c["objective"] == objective)
    ef = res.get("earliest_finish", "none")
    beats = [NAMES[c] for c, o in res.items() if o == "qualifying"]
    if not res:
        overall, tone = "Reported only", "muted"
    elif "guardrail" in res.values():
        overall, tone = "Fails the lateness guardrail", "risk"
    elif all(o == "qualifying" for o in res.values()):
        overall, tone = "Qualifies against all four", "ok"
    elif set(res.values()) <= {"qualifying", "tie"}:
        overall, tone = f"Beats {len(beats)}, ties {len(res) - len(beats)}", "muted"
    else:
        overall, tone = "Mixed", "warn"
    if objective == "lateness" and ef == "tie":
        note = (f"Our lateness policy beats the three supplied baselines on % late and late days, and ties earliest finish. "
                "It makes the same choices as the strongest simple rule, so this is a tie, not a win.")
    elif objective == "defect":
        note = card["detail"] + " It wins its own metric but breaks the lateness guardrail, so it does not qualify."
    elif not res:
        note = card["detail"] + " Hybrids have no course pass rule, so they are reported, not judged."
    else:
        note = card["detail"]
    return {"objective": objective, "label": ev.OBJECTIVE_LABELS[objective], "metric": METRIC[objective][1],
            "ours": headline(data, objective, "allocator", shock), "ef": headline(data, objective, "earliest_finish", shock),
            "ef_outcome": ef, "overall": overall, "tone": tone, "note": note, "outcomes": res, "beats": beats}


def comparison(data, objective: str, shock: bool) -> list[dict]:
    """Our policy and the four comparison policies on the same footing."""
    res = outcomes(data, objective, shock)
    rows = []
    for policy in ["allocator"] + BASELINES:
        obj = objective if policy == "allocator" else "none"
        r = ev.row(data["results"], policy, obj, shock)
        rows.append({"policy": policy, "name": "Our policy" if policy == "allocator" else NAMES[policy],
                     "role": ev.OBJECTIVE_LABELS[objective] + " objective" if policy == "allocator" else ROLE[policy],
                     "headline": headline(data, objective, policy, shock), "pct_late": r.pct_late, "late_days": r.late_days,
                     "cost": r.total_cost, "share": r.max_share, "defect": r.pct_defect_pieces,
                     "outcome": None if policy == "allocator" else res.get(policy, "none")})
    return rows


def claims(data) -> dict[str, list[str]]:
    """What the evidence lets us say, grouped for the presentation."""
    cards = {c["objective"]: c for c in ev.objective_scorecard(data["results"], data["checks"])}
    ours, ef = ev.row(data["results"], "allocator", "lateness", False), ev.row(data["results"], "earliest_finish", "none", False)
    return {
        "Beats or qualifies": ["Lateness beats Random, Biggest workshop and Cheapest on % late and late days, in both scenarios.",
                               "Fairness qualifies against all four comparison policies. " + cards["fairness"]["detail"],
                               "Robustness qualifies against all four. " + cards["robustness"]["detail"]],
        "Ties": [f"Lateness ties earliest finish: {ours.pct_late:.2f}% against {ef.pct_late:.2f}% late, and equal late days. "
                 "Present it as a tie with the strongest simple rule."],
        "Fails": ["Quality only fails the lateness guardrail. " + cards["defect"]["detail"]],
        "Do not claim": ["That our policy beats earliest finish.", "Any language accuracy: human labels are not complete.",
                         "That single-seed diagnostics are official results.", "Hybrid objectives as wins: they have no course pass rule."],
    }
