"""Simulation Lab: a strategy lab that tests the dispatch policy against baselines.

Interactive tabs replay one seed through the unchanged harness (experiments.py,
shock_trace.py). Course Evidence reads the committed ten-seed files and never
recomputes them. The custom sandbox runs extra single-seed replays with user
weights; it never changes PRESETS or any saved evaluation.
"""

from __future__ import annotations

from datetime import date, timedelta
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
from ui.components import (BEAM, BENCH, OURS, SHOCK, SLATE, TERM_CLASS, banner, chart, esc, html, metric_tile, page_head,
                           score_bars, section, status_pill, table, verdict_badge)

LABELS = {"random_choice": "Random", "greedy_biggest": "Biggest", "cheapest": "Cheapest",
          "earliest_finish": "Earliest finish", "lateness": "Lateness", "defect": "Quality only", "fairness": "Fairness",
          "robustness": "Robustness", "hybrid_lateness_fairness": "Lateness and fairness",
          "hybrid_lateness_defect": "Lateness and quality"}
HERO = [("pct_late", "Late batches", "{:.2f}%"), ("late_days", "Average late days", "{:.2f}"),
        ("total_cost", "Cost", "{:,.0f}"), ("max_share", "Largest workshop share", "{:.1f}%")]
FORMATS = {"pct_late": "{:.2f}%", "late_days": "{:.2f}", "mean_days": "{:.1f} days", "p90_days": "{:.1f} days",
           "pct_defect": "{:.1f}%", "pct_defect_pieces": "{:.1f}%", "total_cost": "{:,.0f}", "max_share": "{:.1f}%"}
METRIC_LABELS = {"pct_late": "Late batches", "late_days": "Average late days", "mean_days": "Mean turnaround",
                 "p90_days": "P90 turnaround", "pct_defect": "Defective batches", "pct_defect_pieces": "Defect exposure (pieces)",
                 "total_cost": "Cost", "max_share": "Largest workshop share"}
DEFAULTS = {"lab_seed": 5105, "lab_focus": "lateness", "lab_scenario": "Normal",
            "sb_lateness": 0.5, "sb_defect": 0.0, "sb_fairness": 0.5, "sb_robustness": 0.0, "sb_cost": 0.0}
BASELINES = ["random_choice", "greedy_biggest", "cheapest", "earliest_finish"]
DAY0 = date(2026, 1, 1)


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


def name_of(policy, objective) -> str:
    return LABELS[objective if policy == "allocator" else policy]


def role(policy, objective, focus) -> str:
    if policy == "allocator" and objective == focus:
        return "Our policy"
    return "Earliest finish" if policy == "earliest_finish" else "Other policies"


def fmt(metric, value) -> str:
    return FORMATS.get(metric, "{:.2f}").format(value)


def compare_word(ours, other) -> tuple[str, str]:
    """(verdict word, kind) for a lower-is-better measure."""
    if tied(ours, other):
        return "Tie", "tie"
    return ("Better", "win") if ours < other else ("Worse", "loss")


def day_label(day: int) -> str:
    d = DAY0 + timedelta(days=int(day))
    return f"{d.day} {d:%b}"


# Shared lab pieces ------------------------------------------------------------

def duel(eyebrow, ours_label, ours_value, ours_note, other_label, other_value, other_note, word, kind, caption) -> str:
    """Head-to-head hero: our policy against the strongest simple rule."""
    return (f'<div class="duel glass"><div class="side ours"><small>{esc(eyebrow)}</small><strong>{esc(ours_value)}</strong>'
            f'<span><b>{esc(ours_label)}</b>. {esc(ours_note)}</span></div>'
            f'<div class="vs">{verdict_badge(word, kind)}<span class="meta">{esc(caption)}</span></div>'
            f'<div class="side right"><small>Strong heuristic</small><strong>{esc(other_value)}</strong>'
            f'<span><b>{esc(other_label)}</b>. {esc(other_note)}</span></div></div>')


