"""Simulation Lab: test the dispatch policy against baselines before trusting it.

Interactive views replay one seed through the unchanged harness (experiments.py,
shock_trace.py). Course Evidence reads the committed ten-seed files instead
and never recomputes them. The custom sandbox runs extra single-seed replays
with user weights; it never changes PRESETS or any saved evaluation.
"""

from __future__ import annotations

from dataclasses import asdict
import json

import pandas as pd
import streamlit as st

from allocator import Allocator
from experiments import decision_replay, fingerprints, run_experiment
from objectives import ObjectiveConfig, PRESETS
from run_simulator import METRICS, summarize_outcomes, tied
from shock_trace import run_trace
from simulate import Simulator
from ui import evidence, explain
from ui.components import BASE, HEURISTIC, OURS, TERM_COLORS, banner, chart, chip, esc, html, json_block, kpi, page_head, pill, score_bars, section, table

LABELS = {"random_choice": "Random", "greedy_biggest": "Biggest workshop", "cheapest": "Cheapest",
          "earliest_finish": "Earliest finish", "lateness": "Lateness", "defect": "Quality", "fairness": "Fairness",
          "robustness": "Robustness", "hybrid_lateness_fairness": "Hybrid: lateness and fairness",
          "hybrid_lateness_defect": "Hybrid: lateness and quality", "custom": "Custom sandbox"}
METRIC_LABELS = {"pct_late": "Late batches (%)", "late_days": "Mean late days", "mean_days": "Mean turnaround (days)",
                 "p90_days": "P90 turnaround (days)", "pct_defect": "Defective batches (%)",
                 "pct_defect_pieces": "Pieces in defective batches (%)", "total_cost": "Total cost (units)",
                 "max_share": "Largest workshop share (%)"}
HERO = [("pct_late", "Late batches", "{:.1f}%"), ("mean_days", "Mean turnaround", "{:.1f} d"),
        ("pct_defect_pieces", "Defect exposure", "{:.1f}%"), ("total_cost", "Total cost", "{:,.0f}"),
        ("max_share", "Largest workshop share", "{:.1f}%")]
DEFAULTS = {"lab_seed": 5105, "lab_focus": "lateness", "lab_scenario": "Normal", "lab_metric": "pct_late",
            "sb_lateness": 0.5, "sb_defect": 0.0, "sb_fairness": 0.5, "sb_robustness": 0.0, "sb_cost": 0.0}


def fingerprint() -> str:
    return json.dumps(fingerprints(), sort_keys=True)


@st.cache_data(show_spinner=False, max_entries=8)
def experiment(seed: int, fp: str):
    return run_experiment(seed)


@st.cache_data(show_spinner=False, max_entries=64)
def replay(seed, objective, shock, fp):
    return decision_replay(seed, objective, shock)


@st.cache_data(show_spinner=False, max_entries=32)
def trace(seed, objective, fp):
    return run_trace(seed, objective)


@st.cache_data(show_spinner=False, max_entries=64)
def sandbox_run(seed, shock, weights: tuple, fp):
    config = ObjectiveConfig(**dict(zip(("w_lateness", "w_defect", "w_fairness", "w_robustness", "w_cost"), weights)), name="custom_sandbox")
    outcomes = Simulator(shock=shock, seed=seed).run(Allocator(config), name="custom_sandbox")
    return summarize_outcomes(outcomes), outcomes


def prewarm():
    """Compute the default diagnostic once per server so the Lab opens instantly."""
    experiment(DEFAULTS["lab_seed"], fingerprint())


SHORT = {**LABELS, "greedy_biggest": "Biggest", "hybrid_lateness_fairness": "Hybrid L+F", "hybrid_lateness_defect": "Hybrid L+Q"}


def short_name(row) -> str:
    return SHORT[row["objective"] if row["policy"] == "allocator" else row["policy"]]


def display_name(row) -> str:
    return LABELS[row["objective"] if row["policy"] == "allocator" else row["policy"]]


def fmt(metric, value) -> str:
    spec = next((f for m, _, f in HERO if m == metric), "{:.2f}")
    return spec.format(value)


def compare_badge(metric, ours, other) -> str:
    if tied(ours, other):
        return pill("Tie", "muted")
    delta = ours - other
    unit = " pp" if metric.startswith("pct") or metric == "max_share" else " d" if "days" in metric else ""
    text = f"{abs(delta):,.1f}{unit} {'better' if delta < 0 else 'worse'}"
    return pill(text, "ok" if delta < 0 else "warn")


