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
from ui.components import banner, esc, h3, html, json_block, page_head, table, tag

LOGS = {"live": "Live log", "rehearsal": "Rehearsal log"}
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
    record = row.get("decision_record", {})
    wid = record.get("chosen_workshop")
    return {"Time (UTC)": (row.get("timestamp") or "")[:16].replace("T", " "), "Order": record.get("order_id") or "",
            "Sender": row.get("sender") or "Unknown", "Workshop": workshops[wid].name if wid in workshops else (wid or "None"),
            "Objective": explain.objective_label(record.get("objective_name", "")), "Status": kind(row),
            "Evidence": "Verified" if (row.get("faithfulness") or {}).get("passed") else "Failed"}


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
    head, log_col = st.columns([3, 1], vertical_alignment="bottom")
    with head:
        page_head("Audit trail", "Every confirmed decision, with its evidence.")
    with log_col:
        log = st.segmented_control("Log", list(LOGS), key="audit_log", format_func=LOGS.get, required=True)
    path = desk.REHEARSAL_LOG if log == "rehearsal" else None
    try:
        rows = records.load(path)
    except (OSError, ValueError) as error:
        html(banner("The audit log could not be read.", f" {error}. No records were skipped or repaired.", "risk"))
        return
    if not rows:
        html('<div class="card soft" style="padding:28px"><div class="say">No confirmed decisions yet.</div>'
             '<div class="ask">Run a decision in Dispatch and confirm it. The record appears here. Previews are never recorded.</div></div>')
        return
    senders = sorted({r.get("sender") for r in rows} - {None, ""})
    shops = sorted({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None})
    days = sorted(set(d for d in (logged_date(r) for r in rows) if d))
    for key, options in (("audit_sender", senders), ("audit_workshop", shops), ("audit_kind", KINDS)):
        state[key] = [v for v in state.get(key, []) if v in options]
    if state.get("audit_day") not in [None, *days]:
        state["audit_day"] = None
    with st.container(key="audit_filters"):
        a, b, c, d, e = st.columns([1.3, 1.1, 1.1, 1, 1.2], vertical_alignment="bottom")
        with a:
            query = st.text_input("Order or text", key="audit_q", placeholder="ORD-045")
        with b:
            workshop = st.multiselect("Workshop", shops, key="audit_workshop", format_func=lambda wid: workshops[wid].name if wid in workshops else wid)
        with c:
            sender = st.multiselect("Sender", senders, key="audit_sender")
        with d:
            day = st.selectbox("Date", [None, *reversed(days)], key="audit_day", format_func=lambda v: "Any date" if v is None else explain.long_date(v))
        with e:
            kinds = st.multiselect("Decision type", KINDS, key="audit_kind")
    found = search(rows, query, sender, workshop, kinds, (day, day) if day else None)
    html(f'<div class="meta">{len(found)} of {len(rows)} records, newest first.</div>')
    if not found:
        html(banner("No matching records.", " Clear a filter to widen the search.", "muted"))
        return
    frame = pd.DataFrame([summary(r, workshops) for r in found])
    event = st.dataframe(frame, hide_index=True, width="stretch", height=min(40 + 35 * len(frame), 320),
                         on_select="rerun", selection_mode="single-row", key="audit_table")
    selected = event.selection.rows[0] if event and event.selection.rows else 0
    detail(found[selected], workshops)
    st.download_button("Export shown records (JSONL)", "\n".join(json.dumps(r, ensure_ascii=False) for r in found) + "\n",
                       file_name=f"{log}-audit-records.jsonl", mime="application/x-ndjson", key="audit_export")


