"""Audit Trail: a governance ledger of confirmed decisions. Read-only.

Rows come from records.load(); a malformed log is reported, never skipped.
The live and rehearsal logs are separate files and are never merged. Opening a
row shows the stored record in a slide-over panel; raw JSON stays secondary.
"""

from __future__ import annotations

from datetime import date, datetime
import json

import pandas as pd

import streamlit as st

import desk
import records
from ui import explain, performance
from ui.components import banner, chart, esc, html, icon, json_block, status_pill
from ui.state import bind, one_of, subset_of, text

LOGS = {"live": "Live log", "rehearsal": "Rehearsal log"}
VIEWS = {"decisions": "Decision audit", "performance": "Performance diagnostics"}
KINDS = ["Allocation", "Alternative accepted", "Late return accepted"]
KIND_TONE = {"Allocation": "conf", "Alternative accepted": "info", "Late return accepted": "warn"}
COLUMNS = [1.3, .95, .95, 1.25, 1.2, 1.2, .95, .75]
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
    html('<div class="kicker"><span>Audit trail</span></div>'
         '<div class="home-title" style="margin-top:0.8rem">Every confirmed decision, with its evidence</div>'
         '<div class="home-sub">A record is written only when a dispatcher confirms. Recommendations, previews and simulator runs are never logged here.</div>')
    with st.container(key="audit_switches", horizontal=True, vertical_alignment="bottom"):
        view = bind(st.segmented_control, "View", list(VIEWS), key="audit_view", fallback="decisions", format_func=VIEWS.get, required=True)
        log = None
        if view == "decisions":
            # A missing or stale selection falls back to the log that matches the current reading mode.
            default = "rehearsal" if state.get("desk_source", "live") != "live" else "live"
            log = bind(st.segmented_control, "Log", list(LOGS), key="audit_log", fallback=default, format_func=LOGS.get, required=True)
    if view == "performance":
        html('<div class="home-sub" style="margin:0.2rem 0 0.8rem">Diagnostics only. Timing never changes a recommendation, and nothing here is a decision record.</div>')
        performance.render()
        return
    if log == "rehearsal":
        html(banner("Rehearsal log.", " Confirmations made in rehearsal mode. They are kept apart from the live log and are not operational decisions.", "warn"))
    path = desk.REHEARSAL_LOG if log == "rehearsal" else None
    try:
        rows = records.load(path)
    except (OSError, ValueError) as error:
        html(banner("The audit log could not be read.", f" {error}. No records were skipped or repaired.", "risk"))
        return
    if not rows:
        other = "rehearsal" if log == "live" else "live"
        try:
            others = len(records.load(desk.REHEARSAL_LOG if other == "rehearsal" else None))
        except (OSError, ValueError):
            others = 0
        hint = f'<p class="ae-hint">The {LOGS[other].lower()} has {others} record{"s" if others != 1 else ""}. Switch logs above to see {"it" if others == 1 else "them"}.</p>' if others else ""
        html('<div class="audit-empty"><div class="ae-weave" aria-hidden="true"></div><div class="ae-body">'
             f'{icon("verified_user")}<div class="say">No confirmed decisions in the {esc(LOGS[log].lower())} yet.</div>'
             '<ol class="ae-steps"><li><b>Evaluate a request</b><span>Dispatch reads it and the engine recommends a workshop.</span></li>'
             '<li><b>Confirm it</b><span>Only an explicit confirmation by the dispatcher writes a record.</span></li>'
             '<li><b>Review it here</b><span>The request, candidates, reasons and evidence, kept append-only.</span></li></ol>'
             f'{hint}</div><div class="ae-sheet" aria-hidden="true"><b>{esc(LOGS[log])}</b><i></i><span>No entries yet</span></div></div>')
        return
    focus = state.pop("audit_focus", None)
    focused = next((r for r in rows if focus and r.get("timestamp") == focus), None)
    if focused is not None:
        # Arriving from Dispatch or a trace: clear the filters so the record is in view, then open it once.
        for key, empty in (("audit_q", ""), ("audit_sender", []), ("audit_workshop", []), ("audit_kind", []), ("audit_day", "any")):
            state[key] = empty
        state["audit_opened"] = focus
    senders = sorted({r.get("sender") for r in rows} - {None, ""})
    shops = sorted({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None})
    days = sorted(set(d for d in (logged_date(r) for r in rows) if d))
    for key, options in (("audit_sender", senders), ("audit_workshop", shops), ("audit_kind", KINDS)):
        state[key] = [v for v in state.get(key) or [] if v in options]
    with st.container(key="audit_bar"):
        a, b, c, d, e = st.columns([1.3, 1.1, 1.1, 1, 1.2], vertical_alignment="bottom")
        with a:
            query = bind(st.text_input, "Order or text", key="audit_q", fallback="", accept=text, placeholder="ORD-045")
        with b:
            workshop = bind(st.multiselect, "Workshop", shops, key="audit_workshop", fallback=[], accept=subset_of(shops),
                            format_func=lambda wid: workshop_name(wid, workshops))
        with c:
            sender = bind(st.multiselect, "Requester", senders, key="audit_sender", fallback=[], accept=subset_of(senders))
        with d:
            choice = bind(st.selectbox, "Date", ["any", *reversed(days)], key="audit_day", fallback="any",
                          format_func=lambda v: "Any date" if v == "any" else explain.long_date(v))
            day = None if choice == "any" else choice
        with e:
            kinds = bind(st.multiselect, "Decision type", KINDS, key="audit_kind", fallback=[], accept=subset_of(KINDS))
    found = search(rows, query, sender, workshop, kinds, (day, day) if day else None)
    summary_row(rows, log, workshops)
    if not found:
        html(banner("No matching records.", " Clear a filter to widen the search.", "muted"))
        return
    main, side = st.columns([1.75, 1], gap="medium")
    with main:
        ledger(found[:SHOWN], workshops)
        more = f" Showing the newest {SHOWN}; narrow the filters to reach older records." if len(found) > SHOWN else ""
        html(f'<div class="meta" style="margin-top:0.4rem">{len(found)} of {len(rows)} records, newest first.{esc(more)}</div>')
        st.download_button("Export shown records (JSONL)", "\n".join(json.dumps(r, ensure_ascii=False) for r in found) + "\n",
                           file_name=f"{log}-audit-records.jsonl", mime="application/x-ndjson", key="audit_export",
                           icon=":material/download:")
    with side:
        timeline(found[:12], workshops, log)
    if focused is not None:
        record_panel(focused, workshops)