def render(workshops):
    state = st.session_state
    for key, value in DEFAULTS.items():
        state.setdefault(key, value)
    page_head("Simulation lab", "Test the dispatch policy before trusting it.",
              "Replay all 120 orders through the shared course simulator. Every policy allocates automatically; "
              "queues build, defects cause rework and one scenario closes a workshop without warning.")
    with st.container(key="lab_controls"):
        a, b, c, d = st.columns([1.6, 1.1, .9, .8], vertical_alignment="bottom")
        with a:
            focus = st.selectbox("Our objective", list(PRESETS), key="lab_focus", format_func=lambda k: LABELS[k])
        with b:
            scenario = st.radio("Scenario", ["Normal", "Shock"], key="lab_scenario", horizontal=True)
        with c:
            seed = st.number_input("Seed", min_value=0, max_value=2_147_483_647, key="lab_seed")
        with d:
            run = st.button("Run simulation", key="lab_run", type="primary", width="stretch")
    fp = fingerprint()
    if run or "lab_bundle" not in state:
        try:
            state["lab_bundle"] = experiment(int(seed) if run else int(state.get("lab_bundle", {}).get("seed", seed)), fp)
        except Exception as error:
            html(banner("Simulation failed", f"{type(error).__name__}: {error}", "risk"))
            return
    bundle = state["lab_bundle"]
    if fp != json.dumps(bundle["fingerprints"], sort_keys=True):
        html(banner("Inputs changed", "Data or code changed since this run. Press Run simulation to refresh.", "warn"))
        return
    shock = scenario == "Shock"
    weights = asdict(PRESETS[focus])
    active = " · ".join(f"{k[2:]} {v:g}" for k, v in weights.items() if k.startswith("w_") and v)
    html('<div class="chips">' + chip(f"{LABELS[focus]} ({active})", dot="info") + chip(f"{scenario} scenario")
         + chip("seed", str(bundle["seed"])) + chip("orders", str(bundle["batch_count"])) + chip("pieces", f"{bundle['total_pieces']:,}")
         + chip("policy × scenario runs", str(len(bundle["summary"])))
         + chip("Single-seed diagnostic · course figures use ten seeds", dot="warn") + "</div>")
    if seed != bundle["seed"]:
        html(f'<div class="section-note">Showing seed {bundle["seed"]}. Press Run simulation to evaluate seed {int(seed)}.</div>')
    overview, tradeoffs, disruption, audit, course = st.tabs(
        ["Overview", "Objective trade-offs", "Disruption", "Order audit", "Course evidence"])
    with overview:
        overview_tab(bundle, focus, shock, workshops)
    with tradeoffs:
        tradeoff_tab(bundle, focus, shock, workshops, fp)
    with disruption:
        disruption_tab(bundle, focus, fp)
    with audit:
        audit_tab(bundle, focus, shock, workshops, fp)
    with course:
        course_tab()


# Overview ---------------------------------------------------------------------

def overview_tab(bundle, focus, shock, workshops):
    summary = bundle["summary"]
    subset = summary[summary["shock"] == shock]
    ours = subset[(subset.policy == "allocator") & (subset.objective == focus)].iloc[0]
    ef = subset[subset.policy == "earliest_finish"].iloc[0]
    tiles = "".join(kpi(label, fmt(metric, ours[metric]), f"Earliest finish <b>{esc(fmt(metric, ef[metric]))}</b>",
                        compare_badge(metric, ours[metric], ef[metric])) for metric, label, _ in HERO)
    html(f'<div class="grid c5">{tiles}</div>')
    if all(tied(ours[m], ef[m]) for m in METRICS):
        html(banner("Tie with earliest finish", f"{LABELS[focus]} makes the same choices as the earliest-finish rule here, so all eight "
                    "metrics are identical. A tie is not a win: this objective adds evidence and controls, not a better schedule.", "muted"))
    else:
        better = [METRIC_LABELS[m] for m in METRICS if ours[m] < ef[m] and not tied(ours[m], ef[m])]
        worse = [METRIC_LABELS[m] for m in METRICS if ours[m] > ef[m] and not tied(ours[m], ef[m])]
        html(banner("Against earliest finish", "Better on " + (", ".join(better) or "nothing") + ". Worse on "
                    + (", ".join(worse) or "nothing") + ". Remaining metrics tie.", "info" if better else "warn"))
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        section("How each policy performs", "All four comparison policies and all six objectives. Lower is better.")
        metric = st.selectbox("Metric", list(METRIC_LABELS), key="lab_metric", format_func=METRIC_LABELS.get, label_visibility="collapsed")
        plot = subset.assign(label=subset.apply(display_name, axis=1))
        plot["role"] = ["Ours" if (p == "allocator" and o == focus) else "Earliest finish" if p == "earliest_finish"
                        else "Baseline" if p != "allocator" else "Other objective" for p, o in zip(plot.policy, plot.objective)]
        chart(plot, {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": 18},
                     "encoding": {"y": {"field": "label", "type": "nominal", "sort": {"field": metric, "order": "ascending"}, "title": None,
                                        "axis": {"labelLimit": 240}},
                                  "x": {"field": metric, "type": "quantitative", "title": METRIC_LABELS[metric], "scale": {"zero": True}, "axis": {"tickCount": 8}},
                                  "color": {"field": "role", "type": "nominal",
                                            "scale": {"domain": ["Ours", "Earliest finish", "Baseline", "Other objective"],
                                                      "range": [OURS, HEURISTIC, BASE, "#3A4A60"]}},
                                  "tooltip": [{"field": "label", "title": "Policy"}, {"field": metric, "format": ",.2f", "title": METRIC_LABELS[metric]}]}},
              height=340)
    with right:
        section("Where the work goes", "Pieces per workshop. Concentration, not utilisation.")
        outcomes = bundle["outcomes"]
        rows = []
        for name, mask in ((LABELS[focus], (outcomes.policy == "allocator") & (outcomes.objective == focus)),
                           ("Earliest finish", outcomes.policy == "earliest_finish")):
            totals = outcomes[mask & (outcomes.shock == shock)].groupby("workshop")["pieces"].sum()
            rows += [{"workshop": w.name, "series": name, "pieces": int(totals.get(wid, 0))} for wid, w in workshops.items()]
        chart(pd.DataFrame(rows), {"mark": {"type": "bar", "cornerRadiusEnd": 3},
                                   "encoding": {"y": {"field": "workshop", "type": "nominal", "title": None, "sort": list(w.name for w in workshops.values())},
                                                "yOffset": {"field": "series"},
                                                "x": {"field": "pieces", "type": "quantitative", "title": "Pieces allocated"},
                                                "color": {"field": "series", "scale": {"domain": [LABELS[focus], "Earliest finish"], "range": [OURS, HEURISTIC]}},
                                                "tooltip": [{"field": "workshop"}, {"field": "series"}, {"field": "pieces", "format": ","}]}},
              height=340)


