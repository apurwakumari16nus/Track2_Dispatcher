"""Performance diagnostics: measured execution traces and the model comparison. Read-only.

Kept apart from the decision audit on purpose. A trace is written for every
evaluation (confirmed or not, successful or failed) and says how long each stage
took; it is not a decision record and never changes one. Traces link to a
confirmed record only through the trace ID stored in that record.

The model comparison shows benchmarks/results/<run>/summary.json when a paid run
exists. Until then it says "Not yet measured" and shows the dry-run plan; it never
fills the table with sample numbers.
"""

from __future__ import annotations

from argparse import Namespace
from datetime import date
import importlib.util
import json
from pathlib import Path
import statistics

import pandas as pd

import streamlit as st

import desk
import records
import tracing
from ui import explain
from ui.components import banner, chart, esc, html, status_pill, table
from ui.state import bind, one_of, subset_of, text

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"
SOURCES = {"live": "Live model", "cached": "Recorded reply", "fixture": "Test fixture"}
STAGE_COLOURS = {"llm": "#2A77E8", "parse": "#7FB0F2", "engine": "#20BFA9", "checks": "#0E5A8A", "other": "#B8C4D0"}
SHOWN = 40


def fmt_ms(ms) -> str:
    if ms is None:
        return "None"
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.0f} ms" if ms >= 10 else f"{ms:.1f} ms"


def stage_ms(trace: dict, key: str) -> float:
    return next((s["ms"] for s in trace.get("stages", []) if s["key"] == key), 0.0)


def trace_day(trace: dict) -> date | None:
    try:
        return date.fromisoformat((trace.get("started_utc") or "")[:10])
    except ValueError:
        return None


def linked_records() -> dict[str, tuple[str, str]]:
    """trace_id -> (log name, record timestamp) for every confirmed record that stores one."""
    out = {}
    for log, path in (("live", None), ("rehearsal", desk.REHEARSAL_LOG)):
        try:
            rows = records.load(path)
        except (OSError, ValueError):
            continue
        for row in rows:
            confirmation = row.get("decision_record", {}).get("constraints_applied", {}).get("confirmation", {})
            if confirmation.get("trace_id"):
                out[confirmation["trace_id"]] = (log, row.get("timestamp"))
    return out


def open_record(log: str, timestamp: str) -> None:
    state = st.session_state
    state["audit_view"], state["audit_log"], state["audit_focus"] = "decisions", log, timestamp


def render():
    traces_section()
    comparison_section()


# Execution traces --------------------------------------------------------------------

