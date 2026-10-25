"""Batch run: every inbox request evaluated in order, as one reviewable result.

The run is a preview. Each request is read with the session's reading source and
evaluated by the same engine as Dispatch, on the session's queues; an allocation
that would be ready to confirm is carried forward, so request 12 sees the queue
that requests 1 to 11 would leave. Nothing is written until the dispatcher presses
"Confirm all", one explicit decision that writes one audit record per allocation,
marked as confirmed in batch review. Clarifications, refusals with an alternative
and late returns are never confirmed in bulk: they need a person, request by request.
"""

from __future__ import annotations

from copy import deepcopy

import pandas as pd

import streamlit as st

import desk
import intake
import rehearsal
from objectives import PRESETS
from ui import explain
from ui.components import banner, chart, esc, html, status_pill, table

OUTCOMES = {"ready": ("Ready to confirm", "conf"), "alternative": ("Alternative offered", "info"),
            "late": ("No on-time option", "warn"), "clarify": ("Needs reply", "warn"), "decline": ("Cannot answer", "muted"),
            "blocked": ("Blocked", "risk"), "error": ("Not read", "risk")}


def outcome(preview) -> str:
    parsed, record = preview.response.parsed_request, preview.response.decision_record
    if parsed.behaviour == "clarify":
        return "clarify"
    if parsed.behaviour == "decline":
        return "decline"
    if preview.block_reason or not record.get("chosen_workshop"):
        return "blocked"
    if record.get("awkward_case") == "none_makes_date" or preview.response.already_late:
        return "late"
    if parsed.behaviour == "refuse":
        return "alternative"
    return "ready"


def run(messages, orders, workshops):
    state = st.session_state
    source, config = state["desk_source"], PRESETS[state["desk_preset"]]
    today = max(state["desk_today"], state["desk_queue_date"])
    queues, allocator = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today), deepcopy(state["desk_allocator"])
    rows, previews = [], {}
    bar = st.progress(0.0, text="Reading the inbox")
    for i, line in enumerate(messages):
        rid = line.split()[0]
        bar.progress(i / len(messages), text=f"Evaluating {rid} ({i + 1} of {len(messages)})")
        try:
            with intake.extraction_source(rehearsal.make_source(source, record_live=False)):
                preview = desk.make_preview(line, today, config, orders, workshops, queues, allocator,
                                            state["desk_revision"] + i, source)
        except Exception as error:   # One unreadable request never stops the batch; it is listed with its reason.
            rows.append({"request": rid, "outcome": "error", "detail": type(error).__name__ + (f": {error}" if str(error) else "")})
            continue
        kind = outcome(preview)
        record, parsed = preview.response.decision_record, preview.response.parsed_request
        chosen = explain.chosen_row(record)
        row = {"request": rid, "outcome": kind, "order": parsed.order_id, "pieces": parsed.pieces,
               "workshop": chosen["name"] if chosen else None, "workshop_id": chosen["workshop_id"] if chosen else None,
               "back": chosen["eta_date"] if chosen else None, "spare": chosen["days_to_spare"] if chosen else None,
               "cost": chosen["total_cost"] if chosen else None,
               "evidence": bool((preview.response.faithfulness or {}).get("passed")), "detail": parsed.reason}
        if kind == "ready" and preview.accepted_queues is not None:
            queues, allocator = dict(preview.accepted_queues), deepcopy(preview.accepted_allocator)
            row["queue_after"] = queues[row["workshop_id"]]
            previews[rid] = preview
        rows.append(row)
    bar.progress(1.0, text="Done")
    bar.empty()
    state["batch_run"] = {"rows": rows, "previews": previews, "source": source, "objective": config.name, "today": today,
                          "start_revision": state["desk_revision"], "start_saved": len(state["desk_saved"]),
                          "final_queues": queues, "final_allocator": allocator}


def confirm_all():
    """One explicit decision by the dispatcher: confirm every allocation that was ready, in inbox order."""
    state = st.session_state
    batch = state.get("batch_run")
    if not batch or batch["start_revision"] != state["desk_revision"]:
        state["batch_error"] = "The session changed since the run. Run the batch again before confirming."
        return
    path = desk.audit_path(batch["source"])
    append = (lambda response: desk.records.append(response, path)) if path else None
    written = 0
    for rid, preview in batch["previews"].items():
        try:
            desk.confirm_preview(preview, preview.signature, state["desk_saved"], append=append, batch_review=True)
        except (ValueError, OSError) as error:
            state["batch_error"] = f"Stopped at {rid}: {error}. {written} records were written before it."
            break
        written += 1
        state.setdefault("desk_outcomes", {})[rid] = "Confirmed"
    else:
        state["desk_queues"], state["desk_allocator"] = batch["final_queues"], batch["final_allocator"]
        state["desk_queue_date"] = batch["today"]
    state["desk_revision"] += max(written, 1)
    batch["confirmed"] = written
    batch["log"] = desk.audit_log_name(batch["source"])