def scale(points, *, title="Late batches, lower is better") -> str:
    """Policies on one 0 to 100% axis. Ours wears the beam; baselines stay slate."""
    marks, previous, low = [], None, False
    for label, value, ours in sorted(points, key=lambda p: (p[1], not p[2])):
        low = (not low) if previous is not None and value - previous < 12 else False
        previous = value
        cls = "mk" + (" ours" if ours else "") + (" low" if low else "") + (" edge-l" if value < 8 else " edge-r" if value > 92 else "")
        marks.append(f'<div class="{cls}" style="left:{min(max(value, 0), 100):.2f}%"><i></i><span>{esc(label)}<em>{value:.2f}%</em></span></div>')
    ticks = "".join(f'<div class="tick" style="left:{t}%">{t}%</div>' for t in (0, 25, 50, 75, 100))
    return (f'<div class="card scale-card"><div class="eyebrow">{esc(title)}</div>'
            f'<div class="scale"><div class="axis"></div>{"".join(marks)}{ticks}</div></div>')


def render(workshops):
    state = st.session_state
    for key, value in DEFAULTS.items():
        state.setdefault(key, value)
    head, bar = st.columns([1, 1.3], vertical_alignment="bottom")
    with head:
        page_head("Simulation lab", "Strategy lab")
    with bar:
        with st.container(key="lab_bar"):
            a, b, c, d = st.columns([1.5, 1.15, .85, .7], vertical_alignment="bottom")
            with a:
                focus = st.selectbox("Objective", list(PRESETS), key="lab_focus", format_func=lambda k: LABELS[k])
            with b:
                scenario = st.radio("Scenario", ["Normal", "Shock"], key="lab_scenario", horizontal=True)
            with c:
                seed = st.number_input("Seed", min_value=0, max_value=2_147_483_647, key="lab_seed")
            with d:
                run = st.button("Run", key="lab_run", type="primary", width="stretch", icon=":material/play_arrow:")
    fp = fingerprint()
    if run or "lab_bundle" not in state:
        try:
            state["lab_bundle"] = experiment(int(seed) if run else int(state.get("lab_bundle", {}).get("seed", seed)), fp)
        except Exception as error:
            html(banner("Simulation failed", f" {type(error).__name__}: {error}", "risk"))
            return
    bundle = state["lab_bundle"]
    if fp != json.dumps(bundle["fingerprints"], sort_keys=True):
        html(banner("Inputs changed", " Data or code changed since this run. Press Run to refresh.", "warn"))
        return
    shock = scenario == "Shock"
    overview, tradeoffs, disruption, audit, course = st.tabs(["Overview", "Tradeoffs", "Disruption", "Order Audit", "Course Evidence"])
    with overview:
        overview_tab(bundle, focus, shock, int(seed))
    with tradeoffs:
        tradeoff_tab(bundle, focus, shock, workshops, fp)
    with disruption:
        disruption_tab(bundle, focus, fp)
    with audit:
        audit_tab(bundle, focus, shock, workshops, fp)
    with course:
        course_tab()


# Overview ---------------------------------------------------------------------