def summary_row(rows, log, workshops):
    """Activity summary and a decision history chart, both counted from the records on file."""
    verified = sum(bool((r.get("faithfulness") or {}).get("passed")) for r in rows)
    late = sum(kind(r) == "Late return accepted" for r in rows)
    used = len({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None})
    stats = [(len(rows), "Confirmed decisions"), (f"{verified} of {len(rows)}", "Evidence verified"),
             (late, "Late returns accepted"), (used, "Workshops used")]
    left, right = st.columns([1, 1.5], gap="medium")
    with left:
        html('<div class="an-card au-sum"><div class="an-title">Activity</div><div class="an-sub">'
             f'{esc(LOGS[log])}, append-only.</div><div class="au-stats">'
             + "".join(f'<div><b>{esc(n)}</b><small>{esc(t)}</small></div>' for n, t in stats) + "</div></div>")
    with right, st.container(key="chart_audit_hist"):
        html('<div class="an-title">Decisions by day</div><div class="an-sub">Confirmed records per logged day (UTC), by decision type.</div>')
        frame = pd.DataFrame([{"day": str(logged_date(r)), "type": kind(r)} for r in rows if logged_date(r)])
        if len(frame):
            chart(frame, {"mark": {"type": "bar", "cornerRadiusEnd": 4, "width": {"band": .55}},
                          "encoding": {"x": {"field": "day", "type": "ordinal", "title": None, "axis": {"labelAngle": 0}},
                                       "y": {"aggregate": "count", "type": "quantitative", "title": "Decisions", "axis": {"tickMinStep": 1}},
                                       "color": {"field": "type", "title": None, "scale": {"domain": KINDS, "range": ["#2A77E8", "#7FB0F2", "#E09A2C"]}},
                                       "tooltip": [{"field": "day", "title": "Day"}, {"field": "type", "title": "Type"}, {"aggregate": "count", "title": "Decisions"}]}},
                  height=176)
        html('<div class="an-src">Source: the audit log file. Nothing here is simulated.</div>')


