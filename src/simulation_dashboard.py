"""Simulation-first Streamlit workspace with evidence-backed comparisons."""
from __future__ import annotations

from dataclasses import asdict
from html import escape
import json

import pandas as pd
import streamlit as st

from experiments import decision_replay, fingerprints, run_experiment
from objectives import PRESETS
from run_simulator import METRICS, baseline_report, tied
from shock_trace import run_trace

LABELS = {
    "random_choice": "Random", "greedy_biggest": "Biggest workshop",
    "cheapest": "Cheapest", "earliest_finish": "Earliest finish",
    "lateness": "Lateness", "defect": "Quality", "fairness": "Fairness",
    "robustness": "Robustness", "hybrid_lateness_fairness": "Hybrid: lateness / fairness",
    "hybrid_lateness_defect": "Hybrid: lateness / quality",
}
METRIC_LABELS = {
    "pct_late": "Late batches (%)", "mean_days": "Mean turnaround (days)",
    "p90_days": "P90 turnaround (days)", "pct_defect": "Defective batches (%)",
    "total_cost": "Total cost (simulator units)", "max_share": "Largest workshop share (%)",
}
TEAL, GRAY, RISK = "#146c63", "#87979a", "#b65337"


def display_name(row):
    return LABELS[row["objective"] if row["policy"] == "allocator" else row["policy"]]


def chart(data, spec, *, height=320):
    """Shared final-size chart grammar; data and exact values stay available."""
    st.vega_lite_chart(data, {
        "height": height, "background": "#ffffff",
        "config": {
            "view": {"stroke": None},
            "axis": {"labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": "normal",
                     "labelColor": "#45585d", "titleColor": "#45585d",
                     "gridColor": "#edf1ef", "domain": False, "tickColor": "#dce5e5"},
            "legend": {"labelFontSize": 12, "title": None, "orient": "bottom"},
        }, **spec,
    }, width="stretch", theme=None)


def ranking(frame, metric, focus):
    plot = frame.assign(label=frame.apply(display_name, axis=1))
    plot["emphasis"] = plot["objective"].eq(focus)
    chart(plot, {
        "mark": {"type": "bar", "cornerRadiusEnd": 3, "size": 17},
        "encoding": {
            "y": {"field": "label", "type": "nominal", "sort": {"field": metric, "order": "ascending"},
                  "title": None, "axis": {"labelLimit": 215}},
            "x": {"field": metric, "type": "quantitative", "title": METRIC_LABELS[metric] + " · lower is better",
                  "scale": {"zero": True}},
            "color": {"condition": {"test": "datum.emphasis", "value": TEAL}, "value": GRAY},
            "tooltip": [{"field": "label", "title": "Policy"},
                        {"field": metric, "type": "quantitative", "format": ",.2f", "title": METRIC_LABELS[metric]}],
        },
    })


def tradeoff(frame, focus):
    # Exact ties share one point and a combined tooltip, without jitter.
    values = []
    for (late, cost), group in frame.groupby(["pct_late", "total_cost"], sort=False):
        values.append({"late": late, "cost": cost,
                       "policies": " / ".join(group.apply(display_name, axis=1)),
                       "focus": bool(group["objective"].eq(focus).any())})
    chart(pd.DataFrame(values), {
        "mark": {"type": "point", "filled": True, "size": 130, "opacity": 1},
        "encoding": {
            "x": {"field": "late", "type": "quantitative", "title": "Late batches (%) · lower is better",
                  "scale": {"domain": [0, 100]}},
            "y": {"field": "cost", "type": "quantitative", "title": "Total cost (simulator units) · lower is better",
                  "scale": {"zero": True}},
            "color": {"condition": {"test": "datum.focus", "value": TEAL}, "value": GRAY},
            "shape": {"condition": {"test": "datum.focus", "value": "diamond"}, "value": "circle"},
            "tooltip": [{"field": "policies", "title": "Policies"},
                        {"field": "late", "format": ".2f", "title": "Late batches (%)"},
                        {"field": "cost", "format": ",.2f", "title": "Cost (units)"}],
        },
    })