# Objective trade-offs ---------------------------------------------------------------

def tradeoff_tab(bundle, focus, shock, workshops, fp):
    summary = bundle["summary"]
    subset = summary[summary["shock"] == shock].copy()
    subset["label"] = subset.apply(display_name, axis=1)
    subset["short"] = subset.apply(short_name, axis=1)
    subset["fairness"] = 100 - subset["max_share"]
    subset["role"] = ["Ours" if (p == "allocator" and o == focus) else "Earliest finish" if p == "earliest_finish"
                      else "Baseline" if p != "allocator" else "Other objective" for p, o in zip(subset.policy, subset.objective)]
    section("Same orders, different objectives", "Each objective is only a weight configuration. Pick one above to highlight it.")
    cards = []
    for key, config in PRESETS.items():
        terms = "".join(f'<span class="chip"><i class="dot" style="background:{TERM_COLORS[t]}"></i>{esc(explain.TERM_LABELS[t])} <b>{getattr(config, "w_" + t):g}</b></span>'
                        for t in explain.TERMS if getattr(config, "w_" + t))
        style = ' style="border-color:rgba(78,217,230,.45);background:rgba(78,217,230,.06)"' if key == focus else ""
        cards.append(f'<div class="card tight"{style}><div style="font-weight:650;margin-bottom:8px">{esc(LABELS[key])}</div><div class="chips">{terms}</div></div>')
    html(f'<div class="grid c3">{"".join(cards)}</div>')

    def scatter(y, title, note):
        groups = []
        for (late, value), group in subset.groupby(["pct_late", y], sort=False):
            groups.append({"late": late, "value": value, "policies": " / ".join(group.label), "short": " / ".join(group.short),
                           "role": "Ours" if "Ours" in set(group.role) else group.role.iloc[0]})
        frame = pd.DataFrame(groups).sort_values("late").reset_index(drop=True)
        frame["above"] = [i % 2 == 0 for i in range(len(frame))]
        labels = [{"transform": [{"filter": f"{'' if above else '!'}datum.above"}],
                   "mark": {"type": "text", "align": "left", "dx": 9, "dy": -10 if above else 16, "fontSize": 12},
                   "encoding": {"x": {"field": "late", "type": "quantitative"}, "y": {"field": "value", "type": "quantitative"},
                                "text": {"field": "short"}}} for above in (True, False)]
        chart(frame, {"layer": [
            {"mark": {"type": "point", "filled": True, "size": 150, "opacity": .95},
             "encoding": {"x": {"field": "late", "type": "quantitative", "title": "Late batches (%) · lower is better", "scale": {"domain": [0, 100]}, "axis": {"values": [0, 20, 40, 60, 80, 100]}},
                          "y": {"field": "value", "type": "quantitative", "title": title, "scale": {"zero": False}},
                          "color": {"field": "role", "scale": {"domain": ["Ours", "Earliest finish", "Baseline", "Other objective"],
                                                              "range": [OURS, HEURISTIC, BASE, "#8D9DB0"]}},
                          "tooltip": [{"field": "policies", "title": "Policies"}, {"field": "late", "format": ".2f", "title": "Late (%)"},
                                      {"field": "value", "format": ",.2f", "title": title}]}},
            *labels]}, height=330)
        html(f'<div class="section-note">{esc(note)}</div>')

    left, right = st.columns(2, gap="large")
    with left:
        section("Lateness vs cost")
        scatter("total_cost", "Total cost (units) · lower is better", "Exact ties share one point; hover for every policy at that point.")
    with right:
        section("Lateness vs fairness")
        scatter("fairness", "Fairness = 100 − largest share · higher is better", "Fairness measures concentration of pieces, not capacity-relative equity.")

    section("Which workshops each objective uses", "Share of all pieces in this scenario. The objective changes where work goes.")
    outcomes = bundle["outcomes"]
    rows = []
    policies = [("allocator", key) for key in PRESETS] + [("earliest_finish", "none"), ("random_choice", "none")]
    for policy, objective in policies:
        part = outcomes[(outcomes.policy == policy) & (outcomes.objective == objective) & (outcomes.shock == shock)]
        totals = part.groupby("workshop")["pieces"].sum()
        for wid, w in workshops.items():
            share = 100 * totals.get(wid, 0) / bundle["total_pieces"]
            rows.append({"policy": LABELS[objective if policy == "allocator" else policy], "workshop": w.name, "share": share,
                         "text": f"{share:.0f}%" if share >= .5 else ""})
    order = [LABELS[o if p == "allocator" else p] for p, o in policies]
    chart(pd.DataFrame(rows), {"layer": [
        {"mark": {"type": "rect", "cornerRadius": 3},
         "encoding": {"x": {"field": "workshop", "type": "nominal", "title": None, "sort": [w.name for w in workshops.values()], "axis": {"labelAngle": 0}},
                      "y": {"field": "policy", "type": "nominal", "title": None, "sort": order, "axis": {"labelLimit": 240}},
                      "color": {"field": "share", "type": "quantitative", "title": "Share (%)",
                                "scale": {"range": ["#0C1A2B", "#155E70", "#4ED9E6"], "domain": [0, 75]}, "legend": None},
                      "tooltip": [{"field": "policy"}, {"field": "workshop"}, {"field": "share", "format": ".1f", "title": "Share (%)"}]}},
        {"mark": {"type": "text", "fontSize": 12.5},
         "encoding": {"x": {"field": "workshop", "type": "nominal", "sort": [w.name for w in workshops.values()]},
                      "y": {"field": "policy", "type": "nominal", "sort": order}, "text": {"field": "text"},
                      "color": {"condition": {"test": "datum.share > 40", "value": "#04131A"}, "value": "#D7E1EC"}}}]}, height=330)
    sandbox(bundle, focus, shock, fp)


