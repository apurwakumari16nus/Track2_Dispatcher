"""Audit Trail: search and inspect confirmed decisions. Read-only.

Rows come from records.load(); a malformed log is reported, never skipped.
The live and rehearsal logs are separate files and are never merged.
"""

from __future__ import annotations

from datetime import date, datetime
import json

import pandas as pd
import streamlit as st

import desk
import records
from ui import explain
from ui.components import banner, chip, esc, html, json_block, page_head, pill, table

LOGS = {"live": "Live audit log", "rehearsal": "Rehearsal audit log"}
KINDS = ["Allocation", "Alternative accepted", "Late return accepted"]


def kind(row: dict) -> str:
    confirmation = row.get("decision_record", {}).get("constraints_applied", {}).get("confirmation", {})
    if confirmation.get("accepted_lateness"):
        return "Late return accepted"
    if confirmation.get("accepted_alternative"):
        return "Alternative accepted"
    return "Allocation"


def logged_date(row: dict) -> date | None:
    try:
        return datetime.fromisoformat(row.get("timestamp", "")).date()
    except ValueError:
        return None


def summary(row: dict, workshops) -> dict:
    record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
    wid = record.get("chosen_workshop")
    source = explain.source_label(parsed.get("llm_metadata") or {})[1]
    return {"Logged (UTC)": (row.get("timestamp") or "")[:16].replace("T", " "), "Order": record.get("order_id") or "",
            "Sender": row.get("sender") or "Unknown", "Workshop": workshops[wid].name if wid in workshops else (wid or "None"),
            "Decision": kind(row), "Evidence": "Passed" if (row.get("faithfulness") or {}).get("passed") else "Failed",
            "Objective": explain.objective_label(record.get("objective_name", "")), "Extraction": source}


def search(rows, query="", senders=(), workshops=(), kinds=(), dates=None):
    """Newest first; every filter is optional and they combine with AND."""
    query = query.strip().casefold()
    out = []
    for row in reversed(rows):
        record = row.get("decision_record", {})
        if senders and row.get("sender") not in senders:
            continue
        if workshops and record.get("chosen_workshop") not in workshops:
            continue
        if kinds and kind(row) not in kinds:
            continue
        if dates and len(dates) == 2 and (logged_date(row) is None or not dates[0] <= logged_date(row) <= dates[1]):
            continue
        if query and query not in json.dumps(row, ensure_ascii=False, default=str).casefold():
            continue
        out.append(row)
    return out


def render(workshops):
    state = st.session_state
    state.setdefault("audit_log", "rehearsal" if state.get("desk_source", "live") != "live" else "live")
    page_head("Audit trail", "Every confirmed decision, with the evidence behind it.",
              "One record per confirmation: the original message, the structured extraction, constraints and who imposed them, "
              "every candidate, the score, the reason, the tool evidence and the human confirmation.")
    log = st.segmented_control("Audit log", list(LOGS), key="audit_log", format_func=LOGS.get, required=True,
                               label_visibility="collapsed")
    path = desk.REHEARSAL_LOG if log == "rehearsal" else None
    try:
        rows = records.load(path)
    except (OSError, ValueError) as error:
        html(banner("Audit log could not be read", f"{error}. No records were skipped or repaired.", "risk"))
        return
    if not rows:
        html('<div class="empty"><div class="eyebrow">No records yet</div><h3>Nothing has been confirmed in this log.</h3>'
             '<p>Dispatch a request and press Confirm. The record appears here immediately. Previews are never logged.</p></div>')
        if log == "live":
            html('<div class="section-note">Rehearsal confirmations are kept separately in the rehearsal audit log.</div>')
        return
    senders = sorted({r.get("sender") for r in rows} - {None, ""})
    shops = sorted({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None})
    days = sorted(set(d for d in (logged_date(r) for r in rows) if d))
    # Values restored from another log may no longer be valid options.
    for key, options in (("audit_sender", senders), ("audit_workshop", shops), ("audit_kind", KINDS)):
        state[key] = [v for v in state.get(key, []) if v in options]
    if state.get("audit_day") not in [None, *days]:
        state["audit_day"] = None
    with st.container(key="audit_filters"):
        a, b, c, d, e = st.columns([1.6, 1, 1.1, 1.2, 1.1], vertical_alignment="bottom")
        with a:
            query = st.text_input("Search", key="audit_q", placeholder="Order, sender, workshop or any text")
        with b:
            sender = st.multiselect("Sender", senders, key="audit_sender")
        with c:
            workshop = st.multiselect("Workshop", shops, key="audit_workshop",
                                      format_func=lambda wid: workshops[wid].name if wid in workshops else wid)
        with d:
            kinds = st.multiselect("Decision type", KINDS, key="audit_kind")
        with e:
            day = st.selectbox("Logged on", [None, *reversed(days)], key="audit_day",
                               format_func=lambda d: "Any date" if d is None else explain.long_date(d))
    found = search(rows, query, sender, workshop, kinds, (day, day) if day else None)
    passed = sum((r.get("faithfulness") or {}).get("passed", False) for r in found)
    html('<div class="chips">' + chip("records shown", f"{len(found)} of {len(rows)}") + chip("evidence checks passed", str(passed), dot="ok")
         + "".join(chip(k.lower(), str(sum(kind(r) == k for r in found))) for k in KINDS[1:]) + "</div>")
    if not found:
        html(banner("No matches", "No record matches these filters. Clear a filter to widen the search.", "muted"))
        return
    frame = pd.DataFrame([summary(r, workshops) for r in found])
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        event = st.dataframe(frame, hide_index=True, width="stretch", height=min(40 + 35 * len(frame), 560),
                             on_select="rerun", selection_mode="single-row", key="audit_table",
                             column_order=["Logged (UTC)", "Order", "Sender", "Workshop", "Decision", "Evidence"],
                             column_config={"Logged (UTC)": st.column_config.TextColumn(width="medium")})
        html('<div class="section-note">Select a row to open its record. Objective and extraction source are in the record.</div>')
        selected = event.selection.rows[0] if event and event.selection.rows else 0
        st.download_button("Export shown records (JSONL)", "\n".join(json.dumps(r, ensure_ascii=False) for r in found) + "\n",
                           file_name=f"{log}-audit-records.jsonl", mime="application/x-ndjson", key="audit_export")
    with right:
        detail(found[selected], workshops)