@st.cache_data(show_spinner=False)
def replay(seed, objective, shock, fingerprint):
    return decision_replay(seed, objective, shock)


@st.cache_data(show_spinner=False)
def trace(seed, objective, fingerprint):
    return run_trace(seed, objective)


def method_notes(bundle):
    st.markdown("""**What this experiment proves**

The shared harness replays all supplied orders chronologically. Each policy automatically selects
an eligible workshop; queues accumulate, defects can trigger rework, and return dates determine
lateness. Every policy and scenario starts with fresh state. There is no manual workshop selection.

The three supplied baselines are Random, Biggest workshop and Cheapest. Earliest finish is the
strong simple heuristic. All six allocator objectives run in both normal and shock conditions.

**What it does not prove**

This experiment does not call the LLM or measure language understanding. The 30 chat requests
need a separate intake evaluation for correct extraction, clarification, refusal and unanswerable
questions. Human labels are still incomplete. Simulation results are not intake accuracy.

**Read the metrics correctly**

Late and defective percentages count batches. Largest workshop share counts pieces, not orders
or utilization. Cost is in simulator units. P90 is the harness's sorted-value index, not an
interpolated percentile. Lower is better for all six reported metrics.

This is one seed per scenario, without confidence intervals. The shock run consumes an extra
random draw to choose a workshop, so its rework sequence differs from the normal run.
Their difference is not a controlled estimate of the closure effect alone.
""")
    st.json({k: v for k, v in bundle.items() if k not in {"summary", "outcomes"}})
    st.markdown("**Reproduce from the terminal**")
    st.code(f"uv run python eval/run_simulator.py --seed {bundle['seed']}\n"
            "uv run python eval/run_inbox.py --mock --output-dir Apurwa/validation/mock_inbox", language="bash")
    st.caption("The mock inbox run is a synthetic pipeline check. A live inbox evaluation needs an API key and may incur charges.")