def sandbox(bundle, focus, shock, fp):
    state = st.session_state
    with st.container(key="sandbox"):
        html(f'<div class="hero-label"><span class="section-title">Custom what-if</span>{pill("Sandbox · not an evaluated preset", "warn")}</div>'
             '<div class="section-note">Set your own weights and replay this seed. Uses the same normalised score terms. '
             'Results are single-seed, are not saved and do not change the official presets or course evidence.</div>')
        cols = st.columns(5)
        for col, term in zip(cols, explain.TERMS):
            with col:
                st.slider(explain.TERM_LABELS[term], 0.0, 1.0, step=0.05, key=f"sb_{term}")
        weights = tuple(float(state[f"sb_{t}"]) for t in explain.TERMS)
        if st.button("Run sandbox replay", key="sb_run", disabled=not any(weights)):
            state["sb_result"] = {"weights": weights, "seed": bundle["seed"], "shock": shock}
        result = state.get("sb_result")
        if not any(weights):
            html('<div class="section-note">All weights are zero; at least one weight must be positive.</div>')
        if result and result["seed"] == bundle["seed"] and result["shock"] == shock:
            metrics, _ = sandbox_run(result["seed"], result["shock"], result["weights"], fp)
            summary = bundle["summary"]
            subset = summary[summary.shock == shock]
            ours = subset[(subset.policy == "allocator") & (subset.objective == focus)].iloc[0]
            ef = subset[subset.policy == "earliest_finish"].iloc[0]
            shown = " · ".join(f"{explain.TERM_LABELS[t].lower()} {w:g}" for t, w in zip(explain.TERMS, result["weights"]) if w)
            rows = [[esc(METRIC_LABELS[m]), f"<b>{esc(fmt(m, metrics[m]))}</b>", esc(fmt(m, ours[m])), esc(fmt(m, ef[m]))] for m, _, _ in HERO]
            html(f'<div class="section-note" style="margin-top:6px">Sandbox weights: {esc(shown)} · seed {result["seed"]} · '
                 f'{"shock" if shock else "normal"} scenario</div>'
                 + table(["Metric", "Sandbox", LABELS[focus], "Earliest finish"], rows, right=range(1, 4)))
        elif result:
            html('<div class="section-note">Seed or scenario changed. Run the sandbox again.</div>')