def overview_tab(bundle, focus, shock, seed):
    subset = bundle["summary"][bundle["summary"]["shock"] == shock]
    ours = subset[(subset.policy == "allocator") & (subset.objective == focus)].iloc[0]
    ef = subset[subset.policy == "earliest_finish"].iloc[0]
    html(f'<div class="meta">Seed {bundle["seed"]}, {"shock" if shock else "normal"} scenario, {bundle["batch_count"]} orders, '
         f'{bundle["total_pieces"]:,} pieces. A single-seed diagnostic: the official ten-seed results are under Course Evidence.</div>')
    if seed != bundle["seed"]:
        html(f'<div class="meta">Press Run to evaluate seed {seed}.</div>')
    word, kind = compare_word(ours.pct_late, ef.pct_late)
    html(duel("Our policy", LABELS[focus], fmt("pct_late", ours.pct_late), f"{fmt('late_days', ours.late_days)} average late days",
              "Earliest finish", fmt("pct_late", ef.pct_late), f"{fmt('late_days', ef.late_days)} average late days",
              word, kind, "late batches against earliest finish"))
    points = [(LABELS[focus], ours.pct_late, True)] + [(LABELS[p], subset[subset.policy == p].iloc[0].pct_late, False) for p in BASELINES]
    html(scale(points))
    tiles = []
    for metric, label, _ in HERO:
        verdict_word, verdict_kind = compare_word(ours[metric], ef[metric])
        tone = {"tie": "muted", "win": "ok", "loss": "warn"}[verdict_kind]
        tiles.append(metric_tile(label, fmt(metric, ours[metric]),
                                 f'Earliest finish {esc(fmt(metric, ef[metric]))} {status_pill(verdict_word, tone)}'))
    html(f'<div class="kpis g4">{"".join(tiles)}</div>')
    if all(tied(ours[m], ef[m]) for m in METRICS):
        html(banner(f"{LABELS[focus]} ties earliest finish on all eight measures in this run.",
                    " It makes the same choices as the strongest simple rule. A tie is not a win.", "muted"))
    else:
        better = [METRIC_LABELS[m].lower() for m in METRICS if ours[m] < ef[m] and not tied(ours[m], ef[m])]
        worse = [METRIC_LABELS[m].lower() for m in METRICS if ours[m] > ef[m] and not tied(ours[m], ef[m])]
        html(banner(f"Against earliest finish, {LABELS[focus].lower()} is better on {len(better)} and worse on {len(worse)} of eight measures.",
                    (" Better: " + ", ".join(better) + "." if better else "") + (" Worse: " + ", ".join(worse) + "." if worse else ""),
                    "info" if len(better) >= len(worse) else "warn"))
    with st.expander("Late batches for every policy"):
        plot = subset.assign(label=[name_of(p, o) for p, o in zip(subset.policy, subset.objective)],
                             role=[role(p, o, focus) for p, o in zip(subset.policy, subset.objective)])
        plot["text"] = plot["pct_late"].map(lambda v: f"{v:.1f}%")
        sort = plot.sort_values(["pct_late", "label"])["label"].tolist()
        chart(plot, {"layer": [
            {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": 14},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": sort, "title": None, "axis": {"labelLimit": 220}},
                          "x": {"field": "pct_late", "type": "quantitative", "title": "Late batches (%)", "scale": {"domain": [0, 100]},
                                "axis": {"values": [0, 20, 40, 60, 80, 100]}},
                          "color": {"field": "role", "scale": {"domain": ["Our policy", "Earliest finish", "Other policies"], "range": [OURS, BENCH, SLATE]}},
                          "tooltip": [{"field": "label", "title": "Policy"}, {"field": "pct_late", "format": ".2f", "title": "Late batches (%)"}]}},
            {"mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12.5},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": sort}, "x": {"field": "pct_late", "type": "quantitative"}, "text": {"field": "text"}}}]},
            height=340)


# Tradeoffs -------------------------------------------------------------------------