def performance(bundle, focus, shock, workshops):
    summary = bundle["summary"]
    subset = summary[summary["shock"] == shock].copy()
    selected = subset[(subset["policy"] == "allocator") & (subset["objective"] == focus)].iloc[0]
    heuristic = subset[subset["policy"] == "earliest_finish"].iloc[0]
    for col, metric in zip(st.columns(4), ["pct_late", "mean_days", "pct_defect", "total_cost"]):
        value = selected[metric]
        suffix = "%" if metric.startswith("pct") else " d" if metric == "mean_days" else ""
        delta = value - heuristic[metric]
        col.metric(METRIC_LABELS[metric], f"{value:,.1f}{suffix}",
                   "Tied with earliest finish" if tied(value, heuristic[metric]) else f"{delta:+.2f} vs earliest finish",
                   delta_color="off" if tied(value, heuristic[metric]) else "inverse",
                   help="Percentage differences are percentage points; cost differences are simulator units.")
    if all(tied(selected[m], heuristic[m]) for m in METRICS):
        st.info("This objective ties earliest finish on all six metrics. It does not demonstrate a scheduling improvement over that heuristic.")
    else:
        wins = [METRIC_LABELS[m] for m in METRICS if selected[m] < heuristic[m] and not tied(selected[m], heuristic[m])]
        losses = [METRIC_LABELS[m] for m in METRICS if selected[m] > heuristic[m] and not tied(selected[m], heuristic[m])]
        st.caption("Against earliest finish · Better: " + (", ".join(wins) or "none") +
                   " · Worse: " + (", ".join(losses) or "none") + ". Remaining metrics tie.")
    left, right = st.columns([1.12, 1], gap="large")
    with left:
        st.subheader("How does each policy perform?")
        metric = st.selectbox("Compare metric", list(METRIC_LABELS), format_func=METRIC_LABELS.get, key="lab_metric")
        ranking(subset, metric, focus)
        st.caption(f"Teal highlights {LABELS[focus]}. All four comparison policies and six allocator settings are included.")
    with right:
        st.subheader("The delivery–cost trade-off")
        st.caption("Lower left is better. Diamond marks the selected objective. Hover for policy names and exact values.")
        tradeoff(subset, focus)
    outcomes = bundle["outcomes"]
    own = outcomes[(outcomes["shock"] == shock) & (outcomes["policy"] == "allocator") & (outcomes["objective"] == focus)]
    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("Where the work goes")
        totals = own.groupby("workshop")["pieces"].sum()
        loads = pd.DataFrame([{"workshop": w.name, "pieces": int(totals.get(wid, 0))}
                              for wid, w in workshops.items()])
        chart(loads, {"mark": {"type": "bar", "color": TEAL, "size": 18},
                     "encoding": {
                         "y": {"field": "workshop", "type": "nominal", "sort": "-x", "title": None},
                         "x": {"field": "pieces", "type": "quantitative", "title": "Allocated pieces", "scale": {"zero": True}},
                         "tooltip": [{"field": "workshop"}, {"field": "pieces", "format": ","}],
                     }}, height=260)
        st.caption(f"Largest workshop share: {selected['max_share']:.1f}% of {bundle['total_pieces']:,} pieces. This is concentration, not utilization.")
    with b:
        st.subheader("Turnaround across the order stream")
        base = outcomes[(outcomes["shock"] == shock) & (outcomes["policy"] == "earliest_finish")]
        line = pd.concat([own.assign(series=LABELS[focus]), base.assign(series="Earliest finish")])
        line = line.groupby(["sent_date", "series"], as_index=False)["turnaround"].mean()
        chart(line, {"mark": {"type": "line", "strokeWidth": 2},
                     "encoding": {
                         "x": {"field": "sent_date", "type": "temporal", "title": "Dispatch date"},
                         "y": {"field": "turnaround", "type": "quantitative", "title": "Daily mean turnaround (days)", "scale": {"zero": True}},
                         "color": {"field": "series", "scale": {"domain": [LABELS[focus], "Earliest finish"], "range": [TEAL, GRAY]}},
                         "strokeDash": {"field": "series", "scale": {"domain": [LABELS[focus], "Earliest finish"], "range": [[1, 0], [5, 4]]}, "legend": None},
                         "tooltip": [{"field": "sent_date", "type": "temporal"}, {"field": "series"}, {"field": "turnaround", "format": ".2f"}],
                     }}, height=260)
        st.caption("One mean per dispatch date, over orders sent that day. Coincident lines indicate tied outcomes.")
    with st.expander("All policies · exact scorecard and baseline counterexamples"):
        table = subset.assign(Policy=subset.apply(display_name, axis=1))
        st.dataframe(table[["Policy", *METRICS]].rename(columns=METRIC_LABELS), hide_index=True, width="stretch")
        st.caption("All metrics are lower-is-better. The downloadable report enumerates every baseline win and tie across both scenarios.")