# Disruption -----------------------------------------------------------------------

def disruption_tab(bundle, focus, fp):
    detail = trace(bundle["seed"], focus, fp)
    target, name = detail["shocked_workshop_id"], detail["shocked_workshop_name"]
    days = pd.DataFrame(detail["rows"])
    events = [e for e in detail["events"] if e["workshop_id"] == target]
    flags = [e for e in events if e["status"] == "suspect"]
    clears = [e for e in events if e["status"] == "cleared"]
    first = flags[0] if flags else None
    cleared = clears[0] if clears else None
    sent_flagged = int(days["ours_pieces_while_suspect"].sum())
    before = int(days.loc[days.day < (first["flagged_on_day"] if first else 10**6), "ours_pieces"].sum())
    tiles = [kpi("Closed workshop", name, f"{esc(target)} · days 30 to 44 · 31 Jan to 14 Feb"),
             kpi("First anomaly flag", f"Day {first['flagged_on_day']}" if first else "Not flagged",
                 (f"Queue expected {first['expected']:.1f} d, observed <b>{first['observed']:.1f} d</b>" if first else "No unexplained jump seen")),
             kpi("Pieces sent while flagged", f"{sent_flagged:,}", f"{before:,} pieces sent before the flag"),
             kpi("Flag cleared", f"Day {cleared['cleared_on_day']}" if cleared else "Still flagged" if first else "n/a",
                 "Queue back within the expected range" if cleared else "")]
    html(f'<div class="grid c4">{"".join(tiles)}</div>')
    section(f"Routing to {name} through the shock run", f"Pieces sent to {name} per day: {LABELS[focus]} vs the random baseline.")
    long = days.melt(id_vars=["day", "date"], value_vars=["ours_pieces", "random_pieces"], var_name="series", value_name="pieces")
    long["series"] = long["series"].map({"ours_pieces": LABELS[focus], "random_pieces": "Random baseline"})
    long = long[long.pieces > 0].copy()
    long["x"] = long["day"] + long["series"].map({LABELS[focus]: -0.22, "Random baseline": 0.22})
    marks = [{"day": 30, "end": 44, "label": "Closure window", "kind": "closure"}]
    if first:
        marks.append({"day": first["flagged_on_day"], "end": cleared["cleared_on_day"] if cleared else int(days.day.max()),
                      "label": "Flagged as suspect", "kind": "flag"})
    rules = ([{"day": first["flagged_on_day"], "text": f"First flag · day {first['flagged_on_day']}", "color": "#F4BB55"}] if first else []) + \
            ([{"day": cleared["cleared_on_day"], "text": f"Cleared · day {cleared['cleared_on_day']}", "color": "#4AD889"}] if cleared else [])
    top = max(int(long.pieces.max()) if len(long) else 1, 1)
    chart(long, {"layer": [
        {"data": {"values": [m for m in marks if m["kind"] == "closure"]}, "mark": {"type": "rect", "color": "#FF7068", "opacity": .16},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "x2": {"field": "end"}}},
        {"data": {"values": [m for m in marks if m["kind"] == "flag"]}, "mark": {"type": "rect", "color": "#F4BB55", "opacity": .07},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "x2": {"field": "end"}}},
        {"data": {"values": [{"day": 37, "text": "Closure window", "y": top * 1.08}]},
         "mark": {"type": "text", "color": "#FF8A82", "fontSize": 12.5, "fontWeight": 600},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}, "text": {"field": "text"}}},
        {"mark": {"type": "bar", "width": 5, "cornerRadiusEnd": 2},
         "encoding": {"x": {"field": "x", "type": "quantitative", "title": "Day of the replay (day 0 = 1 Jan 2026)",
                            "scale": {"domain": [0, int(days.day.max()) + 1], "nice": False}},
                      "y": {"field": "pieces", "type": "quantitative", "title": f"Pieces sent to {name}", "scale": {"domain": [0, top * 1.18]}},
                      "color": {"field": "series", "scale": {"domain": [LABELS[focus], "Random baseline"], "range": [OURS, BASE]}},
                      "tooltip": [{"field": "day"}, {"field": "date"}, {"field": "series"}, {"field": "pieces", "format": ","}]}},
        {"data": {"values": rules}, "mark": {"type": "rule", "strokeDash": [5, 4], "strokeWidth": 2},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "color": {"field": "color", "type": "nominal", "scale": None}}},
        {"data": {"values": [{**r, "y": top * .96} for r in rules]}, "mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12.5, "fontWeight": 600},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}, "text": {"field": "text"},
                      "color": {"field": "color", "type": "nominal", "scale": None}}},
    ]}, height=320)
    html(banner("Why the flag can come before the closure",
                "The course simulator adds a stuck batch's full closure delay to that workshop's queue as soon as the batch is waiting. "
                f"The monitor sees that queue jump and flags {name}. It never receives the closure dates or the target. "
                "An early flag is a reaction to simulated queue data, not evidence of real-world advance warning.", "info"))
    summary = bundle["summary"]
    paired = summary.pivot_table(index=["policy", "objective"], columns="shock", values="pct_late").reset_index()
    paired["label"] = paired.apply(display_name, axis=1)
    long2 = pd.concat([paired.assign(scenario="Normal", late=paired[False]), paired.assign(scenario="Shock", late=paired[True])])
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        section("Normal vs shock: late batches", f"Seed {bundle['seed']} only. Ten-seed averages are under Course evidence.")
        chart(long2[["label", "scenario", "late"]], {"mark": {"type": "bar", "cornerRadiusEnd": 3},
              "encoding": {"y": {"field": "label", "type": "nominal", "title": None, "sort": {"field": "late", "order": "ascending"}, "axis": {"labelLimit": 240}},
                           "yOffset": {"field": "scenario"}, "x": {"field": "late", "type": "quantitative", "title": "Late batches (%)"},
                           "color": {"field": "scenario", "scale": {"domain": ["Normal", "Shock"], "range": [HEURISTIC, "#FF7068"]}},
                           "tooltip": [{"field": "label"}, {"field": "scenario"}, {"field": "late", "format": ".2f"}]}}, height=360)
    with right:
        section("Change under shock", "Shock minus normal. Positive means worse.")
        rows = []
        late_days = summary.pivot_table(index=["policy", "objective"], columns="shock", values="late_days").reset_index()
        for item in paired.assign(change=paired[True] - paired[False]).sort_values("change").to_dict("records"):
            days_row = late_days[(late_days.policy == item["policy"]) & (late_days.objective == item["objective"])].iloc[0]
            ours = item["policy"] == "allocator" and item["objective"] == focus
            rows.append(([f"<b>{esc(item['label'])}</b>" if ours else esc(item["label"]), f"{item[False]:.1f}", f"{item[True]:.1f}",
                          f'<span class="{"neg" if item["change"] > 0 else "pos"}">{item["change"]:+.1f}</span>',
                          f"{days_row[True] - days_row[False]:+.2f}"], "chosen" if ours else ""))
        html(table(["Policy", "Normal %", "Shock %", "Δ pp", "Δ late days"], [r for r, _ in rows], right=range(1, 5),
                   classes=[c for _, c in rows]))
    with st.expander("Observed anomaly and recovery evidence"):
        if events:
            json_block(events, height=260)
        else:
            st.write("No anomaly events for the closed workshop in this run.")