def render(messages, orders, workshops):
    state = st.session_state
    source = rehearsal.SOURCES[state["desk_source"]]
    html('<div class="an-title" style="margin-top:0.4rem">Run the whole inbox</div>'
         f'<div class="an-sub">Evaluates all {len(messages)} requests in order with <b>{esc(source.label)}</b> and the '
         f'<b>{esc(explain.objective_label(state["desk_preset"]))}</b> objective, starting from this session\'s queues. '
         'Each allocation that is ready is carried forward, so later requests see the queues earlier ones leave. '
         'Nothing is saved until you confirm.</div>')
    if state["desk_source"] == "live":
        html(banner("Live model.", f" This makes {len(messages)} model calls, about USD 0.31 and two to three minutes. "
                    "Rehearsal modes make none.", "warn"))
    if st.button(f"Run all {len(messages)} requests", key="batch_run_btn", type="primary", icon=":material/play_arrow:"):
        state.pop("batch_error", None)
        run(messages, orders, workshops)
    batch = state.get("batch_run")
    if not batch:
        return
    rows = batch["rows"]
    counts = {k: sum(r["outcome"] == k for r in rows) for k in OUTCOMES}
    html('<div class="an-card au-sum" style="margin-top:0.8rem"><div class="an-title">Result</div>'
         f'<div class="an-sub">{len(rows)} requests, {esc(rehearsal.SOURCES[batch["source"]].label)}, scenario date '
         f'{esc(explain.long_date(batch["today"].isoformat()))}.</div><div class="au-stats" style="grid-template-columns:repeat(5,minmax(0,1fr))">'
         + "".join(f'<div><b>{counts[k]}</b><small>{esc(OUTCOMES[k][0])}</small></div>' for k in ("ready", "alternative", "late", "clarify", "decline")
                   ) + "</div></div>")
    body = []
    for r in rows:
        word, tone = OUTCOMES[r["outcome"]]
        body.append([f'<b class="id">{esc(r["request"])}</b>', status_pill(word, tone), esc(r.get("order") or ""),
                     esc(r.get("workshop") or ""), esc(explain.short_date(r["back"]) if r.get("back") else ""),
                     esc(f'{r["spare"]:+d}' if r.get("spare") is not None else ""), esc(f'{r["cost"]:,.0f}' if r.get("cost") is not None else ""),
                     esc(f'{r["queue_after"]:.1f} d' if r.get("queue_after") is not None else ""),
                     ("Verified" if r.get("evidence") else "") if r["outcome"] != "error" else esc(r.get("detail", ""))])
    html(table(["Request", "Outcome", "Order", "Workshop", "Back", "Spare", "Cost", "Queue after", "Evidence"], body,
               right=(5, 6, 7), max_height=520))
    ready = [r for r in rows if r["outcome"] == "ready"]
    if ready:
        load = pd.DataFrame([{"workshop": r["workshop"], "pieces": r["pieces"] or 0} for r in ready])
        with st.container(key="chart_batch_load"):
            html('<div class="an-title">Pieces per workshop if every ready allocation is confirmed</div>'
                 '<div class="an-sub">From the ready rows above. Refusals, late returns and clarifications are not included.</div>')
            chart(load, {"mark": {"type": "bar", "cornerRadiusEnd": 4, "height": {"band": .6}},
                         "encoding": {"y": {"field": "workshop", "type": "nominal", "title": None, "sort": "-x"},
                                      "x": {"field": "pieces", "type": "quantitative", "aggregate": "sum", "title": "Pieces"},
                                      "color": {"value": "#2A77E8"},
                                      "tooltip": [{"field": "workshop"}, {"field": "pieces", "aggregate": "sum", "title": "Pieces"}]}},
                  height=max(140, 30 * load["workshop"].nunique() + 40))
    if state.get("batch_error"):
        html(banner("Not confirmed.", " " + state["batch_error"], "risk"))
    if batch.get("confirmed") is not None:
        html(banner(f"{batch['confirmed']} allocations confirmed.", f" Written to the {batch['log']} audit log, each marked as confirmed "
                    "in batch review. The other requests still need you on Dispatch.", "info"))
    elif ready:
        log = desk.audit_log_name(batch["source"])
        a, b = st.columns([1.3, 2], vertical_alignment="center")
        with a:
            st.button(f"Confirm all {len(ready)} ready allocations", key="batch_confirm", type="primary", on_click=confirm_all,
                      icon=":material/done_all:")
        with b:
            html(f'<div class="meta">Writes {len(ready)} records to the {log} audit log and updates the session queues. '
                 'Alternatives, late returns and clarifications are left for you to decide one by one.</div>')
    st.download_button("Export this run (CSV)", pd.DataFrame(rows).drop(columns=["workshop_id"], errors="ignore").to_csv(index=False),
                       file_name="inbox-batch-run.csv", mime="text/csv", key="batch_export", icon=":material/download:")