def disruption(bundle, focus, fingerprint):
    detail = trace(bundle["seed"], focus, fingerprint)
    st.subheader("Does the allocator notice a disruption?")
    st.caption(f"Shock replay · {detail['shocked_workshop_name']} ({detail['shocked_workshop_id']}) · closure begins on day 30; reopening day 44.")
    st.info("The target and closure window are displayed after the run for analysis. The allocator only sees orders, workshop profiles and observed queues.")
    days = pd.DataFrame(detail["rows"])
    target_events = [e for e in detail["events"] if e["workshop_id"] == detail["shocked_workshop_id"]]
    flags = [e for e in target_events if e["status"] == "suspect"]
    first = min((e["flagged_on_day"] for e in flags), default=None)
    c1, c2, c3 = st.columns(3)
    c1.metric("First target anomaly flag", f"Day {first}" if first is not None else "Not flagged")
    c2.metric("Pieces sent while target flagged", f"{int(days['ours_pieces_while_suspect'].sum()):,}")
    c3.metric("Target pieces, full shock replay", f"{int(days['ours_pieces'].sum()):,}")
    long = days.melt(id_vars=["day"], value_vars=["random_pieces", "ours_pieces"],
                     var_name="series", value_name="pieces")
    long["series"] = long["series"].map({"random_pieces": "Random baseline", "ours_pieces": LABELS[focus]})
    chart(long, {"layer": [
        {"data": {"values": [{"start": 30, "end": 44}]},
         "mark": {"type": "rect", "color": "#f4e6df", "opacity": .6},
         "encoding": {"x": {"field": "start", "type": "quantitative"}, "x2": {"field": "end"}}},
        {"mark": {"type": "line", "strokeWidth": 2},
         "encoding": {
             "x": {"field": "day", "type": "quantitative", "title": "Days since first order"},
             "y": {"field": "pieces", "type": "quantitative", "title": "Pieces sent to the affected workshop", "scale": {"zero": True}},
             "color": {"field": "series", "scale": {"domain": [LABELS[focus], "Random baseline"], "range": [TEAL, GRAY]}},
             "strokeDash": {"field": "series", "scale": {"domain": [LABELS[focus], "Random baseline"], "range": [[1, 0], [5, 4]]}, "legend": None},
             "tooltip": [{"field": "day"}, {"field": "series"}, {"field": "pieces"}],
         }},
    ]}, height=320)
    st.caption("Shaded region: closure window. The harness delays production starts inside the window; dispatch date alone does not determine exposure.")
    summary = bundle["summary"]
    paired = summary.pivot(index=["policy", "objective"], columns="shock", values="pct_late").reset_index()
    paired = paired.rename(columns={False: "Normal late (%)", True: "Shock late (%)"})
    paired["Policy"] = paired.apply(display_name, axis=1)
    paired["Change (pp)"] = paired["Shock late (%)"] - paired["Normal late (%)"]
    st.dataframe(paired[["Policy", "Normal late (%)", "Shock late (%)", "Change (pp)"]],
                 hide_index=True, width="stretch")
    st.caption("Normal/shock differences include changed defect draws. Avoid interpreting this as closure-only causality.")
    with st.expander("Observed anomaly and recovery evidence"):
        if target_events:
            st.dataframe(pd.DataFrame(target_events), hide_index=True, width="stretch")
        else:
            st.write("No target anomaly events in this run.")


def order_audit(bundle, focus, shock, fingerprint, workshops):
    st.subheader("Every automatic choice has a record")
    st.caption("Inspect one of the simulated decisions. Selecting an order here only changes what you inspect.")
    outcomes = bundle["outcomes"]
    own = outcomes[(outcomes["shock"] == shock) & (outcomes["policy"] == "allocator") & (outcomes["objective"] == focus)]
    only_late = st.checkbox("Show late orders only", key="lab_late")
    visible = own[own["late"]] if only_late else own
    st.dataframe(visible[["order_id", "sent_date", "due_date", "workshop", "pieces", "turnaround", "late", "defective", "cost"]],
                 hide_index=True, width="stretch", height=280)
    if visible.empty:
        st.info("No late orders in this view.")
        return
    order = st.selectbox("Inspect order", visible["order_id"].tolist(), key="lab_order")
    records = replay(bundle["seed"], focus, shock, fingerprint)
    record = records[order]
    outcome = visible[visible["order_id"] == order].iloc[0]
    wid = record["chosen_workshop"]
    st.markdown(f"**{order} → {workshops[wid].name}**")
    st.write(record["reason_chosen"])
    st.caption(f"Realized turnaround {outcome['turnaround']:.2f} days · {'Late' if outcome['late'] else 'On time'} · "
               f"{'Defective batch' if outcome['defective'] else 'No defect sampled'}")
    st.dataframe(pd.DataFrame(record["candidates"])[["name", "queue_days", "processing_days", "lead_days",
                 "eta_date", "days_to_spare", "total_cost", "expected_defect_rate", "score"]],
                 hide_index=True, width="stretch")
    st.caption("Candidate values are pre-allocation estimates. Realized outcomes include sampled rework and any hidden closure.")
    with st.expander("Full structured decision"):
        st.json(record)
    st.download_button("Download this decision", json.dumps(record, indent=2, default=str),
                       file_name=f"{order}-simulation-decision.json", mime="application/json")