def timeline(found, workshops, log="live"):
    items = []
    for row in found:
        record = row.get("decision_record", {})
        passed = (row.get("faithfulness") or {}).get("passed")
        rh = " rh" if log == "rehearsal" else ""
        items.append(f'<li class="{KIND_TONE[kind(row)]}{rh}"><span class="tl-d"></span><div><div class="tl-h"><b>{esc(workshop_name(record.get("chosen_workshop"), workshops))}</b>'
                     f'<em>{esc(when(row))}</em></div><p><span class="id">{esc(record.get("order_id") or "None")}</span> for {esc(row.get("sender") or "unknown")}. '
                     f'{esc(kind(row))}, confirmed by the dispatcher{"<em> in rehearsal</em>" if rh else ""}. Evidence {"verified" if passed else "failed"}.</p></div></li>')
    note = "Rehearsal confirmations, kept apart from live decisions." if log == "rehearsal" else "Each entry is a human-confirmed allocation."
    html(f'<div class="an-card"><div class="an-title">Decision timeline</div><div class="an-sub">Newest first. {note}</div>'
         f'<ol class="au-tl">{"".join(items)}</ol></div>')


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
                if st.session_state.get("audit_opened") == row.get("timestamp"):
                    html('<span class="lg-open" aria-hidden="true"></span>')
                with cols[-1]:
                    if st.button("Open", key=f"audit_open_{i}", width="stretch"):
                        st.session_state["audit_opened"] = row.get("timestamp")
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
         f'<div style="display:flex;gap:0.5333rem;margin-top:0.8rem">{status_pill(kind(row), "dark-muted")}'
         f'{status_pill("Evidence verified" if passed else "Evidence failed", "dark" if passed else "dark-risk")}'
         f'{status_pill("Confirmed by dispatcher" if confirmation.get("confirmed") else "Not confirmed", "dark-conf" if confirmation.get("confirmed") else "dark-muted")}</div></div>')
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
        html(f'<div class="dk-card" style="margin-top:0.4rem"><div class="eyebrow" style="color:var(--cyan)">Original request</div>'
             f'<p style="font-size:1.1rem;margin:0.4rem 0 0">{esc(parsed.get("raw_text"))}</p></div>'
             f'<div class="dk-card beam" style="margin-top:0.8rem"><div class="eyebrow" style="color:var(--cyan)">Why this workshop</div>'
             f'<p style="font-size:1.1rem;margin:0.4rem 0 0.2667rem">{esc(won["sentence"] if won else record.get("reason_chosen"))}</p>'
             f'<div class="ev">Objective {esc(explain.objective_label(record.get("objective_name", "")))}.</div></div>'
             '<div class="grid g2" style="margin-top:0.8rem">'
             f'<div class="dk-card"><div class="eyebrow" style="color:var(--cyan)">Parsed request</div><dl class="kv" style="grid-template-columns:7.3333rem 1fr;font-size:0.9667rem;margin-top:0.5333rem">'
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
             f'<td class="r">Score</td></tr>{"".join(body)}</table><p class="ev" style="margin-top:0.6667rem">Lower score wins. Values are the stored record, not a recalculation.</p>')
    with evidence_tab:
        items = [("Values checked", f'{len(check.get("numbers_in_text", []))}, unsupported {len(check.get("unmatched", []))}'),
                 ("Confirmed by dispatcher", "Yes" if confirmation.get("confirmed") else "No"),
                 ("Accepted late return", "Yes" if confirmation.get("accepted_lateness") else "No"),
                 ("Accepted an alternative", "Yes" if confirmation.get("accepted_alternative") else "No"),
                 ("Request reading", confirmation.get("extraction_source") or "live"),
                 ("Made in the guided demo", "Yes" if confirmation.get("guided_demo") else "No"),
                 ("Execution trace", confirmation.get("trace_id") or "Not recorded"),
                 ("Logged at (UTC)", (row.get("timestamp") or "")[:19].replace("T", " ")),
                 ("Business date", record.get("timestamp", "")[:10])]
        html('<div class="dk-card" style="margin-top:0.4rem"><dl class="kv" style="grid-template-columns:12.6667rem 1fr;font-size:0.9667rem">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in items) + "</dl>"
             '<p class="ev" style="margin:0.8rem 0 0">Confirmation records the decision locally. It does not contact the workshop.</p></div>')
        if st.toggle("View tool trace", key="audit_raw_trace"):
            json_block(record.get("tool_outputs", {}).get("call_trace", []), height=300)
        if st.toggle("View raw record", key="audit_raw_record"):
            json_block(row, height=340)
        st.download_button("Download this record", json.dumps(row, indent=2, ensure_ascii=False, default=str),
                           file_name=f"{record.get('order_id') or 'record'}-audit.json", mime="application/json", key="audit_download")