# Order audit ------------------------------------------------------------------------

def audit_tab(bundle, focus, shock, workshops, fp):
    state = st.session_state
    outcomes = bundle["outcomes"]
    own = outcomes[(outcomes.shock == shock) & (outcomes.policy == "allocator") & (outcomes.objective == focus)]
    a, b = st.columns([1, 3], vertical_alignment="bottom")
    with a:
        only_late = st.toggle("Late orders only", key="lab_late")
    visible = own[own["late"]] if only_late else own
    if visible.empty:
        html(banner("No late orders", "Every order in this view was on time.", "ok"))
        return
    labels = {r.order_id: f"{r.order_id} · sent {explain.short_date(r.sent_date)} · {workshops[r.workshop].name} · "
              + ("late" if r.late else "on time") for r in visible.itertuples()}
    if state.get("lab_order") not in labels:
        state["lab_order"] = next(iter(labels))
    with b:
        order = st.selectbox("Inspect an automatic decision", list(labels), key="lab_order", format_func=labels.get)
    record = replay(bundle["seed"], focus, shock, fp)[order]
    outcome = visible[visible.order_id == order].iloc[0]
    chosen = explain.chosen_row(record)
    won = explain.why_won(record)
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        facts = [("Order", order), ("Sent", explain.long_date(outcome.sent_date)), ("Due", explain.long_date(outcome.due_date)),
                 ("Pieces", f"{int(outcome.pieces):,}"), ("Chosen", f"{workshops[outcome.workshop].name} ({outcome.workshop})"),
                 ("Estimated return", explain.long_date(chosen["eta_date"])),
                 ("Realised turnaround", f"{outcome.turnaround:.1f} days"),
                 ("Outcome", ("Late" if outcome.late else "On time") + (" · defective batch, rework added" if outcome.defective else ""))]
        rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in facts)
        html(f'<div class="card"><div class="hero-label"><h4 style="margin:0">Automatic decision</h4>'
             f'{pill("Late" if outcome.late else "On time", "warn" if outcome.late else "ok")}</div>'
             f'<dl class="kv" style="margin-top:12px">{rows}</dl><div class="why" style="margin-top:14px"><b>Why this won</b>'
             f'<p style="font-size:15px">{esc(won["sentence"] if won else record["reason_chosen"])}</p></div></div>')
        st.download_button("Download this decision (JSON)", json.dumps(record, indent=2, default=str),
                           file_name=f"{order}-simulation-decision.json", mime="application/json", key="lab_download")
    with right:
        section("Every candidate at the moment of choice", "Pre-allocation estimates. Realised outcomes add sampled rework and any closure.")
        body, classes = [], []
        for row in explain.selection_order(record):
            body.append([f"<b>{esc(row['name'])}</b><small>{esc(row['workshop_id'])}</small>", f"{row['queue_days']:.1f}",
                         f"{row['processing_days']:.1f}", str(row["lead_days"]), esc(explain.short_date(row["eta_date"])),
                         f'<span class="{"neg" if row["days_to_spare"] < 0 else "pos"}">{row["days_to_spare"]:+d}</span>',
                         f"{row['total_cost']:,.0f}", f"{row['expected_defect_rate']:.0%}", f"{row['score']:.5f}"])
            classes.append("chosen" if row["workshop_id"] == record["chosen_workshop"] else "")
        for row in record.get("ineligible", []):
            body.append([f"<b>{esc(row['name'])}</b><small>{esc(row['workshop_id'])}</small>",
                         esc(explain.ineligible_headline(row["reason"]))] + ["n/a"] * 7)
            classes.append("dim")
        html(table(["Workshop", "Queue d", "Process d", "Transport d", "Back", "Spare", "Cost", "Defect", "Score"], body,
                   right=range(1, 9), classes=classes))
        config = explain.effective_config(record["objective_name"])
        section("Score decomposition")
        html(score_bars(explain.score_breakdown(explain.selection_order(record)[:6], config), record["chosen_workshop"],
                        explain.TERMS, explain.TERM_LABELS, "Weighted penalty per term from the recorded score terms. Lower wins."))