def detail(row, workshops):
    record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
    wid = record.get("chosen_workshop")
    chosen = explain.chosen_row(record)
    confirmation = record.get("constraints_applied", {}).get("confirmation", {})
    audit = row.get("faithfulness") or {}
    name = workshops[wid].name if wid in workshops else wid
    with st.container(key="audit_detail"):
        html(f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px"><div>'
             f'<div class="eyebrow">Record {esc(record.get("order_id"))}</div><div class="page-title" style="font-size:24px">{esc(name)}</div>'
             + (f'<div class="meta">Back {esc(explain.long_date(chosen["eta_date"]))}, {chosen["days_to_spare"]:+d} days to spare, cost {chosen["total_cost"]:,.0f}</div>' if chosen else "")
             + f'</div><div style="display:flex;gap:8px">{tag(kind(row), "info")}{tag("Evidence verified" if audit.get("passed") else "Evidence failed", "ok" if audit.get("passed") else "risk")}</div></div>')
        left, right = st.columns(2, gap="large")
        with left:
            h3("Original request")
            html(f'<div class="card soft" style="margin:6px 0 14px">{esc(parsed.get("raw_text"))}</div>')
            h3("Parsed structure")
            fields = [("Order", parsed.get("order_id")), ("Customer", parsed.get("customer")), ("Product", parsed.get("product")),
                      ("Pieces", parsed.get("pieces")), ("Due", explain.long_date(parsed.get("due_date")) if parsed.get("due_date") else None),
                      ("Preference", explain.PREFERENCE_LABELS.get(parsed.get("preference"), "None")),
                      ("Read by", explain.source_label(parsed.get("llm_metadata") or {})[1])]
            html('<dl class="kv" style="margin:6px 0 14px">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in fields if v is not None) + "</dl>")
            h3("Constraints")
            statements = record.get("constraints_applied", {}).get("statements") or []
            excluded = record.get("constraints_applied", {}).get("exclude") or []
            lines = [f"“{s.get('text')}”, imposed by {s.get('imposed_by') or 'unknown'}" + (f", relayed by {s['relayed_by']}" if s.get("relayed_by") else "")
                     for s in statements] + ([f"Excluded workshops: {', '.join(excluded)}"] if excluded else [])
            html('<ul style="margin:6px 0 0">' + ("".join(f"<li>{esc(t)}</li>" for t in lines) or "<li>None stated</li>") + "</ul>")
        with right:
            h3("Chosen workshop and reason")
            won = explain.why_won(record)
            html(f'<p style="margin:6px 0 4px">{esc(won["sentence"] if won else record.get("reason_chosen"))}</p>'
                 f'<div class="meta" style="margin-bottom:12px">Objective {esc(explain.objective_label(record.get("objective_name", "")))}. '
                 f'{esc(record.get("reason_chosen"))}</div>')
            h3("Candidate list")
            body, classes = [], []
            for c in explain.selection_order(record):
                body.append([esc(c["name"]), esc(explain.short_date(c["eta_date"])), f'{c["days_to_spare"]:+d}', f'{c["total_cost"]:,.0f}', f'{c["score"]:.5f}'])
                classes.append("chosen" if c["workshop_id"] == wid else "")
            for c in record.get("ineligible", []):
                body.append([esc(c["name"]), esc(explain.ineligible_headline(c["reason"])), "n/a", "n/a", "n/a"])
                classes.append("dim")
            html(table(["Workshop", "Return", "Spare", "Cost", "Score"], body, right=range(2, 5), classes=classes))
            h3("Faithfulness and confirmation")
            items = [("Numbers checked", f'{len(audit.get("numbers_in_text", []))}, unsupported {len(audit.get("unmatched", []))}'),
                     ("Confirmed by dispatcher", "Yes" if confirmation.get("confirmed") else "No"),
                     ("Accepted late return", "Yes" if confirmation.get("accepted_lateness") else "No"),
                     ("Accepted an alternative", "Yes" if confirmation.get("accepted_alternative") else "No"),
                     ("Logged at (UTC)", (row.get("timestamp") or "")[:19].replace("T", " ")),
                     ("Business date", record.get("timestamp", "")[:10])]
            html('<dl class="kv" style="margin-top:6px">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in items) + "</dl>"
                 '<div class="meta" style="margin-top:8px">Confirmation records the decision locally. It does not contact the workshop.</div>')
        with st.expander("Tool evidence"):
            json_block(record.get("tool_outputs", {}).get("call_trace", []), height=320)
        with st.expander("Raw record"):
            json_block(row, height=360)
            st.download_button("Download this record", json.dumps(row, indent=2, ensure_ascii=False, default=str),
                               file_name=f"{record.get('order_id') or 'record'}-audit.json", mime="application/json", key="audit_download")