def tradeoff_tab(bundle, focus, shock, workshops, fp):
    subset = bundle["summary"][bundle["summary"]["shock"] == shock].copy()
    subset["label"] = [name_of(p, o) for p, o in zip(subset.policy, subset.objective)]
    subset["role"] = [role(p, o, focus) for p, o in zip(subset.policy, subset.objective)]
    subset["fairness"] = 100 - subset["max_share"]
    section("Same orders, different objectives", "An objective is only a weight configuration. The selected one is edge-lit.")
    cards = []
    for key, config in PRESETS.items():
        chips = "".join(f'<span class="weight"><i class="{TERM_CLASS[t]}"></i>{esc(explain.TERM_LABELS[t])} <b>{getattr(config, "w_" + t):g}</b></span>'
                        for t in explain.TERMS if getattr(config, "w_" + t))
        cards.append(f'<div class="card obj{" beam selected" if key == focus else ""}"><b>{esc(LABELS[key])}</b>'
                     f'<div class="weights" style="margin-top:10px">{chips}</div></div>')
    html(f'<div class="grid g3" style="margin-top:10px">{"".join(cards)}</div>')
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        axis = st.segmented_control("Compare lateness with", ["Cost", "Fairness"], key="lab_tradeoff", default="Cost")
        y, title = ("total_cost", "Total cost") if axis != "Fairness" else ("fairness", "Fairness: 100 minus largest share")
        groups = []
        for (late, value), group in subset.groupby(["pct_late", y], sort=False):
            key = set(group.label) & {"Random", "Biggest", "Cheapest", "Earliest finish", LABELS[focus]}
            groups.append({"late": late, "value": value, "policies": " and ".join(group.label),
                           "text": " and ".join(l for l in group.label if l in key),
                           "role": "Our policy" if "Our policy" in set(group.role) else group.role.iloc[0]})
        frame = pd.DataFrame(groups).sort_values("late").reset_index(drop=True)
        frame["above"] = [i % 2 == 0 for i in range(len(frame))]
        labels = [{"transform": [{"filter": f"{'' if up else '!'}datum.above"}],
                   "mark": {"type": "text", "align": "left", "dx": 10, "dy": -11 if up else 17, "fontSize": 12},
                   "encoding": {"x": {"field": "late", "type": "quantitative"}, "y": {"field": "value", "type": "quantitative"}, "text": {"field": "text"}}}
                  for up in (True, False)]
        ours = "datum.role === 'Our policy'"
        chart(frame, {"layer": [
            {"mark": {"type": "point", "filled": True, "opacity": 1},
             "encoding": {"x": {"field": "late", "type": "quantitative", "title": "Late batches (%), lower is better", "scale": {"domain": [0, 100]},
                                "axis": {"values": [0, 20, 40, 60, 80, 100]}},
                          "y": {"field": "value", "type": "quantitative", "title": title, "scale": {"zero": False}},
                          "color": {"field": "role", "scale": {"domain": ["Our policy", "Earliest finish", "Other policies"], "range": [OURS, BENCH, SLATE]}},
                          "size": {"condition": {"test": ours, "value": 260}, "value": 130},
                          "stroke": {"condition": {"test": ours, "value": BEAM}, "value": "#FFFFFF"},
                          "strokeWidth": {"condition": {"test": ours, "value": 3}, "value": 2},
                          "tooltip": [{"field": "policies", "title": "Policies"}, {"field": "late", "format": ".2f", "title": "Late (%)"},
                                      {"field": "value", "format": ",.2f", "title": title}]}}, *labels]}, height=340)
        html('<div class="meta">Slate points are the other objectives and baselines. Hover any point for its name and values.</div>')
    with right:
        section("Where the work goes", "Share of all pieces in this scenario.")
        outcomes = bundle["outcomes"]
        rows = []
        policies = [("allocator", key) for key in PRESETS] + [("earliest_finish", "none"), ("random_choice", "none")]
        for policy, objective in policies:
            part = outcomes[(outcomes.policy == policy) & (outcomes.objective == objective) & (outcomes.shock == shock)]
            totals = part.groupby("workshop")["pieces"].sum()
            for wid, w in workshops.items():
                share = 100 * totals.get(wid, 0) / bundle["total_pieces"]
                rows.append({"policy": name_of(policy, objective), "workshop": w.name, "share": share, "text": f"{share:.0f}" if share >= .5 else ""})
        order = [name_of(p, o) for p, o in policies]
        names = [w.name for w in workshops.values()]
        chart(pd.DataFrame(rows), {"layer": [
            {"mark": {"type": "rect", "cornerRadius": 4, "stroke": "#FFFFFF", "strokeWidth": 2},
             "encoding": {"x": {"field": "workshop", "type": "nominal", "title": None, "sort": names, "axis": {"labelAngle": -30}},
                          "y": {"field": "policy", "type": "nominal", "title": None, "sort": order, "axis": {"labelLimit": 200}},
                          "color": {"field": "share", "type": "quantitative", "scale": {"range": ["#F1F4FA", "#9DB0F4", "#3E5FD9"], "domain": [0, 75]}, "legend": None},
                          "tooltip": [{"field": "policy"}, {"field": "workshop"}, {"field": "share", "format": ".1f", "title": "Share (%)"}]}},
            {"mark": {"type": "text", "fontSize": 12},
             "encoding": {"x": {"field": "workshop", "type": "nominal", "sort": names}, "y": {"field": "policy", "type": "nominal", "sort": order},
                          "text": {"field": "text"}, "color": {"condition": {"test": "datum.share > 40", "value": "#FFFFFF"}, "value": "#122233"}}}]},
            height=360)
    with st.expander("Custom what-if sandbox"):
        sandbox(bundle, focus, shock, fp)