def detail(row, workshops):
    record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
    wid = record.get("chosen_workshop")
    chosen = explain.chosen_row(record)
    confirmation = record.get("constraints_applied", {}).get("confirmation", {})
    audit = row.get("faithfulness") or {}
    name = workshops[wid].name if wid in workshops else wid
    with st.container(key="audit_detail"):
        html(f'<div class="hero-label"><span class="eyebrow">{esc(record.get("order_id"))} · {esc(row.get("sender") or "Unknown sender")}</span>'
             f'<span class="chips">{pill(kind(row), "human")}{pill("Evidence passed" if audit.get("passed") else "Evidence failed", "ok" if audit.get("passed") else "risk")}</span></div>'
             f'<div class="hero-name" style="font-size:30px">{esc(name)}</div>'
             + (f'<div class="section-note">Back {esc(explain.long_date(chosen["eta_date"]))} · {chosen["days_to_spare"]:+d} days to spare · '
                f'cost {chosen["total_cost"]:,.0f} · {esc(explain.objective_label(record.get("objective_name", "")))}</div>' if chosen else ""))
        request, decision, evidence, human, raw = st.tabs(["Request", "Decision", "Evidence", "Confirmation", "Raw JSON"])
        with request:
            html(f'<div class="card tight"><h4>Original message</h4><p style="margin:0">{esc(parsed.get("raw_text"))}</p></div>')
            fields = [("Order", parsed.get("order_id")), ("Customer", parsed.get("customer")), ("Product", parsed.get("product")),
                      ("Category", parsed.get("category")), ("Pieces", parsed.get("pieces")), ("Due", parsed.get("due_date")),
                      ("Preference", parsed.get("preference") or "None"), ("Extraction", explain.source_label(parsed.get("llm_metadata") or {})[1])]
            html('<dl class="kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in fields) + "</dl>")
            statements = record.get("constraints_applied", {}).get("statements") or []
            if statements:
                html('<h4 class="section-note" style="margin-top:10px">Constraints and who imposed them</h4><ul>' + "".join(
                    f'<li>“{esc(s.get("text"))}” · {esc(s.get("imposed_by") or "unknown")}' + (f', relayed by {esc(s["relayed_by"])}' if s.get("relayed_by") else "") + "</li>"
                    for s in statements) + "</ul>")
        with decision:
            won = explain.why_won(record)
            if won:
                html(f'<div class="why"><b>Why this won</b><p style="font-size:15px">{esc(won["sentence"])}</p></div>')
            body, classes = [], []
            for c in explain.selection_order(record):
                body.append([esc(c["name"]), esc(explain.short_date(c["eta_date"])), f'{c["days_to_spare"]:+d}', f'{c["total_cost"]:,.0f}', f'{c["score"]:.5f}'])
                classes.append("chosen" if c["workshop_id"] == wid else "")
            for c in record.get("ineligible", []):
                body.append([esc(c["name"]), esc(explain.ineligible_headline(c["reason"])), "n/a", "n/a", "n/a"])
                classes.append("dim")
            html(table(["Workshop", "Back", "Spare", "Cost", "Score"], body, right=range(2, 5), classes=classes))
            html(f'<div class="section-note">{esc(record.get("reason_chosen"))}</div>')
        with evidence:
            numbers = audit.get("numbers_in_text", [])
            html(f'<p>{len(numbers)} numeric claims checked against tool outputs when the record was written. '
                 f'Unmatched: {esc(", ".join(audit.get("unmatched", [])) or "none")}.</p>')
            with st.expander("Tool call trace"):
                json_block(record.get("tool_outputs", {}).get("call_trace", []), height=360)
            with st.expander("Recorded explanation"):
                st.text(row.get("explanation_text", ""))
        with human:
            items = [("Confirmed", "Yes" if confirmation.get("confirmed") else "No"),
                     ("Accepted late return", "Yes" if confirmation.get("accepted_lateness") else "No"),
                     ("Accepted an alternative", "Yes" if confirmation.get("accepted_alternative") else "No"),
                     ("Extraction source", confirmation.get("extraction_source", "live")),
                     ("Preview token", confirmation.get("preview_token")),
                     ("Logged at (UTC)", row.get("timestamp")), ("Business date", record.get("timestamp", "")[:10])]
            html('<dl class="kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in items) + "</dl>"
                 '<div class="section-note" style="margin-top:10px">Confirmation records the decision locally. It does not contact the workshop.</div>')
        with raw:
            json_block(row, height=420)
            st.download_button("Download this record (JSON)", json.dumps(row, indent=2, ensure_ascii=False, default=str),
                               file_name=f"{record.get('order_id') or 'record'}-audit.json", mime="application/json", key="audit_download")