# Course evidence ----------------------------------------------------------------------

def course_tab():
    data = evidence.load()
    meta, prov = data["metadata"], data["provenance"]
    seeds = meta.get("seed_values", [])
    status = (pill("Evidence matches current code", "ok") if prov["matches"]
              else pill("Code changed since this evidence was generated", "warn"))
    html('<div class="chips">' + chip(f"paired seeds ({seeds[0]} to {seeds[-1]})" if seeds else "paired seeds", str(meta.get("seeds")))
         + chip("simulator runs", str(len(data["per_seed"]))) + chip("orders per run", str(meta.get("batch_count")))
         + chip("pieces per run", f"{meta.get('total_pieces', 0):,}") + chip("Whole-job mode, stages off") + status + "</div>")
    if not prov["matches"]:
        html(banner("Stale evidence", "Re-run eval/run_simulator.py before quoting these numbers. Changed: " + ", ".join(prov["stale"]), "warn"))
    html('<div class="section-note">Read from the committed files in eval/ (results.csv, results_per_seed.csv, objective_checks.csv, '
         'shock_changes.csv). This page does not recompute them. Ties use the evaluator\'s rule and are never counted as wins.</div>')
    tone = {"tie": "muted", "win": "ok", "loss": "warn"}
    word = {"tie": "Tie", "win": "Supported", "loss": "Limitation"}
    html('<div class="card"><h4>What the ten-seed evidence says</h4><div class="grid" style="gap:10px">' + "".join(
        f'<div style="display:flex;gap:12px;align-items:baseline">{pill(word[f["tone"]], tone[f["tone"]])}<span>{esc(f["text"])}</span></div>'
        for f in evidence.findings(data["results"], data["checks"])) + "</div></div>")
    left, right = st.columns([1, 1.1], gap="large")
    with left:
        section("Primary objective: lateness", "Mean of ten paired seeds. % late and mean late days, lower is better.")
        rows, classes = [], []
        primary = evidence.primary_table(data["results"])
        ours = primary[-1]
        for item in primary:
            same = evidence.tied(item["normal_pct_late"], ours["normal_pct_late"]) and evidence.tied(item["shock_pct_late"], ours["shock_pct_late"])
            tag = " " + pill("Ties ours", "muted", soft=True) if same and not item["ours"] else ""
            rows.append([f"<b>{esc(item['label'])}</b>{tag}", f"{item['normal_pct_late']:.2f}", f"{item['normal_late_days']:.2f}",
                         f"{item['shock_pct_late']:.2f}", f"{item['shock_late_days']:.2f}"])
            classes.append("chosen" if item["ours"] else "")
        html(table(["Policy", "Normal % late", "Normal late days", "Shock % late", "Shock late days"], rows, right=range(1, 5), classes=classes))
    with right:
        section("Course criteria and guardrails", "From objective_checks.csv. A qualifying win needs the metric win and its guardrail.")
        cells = {"qualifying": ("Qualifies", "ok"), "tie": ("Tie", "muted"), "guardrail": ("Guardrail fails", "warn"), "no_win": ("No win", "risk")}
        matrix = evidence.check_matrix(data["results"], data["checks"])
        groups = {}
        for item in matrix:
            groups.setdefault((item["objective"], item["scenario"]), {})[item["comparator"]] = item["outcome"]
        rows = [[f"<b>{esc(evidence.OBJECTIVE_LABELS[o])}</b><small>{esc(s)}</small>"]
                + [pill(*cells[g[c]], soft=True) for c in evidence.COMPARATORS] for (o, s), g in groups.items()]
        html(table(["Objective", "Random", "Biggest", "Cheapest", "Earliest finish"], rows))
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        section("Variation across seeds", "Late batches per seed. Each dot is one run; spread shows seed sensitivity.")
        spread = evidence.seed_spread(data["per_seed"])
        chart(spread, {"mark": {"type": "tick", "thickness": 2.5, "size": 16},
                       "encoding": {"y": {"field": "label", "type": "nominal", "title": None, "axis": {"labelLimit": 260}},
                                    "x": {"field": "pct_late", "type": "quantitative", "title": "Late batches (%) per seed"},
                                    "yOffset": {"field": "scenario"},
                                    "color": {"field": "scenario", "scale": {"domain": ["Normal", "Shock"], "range": [HEURISTIC, "#FF7068"]}},
                                    "tooltip": [{"field": "label"}, {"field": "scenario"}, {"field": "seed"}, {"field": "pct_late", "format": ".2f"}]}},
              height=330)
    with right:
        section("Robustness: change under shock", "Mean paired change, shock minus normal. Positive means worse.")
        frame = data["shock"].copy()
        frame["label"] = [evidence.policy_label(p, o) for p, o in zip(frame.policy, frame.objective)]
        frame = frame.sort_values("delta_pct_late")
        rows = [[esc(r.label), f'<span class="{"" if abs(r.delta_pct_late) < 1e-9 else "neg" if r.delta_pct_late > 0 else "pos"}">{r.delta_pct_late:+.2f}</span>',
                 f"{r.delta_late_days:+.3f}"] for r in frame.itertuples()]
        html(table(["Policy", "Δ % late (pp)", "Δ late days"], rows, right=(1, 2),
                   classes=["chosen" if (p == "allocator" and o == "robustness") else "" for p, o in zip(frame.policy, frame.objective)]))
    language_card()