def sandbox(bundle, focus, shock, fp):
    state = st.session_state
    html(f'<div style="display:flex;gap:12px;align-items:center">{status_pill("Sandbox, not an evaluated preset", "warn")}'
         '<span class="note">Set your own weights and replay this seed. Nothing is saved and the official presets do not change.</span></div>')
    cols = st.columns(5)
    for col, term in zip(cols, explain.TERMS):
        with col:
            st.slider(explain.TERM_LABELS[term], 0.0, 1.0, step=0.05, key=f"sb_{term}")
    weights = tuple(float(state[f"sb_{t}"]) for t in explain.TERMS)
    if st.button("Run sandbox replay", key="sb_run", disabled=not any(weights)):
        state["sb_result"] = {"weights": weights, "seed": bundle["seed"], "shock": shock}
    result = state.get("sb_result")
    if result and result["seed"] == bundle["seed"] and result["shock"] == shock:
        metrics, _ = sandbox_run(result["seed"], result["shock"], result["weights"], fp)
        subset = bundle["summary"][bundle["summary"].shock == shock]
        ours = subset[(subset.policy == "allocator") & (subset.objective == focus)].iloc[0]
        ef = subset[subset.policy == "earliest_finish"].iloc[0]
        shown = ", ".join(f"{explain.TERM_LABELS[t].lower()} {w:g}" for t, w in zip(explain.TERMS, result["weights"]) if w)
        rows = [[esc(METRIC_LABELS[m]), f"<b>{esc(fmt(m, metrics[m]))}</b>", esc(fmt(m, ours[m])), esc(fmt(m, ef[m]))] for m, _, _ in HERO]
        html(f'<div class="meta" style="margin:6px 0">Sandbox weights: {esc(shown)}. Seed {result["seed"]}, {"shock" if shock else "normal"} scenario.</div>'
             + table(["Measure", "Sandbox", LABELS[focus], "Earliest finish"], rows, right=range(1, 4)))
    elif result:
        html('<div class="meta">Seed or scenario changed. Run the sandbox again.</div>')


# Disruption -----------------------------------------------------------------------