def traces_section():
    state = st.session_state
    html('<div class="an-title" style="margin-top:0.4rem">Execution traces</div>'
         '<div class="an-sub">Server-side time for each evaluation, measured with a monotonic clock. Written for every evaluation, '
         'confirmed or not. Stored locally in records/traces.jsonl, newest 500 kept. No message text or credentials are stored.</div>')
    traces = [t for t in tracing.load() if t.get("meta", {}).get("kind", "evaluation") == "evaluation"]
    if not traces:
        html(banner("No execution traces yet.", " Evaluate a request on Dispatch and its timing appears here.", "muted"))
        return
    sources = sorted({t["meta"].get("source") for t in traces} - {None})
    days = sorted({d for d in map(trace_day, traces) if d})
    with st.container(key="perf_bar"):
        a, b, c, d = st.columns([1.2, 1.2, 1, 1], vertical_alignment="bottom")
        with a:
            query = bind(st.text_input, "Request or trace ID", key="perf_q", fallback="", accept=text, placeholder="R09")
        with b:
            chosen = bind(st.multiselect, "Reading source", sources, key="perf_source", fallback=[], accept=subset_of(sources),
                          format_func=lambda v: SOURCES.get(v, v))
        with c:
            status = bind(st.selectbox, "Status", ["any", "ok", "error"], key="perf_status", fallback="any", accept=one_of(["any", "ok", "error"]),
                          format_func={"any": "Any status", "ok": "Completed", "error": "Failed"}.get)
        with d:
            day = bind(st.selectbox, "Date (UTC)", ["any", *reversed(days)], key="perf_day", fallback="any",
                       format_func=lambda v: "Any date" if v == "any" else explain.long_date(v))
    q = query.strip().lower()
    found = [t for t in reversed(traces)
             if (not q or q in (t["meta"].get("request_id") or "").lower() or q in t["trace_id"])
             and (not chosen or t["meta"].get("source") in chosen)
             and (status == "any" or t.get("status") == status)
             and (day == "any" or trace_day(t) == day)]
    if not found:
        html(banner("No matching traces.", " Clear a filter to widen the search.", "muted"))
        return
    totals = [t["total_ms"] for t in found]
    live = [t for t in found if t["meta"].get("source") == "live" and t.get("status") == "ok"]
    stats = [(len(found), "Evaluations"), (fmt_ms(statistics.median(totals)), "Median total"),
             (fmt_ms(statistics.median(stage_ms(t, "llm") for t in live)) if live else "None", "Median live model stage"),
             (sum(t.get("status") == "error" for t in found), "Failed")]
    left, right = st.columns([1, 1.6], gap="medium")
    with left:
        html('<div class="an-card au-sum"><div class="an-title">Summary</div><div class="an-sub">For the traces shown. '
             'Rehearsal readings make no API call, so their model stage is near zero.</div><div class="au-stats">'
             + "".join(f'<div><b>{esc(n)}</b><small>{esc(t)}</small></div>' for n, t in stats) + "</div></div>")
    with right, st.container(key="chart_perf_stages"):
        html('<div class="an-title">Time by stage</div><div class="an-sub">Newest 15 evaluations. Each stage is its own time, '
             'so the bar adds up to the total.</div>')
        labels = {key: label for key, label, _ in tracing.GROUPS} | {tracing.OTHER[0]: tracing.OTHER[1]}
        frame = pd.DataFrame([{"trace": f'{t["meta"].get("request_id") or "Typed"} · {t["trace_id"][:6]}', "stage": labels[s["key"]],
                               "ms": s["ms"], "order": i} for i, t in enumerate(found[:15]) for s in t.get("stages", [])])
        chart(frame, {"mark": {"type": "bar", "height": {"band": .6}},
                      "encoding": {"y": {"field": "trace", "type": "nominal", "sort": {"field": "order"}, "title": None},
                                   "x": {"field": "ms", "type": "quantitative", "aggregate": "sum", "title": "Milliseconds", "stack": "zero"},
                                   "color": {"field": "stage", "title": None, "legend": {"orient": "bottom", "columns": 3},
                                             "scale": {"domain": list(labels.values()),
                                                                                      "range": [STAGE_COLOURS[k] for k in labels]}},
                                   "tooltip": [{"field": "trace", "title": "Evaluation"}, {"field": "stage", "title": "Stage"},
                                               {"field": "ms", "aggregate": "sum", "title": "ms", "format": ".1f"}]}},
              height=max(150, 22 * min(15, len(found)) + 40))
    links = linked_records()
    body = []
    for t in found[:SHOWN]:
        meta, llm = t["meta"], t["meta"].get("llm") or {}
        body.append([esc(t["started_utc"][:19].replace("T", " ")), f'<b class="id">{esc(meta.get("request_id") or "Typed")}</b>',
                     esc(SOURCES.get(meta.get("source"), meta.get("source") or "Unknown")) + (" · demo" if meta.get("guided_demo") else ""),
                     esc(llm.get("served_model") or meta.get("requested_model") or "None"),
                     status_pill("Completed", "ok") if t.get("status") == "ok" else status_pill(t.get("error") or "Failed", "risk"),
                     esc(fmt_ms(t["total_ms"])), esc(fmt_ms(stage_ms(t, "llm"))), esc(fmt_ms(stage_ms(t, "engine"))),
                     f'<span class="id">{esc(t["trace_id"])}</span>', "Confirmed" if t["trace_id"] in links else ""])
    html(table(["Started (UTC)", "Request", "Source", "Model", "Status", "Total", "Model stage", "Engine", "Trace", "Record"],
               body, right=(5, 6, 7), max_height=420)
         + f'<div class="meta" style="margin-top:0.4rem">{min(len(found), SHOWN)} of {len(found)} traces, newest first.</div>')
    ids = [t["trace_id"] for t in found[:SHOWN]]
    pick = bind(st.selectbox, "Inspect a trace", ids, key="perf_pick", fallback=ids[0], accept=one_of(ids),
                format_func=lambda i: f'{i} · {next(t["meta"].get("request_id") or "Typed" for t in found if t["trace_id"] == i)}')
    picked = next(t for t in found if t["trace_id"] == pick)
    detail, action = st.columns([3, 1], vertical_alignment="bottom")
    with detail:
        spans = picked.get("spans", [])
        depth = {}
        for i, s in enumerate(spans):
            depth[i] = 0 if s["parent"] is None else depth.get(s["parent"], 0) + 1
        rows = [[("&nbsp;" * 4 * depth[i]) + esc(s["name"]), esc(s["status"] + (f' ({s["error"]})' if s.get("error") else "")),
                 f'{s["ms"]:.1f}', f'{s["offset_ms"]:.1f}'] for i, s in enumerate(spans)]
        html(table(["Span", "Status", "ms", "Starts at ms"], rows, right=(2, 3), max_height=320))
    with action:
        if pick in links:
            st.button("Open the decision record", key="perf_open", icon=":material/fact_check:", on_click=open_record, args=links[pick])
        else:
            html('<p class="ev">Not confirmed: no decision record uses this trace.</p>')
    st.download_button("Export shown traces (JSONL)", "\n".join(json.dumps(t, ensure_ascii=False) for t in found) + "\n",
                       file_name="execution-traces.jsonl", mime="application/x-ndjson", key="perf_export", icon=":material/download:")


