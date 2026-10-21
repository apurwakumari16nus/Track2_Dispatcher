"""Simulation Lab: how does our policy perform, and what can we honestly claim?

The hero, comparison cards, objective verdicts and Course Evidence read the
committed ten-seed files (eval/) through ui.evidence and ui.lab_evidence; they
never recompute them. Tabs marked as a seed replay one seed through the
unchanged harness (experiments.py, shock_trace.py) as a diagnostic. The custom
sandbox runs extra single-seed replays with user weights; it never changes
PRESETS or any saved evaluation.
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
from ui import lab_evidence as le
from ui.components import (TERM_CLASS, banner, chart, esc, html, icon, metric_tile, score_bars, section, status_pill, table)

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
# Chart palette: Threadline royal for our policy, light blue for our other objectives,
# slate for supplied baselines, deep slate for the strong simple rule, amber for shock.
OURS, OTHER_OBJ, BASE, STRONG, SHOCK_C = "#2A77E8", "#9DBDF0", "#A9B4C2", "#5E6D82", "#E09A2C"
OUTCOME_DARK = {"ok": "dk-ok", "muted": "dk-muted", "risk": "dk-risk", "warn": "dk-warn"}
OBJECTIVES = ["lateness", "fairness", "robustness", "defect", "hybrid_lateness_fairness", "hybrid_lateness_defect"]


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
    if policy == "allocator":
        return "Our other objectives"
    return "Earliest finish" if policy == "earliest_finish" else "Supplied baselines"


ROLE_DOMAIN = ["Our policy", "Our other objectives", "Earliest finish", "Supplied baselines"]
ROLE_RANGE = [OURS, OTHER_OBJ, STRONG, BASE]


def fmt(metric, value) -> str:
    return FORMATS.get(metric, "{:.2f}").format(value)


def day_label(day: int) -> str:
    d = DAY0 + timedelta(days=int(day))
    return f"{d.day} {d:%b}"


def set_focus(objective):
    st.session_state["lab_focus"] = objective


# Page ----------------------------------------------------------------------------

SPACES = {"performance": ":material/insights: Performance", "tradeoffs": ":material/tune: Tradeoffs",
          "disruption": ":material/report: Disruption", "evidence": ":material/verified: Evidence"}
QUESTIONS = {"performance": "How does our policy perform against the baselines?",
             "tradeoffs": "What do we gain or give up when the objective changes?",
             "disruption": "What happens when a workshop closes without warning?",
             "evidence": "Can we defend these results academically?"}


def render(workshops):
    state = st.session_state
    for key, value in DEFAULTS.items():
        state.setdefault(key, value)
    state.setdefault("lab_space", "performance")
    head, bar = st.columns([1.05, 1.1], vertical_alignment="bottom")
    with head:
        html('<div class="kicker"><span>Simulation lab</span></div>'
             '<div class="home-title" style="margin-top:12px">How does our policy perform?</div>'
             '<div class="home-sub">120 orders replayed through the shared course simulator and compared with the supplied baselines over ten seeds.</div>')
    with bar, st.container(key="lab_bar"):
        a, b = st.columns([1.4, 1.1], vertical_alignment="bottom")
        with a:
            focus = st.selectbox("Objective", list(PRESETS), key="lab_focus", format_func=lambda k: LABELS[k])
        with b:
            scenario = st.radio("Scenario", ["Normal", "Shock"], key="lab_scenario", horizontal=True)
    with st.container(key="lab_nav"):
        space = st.segmented_control("Workspace", list(SPACES), key="lab_space", required=True, format_func=SPACES.get,
                                     label_visibility="collapsed")
        html(f'<div class="ws-q">{esc(QUESTIONS[space])}</div>')
    shock = scenario == "Shock"
    data = evidence.load()
    if not data["provenance"]["matches"]:
        html(banner("Re-run the evaluation before quoting these numbers.", " Changed since the evidence was produced: "
                    + ", ".join(data["provenance"]["stale"]), "warn"))
    if space == "performance":
        performance_space(data, focus, shock)
    elif space == "tradeoffs":
        tradeoffs_space(data, focus, shock, workshops)
    elif space == "disruption":
        disruption_space(data, focus, workshops)
    else:
        evidence_space(data, focus, shock, workshops)


def keep_seed():
    st.session_state["lab_seed_value"] = st.session_state["lab_seed"]


def seed_bar(label: str):
    """Seed controls for single-seed diagnostics. Returns (bundle, fingerprint) or (None, fp) if it cannot run."""
    state = st.session_state
    # The seed widget is not drawn on every workspace, so Streamlit forgets it; this mirror is the source of truth.
    state.setdefault("lab_seed_value", int(state.get("lab_bundle", {}).get("seed", DEFAULTS["lab_seed"])))
    state["lab_seed"] = state["lab_seed_value"]
    with st.container(key="lab_seedbar"):
        a, b, c = st.columns([2.6, .8, .6], vertical_alignment="bottom")
        with a:
            html(f'<div class="sd-note"><b>{esc(label)}</b><span>A single-seed diagnostic: the official ten-seed results are under Evidence.</span></div>')
        with b:
            seed = st.number_input("Seed", min_value=0, max_value=2_147_483_647, key="lab_seed", on_change=keep_seed)
        with c:
            run = st.button("Run", key="lab_run", type="primary", width="stretch", icon=":material/play_arrow:")
    fp = fingerprint()
    if run or "lab_bundle" not in state:
        try:
            state["lab_bundle"] = experiment(int(seed) if run else int(state.get("lab_bundle", {}).get("seed", seed)), fp)
        except Exception as error:
            html(banner("Simulation failed", f" {type(error).__name__}: {error}", "risk"))
            return None, fp
    bundle = state["lab_bundle"]
    if fp != json.dumps(bundle["fingerprints"], sort_keys=True):
        html(banner("Inputs changed", " Data or code changed since this run. Press Run to refresh.", "warn"))
        return None, fp
    if int(seed) != bundle["seed"]:
        html(f'<div class="meta">Showing seed {bundle["seed"]}. Press Run to evaluate seed {int(seed)}.</div>')
    return bundle, fp


def chart_card(key: str, title: str, sub: str, source: str):
    """An analytical surface with a title, a one-line question and its data source."""
    box = st.container(key=f"chart_{key}")
    with box:
        html(f'<div class="an-title">{esc(title)}</div><div class="an-sub">{esc(sub)}</div>')
    return box, source


def source_note(text: str):
    html(f'<div class="an-src">Source: {esc(text)}</div>')


# Performance ----------------------------------------------------------------------

def performance_space(data, focus, shock):
    hero_block(data, focus, shock)
    comparison_cards(data, focus, shock)
    frame = data["results"].copy()
    keep = [("allocator", focus)] + [(p, "none") for p in BASELINES]
    frame = frame[[(p, o) in keep for p, o in zip(frame.policy, frame.objective)]].copy()
    frame["label"] = [name_of(p, o) if p != "allocator" else f"Our policy ({LABELS[o].lower()})" for p, o in zip(frame.policy, frame.objective)]
    frame["scenario"] = frame.shock.map({False: "Normal", True: "Shock"})
    metric, title = ("pct_late", "Late batches (%)")
    order = frame[~frame.shock].sort_values(metric)["label"].tolist()
    box, _ = chart_card("perf_shock", "Normal and shock, side by side",
                        "Late batches per policy in both scenarios. A short line means the policy holds up when a workshop closes.", "")
    with box:
        wide = frame.pivot_table(index="label", columns="scenario", values=metric).reset_index()
        chart(frame, {"layer": [
            {"data": {"values": wide.to_dict("records")}, "mark": {"type": "rule", "strokeWidth": 4, "strokeCap": "round", "color": "#D3DCE6"},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": order, "title": None}, "x": {"field": "Normal", "type": "quantitative"}, "x2": {"field": "Shock"}}},
            {"mark": {"type": "point", "filled": True, "size": 150, "opacity": 1, "stroke": "#FFFFFF", "strokeWidth": 1.5},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": order, "title": None, "axis": {"labelLimit": 240}},
                          "x": {"field": metric, "type": "quantitative", "title": title, "scale": {"domain": [0, 100]}, "axis": {"values": [0, 20, 40, 60, 80, 100]}},
                          "color": {"field": "scenario", "title": None, "scale": {"domain": ["Normal", "Shock"], "range": [STRONG, SHOCK_C]}},
                          "tooltip": [{"field": "label", "title": "Policy"}, {"field": "scenario"}, {"field": metric, "format": ".2f", "title": title}]}}]}, height=230)
        source_note("eval/ ten-seed results (seeds 5105 to 5114), normal and shock runs.")


# Tradeoffs ------------------------------------------------------------------------

def tradeoffs_space(data, focus, shock, workshops):
    objectives_row(data, focus, shock)
    config = PRESETS[focus]
    chips = "".join(f'<span class="weight"><i class="{TERM_CLASS[t]}"></i>{esc(explain.TERM_LABELS[t])} <b>{getattr(config, "w_" + t):g}</b></span>'
                    for t in explain.TERMS if getattr(config, "w_" + t))
    html(f'<div class="wt-line"><span>{esc(LABELS[focus])} uses these weights</span>{chips}<span class="meta">Same engine, same orders. Only the weights change.</span></div>')
    res = data["results"][data["results"].shock == shock].copy()
    res["label"] = [name_of(p, o) for p, o in zip(res.policy, res.objective)]
    res["role"] = [role(p, o, focus) for p, o in zip(res.policy, res.objective)]
    axes = {"Cost": ("total_cost", "Total cost", ",.0f"), "Fairness": ("max_share", "Largest workshop share (%)", ".1f"),
            "Quality": ("pct_defect_pieces", "Defect exposure, pieces (%)", ".1f")}
    left, right = st.columns([1.35, 1], gap="medium")
    with left:
        box, _ = chart_card("trade", "Lateness against a second goal",
                            "Each point is one policy, ten-seed average. Down and to the left is better on both.", "")
        with box:
            pick = st.segmented_control("Second goal", list(axes), key="lab_tradeoff", default="Cost", label_visibility="collapsed") or "Cost"
            y, title, f = axes[pick]
            res["text"] = ""
            for _, group in res.groupby([res.pct_late.round(6), res[y].round(4)]):
                names = sorted(group.label, key=lambda n: n != LABELS[focus])
                shown = [n for n in names if n in (LABELS[focus], "Random", "Biggest", "Cheapest", "Earliest finish")]
                if shown:
                    res.loc[group.index[0], "text"] = " and ".join(shown) + (" (tie)" if len(names) > 1 and len(shown) > 1 else "")
            res = res.sort_values("role", key=lambda r: r.map({"Our policy": 3, "Earliest finish": 2}).fillna(1))
            chart(res, {"layer": [
                {"mark": {"type": "point", "filled": True, "opacity": 1, "stroke": "#FFFFFF", "strokeWidth": 2},
                 "encoding": {"x": {"field": "pct_late", "type": "quantitative", "title": "Late batches (%)", "scale": {"domain": [0, 100]},
                                    "axis": {"values": [0, 20, 40, 60, 80, 100]}},
                              "y": {"field": y, "type": "quantitative", "title": title, "scale": {"zero": False}, "axis": {"format": f}},
                              "color": {"field": "role", "title": None, "scale": {"domain": ROLE_DOMAIN, "range": ROLE_RANGE}},
                              "size": {"condition": {"test": "datum.role === 'Our policy'", "value": 300}, "value": 130},
                              "tooltip": [{"field": "label", "title": "Policy"}, {"field": "pct_late", "format": ".2f", "title": "Late (%)"},
                                          {"field": y, "format": f, "title": title}]}},
                {"mark": {"type": "text", "align": "left", "dx": 12, "dy": -17, "fontSize": 12.5, "fontWeight": 600},
                 "encoding": {"x": {"field": "pct_late", "type": "quantitative"}, "y": {"field": y, "type": "quantitative"},
                              "text": {"field": "text"}, "color": {"value": "#33465E"}}}]}, height=330)
            source_note(f"eval/ ten-seed results, {'shock' if shock else 'normal'} scenario. No point is an optimised result; each is a preset run as is.")
    with right:
        cards = []
        for key, cfg in PRESETS.items():
            row = evidence.row(data["results"], "allocator", key, shock)
            weights = ", ".join(f"{explain.TERM_LABELS[t].lower()} {getattr(cfg, 'w_' + t):g}" for t in explain.TERMS if getattr(cfg, "w_" + t))
            cards.append(f'<div class="tw{" on" if key == focus else ""}"><div><b>{esc(LABELS[key])}</b><small>{esc(weights)}</small></div>'
                         f'<dl><dt>Late</dt><dd>{row.pct_late:.1f}%</dd><dt>Cost</dt><dd>{row.total_cost:,.0f}</dd>'
                         f'<dt>Share</dt><dd>{row.max_share:.1f}%</dd><dt>Defect</dt><dd>{row.pct_defect_pieces:.1f}%</dd></dl></div>')
        html('<div class="an-card"><div class="an-title">What each objective trades</div><div class="an-sub">Ten-seed averages for every preset. '
             'Lower is better in every column.</div><div class="tws">' + "".join(cards) + '</div><div class="an-src">Source: eval/ ten-seed results.</div></div>')
    with st.expander("Workload by workshop and custom weights (single seed)"):
        bundle, fp = seed_bar("Seed diagnostics")
        if bundle is not None:
            workload_heatmap(bundle, shock, workshops)
            st.divider()
            sandbox(bundle, focus, shock, fp)


def workload_heatmap(bundle, shock, workshops):
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
    section(f"Where the work goes, seed {bundle['seed']}", "Share of all pieces by workshop, percent.")
    chart(pd.DataFrame(rows), {"layer": [
        {"mark": {"type": "rect", "cornerRadius": 4, "stroke": "#FFFFFF", "strokeWidth": 2},
         "encoding": {"x": {"field": "workshop", "type": "nominal", "title": None, "sort": names, "axis": {"labelAngle": 0}},
                      "y": {"field": "policy", "type": "nominal", "title": None, "sort": order, "axis": {"labelLimit": 200}},
                      "color": {"field": "share", "type": "quantitative", "scale": {"range": ["#F2F6FB", "#9DBDF0", "#1F63C9"], "domain": [0, 75]}, "legend": None},
                      "tooltip": [{"field": "policy"}, {"field": "workshop"}, {"field": "share", "format": ".1f", "title": "Share (%)"}]}},
        {"mark": {"type": "text", "fontSize": 12},
         "encoding": {"x": {"field": "workshop", "type": "nominal", "sort": names}, "y": {"field": "policy", "type": "nominal", "sort": order},
                      "text": {"field": "text"}, "color": {"condition": {"test": "datum.share > 40", "value": "#FFFFFF"}, "value": "#102238"}}}]},
        height=320)


# Disruption -----------------------------------------------------------------------

def disruption_space(data, focus, workshops):
    bundle, fp = seed_bar("Closure replay")
    if bundle is None:
        return
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
    sent = int(days["ours_pieces_while_suspect"].sum())
    robust = sent if focus == "robustness" else int(sum(r["ours_pieces_while_suspect"] for r in trace(bundle["seed"], "robustness", fp)["rows"]))
    flag, clear = (first["flagged_on_day"] if first else None), (cleared["cleared_on_day"] if cleared else None)
    official = evidence.row(data["results"], "allocator", focus, True).pct_late - evidence.row(data["results"], "allocator", focus, False).pct_late
    steps = [
        ("normal", "Normal operation", f"Day 0 to {min(flag or 30, 30)}", "All eight workshops run on their supplied queues.", "Simulator"),
        ("truth", f"{name} closes", f"Day 30 to 44, {day_label(30)} to {day_label(44)}",
         "Simulator ground truth. The closure, its dates and its target are hidden from every policy.", "Simulator, hidden"),
        ("seen", "Anomaly observed" if first else "No anomaly flagged",
         f"Day {flag}, {day_label(flag)}" if first else "Not flagged in this seed",
         (f"The queue monitor sees {first['observed']:.1f} days queued against {first['expected']:.1f} expected and flags {name} as suspect. "
          "This can come before day 30: the simulator adds a stuck batch's full delay to the queue at once, so an early flag is a "
          "reaction to simulated queue data, not real advance warning.") if first else "The queue never grew enough to trip the monitor.", "Observed"),
        ("route", "Routing response", f"While flagged{f', cleared day {clear}' if clear else ''}",
         f"{sent:,} pieces sent to {name} while it was suspect under the {LABELS[focus].lower()} objective"
         + ("." if focus == "robustness" else f"; the robustness objective sent {robust:,}."), "Engine decision"),
        ("outcome", "Measured outcome", f"Seed {bundle['seed']}",
         f"Late batches {ours_n.pct_late:.2f}% normal, {ours_s.pct_late:.2f}% under shock ({ours_s.pct_late - ours_n.pct_late:+.2f} points). "
         f"Official ten-seed change: {official:+.2f} points.", "Measured"),
    ]
    left, right = st.columns([1, 1.25], gap="medium")
    with left:
        html('<div class="an-card"><div class="an-title">Event timeline</div><div class="an-sub">What the simulator did, what the monitor saw, '
             'and what the engine did about it.</div><ol class="evt">'
             + "".join(f'<li class="{k}"><span class="evt-dot"></span><div><div class="evt-h"><b>{esc(t)}</b><em>{esc(tag)}</em></div>'
                       f'<small>{esc(when)}</small><p>{esc(body)}</p></div></li>' for k, t, when, body, tag in steps)
             + f'</ol><div class="an-src">Source: shock_trace.py replay, seed {bundle["seed"]}, plus eval/ ten-seed results for the official change.</div></div>')
    with right:
        box, _ = chart_card("daily", f"Pieces sent to {name}, day by day",
                            f"{LABELS[focus]} objective against the random baseline. Shaded: the closure. Dashed: the monitor's flag and clear.", "")
        with box:
            long = days.melt(id_vars=["day", "date"], value_vars=["ours_pieces", "random_pieces"], var_name="series", value_name="pieces")
            long["series"] = long["series"].map({"ours_pieces": "Our policy", "random_pieces": "Random baseline"})
            long = long[long.pieces > 0].copy()
            long["x"] = long["day"] + long["series"].map({"Our policy": -0.22, "Random baseline": 0.22})
            top = max(int(long.pieces.max()) if len(long) else 1, 1)
            rules = ([{"day": flag, "text": f"Flag, day {flag}", "color": "#8C5A06"}] if first else []) + \
                    ([{"day": clear, "text": f"Cleared, day {clear}", "color": "#0B6F61"}] if cleared else [])
            chart(long, {"layer": [
                {"data": {"values": [{"start": 30, "end": 44}]}, "mark": {"type": "rect", "color": "#F56F67", "opacity": .1},
                 "encoding": {"x": {"field": "start", "type": "quantitative"}, "x2": {"field": "end"}}},
                {"mark": {"type": "bar", "width": 5, "cornerRadiusEnd": 2},
                 "encoding": {"x": {"field": "x", "type": "quantitative", "title": "Day of the replay", "scale": {"domain": [0, end], "nice": False}},
                              "y": {"field": "pieces", "type": "quantitative", "title": "Pieces sent", "scale": {"domain": [0, top * 1.25]}},
                              "color": {"field": "series", "title": None, "scale": {"domain": ["Our policy", "Random baseline"], "range": [OURS, BASE]}},
                              "tooltip": [{"field": "day"}, {"field": "date"}, {"field": "series"}, {"field": "pieces", "format": ","}]}},
                {"data": {"values": rules}, "mark": {"type": "rule", "strokeDash": [5, 4], "strokeWidth": 2},
                 "encoding": {"x": {"field": "day", "type": "quantitative"}, "color": {"field": "color", "type": "nominal", "scale": None}}},
                {"data": {"values": [{**r, "y": top * 1.15} for r in rules]}, "mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12.5, "fontWeight": 600},
                 "encoding": {"x": {"field": "day", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}, "text": {"field": "text"},
                              "color": {"field": "color", "type": "nominal", "scale": None}}}]}, height=250)
            source_note(f"shock_trace.py, seed {bundle['seed']}.")
        shock_change_chart(data, focus)


def shock_change_chart(data, focus):
    frame = data["results"].copy()
    frame["label"] = [name_of(p, o) for p, o in zip(frame.policy, frame.objective)]
    wide = frame.pivot_table(index="label", columns="shock", values="pct_late").reset_index()
    wide["change"] = wide[True] - wide[False]
    wide = wide[["label", "change"]]
    order = wide.sort_values("change")["label"].tolist()
    wide["tone"] = ["Our policy" if lab == LABELS[focus] else "Other" for lab in wide.label]
    wide["text"] = wide["change"].map(lambda v: f"{v:+.2f}")
    box, _ = chart_card("change", "Change in late batches under shock, every policy",
                        "Official ten-seed averages. Points added by the closure; below zero means fewer late batches.", "")
    with box:
        chart(wide, {"layer": [
            {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": 13},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": order, "title": None, "axis": {"labelLimit": 200}},
                          "x": {"field": "change", "type": "quantitative", "title": "Change in late batches (points)"},
                          "color": {"field": "tone", "legend": None, "scale": {"domain": ["Our policy", "Other"], "range": [OURS, BASE]}},
                          "tooltip": [{"field": "label", "title": "Policy"}, {"field": "change", "format": "+.2f", "title": "Change (points)"}]}},
            *[{"transform": [{"filter": f"datum.change {op} 0"}], "mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12},
               "encoding": {"y": {"field": "label", "type": "nominal", "sort": order}, "x": x, "text": {"field": "text"}, "color": {"value": "#33465E"}}}
              for op, x in ((">=", {"field": "change", "type": "quantitative"}), ("<", {"datum": 0, "type": "quantitative"}))]]}, height=300)
        source_note("eval/ ten-seed results, shock minus normal.")


# Evidence -------------------------------------------------------------------------

def evidence_space(data, focus, shock, workshops):
    part = st.segmented_control("Evidence view", ["official", "explorer"], key="lab_evidence_view", default="official", required=True,
                                format_func={"official": "Official ten-seed evidence", "explorer": "Single-seed explorer"}.get,
                                label_visibility="collapsed")
    if part == "explorer":
        bundle, fp = seed_bar("Single-seed explorer")
        if bundle is None:
            return
        run_tab, audit_t = st.tabs([f"Seed {bundle['seed']} run", "Order audit"])
        with run_tab:
            single_seed_tab(bundle, focus, shock)
        with audit_t:
            audit_tab(bundle, focus, shock, workshops, fp)
        return
    course_evidence(data)
    variability_tab(data, focus, shock)
    with st.expander("Change under shock, every policy (table)"):
        frame = data["shock"].copy()
        frame["label"] = [evidence.policy_label(p, o) for p, o in zip(frame.policy, frame.objective)]
        frame = frame.sort_values("delta_pct_late")
        body = [[esc(r.label), f'<span class="{"" if abs(r.delta_pct_late) < 1e-9 else "neg" if r.delta_pct_late > 0 else "pos"}">{r.delta_pct_late:+.2f}</span>',
                 f"{r.delta_late_days:+.3f}"] for r in frame.itertuples()]
        html(table(["Policy", "Change in late batches (points)", "Change in late days"], body, right=(1, 2)))
    with st.expander("Full results, every policy and metric (table)"):
        res = data["results"].copy()
        res["Policy"] = [evidence.policy_label(p, o) for p, o in zip(res.policy, res.objective)]
        res["Scenario"] = res.shock.map({False: "Normal", True: "Shock"})
        cols = ["pct_late", "late_days", "mean_days", "p90_days", "pct_defect_pieces", "total_cost", "max_share"]
        body = [[esc(r["Policy"]), esc(r["Scenario"])] + [esc(fmt(c, r[c])) for c in cols] for _, r in res.iterrows()]
        html(table(["Policy", "Scenario"] + [METRIC_LABELS[c] for c in cols], body, right=tuple(range(2, 2 + len(cols))), max_height=420))
    sources(data)
    language_card()


def sources(data):
    meta, prov = data["metadata"], data["provenance"]
    hashes = meta.get("source_hashes", {})
    rows = "".join(f"<dt>{esc(k)}</dt><dd><span class=\"id\">{esc(str(v)[:12])}</span></dd>" for k, v in list(hashes.items())[:8])
    html(f'<div class="an-card" style="margin-top:12px"><div class="an-title">Where these numbers come from</div><div class="an-sub">'
         f'{meta.get("seeds")} paired seeds ({esc(", ".join(map(str, meta.get("seed_values", [])[:1])))} to {esc(str(meta.get("seed_values", [""])[-1]))}), '
         f'{meta.get("batch_count")} orders, {meta.get("total_pieces", 0):,} pieces, aggregated as {esc(str(meta.get("aggregation", "mean")))}. '
         f'Files in eval/ are read, never recomputed by this page. Source hashes {"match" if prov["matches"] else "do not match"} the current code.</div>'
         f'<dl class="kv src-kv">{rows}</dl></div>')


# Hero and comparison -----------------------------------------------------------------

def hero_block(data, focus, shock):
    h = le.hero(data, focus, shock)
    scenario = "paired normal and shock runs" if focus == "robustness" else ("shock scenario" if shock else "normal scenario")
    word, tone = le.OUTCOME[h["ef_outcome"]]
    rows = le.comparison(data, focus, shock)
    top = max(abs(r["headline"]) for r in rows) or 1
    side = []
    for r in rows:
        width = abs(r["headline"]) / top * 100
        chip = "" if r["outcome"] is None else f'<span class="lh-chip {OUTCOME_DARK[le.OUTCOME[r["outcome"]][1]]}">{esc(le.OUTCOME[r["outcome"]][0])}</span>'
        side.append(f'<div class="lh-row{" ours" if r["policy"] == "allocator" else ""}"><span class="lh-n">{esc(r["name"])}</span>'
                    f'<div class="lh-bar"><i style="width:{max(width, 1.5):.1f}%"></i></div>'
                    f'<b>{esc(le.fmt_headline(focus, r["headline"]))}</b>{chip}</div>')
    ef_value = le.fmt_headline(focus, h["ef"])
    versus = {"tie": f"with earliest finish ({ef_value})", "qualifying": f"against earliest finish ({ef_value})",
              "guardrail": f"Better than earliest finish on its own metric ({ef_value}), but too late to qualify",
              "no_win": f"against earliest finish ({ef_value})", "none": f"Earliest finish: {ef_value}. No course pass rule"}[h["ef_outcome"]]
    html(f'<div class="lab-hero"><div class="lh-main"><span class="lh-eyebrow">Official result, ten seeds, {esc(scenario)}</span>'
         f'<div class="lh-obj">{esc(h["label"])} objective</div>'
         f'<div class="lh-num">{esc(le.fmt_headline(focus, h["ours"]))}<small>{esc("change in late batches under shock" if focus == "robustness" else h["metric"])}</small></div>'
         f'<div class="lh-verdict"><span class="lh-badge {OUTCOME_DARK[tone]}">{esc(word)}</span><span>{esc(versus)}</span></div><p class="lh-note">{esc(h["note"])}</p></div>'
         f'<div class="lh-side"><div class="lh-side-t"><span>Against the comparison policies</span>'
         f'<span class="lh-overall {OUTCOME_DARK[h["tone"]]}">{esc(h["overall"])}</span></div>{"".join(side)}'
         f'<div class="lh-foot">Lower is better. Bars share one scale.</div></div></div>')


def comparison_cards(data, focus, shock):
    rows = le.comparison(data, focus, shock)
    cards = []
    for r in rows:
        ours = r["policy"] == "allocator"
        word, tone = ("Our policy", "info") if ours else le.OUTCOME[r["outcome"]]
        if not ours and r["outcome"] not in (None, "none"):
            word = {"qualifying": "We beat it", "tie": "Tie", "guardrail": "We fail guardrail", "no_win": "We do not win"}[r["outcome"]]
        metrics = [("Late batches", f'{r["pct_late"]:.2f}%'), ("Late days", f'{r["late_days"]:.2f}'),
                   ("Cost", f'{r["cost"]:,.0f}'), ("Largest share", f'{r["share"]:.1f}%')]
        cards.append(f'<div class="pc{" ours" if ours else ""}"><div class="pc-top"><div><b>{esc(r["name"])}</b><small>{esc(r["role"])}</small></div>'
                     f'{status_pill(word, tone)}</div><div class="pc-num">{esc(le.fmt_headline(focus, r["headline"]))}'
                     f'<small>{esc("shock change" if focus == "robustness" else le.METRIC[focus][1])}</small></div>'
                     '<dl class="pc-m">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in metrics) + "</dl></div>")
    html(f'<div class="lab-sec"><div class="title">Policy comparison</div><div class="meta">Ten-seed averages, '
         f'{"normal and shock paired" if focus == "robustness" else ("shock" if shock else "normal")} scenario. '
         f'Status is the course pass rule for the {esc(LABELS[focus].lower())} objective.</div></div><div class="pcs">{"".join(cards)}</div>')


def objectives_row(data, focus, shock):
    html('<div class="lab-sec"><div class="title">Every objective</div><div class="meta">One verdict per objective from the committed '
         'objective checks. Select one to compare it below and in Performance.</div></div>')
    cols = st.columns(len(OBJECTIVES), gap="small")
    for col, objective in zip(cols, OBJECTIVES):
        h = le.hero(data, objective, shock)
        with col, st.container(key=f"obj_{objective}"):
            html(f'<div class="ob-card{" on" if objective == focus else ""} t-{h["tone"]}"><small>{esc(evidence.OBJECTIVE_LABELS[objective])}</small>'
                 f'<b>{esc(h["overall"])}</b><span>{esc(le.fmt_headline(objective, h["ours"]))} '
                 f'{esc("shock change" if objective == "robustness" else le.METRIC[objective][1])}</span></div>')
            st.button(f"Show {LABELS[objective]}", key=f"objbtn_{objective}", on_click=set_focus, args=(objective,))


# Analysis tabs --------------------------------------------------------------------

def variability_tab(data, focus, shock):
    spread = evidence.seed_spread(data["per_seed"])
    spread = spread[spread.scenario == ("Shock" if shock else "Normal")].copy()
    spread["label"] = spread["label"].str.replace("Ours: hybrid: ", "Ours: ", regex=False)
    ours = evidence.policy_label("allocator", focus).replace("Ours: hybrid: ", "Ours: ")
    spread["role"] = ["Our policy" if lab == ours else "Earliest finish" if lab == "Earliest finish"
                      else "Our other objectives" if lab.startswith("Ours") else "Supplied baselines" for lab in spread.label]
    order = spread.groupby("label")["pct_late"].mean().sort_values().index.tolist()
    box, _ = chart_card("seeds", "Late batches, seed by seed", f"Each dot is one of the ten official seeds, {'shock' if shock else 'normal'} scenario. "
                        "A tight cluster means the result does not hinge on one lucky seed.", "")
    with box:
        chart(spread, {"layer": [
            {"mark": {"type": "tick", "thickness": 2, "size": 22, "color": "#102238"},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": order, "title": None}, "x": {"aggregate": "mean", "field": "pct_late", "type": "quantitative"},
                          "tooltip": [{"field": "label"}, {"aggregate": "mean", "field": "pct_late", "format": ".2f", "title": "Mean late (%)"}]}},
            {"mark": {"type": "circle", "size": 70, "opacity": .75},
             "encoding": {"y": {"field": "label", "type": "nominal", "sort": order, "title": None, "axis": {"labelLimit": 240}},
                          "x": {"field": "pct_late", "type": "quantitative", "title": "Late batches (%) per seed", "scale": {"domain": [0, 100]},
                                "axis": {"values": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]}},
                          "yOffset": {"field": "seed", "type": "nominal", "scale": {"paddingInner": .2}},
                          "color": {"field": "role", "title": None, "scale": {"domain": ROLE_DOMAIN, "range": ROLE_RANGE}},
                          "tooltip": [{"field": "label"}, {"field": "seed"}, {"field": "pct_late", "format": ".2f", "title": "Late (%)"}]}}]}, height=380)
        source_note("eval/ per-seed results. The dark tick is the ten-seed mean. Our lateness and earliest finish land on the same values in every seed, which is why they tie.")


def single_seed_tab(bundle, focus, shock):
    subset = bundle["summary"][bundle["summary"]["shock"] == shock]
    ours = subset[(subset.policy == "allocator") & (subset.objective == focus)].iloc[0]
    ef = subset[subset.policy == "earliest_finish"].iloc[0]
    html(f'<div class="meta">Seed {bundle["seed"]}, {"shock" if shock else "normal"} scenario, {bundle["batch_count"]} orders, '
         f'{bundle["total_pieces"]:,} pieces. A single-seed diagnostic: the official ten-seed results are under Evidence.</div>')
    tiles = []
    for metric, label, _ in HERO:
        same = tied(ours[metric], ef[metric])
        word, tone = ("Tie", "muted") if same else (("Better", "ok") if ours[metric] < ef[metric] else ("Worse", "warn"))
        tiles.append(metric_tile(label, fmt(metric, ours[metric]), f'Earliest finish {esc(fmt(metric, ef[metric]))} {status_pill(word, tone)}'))
    html(f'<div class="kpis g4">{"".join(tiles)}</div>')
    if all(tied(ours[m], ef[m]) for m in METRICS):
        html(banner(f"{LABELS[focus]} ties earliest finish on all eight measures in this run.",
                    " It makes the same choices as the strongest simple rule. A tie is not a win.", "muted"))
    outcomes = bundle["outcomes"]
    picks = [("allocator", focus, "Our policy"), ("earliest_finish", "none", "Earliest finish"), ("random_choice", "none", "Random")]
    rows = []
    for policy, objective, label in picks:
        part = outcomes[(outcomes.policy == policy) & (outcomes.objective == objective) & (outcomes.shock == shock)]
        rows += [{"policy": label, "turnaround": t, "late": "Late" if l else "On time"} for t, l in zip(part.turnaround, part.late)]
    section("Completion time, order by order", "Days from dispatch to return. Each bar counts orders in a two-day bin.")
    chart(pd.DataFrame(rows), {
        "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
        "encoding": {"x": {"field": "turnaround", "type": "quantitative", "bin": {"step": 2}, "title": "Days to return"},
                     "y": {"aggregate": "count", "type": "quantitative", "title": "Orders"},
                     "xOffset": {"field": "policy", "sort": ["Our policy", "Earliest finish", "Random"]},
                     "color": {"field": "policy", "title": None, "scale": {"domain": ["Our policy", "Earliest finish", "Random"], "range": [OURS, STRONG, BASE]}},
                     "tooltip": [{"field": "policy"}, {"field": "turnaround", "bin": {"step": 2}, "title": "Days"}, {"aggregate": "count", "title": "Orders"}]}},
        height=300)


# Course evidence -----------------------------------------------------------------

def course_evidence(data):
    meta, prov = data["metadata"], data["provenance"]
    seeds = meta.get("seed_values", [])
    status = status_pill("Matches current code", "ok") if prov["matches"] else status_pill("Code changed since this evidence", "warn")
    html(f'<div class="lab-sec ce-head"><div><div class="title">Official ten-seed evidence</div><div class="meta">{meta.get("seeds")} paired seeds, '
         f'{seeds[0] if seeds else ""} to {seeds[-1] if seeds else ""}, {len(data["per_seed"])} simulator runs, read from the committed files in eval/. '
         f'What to say in the presentation, and what not to.</div></div>{status}</div>')
    claims = le.claims(data)
    tones = {"Beats or qualifies": ("ok", "verified"), "Ties": ("muted", "drag_handle"), "Fails": ("risk", "cancel"), "Do not claim": ("dont", "block")}
    html('<div class="claims">' + "".join(
        f'<div class="cl {tones[k][0]}"><div class="cl-h">{icon(tones[k][1])}<b>{esc(k)}</b></div><ul>' + "".join(f"<li>{esc(t)}</li>" for t in items) + "</ul></div>"
        for k, items in claims.items()) + "</div>")
    matrix = evidence.check_matrix(data["results"], data["checks"])
    groups = {}
    for item in matrix:
        groups.setdefault((item["objective"], item["scenario"]), {})[item["comparator"]] = item["outcome"]
    head = "".join(f"<span>{esc(le.NAMES[c])}</span>" for c in evidence.COMPARATORS)
    body = "".join(f'<div class="mx-r"><span class="mx-o"><b>{esc(evidence.OBJECTIVE_LABELS[o])}</b><small>{esc(s)}</small></span>'
                   + "".join(f'<span>{status_pill(*le.OUTCOME[g[c]])}</span>' for c in evidence.COMPARATORS) + "</div>"
                   for (o, s), g in groups.items())
    html(f'<div class="mx"><div class="mx-t"><div class="an-title">Objective qualification matrix</div><div class="an-sub">Each objective against each '
         f'comparison policy, from eval/objective_checks.csv.</div></div><div class="mx-r mx-h"><span>Objective, scenario</span>{head}</div>{body}</div>'
         '<div class="meta" style="margin-top:6px">Beats: the course pass rule holds. Tie: the required metric is equal. '
         'Guardrail fails: it wins its own metric but is later than the lateness guardrail allows. Hybrids have no pass rule.</div>')


# Diagnostics kept from the previous Lab ---------------------------------------------

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