def disruption_tab(bundle, focus, fp):
    detail = trace(bundle["seed"], focus, fp)
    target, name = detail["shocked_workshop_id"], detail["shocked_workshop_name"]
    days = pd.DataFrame(detail["rows"])
    end = int(days.day.max()) + 1
    events = [e for e in detail["events"] if e["workshop_id"] == target]
    first = next((e for e in events if e["status"] == "suspect"), None)
    cleared = next((e for e in events if e["status"] == "cleared"), None)
    summary = bundle["summary"]
    ours_n = summary[(summary.policy == "allocator") & (summary.objective == focus) & (~summary.shock)].iloc[0]
    ours_s = summary[(summary.policy == "allocator") & (summary.objective == focus) & (summary.shock)].iloc[0]
    sent_flagged = int(days["ours_pieces_while_suspect"].sum())
    robust = sent_flagged if focus == "robustness" else int(sum(r["ours_pieces_while_suspect"] for r in trace(bundle["seed"], "robustness", fp)["rows"]))

    flag, clear = (first["flagged_on_day"] if first else None), (cleared["cleared_on_day"] if cleared else None)
    segments = []
    if flag is not None and flag < 30:
        segments += [("normal", "Normal operation", 0, flag), ("anomaly", "Anomaly observed", flag, 30)]
    else:
        segments.append(("normal", "Normal operation", 0, 30))
    segments.append(("closure", "Closure", 30, 44))
    recover_end = clear if clear and clear > 44 else 44
    if recover_end > 44:
        segments.append(("recovery", "Recovery", 44, recover_end))
    segments.append(("normal", "Normal operation", recover_end, end))
    bars = "".join(f'<div class="phase {kind}" style="flex:{max(b - a, 1)}"><b>{esc(label)}</b><span>{esc(day_label(a))} to {esc(day_label(b))}</span></div>'
                   for kind, label, a, b in segments if b > a)
    section(f"{name} closes for two weeks", f"Shock run, seed {bundle['seed']}. The closure and target are hidden from every policy.")
    html(f'<div class="phases" style="margin-top:10px">{bars}</div><div class="phase-axis"><span>Day 0, 1 Jan</span><span>Day {end}, {esc(day_label(end))}</span></div>')
    tiles = [metric_tile("Affected workshop", name, "Closed day 30 to 44"),
             metric_tile("First anomaly flag", f"Day {flag}" if first else "Not flagged",
                         esc(f"{day_label(flag)}, queue {first['observed']:.1f} d against {first['expected']:.1f} d expected") if first else ""),
             metric_tile("Pieces routed while suspect", f"{sent_flagged:,}",
                         esc(f"{LABELS[focus]} objective" + ("" if focus == "robustness" else f". Robustness objective: {robust:,}"))),
             metric_tile("Normal lateness", f"{ours_n.pct_late:.2f}%", "Late batches, this seed"),
             metric_tile("Shock lateness", f"{ours_s.pct_late:.2f}%", esc(f"{ours_s.pct_late - ours_n.pct_late:+.2f} points against normal"))]
    html(f'<div class="kpis g5">{"".join(tiles)}</div>')
    with st.expander("About early flags"):
        html('<div class="note">The course simulator adds a stuck batch\'s full closure delay to that workshop\'s queue as soon as the batch is waiting. '
             f'The monitor sees the queue jump and flags {esc(name)}. It never receives the closure dates or the target. '
             'An early flag is a reaction to simulated queue data, not evidence of real-world advance warning.</div>')
    section(f"Daily pieces sent to {name}", f"{LABELS[focus]} objective against the random baseline.")
    long = days.melt(id_vars=["day", "date"], value_vars=["ours_pieces", "random_pieces"], var_name="series", value_name="pieces")
    long["series"] = long["series"].map({"ours_pieces": "Our policy", "random_pieces": "Random baseline"})
    long = long[long.pieces > 0].copy()
    long["x"] = long["day"] + long["series"].map({"Our policy": -0.22, "Random baseline": 0.22})
    top = max(int(long.pieces.max()) if len(long) else 1, 1)
    rules = ([{"day": flag, "text": f"First flag, day {flag}", "color": "#8C5A06"}] if first else []) + \
            ([{"day": clear, "text": f"Flag cleared, day {clear}", "color": "#167F4C"}] if cleared else [])
    chart(long, {"layer": [
        {"data": {"values": [{"start": 30, "end": 44}]}, "mark": {"type": "rect", "color": "#F56F67", "opacity": .1},
         "encoding": {"x": {"field": "start", "type": "quantitative"}, "x2": {"field": "end"}}},
        {"mark": {"type": "bar", "width": 5, "cornerRadiusEnd": 2},
         "encoding": {"x": {"field": "x", "type": "quantitative", "title": "Day of the replay", "scale": {"domain": [0, end], "nice": False}},
                      "y": {"field": "pieces", "type": "quantitative", "title": "Pieces sent", "scale": {"domain": [0, top * 1.2]}},
                      "color": {"field": "series", "scale": {"domain": ["Our policy", "Random baseline"], "range": [OURS, SLATE]}},
                      "tooltip": [{"field": "day"}, {"field": "date"}, {"field": "series"}, {"field": "pieces", "format": ","}]}},
        {"data": {"values": rules}, "mark": {"type": "rule", "strokeDash": [5, 4], "strokeWidth": 2},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "color": {"field": "color", "type": "nominal", "scale": None}}},
        {"data": {"values": [{**r, "y": top * 1.12} for r in rules]}, "mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12.5, "fontWeight": 600},
         "encoding": {"x": {"field": "day", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}, "text": {"field": "text"},
                      "color": {"field": "color", "type": "nominal", "scale": None}}},
    ]}, height=260)


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
        html(banner("No late orders", " Every order in this view was on time.", "info"))
        return
    labels = {r.order_id: f"{r.order_id}, sent {explain.short_date(r.sent_date)}, {workshops[r.workshop].name}, " + ("late" if r.late else "on time")
              for r in visible.itertuples()}
    if state.get("lab_order") not in labels:
        state["lab_order"] = next(iter(labels))
    with b:
        order = st.selectbox("Automatic decision", list(labels), key="lab_order", format_func=labels.get)
    record = replay(bundle["seed"], focus, shock, fp)[order]
    outcome = visible[visible.order_id == order].iloc[0]
    chosen = explain.chosen_row(record)
    won = explain.why_won(record)
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        facts = [("Order", order), ("Sent", explain.long_date(outcome.sent_date)), ("Due", explain.long_date(outcome.due_date)),
                 ("Pieces", f"{int(outcome.pieces):,}"), ("Chosen", workshops[outcome.workshop].name),
                 ("Estimated return", explain.long_date(chosen["eta_date"])), ("Actual turnaround", f"{outcome.turnaround:.1f} days"),
                 ("Outcome", ("Late" if outcome.late else "On time") + (", rework after a defect" if outcome.defective else ""))]
        html(f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><div class="title" style="font-size:18px">Automatic decision</div>'
             f'{status_pill("Late" if outcome.late else "On time", "warn" if outcome.late else "ok")}</div>'
             f'<dl class="kv" style="margin-top:12px">{"".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in facts)}</dl>'
             f'<p style="margin:14px 0 0">{esc(won["sentence"] if won else record["reason_chosen"])}</p></div>')
        st.download_button("Download this decision", json.dumps(record, indent=2, default=str),
                           file_name=f"{order}-simulation-decision.json", mime="application/json", key="lab_download")
    with right:
        section("Every candidate at the moment of choice", "Estimates before allocation. The actual outcome adds sampled rework and any closure.")
        body, classes = [], []
        for row in explain.selection_order(record):
            spare = row["days_to_spare"]
            body.append([f"<b>{esc(row['name'])}</b>", esc(explain.short_date(row["eta_date"])), f'<span class="{"neg" if spare < 0 else ""}">{spare:+d}</span>',
                         f"{row['total_cost']:,.0f}", f"{row['expected_defect_rate']:.0%}", f"{row['score']:.5f}"])
            classes.append("chosen" if row["workshop_id"] == record["chosen_workshop"] else "")
        for row in record.get("ineligible", []):
            body.append([f"<b>{esc(row['name'])}</b>", esc(explain.ineligible_headline(row["reason"]))] + ["n/a"] * 4)
            classes.append("dim")
        html(table(["Workshop", "Return", "Spare", "Cost", "Defect", "Score"], body, right=range(1, 6), classes=classes))
        config = explain.effective_config(record["objective_name"])
        with st.expander("Score breakdown"):
            html('<div class="dark-panel">' + score_bars(explain.score_breakdown(explain.selection_order(record)[:6], config),
                                                         record["chosen_workshop"], explain.TERMS, explain.TERM_LABELS) + "</div>")