def language_card():
    status = evidence.language_status()
    mix = "".join(f'<span class="chip"><b>{n}</b> {esc(kind)}</span>' for kind, n in status["mix"])
    run = status["inbox_run"]
    run_text = (f"{run.get('mode')} run on {run.get('requests')} requests ({run.get('model')})" if run and run.get("requests")
                else "Not run in this checkout")
    rows = [("Official requests", str(status["requests"])),
            ("Final human labels", f"{status['final_labels']} of {status['requests']}"),
            ("Reviewer labels", f"{status['reviewer_1']} and {status['reviewer_2']} of {status['requests']}"),
            ("Reconciliation", status["reconciliation"].capitalize()),
            ("Live inbox evaluation", run_text),
            ("Held-out requests", "None in the repository yet")]
    kv = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows)
    html(f'<div class="card"><div class="hero-label"><h4 style="margin:0">Language evaluation status</h4>'
         f'{pill("Accuracy not reported yet", "warn")}</div><div class="grid c2" style="margin-top:12px">'
         f'<dl class="kv">{kv}</dl><div><div class="section-note" style="margin-bottom:8px">Official request mix (data_dictionary.md)</div>'
         f'<div class="chips">{mix}</div><div class="section-note" style="margin-top:12px">Behaviour accuracy will be shown only after two '
         'independent reviewers complete and reconcile labels for all 30 requests. Synthetic test fixtures and rehearsal runs are never '
         'evidence of language accuracy.</div></div></div></div>')
