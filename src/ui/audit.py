"""Audit Trail: a governance ledger of confirmed decisions. Read-only.

Rows come from records.load(); a malformed log is reported, never skipped.
The live and rehearsal logs are separate files and are never merged. Opening a
row shows the stored record in a slide-over panel; raw JSON stays secondary.
"""

from __future__ import annotations

from datetime import date, datetime
import json

import streamlit as st

import desk
import records
from ui import explain
from ui.components import banner, esc, html, json_block, page_head, status_pill

LOGS = {"live": "Live log", "rehearsal": "Rehearsal log"}
KINDS = ["Allocation", "Alternative accepted", "Late return accepted"]
KIND_TONE = {"Allocation": "ok", "Alternative accepted": "info", "Late return accepted": "warn"}
COLUMNS = [1.05, .95, .9, 1.25, 1.35, 1.55, 1.05, .62]
SHOWN = 60


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


def when(row: dict) -> str:
    try:
        moment = datetime.fromisoformat(row.get("timestamp", ""))
    except ValueError:
        return "Unknown"
    return f"{moment.day} {moment:%b}, {moment:%H:%M}"


def workshop_name(wid, workshops) -> str:
    return workshops[wid].name if wid in workshops else (wid or "None")


def summary(row: dict, workshops) -> dict:
    record = row.get("decision_record", {})
    return {"Time (UTC)": (row.get("timestamp") or "")[:16].replace("T", " "), "Order": record.get("order_id") or "",
            "Sender": row.get("sender") or "Unknown", "Workshop": workshop_name(record.get("chosen_workshop"), workshops),
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
        html('<div class="empty"><i></i><div class="say">No confirmed decisions yet.</div>'
             '<div class="ask">Evaluate a request in Dispatch and confirm it. The record appears here. Previews are never recorded.</div></div>')
        return
    senders = sorted({r.get("sender") for r in rows} - {None, ""})
    shops = sorted({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None})
    days = sorted(set(d for d in (logged_date(r) for r in rows) if d))
    for key, options in (("audit_sender", senders), ("audit_workshop", shops), ("audit_kind", KINDS)):
        state[key] = [v for v in state.get(key, []) if v in options]
    if state.get("audit_day") not in [None, *days]:
        state["audit_day"] = None
    with st.container(key="audit_bar"):
        a, b, c, d, e = st.columns([1.3, 1.1, 1.1, 1, 1.2], vertical_alignment="bottom")
        with a:
            query = st.text_input("Order or text", key="audit_q", placeholder="ORD-045")
        with b:
            workshop = st.multiselect("Workshop", shops, key="audit_workshop", format_func=lambda wid: workshop_name(wid, workshops))
        with c:
            sender = st.multiselect("Requester", senders, key="audit_sender")
        with d:
            day = st.selectbox("Date", [None, *reversed(days)], key="audit_day", format_func=lambda v: "Any date" if v is None else explain.long_date(v))
        with e:
            kinds = st.multiselect("Decision type", KINDS, key="audit_kind")
    found = search(rows, query, sender, workshop, kinds, (day, day) if day else None)
    verified = sum(bool((r.get("faithfulness") or {}).get("passed")) for r in rows)
    late = sum(kind(r) == "Late return accepted" for r in rows)
    stats = [(len(rows), "confirmed records"), (verified, "evidence verified"), (late, "late returns accepted"),
             (len({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None}), "workshops used")]
    html('<div class="nstats" style="margin-top:0">' + "".join(f'<div class="nstat"><strong>{n}</strong><small>{esc(t)}</small></div>' for n, t in stats)
         + f'<div class="ledger-note">{esc(LOGS[log])}. Append-only, written only after a dispatcher confirms.</div></div>')
    if not found:
        html(banner("No matching records.", " Clear a filter to widen the search.", "muted"))
        return
    ledger(found[:SHOWN], workshops)
    more = f" Showing the newest {SHOWN}; narrow the filters to reach older records." if len(found) > SHOWN else ""
    html(f'<div class="meta">{len(found)} of {len(rows)} records, newest first.{esc(more)}</div>')
    st.download_button("Export shown records (JSONL)", "\n".join(json.dumps(r, ensure_ascii=False) for r in found) + "\n",
                       file_name=f"{log}-audit-records.jsonl", mime="application/x-ndjson", key="audit_export",
                       icon=":material/download:")


def ledger(found, workshops):
    with st.container(key="ledger"):
        cols = st.columns(COLUMNS, vertical_alignment="center")
        for col, title in zip(cols, ["Time (UTC)", "Order", "Requester", "Workshop", "Objective", "Decision", "Evidence", ""]):
            with col:
                html(f'<div class="lg-head">{esc(title)}</div>')
        for i, row in enumerate(found):
            record = row.get("decision_record", {})
            passed = (row.get("faithfulness") or {}).get("passed")
            cells = [f'<div class="lg-cell m">{esc(when(row))}</div>', f'<div class="lg-cell"><b class="id">{esc(record.get("order_id") or "None")}</b></div>',
                     f'<div class="lg-cell">{esc(row.get("sender") or "Unknown")}</div>',
                     f'<div class="lg-cell"><b>{esc(workshop_name(record.get("chosen_workshop"), workshops))}</b></div>',
                     f'<div class="lg-cell m">{esc(explain.objective_label(record.get("objective_name", "")))}</div>',
                     status_pill(kind(row), KIND_TONE[kind(row)]),
                     status_pill("Verified", "ok") if passed else status_pill("Failed", "risk")]
            with st.container(key=f"lrow_{i}"):
                cols = st.columns(COLUMNS, vertical_alignment="center")
                for col, cell in zip(cols, cells):
                    with col:
                        html(cell)
                with cols[-1]:
                    if st.button("Open", key=f"audit_open_{i}", width="stretch"):
                        record_panel(row, workshops)


@st.dialog("Audit record", width="large")
def record_panel(row, workshops):
    record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
    wid = record.get("chosen_workshop")
    chosen = explain.chosen_row(record)
    confirmation = record.get("constraints_applied", {}).get("confirmation", {})
    check = row.get("faithfulness") or {}
    passed = check.get("passed")
    back = (f'Back {explain.long_date(chosen["eta_date"])}, {chosen["days_to_spare"]:+d} days to spare, cost {chosen["total_cost"]:,.0f}.'
            if chosen else "")
    html(f'<div class="inspector"><div class="eyebrow">Record {esc(record.get("order_id"))}, logged {esc(when(row))} UTC</div>'
         f'<div class="ins-title">{esc(workshop_name(wid, workshops))}</div><div class="ins-sub">{esc(back)}</div>'
         f'<div style="display:flex;gap:8px;margin-top:12px">{status_pill(kind(row), "dark")}'
         f'{status_pill("Evidence verified" if passed else "Evidence failed", "dark-green" if passed else "dark-risk")}'
         f'{status_pill("Confirmed by dispatcher" if confirmation.get("confirmed") else "Not confirmed", "dark-muted")}</div></div>')
    summary_tab, candidates_tab, evidence_tab = st.tabs(["Decision", "Candidates", "Evidence"])
    with summary_tab:
        fields = [("Order", parsed.get("order_id")), ("Customer", parsed.get("customer")), ("Product", parsed.get("product")),
                  ("Pieces", parsed.get("pieces")), ("Due", explain.long_date(parsed.get("due_date")) if parsed.get("due_date") else None),
                  ("Preference", explain.PREFERENCE_LABELS.get(parsed.get("preference"), "None")),
                  ("Read by", explain.source_label(parsed.get("llm_metadata") or {})[1])]
        statements = record.get("constraints_applied", {}).get("statements") or []
        excluded = record.get("constraints_applied", {}).get("exclude") or []
        lines = [f"“{s.get('text')}”, imposed by {s.get('imposed_by') or 'unknown'}" + (f", relayed by {s['relayed_by']}" if s.get("relayed_by") else "")
                 for s in statements] + ([f"Excluded workshops: {', '.join(excluded)}"] if excluded else [])
        won = explain.why_won(record)
        html(f'<div class="dk-card" style="margin-top:6px"><div class="eyebrow" style="color:var(--cyan)">Original request</div>'
             f'<p style="font-size:16px;margin:6px 0 0">{esc(parsed.get("raw_text"))}</p></div>'
             f'<div class="dk-card beam" style="margin-top:12px"><div class="eyebrow" style="color:var(--cyan)">Why this workshop</div>'
             f'<p style="font-size:16px;margin:6px 0 4px">{esc(won["sentence"] if won else record.get("reason_chosen"))}</p>'
             f'<div class="ev">Objective {esc(explain.objective_label(record.get("objective_name", "")))}.</div></div>'
             '<div class="grid g2" style="margin-top:12px">'
             f'<div class="dk-card"><div class="eyebrow" style="color:var(--cyan)">Parsed request</div><dl class="kv" style="grid-template-columns:110px 1fr;font-size:14px;margin-top:8px">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in fields if v is not None) + "</dl></div>"
             f'<div class="dk-card"><div class="eyebrow" style="color:var(--cyan)">Constraints</div><ul class="dk-list">'
             + ("".join(f"<li>{esc(t)}</li>" for t in lines) or "<li>None stated</li>") + "</ul></div></div>")
    with candidates_tab:
        body = []
        for c in explain.selection_order(record):
            mark = " class=\"w\"" if c["workshop_id"] == wid else ""
            body.append(f'<tr{mark}><td>{esc(c["name"])}</td><td class="r">{esc(explain.short_date(c["eta_date"]))}</td><td class="r">{c["days_to_spare"]:+d}</td>'
                        f'<td class="r">{c["total_cost"]:,.0f}</td><td class="r">{c["score"]:.5f}</td></tr>')
        for c in record.get("ineligible", []):
            body.append(f'<tr class="off"><td>{esc(c["name"])}</td><td colspan="4">{esc(explain.ineligible_headline(c["reason"]))}</td></tr>')
        html('<table class="ev-table cand"><tr class="h"><td>Workshop</td><td class="r">Return</td><td class="r">Spare</td><td class="r">Cost</td>'
             f'<td class="r">Score</td></tr>{"".join(body)}</table><p class="ev" style="margin-top:10px">Lower score wins. Values are the stored record, not a recalculation.</p>')
    with evidence_tab:
        items = [("Values checked", f'{len(check.get("numbers_in_text", []))}, unsupported {len(check.get("unmatched", []))}'),
                 ("Confirmed by dispatcher", "Yes" if confirmation.get("confirmed") else "No"),
                 ("Accepted late return", "Yes" if confirmation.get("accepted_lateness") else "No"),
                 ("Accepted an alternative", "Yes" if confirmation.get("accepted_alternative") else "No"),
                 ("Request reading", confirmation.get("extraction_source") or "live"),
                 ("Logged at (UTC)", (row.get("timestamp") or "")[:19].replace("T", " ")),
                 ("Business date", record.get("timestamp", "")[:10])]
        html('<div class="dk-card" style="margin-top:6px"><dl class="kv" style="grid-template-columns:190px 1fr;font-size:14px">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in items) + "</dl>"
             '<p class="ev" style="margin:12px 0 0">Confirmation records the decision locally. It does not contact the workshop.</p></div>')
        if st.toggle("View tool trace", key="audit_raw_trace"):
            json_block(record.get("tool_outputs", {}).get("call_trace", []), height=300)
        if st.toggle("View raw record", key="audit_raw_record"):
            json_block(row, height=340)
        st.download_button("Download this record", json.dumps(row, indent=2, ensure_ascii=False, default=str),
                           file_name=f"{record.get('order_id') or 'record'}-audit.json", mime="application/json", key="audit_download")