# Course evidence ----------------------------------------------------------------------

def course_tab():
    data = evidence.load()
    meta, prov, results = data["metadata"], data["provenance"], data["results"]
    seeds = meta.get("seed_values", [])
    status = status_pill("Matches current code", "ok") if prov["matches"] else status_pill("Code changed since this evidence", "warn")
    html(f'<div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px"><div><div class="eyebrow">Official ten-seed evidence</div>'
         f'<div class="title" style="margin-top:4px">Primary objective: lateness</div>'
         f'<div class="meta">{meta.get("seeds")} paired seeds, {seeds[0] if seeds else ""} to {seeds[-1] if seeds else ""}. '
         f'{len(data["per_seed"])} simulator runs. Read from the committed files in eval/.</div></div>{status}</div>')
    if not prov["matches"]:
        html(banner("Re-run the evaluation before quoting these numbers.", " Changed: " + ", ".join(prov["stale"]), "warn"))
    primary = {item["policy"]: item for item in evidence.primary_table(results)}
    ours, ef = primary["allocator"], primary["earliest_finish"]
    word, kind = compare_word(ours["normal_pct_late"], ef["normal_pct_late"])
    html(duel("Our policy", "Lateness objective", f'{ours["normal_pct_late"]:.2f}%', f'Late batches. Under shock {ours["shock_pct_late"]:.2f}%',
              "Earliest finish", f'{ef["normal_pct_late"]:.2f}%', f'Late batches. Under shock {ef["shock_pct_late"]:.2f}%',
              word, kind, "same late rate, ten seeds" if kind == "tie" else "late batches, ten seeds"))
    points = [("Ours", ours["normal_pct_late"], True)] + [(evidence.POLICY_LABELS[p], primary[p]["normal_pct_late"], False) for p in BASELINES]
    html(scale(points, title="Late batches in normal runs, lower is better"))
    matrix = evidence.check_matrix(results, data["checks"])
    beats = all(r["outcome"] == "qualifying" for r in matrix if r["objective"] == "lateness" and r["comparator"] != "earliest_finish")
    ties = all(r["outcome"] == "tie" for r in matrix if r["objective"] == "lateness" and r["comparator"] == "earliest_finish")
    html('<div style="display:flex;gap:10px;flex-wrap:wrap">' + (status_pill("Beats all three supplied baselines", "ok") if beats else "")
         + (status_pill("Ties earliest finish, not a win", "muted") if ties else "") + "</div>")
    cards = {r["objective"]: r for r in evidence.objective_scorecard(results, data["checks"])}
    figures = {"fairness": f'{evidence.row(results, "allocator", "fairness", False).max_share:.1f}% largest share',
               "robustness": (f'{evidence.row(results, "allocator", "robustness", True).pct_late - evidence.row(results, "allocator", "robustness", False).pct_late:+.2f}'
                              " points under shock"),
               "defect": (f'{evidence.row(results, "allocator", "defect", False).pct_defect_pieces:.1f}% defect, '
                          f'{evidence.row(results, "allocator", "defect", False).pct_late:.1f}% late')}
    titles = {"fairness": "Fairness", "robustness": "Robustness", "defect": "Quality"}
    verdict_words = {"Fails lateness guardrail": "Guardrail fails"}
    blocks = []
    for key in ("fairness", "robustness", "defect"):
        card = cards[key]
        tone = {"ok": "ok", "risk": "risk"}.get(card["tone"], "muted")
        blocks.append(f'<div class="vblock {tone}"><div class="k">{esc(titles[key])}</div>'
                      f'<div class="v {tone}">{esc(verdict_words.get(card["verdict"], card["verdict"]))}</div>'
                      f'<div class="fig">{esc(figures[key])}</div><p>{esc(card["detail"])}</p></div>')
    html(f'<div class="grid g3">{"".join(blocks)}</div>')
    hybrids = "".join(f'<div class="hy"><b>{esc(cards[k]["label"])}</b><span>{esc(cards[k]["detail"])}</span>{status_pill(cards[k]["verdict"], "muted")}</div>'
                      for k in ("hybrid_lateness_fairness", "hybrid_lateness_defect"))
    html(f'<div class="card hybrids"><div class="eyebrow" style="margin-bottom:6px">Hybrid objectives</div>{hybrids}</div>')
    with st.expander("Every comparison against every comparator"):
        cells = {"qualifying": ("Qualifies", "ok"), "tie": ("Tie", "muted"), "guardrail": ("Guardrail fails", "warn"), "no_win": ("No win", "risk")}
        groups = {}
        for item in matrix:
            groups.setdefault((item["objective"], item["scenario"]), {})[item["comparator"]] = item["outcome"]
        body = [[f"<b>{esc(evidence.OBJECTIVE_LABELS[o])}</b><small>{esc(s)}</small>"] + [status_pill(*cells[g[c]]) for c in evidence.COMPARATORS]
                for (o, s), g in groups.items()]
        html(table(["Objective", "Random", "Biggest", "Cheapest", "Earliest finish"], body))
    with st.expander("Change under shock, every policy"):
        frame = data["shock"].copy()
        frame["label"] = [evidence.policy_label(p, o) for p, o in zip(frame.policy, frame.objective)]
        frame = frame.sort_values("delta_pct_late")
        body = [[esc(r.label), f'<span class="{"" if abs(r.delta_pct_late) < 1e-9 else "neg" if r.delta_pct_late > 0 else "pos"}">{r.delta_pct_late:+.2f}</span>',
                 f"{r.delta_late_days:+.3f}"] for r in frame.itertuples()]
        html(table(["Policy", "Change in late batches (points)", "Change in late days"], body, right=(1, 2)))
    with st.expander("Variation across seeds"):
        spread = evidence.seed_spread(data["per_seed"])
        chart(spread, {"mark": {"type": "tick", "thickness": 2.5, "size": 16},
                       "encoding": {"y": {"field": "label", "type": "nominal", "title": None, "axis": {"labelLimit": 260}},
                                    "x": {"field": "pct_late", "type": "quantitative", "title": "Late batches (%) per seed"},
                                    "yOffset": {"field": "scenario"},
                                    "color": {"field": "scenario", "scale": {"domain": ["Normal", "Shock"], "range": [OURS, SHOCK]}},
                                    "tooltip": [{"field": "label"}, {"field": "scenario"}, {"field": "seed"}, {"field": "pct_late", "format": ".2f"}]}},
              height=320)
    language_card()


def language_card():
    status = evidence.language_status()
    run = status["inbox_run"]
    run_text = (f"{run.get('mode')} run, {run.get('requests')} requests" if run and run.get("requests") else "Not run in this checkout")
    rows = [("Official requests", str(status["requests"])), ("Final human labels", f"{status['final_labels']} of {status['requests']}"),
            ("Reviewer labels", f"{status['reviewer_1']} and {status['reviewer_2']} of {status['requests']}"),
            ("Reconciliation", status["reconciliation"].capitalize()), ("Live inbox evaluation", run_text),
            ("Held-out requests", "None yet")]
    mix = "".join(f'<span class="weight"><b>{n}</b> {esc(kind)}</span>' for kind, n in status["mix"])
    html(f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><div class="title" style="font-size:18px">Language evaluation</div>'
         f'{status_pill("Accuracy not reported yet", "warn")}</div><div class="grid g2" style="margin-top:12px">'
         f'<dl class="kv">{"".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows)}</dl>'
         f'<div><div class="weights">{mix}</div><div class="note" style="margin-top:12px">Accuracy appears only after two independent reviewers '
         'label and reconcile all 30 requests. Test fixtures and rehearsal runs are never evidence of language accuracy.</div></div></div></div>')