# Model comparison --------------------------------------------------------------------

def benchmark_module():
    spec = importlib.util.spec_from_file_location("run_models", ROOT / "benchmarks" / "run_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def latest_summary() -> tuple[Path, dict] | None:
    runs = sorted(p for p in RESULTS.glob("*/summary.json")) if RESULTS.exists() else []
    if not runs:
        return None
    try:
        return runs[-1], json.loads(runs[-1].read_text())
    except (OSError, ValueError):
        return None


def comparison_section():
    html('<div class="an-title" style="margin-top:1.6rem">Model comparison: Sonnet 5.5 and Haiku 5.5</div>'
         '<div class="an-sub">Same requests, prompt, schema, data and engine; only the model changes. Method and decision rule: benchmarks/README.md.</div>')
    found = latest_summary()
    if found is None:
        try:
            plan = benchmark_module().plan(Namespace(sets=["official", "stress"], models=["claude-sonnet-5-5", "claude-haiku-5-5"],
                                                     trials=3, effort=None))
        except Exception as error:   # The plan is a convenience; a broken benchmark must not break Audit.
            plan = None
            html(banner("The benchmark plan could not be computed.", f" {type(error).__name__}.", "warn"))
        html(banner("Not yet measured.", " No paid benchmark run exists, so there are no accuracy, latency or cost results to compare. "
                    "Nothing below is a result.", "warn"))
        if plan:
            per = plan["estimated_cost_per_call_usd"]
            html('<div class="an-card"><div class="an-title">Planned run (dry run)</div><dl class="kv" style="grid-template-columns:14rem 1fr;margin-top:0.5rem">'
                 f'<dt>Cases</dt><dd>{plan["cases"]} (30 inbox requests, 13 author-labelled stress cases)</dd>'
                 f'<dt>Trials per model</dt><dd>{plan["trials"]}</dd><dt>API calls</dt><dd>{plan["calls"]}</dd>'
                 f'<dt>Estimated cost per call</dt><dd>Sonnet 5.5 USD {per["claude-sonnet-5-5"]:.4f}, Haiku 5.5 USD {per["claude-haiku-5-5"]:.4f}</dd>'
                 f'<dt>Estimated total</dt><dd>USD {plan["estimated_cost_usd"]:.2f}</dd></dl>'
                 f'<p class="ev" style="margin-top:0.6rem">{esc(plan["estimate_basis"])} Prices: official Claude API page, fetched 22 October 2026. '
                 'The run starts only from the command line with --execute.</p></div>')
        return
    path, summary = found
    models = summary["models"]
    names = {"claude-sonnet-5-5": "Sonnet 5.5", "claude-haiku-5-5": "Haiku 5.5"}
    html(banner(f"Run {summary['run']}.", f" {summary['human_labels']}. Stress-set accuracy uses author labels that no person has reviewed; "
                "inbox results are agreement with the test fixtures, not accuracy.", "info"))

    def rate(v):
        return "None" if v is None else f"{v * 100:.1f}%"
    rows = []
    for key, label, get in [
        ("calls", "Calls", lambda m: m["calls"]), ("ok", "Successful", lambda m: m["successful"]),
        ("schema", "Schema-valid output", lambda m: rate(m["schema_valid_rate"])), ("err", "Error rate", lambda m: rate(m["error_rate"])),
        ("retry", "Calls with a retry", lambda m: rate(m["retry_rate"])), ("fb", "Served by a fallback model", lambda m: m["fallback_served"]),
        ("crit", "Critical fields correct (stress)", lambda m: rate(m["stress_accuracy"]["critical_field_rate"])),
        ("clar", "Clarifies when it should (stress)", lambda m: rate(m["stress_accuracy"]["clarification_recall"])),
        ("agree", "Same decision as fixtures (inbox)", lambda m: rate(m["official_agreement_with_fixture"]["decision_agreement"])),
        ("l50", "Model call, median", lambda m: fmt_ms(m["llm_ms"]["p50"])), ("l90", "Model call, p90", lambda m: fmt_ms(m["llm_ms"]["p90"])),
        ("e50", "Full evaluation, median", lambda m: fmt_ms(m["e2e_ms"]["p50"])), ("e90", "Full evaluation, p90", lambda m: fmt_ms(m["e2e_ms"]["p90"])),
        ("cost", "Cost per successful request", lambda m: "None" if m["cost"]["mean_per_success_usd"] is None else f'USD {m["cost"]["mean_per_success_usd"]:.5f}'),
        ("k", "Cost per 1,000 requests", lambda m: "None" if m["cost"]["per_1000_usd"] is None else f'USD {m["cost"]["per_1000_usd"]:.2f}')]:
        rows.append([esc(label)] + [esc(get(models[m])) if m in models else "Not run" for m in names])
    html(table(["Measure", *names.values()], rows, right=(1, 2)))
    lat = pd.DataFrame([{"model": names.get(m, m), "measure": f"{part} {q}", "ms": models[m][key][q]}
                        for m in models for key, part in (("llm_ms", "Model call"), ("e2e_ms", "Full evaluation"))
                        for q in ("p50", "p90") if models[m][key][q] is not None])
    if len(lat):
        with st.container(key="chart_perf_latency"):
            html('<div class="an-title">Latency</div><div class="an-sub">Milliseconds, lower is faster.</div>')
            chart(lat, {"mark": {"type": "bar", "height": {"band": .7}},
                        "encoding": {"y": {"field": "measure", "type": "nominal", "title": None}, "yOffset": {"field": "model"},
                                     "x": {"field": "ms", "type": "quantitative", "title": "Milliseconds"},
                                     "color": {"field": "model", "title": None, "scale": {"range": ["#2A77E8", "#20BFA9"]}},
                                     "tooltip": [{"field": "model"}, {"field": "measure"}, {"field": "ms", "format": ",.0f"}]}}, height=220)
    decision = summary.get("decision", {})
    checks = decision.get("checks", {})
    html('<div class="an-card" style="margin-top:0.8rem"><div class="an-title">Decision rule</div><ul class="dk-list">'
         + "".join(f'<li>{status_pill("Pass", "ok") if v else status_pill("Fail", "risk") if v is False else status_pill("Unknown", "muted")} '
                   f'{esc(k.replace("_", " ").capitalize())}</li>' for k, v in checks.items())
         + f'</ul><p style="margin:0.6rem 0 0"><b>{esc(decision.get("verdict", ""))}</b></p></div>')
    a, b = st.columns(2)
    with a:
        st.download_button("Download summary (JSON)", path.read_text(), file_name=f"benchmark-{summary['run']}-summary.json",
                           mime="application/json", key="perf_bench_json", icon=":material/download:")
    with b:
        calls = path.parent / "calls.csv"
        if calls.exists():
            st.download_button("Download every call (CSV)", calls.read_text(), file_name=f"benchmark-{summary['run']}-calls.csv",
                               mime="text/csv", key="perf_bench_csv", icon=":material/download:")