def dashboard(workshops):
    for key, value in st.session_state.get("lab_controls", {}).items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.markdown('<div class="page-kicker">EXPERIMENTS / SHARED SIMULATOR</div>', unsafe_allow_html=True)
    st.title("See how the system decides.")
    st.caption("Replay the order book. Compare objectives. Find what breaks when a workshop closes.")
    seed_col, action_col, info_col = st.columns([1, 1.25, 2.5], vertical_alignment="bottom")
    with seed_col:
        seed = st.number_input("Experiment seed", min_value=0, max_value=2147483647, value=5105, key="lab_seed")
    with action_col:
        run = st.button("Run simulation", type="primary", width="stretch", key="lab_run")
    with info_col:
        st.caption("All orders · 10 policies / objectives · Normal + shock\n\nAutomatic allocations. No API key needed.")
    fingerprint = json.dumps(fingerprints(), sort_keys=True)
    if run or "lab_bundle" not in st.session_state:
        with st.spinner("Replaying orders across all policies and both scenarios…"):
            try:
                st.session_state["lab_bundle"] = run_experiment(int(seed))
            except Exception as error:
                st.error(f"Simulation failed: {type(error).__name__}: {error}")
                return
    bundle = st.session_state["lab_bundle"]
    if fingerprint != json.dumps(bundle["fingerprints"], sort_keys=True):
        st.warning("Inputs or implementation have changed. Run simulation again to refresh the results.")
        return
    if seed != bundle["seed"]:
        st.info(f"Showing seed {bundle['seed']}. Press Run simulation to evaluate seed {seed}.")
    st.markdown(f'<div class="workspace-summary"><span><strong>{bundle["batch_count"]}</strong> orders per run</span>'
                f'<span><strong>{bundle["total_pieces"]:,}</strong> pieces per run</span>'
                f'<span><strong>{len(bundle["summary"])}</strong> policy × scenario runs</span>'
                f'<span>Seed <strong>{bundle["seed"]}</strong> · computed {escape(bundle["started_at"][:19])} UTC</span></div>',
                unsafe_allow_html=True)
    f, c = st.columns([2, 1])
    with f:
        focus = st.selectbox("Inspect allocator objective", list(PRESETS), format_func=LABELS.get, key="lab_focus")
    with c:
        scenario = st.radio("Scenario", ["Normal", "Shock"], horizontal=True, key="lab_scenario")
    st.caption("These controls inspect completed automatic runs. They do not assign workshops.")
    st.caption("Objective weights: " + " · ".join(f"{k[2:]} {v:g}" for k, v in asdict(PRESETS[focus]).items()
                                                if k.startswith("w_") and v))
    st.session_state["lab_controls"] = {key: st.session_state[key] for key in
                                      ("lab_seed", "lab_focus", "lab_scenario")}
    performance_tab, shock_tab, audit_tab, method_tab = st.tabs(["Performance", "Disruption analysis", "Order audit", "How it works"])
    with performance_tab:
        performance(bundle, focus, scenario == "Shock", workshops)
    with shock_tab:
        disruption(bundle, focus, fingerprint)
    with audit_tab:
        order_audit(bundle, focus, scenario == "Shock", fingerprint, workshops)
    with method_tab:
        method_notes(bundle)
    st.divider()
    st.caption("Export evidence from this run")
    a, b, c = st.columns(3)
    a.download_button("Results CSV", bundle["summary"].to_csv(index=False),
                      f"simulation-{bundle['seed']}.csv", "text/csv", width="stretch")
    b.download_button("Batch outcomes CSV", bundle["outcomes"].to_csv(index=False),
                      f"outcomes-{bundle['seed']}.csv", "text/csv", width="stretch")
    c.download_button("Baseline comparison report", baseline_report(bundle["summary"], bundle["seed"]),
                      f"comparison-{bundle['seed']}.md", "text/markdown", width="stretch")
