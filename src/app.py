"""Streamlit dispatch desk. Run: streamlit run src/app.py

Dispatch is a preview. Only the explicit confirmation callback writes an audit
row and commits local history/queues. This app does not contact a workshop.
Queue figures are nominal local-session projections from the CSV snapshot.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
from html import escape
import json
from pathlib import Path
import sys
from uuid import uuid4

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "harness")]

from agent import Agent, AgentResponse
from allocator import Allocator
import faithfulness
from objectives import ObjectiveConfig, PRESETS, score_candidate, score_terms
import records
from simulate import load_workshops
import tools

TODAY = date(2026, 4, 1)
VERDICTS = {"allocate": ("ALLOCATE", "allocate"), "clarify": ("NEEDS CLARIFICATION", "clarify"),
            "refuse": ("REFUSED", "refuse"), "decline": ("CANNOT ANSWER", "decline")}

CSS = """
<style>
.stApp { background:#fff; color:#202020; }
.block-container { padding:2.8rem 1.5rem 1.5rem; max-width:1600px; }
header[data-testid="stHeader"] { background:#fff; }
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"] { display:none; }
[data-testid="stHeadingWithActionElements"] h1 { font-size:1.55rem; padding:.15rem 0; }
[data-testid="stHeadingWithActionElements"] h3 { font-size:1.05rem; padding:.2rem 0; }
[data-testid="stVerticalBlock"] { gap:.6rem; }
[data-testid="stSidebar"] { background:#f5f5f5; }
[data-testid="stSidebar"][aria-expanded="true"] { width:180px; min-width:180px; max-width:180px; }
button, input, textarea { accent-color:#222 !important; }
button[kind="secondary"] { color:#202020; border-color:#d4d4d4; }
button[kind="primary"] { background:#222; border-color:#222; color:#fff; }
button[kind="primary"]:hover { background:#444; border-color:#444; }
button:focus-visible, textarea:focus-visible, input:focus-visible { outline-color:#555 !important; }
[data-testid="stTextArea"] textarea { font-size:.84rem; line-height:1.45; }
.st-key-inbox_list button { text-align:left; justify-content:flex-start; font-size:.77rem; min-height:2.5rem; }
.st-key-inbox_list button p { font-size:.77rem; }
.desk-banner { padding:.55rem .8rem; border-left:4px solid; font-weight:700; font-size:.83rem; margin-bottom:.45rem; }
.desk-banner.allocate { background:#e9f5ec; color:#164b2c; border-color:#31734a; }
.desk-banner.clarify { background:#fff3d9; color:#694607; border-color:#a87718; }
.desk-banner.refuse { background:#fbecec; color:#802a2a; border-color:#ae4545; }
.desk-banner.decline { background:#ededed; color:#444; border-color:#777; }
.recommendation { border:1px solid #d3d3d3; border-radius:7px; padding:1rem; }
.eyebrow { text-transform:uppercase; letter-spacing:.08em; color:#666; font-size:.66rem; font-weight:700; }
.shop-title { font-size:1.5rem; font-weight:700; line-height:1.2; margin:.25rem 0 .75rem; }
.metrics { display:grid; grid-template-columns:1.25fr .8fr 1fr .9fr; gap:.65rem; }
.metric { text-align:right; font-variant-numeric:tabular-nums; }
.metric small { display:block; color:#666; font-size:.68rem; }
.metric strong { font-size:1.04rem; white-space:nowrap; }
.reason { font-size:.83rem; margin:.8rem 0 0; line-height:1.4; }
.weights { display:grid; grid-template-columns:repeat(5,1fr); gap:.65rem; padding-top:.55rem; }
.weights div { text-align:right; font-variant-numeric:tabular-nums; }
.weights small { display:block; font-size:.65rem; color:#666; }
.weights strong { font-size:.95rem; }
.mono-badge { display:inline-block; border:1px solid #aaa; border-radius:4px; padding:.18rem .45rem; font-size:.72rem; font-weight:600; }
.table-wrap { overflow:auto; max-height:270px; border:1px solid #ddd; border-radius:5px; }
.desk-table { width:100%; border-collapse:collapse; font-size:.73rem; }
.desk-table th { position:sticky; top:0; background:#f2f2f2; text-align:left; color:#555; font-weight:600; }
.desk-table th,.desk-table td { padding:.45rem .5rem; border-bottom:1px solid #e5e5e5; white-space:nowrap; }
.desk-table .num { text-align:right; font-variant-numeric:tabular-nums; }
.desk-table tr.chosen { background:#ededed; font-weight:700; outline:1px solid #777; outline-offset:-1px; }
.desk-table tr.excluded { color:#686868; }
.register { max-height:600px; overflow:auto; }
.shop-register { border-bottom:1px solid #ddd; padding:.48rem 0; }
.shop-register strong { font-size:.79rem; }
.shop-meta { font-size:.63rem; color:#666; margin:.1rem 0; }
.shop-values { display:grid; grid-template-columns:repeat(3,1fr); gap:.45rem; text-align:right; font-size:.75rem; font-variant-numeric:tabular-nums; }
.shop-values small { display:block; font-size:.59rem; color:#666; }
.suspect { font-size:.62rem; border:1px solid #666; padding:.1rem .2rem; font-weight:700; }
.empty-state { border:1px dashed #bbb; border-radius:7px; padding:2rem 1.4rem; color:#666; font-size:.92rem; }
pre,code { color:#202020 !important; }
@media(max-width:1100px) { .block-container {padding:2.8rem 1rem 1rem;} .metrics {gap:.4rem;} .metric strong {font-size:.9rem;} }
</style>
"""


@dataclass
class Preview:
    response: AgentResponse
    signature: str
    token: str
    accepted_allocator: Allocator | None
    accepted_queues: dict
    today: date
    block_reason: str | None


def load_inputs():
    orders = pd.read_csv(ROOT / "data/orders.csv")
    workshops = load_workshops()
    messages = [line for line in (ROOT / "data/dispatch_requests.txt").read_text(encoding="utf-8").splitlines() if line.startswith("R")]
    return orders, workshops, messages


def projected_queues(queues, anchor, today):
    if today < anchor:
        raise ValueError("Choose a date on or after the current queue snapshot date.")
    elapsed = (today - anchor).days
    return {wid: max(0.0, value - elapsed) for wid, value in queues.items()}


def signature(message, today, config, orders, workshops, queues, revision):
    profiles = {wid: {**asdict(w), "makes": sorted(w.makes)} for wid, w in workshops.items()}
    data = [message, today.isoformat(), asdict(config), orders.to_csv(index=False), profiles, queues, revision]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def make_preview(message, today, config, orders, workshops, queues, allocator, revision=0):
    """Prepare all reviewable evidence and prospective state, without persistence."""
    current_signature = signature(message, today, config, orders, workshops, queues, revision)
    worker = Agent(config)
    worker.allocator = deepcopy(allocator)
    worker.allocator.config = config
    accepted, next_queues = None, dict(queues)
    with tools.trace_calls() as calls:
        response = worker.handle(message, today, orders, workshops, queues)
        parsed, record = response.parsed_request, response.decision_record
        block = None
        if parsed.behaviour not in {"allocate", "refuse"}:
            block = "This request needs a response, not an allocation."
        elif record["chosen_workshop"] is None:
            block = "There is no whole-batch allocation to confirm."
        if any(row.get("current_stage") == "PACKING" for row in record.get("tool_outputs", {}).get("order_options", [])):
            block = "Resolve the packing-stage clarification before allocating."
        complete = all(getattr(parsed, k) is not None for k in ("order_id", "category", "pieces", "due_date"))
        if complete and parsed.behaviour in {"allocate", "refuse"}:
            effective = (ObjectiveConfig(w_cost=1, name="cheapest_on_time") if record["objective_name"] == "cheapest_on_time"
                         else PRESETS[record["objective_name"]])
            accepted = deepcopy(allocator)
            accepted.config = effective
            batch = {"order_id": parsed.order_id, "pieces": parsed.pieces, "category": parsed.category,
                     "due_date": parsed.due_date, "sent_date": today}
            constraints = record["constraints_applied"]
            verified = accepted.decide(batch, workshops, queues, today,
                                      exclude=constraints["exclude"], must_make_date=constraints["must_make_date"])
            if verified.chosen_workshop != record["chosen_workshop"] or verified.candidates != record["candidates"]:
                raise ValueError("The allocation changed during preparation; dispatch again.")
            permitted = {row["workshop_id"]: row for row in record["candidates"]}
            all_rows = tools.candidates(batch, workshops, queues, today)
            state = {"pieces_by_workshop": allocator.pieces_by_workshop, "shock_monitor": accepted.shock_monitor,
                     "workshops": workshops}
            any_on_time = any(row["days_to_spare"] >= 0 for row in record["candidates"])
            for row in all_rows:
                wid = row["workshop_id"]
                row.update(score_terms=score_terms(row, state), score=score_candidate(row, effective, state))
                row["exclusion_reason"] = ("Excluded by request" if wid not in permitted else
                    "Misses required due date" if constraints["must_make_date"] and any_on_time and row["days_to_spare"] < 0 else "")
            record["tool_outputs"]["ui_candidate_inventory"] = sorted(all_rows, key=lambda row: (row["score"], row["total_days"], row["workshop_id"]))
            if verified.chosen_workshop:
                probe = tools.overload_probe(batch, verified.chosen_workshop, workshops, queues)
                next_queues[verified.chosen_workshop] = probe["queue_after"]
            accepted.config = config
        else:
            block = block or "Confirm all order details before allocating."
    response.decision_record["tool_outputs"]["call_trace"] = deepcopy(calls)
    response.faithfulness = faithfulness.check(response.explanation_text, response.decision_record)
    if not response.faithfulness["passed"]:
        block = "The explanation failed its numerical evidence check."
    # Preparing a copy must not present the request as confirmed in the UI/log.
    response.allocation_committed = False
    return Preview(response, current_signature, uuid4().hex, accepted, next_queues, today, block)


def confirm_preview(preview, current_signature, saved, *, append=None):
    """Validate first; append once; caller adopts new state only after success."""
    if preview.token in saved:
        return saved[preview.token]
    if preview.signature != current_signature:
        raise ValueError("Inputs changed. Dispatch again before confirming.")
    if preview.block_reason or preview.accepted_allocator is None:
        raise ValueError(preview.block_reason or "No allocation is available.")
    response = deepcopy(preview.response)
    response.allocation_committed = True
    response.explanation_text = "CONFIRMED ALLOCATION. The dispatcher accepted this recommendation.\n\nOriginal preview:\n" + response.explanation_text
    response.decision_record["constraints_applied"]["confirmation"] = {
        "confirmed": True, "preview_token": preview.token,
        "accepted_lateness": bool(response.already_late or response.awkward_case == "none_makes_date"),
        "accepted_alternative": response.parsed_request.behaviour == "refuse",
    }
    row = (append or records.append)(response)
    saved[preview.token] = row
    return row


def filtered_records(rows, workshop=None, sender=None):
    """Reverse append order, preserving the full persisted audit record."""
    return [row for row in reversed(rows)
            if (not workshop or row.get("decision_record", {}).get("chosen_workshop") == workshop)
            and (not sender or row.get("sender") == sender)]


def html(text):
    st.markdown(text, unsafe_allow_html=True)


def banner(text, kind):
    html(f'<div class="desk-banner {kind}" role="status">{escape(text)}</div>')


def raw_json(value):
    st.code(json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False), language=None, wrap_lines=True)


def table(headers, rows, *, numeric=(), classes=None):
    cells = ''.join(f'<th class="{"num" if i in numeric else ""}">{escape(label)}</th>' for i, label in enumerate(headers))
    body = []
    for index, values in enumerate(rows):
        content = ''.join(f'<td class="{"num" if i in numeric else ""}">{escape(str(value))}</td>' for i, value in enumerate(values))
        body.append(f'<tr class="{classes[index] if classes else ""}">{content}</tr>')
    html(f'<div class="table-wrap"><table class="desk-table"><thead><tr>{cells}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def invalidate():
    st.session_state.pop("desk_preview", None)
    st.session_state.pop("desk_error", None)


def select_message(message):
    st.session_state["desk_message"] = message
    invalidate()


def register_panel(workshops, queues, flags):
    st.subheader("Register")
    st.caption("Current queues: local session projection")
    cards = []
    for wid, w in workshops.items():
        flag = '<span class="suspect">SUSPECT</span>' if wid in flags else ''
        cards.append(f'<div class="shop-register"><strong>{escape(w.name)}</strong> {flag}'
                     f'<div class="shop-meta">{escape(wid)} / {escape(w.status)} / {escape(" + ".join(sorted(w.makes)))}</div>'
                     f'<div class="shop-values"><div><small>Capacity/day</small>{w.capacity:g}</div>'
                     f'<div><small>Queue days</small>{queues[wid]:.2f}</div>'
                     f'<div><small>Batch cap</small>{w.max_batch if w.max_batch is not None else "None"}</div></div></div>')
    html('<div class="register">' + ''.join(cards) + '</div>')


def recommendation(response, workshops):
    record = response.decision_record
    chosen = next((row for row in record["candidates"] if row["workshop_id"] == record["chosen_workshop"]), None)
    if not chosen:
        st.write(response.explanation_text)
        return
    label = "Alternative to the refused workshop" if response.parsed_request.behaviour == "refuse" else "Recommended allocation"
    reason = record["reason_chosen"].split(":", 1)[0] + "."
    values = [("Back by", chosen["eta_date"]), ("Days to spare", str(chosen["days_to_spare"])),
              ("Total cost", f"{chosen['total_cost']:,.2f}"), ("Batch defect", f"{chosen['expected_defect_rate']:.1%}")]
    metrics = ''.join(f'<div class="metric"><small>{escape(label)}</small><strong>{escape(value)}</strong></div>' for label, value in values)
    html(f'<section class="recommendation" aria-label="Recommendation"><div class="eyebrow">{label}</div>'
         f'<div class="shop-title">{escape(chosen["name"])} <span style="font-size:.8rem;font-weight:400">{escape(chosen["workshop_id"])}</span></div>'
         f'<div class="metrics">{metrics}</div><p class="reason">{escape(reason)}</p></section>')


def result_panel(preview, current_signature, workshops):
    response = preview.response
    record = response.decision_record
    text, color = VERDICTS[response.parsed_request.behaviour]
    banner(text, color)
    if preview.signature != current_signature and preview.token not in st.session_state["desk_saved"]:
        banner("INPUTS CHANGED: Dispatch again before confirming", "clarify")
    notices = []
    if response.already_late:
        notices.append("ALREADY LATE: due today or earlier")
    if response.awkward_case == "none_makes_date":
        notices.append("NONE MAKES DATE: confirmation accepts the late ETA")
    elif response.awkward_case == "no_eligible":
        notices.append("NO ELIGIBLE WHOLE-BATCH OPTION: escalate")
    if notices:
        banner(" / ".join(notices), "clarify")
    recommendation(response, workshops)
    if record["objective_name"] != st.session_state["desk_preset"]:
        st.caption("Request preference applied: " + record["objective_name"].replace("_", " "))
    left, right = st.columns([1, 1.2], vertical_alignment="center")
    with left:
        passed = faithfulness.check(response.explanation_text, record)
        html('<span class="mono-badge">Faithfulness: ' + ('PASSED' if passed['passed'] else 'FAILED') + '</span>')
        if not passed["passed"]:
            st.write("Unmatched numbers: " + ", ".join(passed["unmatched"]))
    with right:
        saved = st.session_state["desk_saved"]
        confirmed = preview.token in saved
        if st.button("Confirmed" if confirmed else "Confirm allocation", key="desk_confirm", type="primary", width="stretch",
                     disabled=confirmed or bool(preview.block_reason) or preview.signature != current_signature or not passed["passed"]):
            try:
                confirm_preview(preview, current_signature, saved)
            except (ValueError, OSError) as error:
                st.session_state["desk_error"] = f"Audit could not be saved: {error}"
            else:
                st.session_state["desk_allocator"] = deepcopy(preview.accepted_allocator)
                st.session_state["desk_queues"] = dict(preview.accepted_queues)
                st.session_state["desk_queue_date"] = preview.today
                st.session_state["desk_revision"] += 1
                st.session_state.pop("desk_error", None)
            st.rerun()
    if preview.block_reason:
        st.caption(preview.block_reason)
    elif preview.token not in st.session_state["desk_saved"]:
        st.caption("Preview only. Confirm saves the allocation; no workshop is contacted.")
    if preview.token in st.session_state["desk_saved"]:
        with st.expander("Saved audit entry", expanded=True):
            raw_json(st.session_state["desk_saved"][preview.token])

    st.subheader("Candidates")
    rows = record.get("tool_outputs", {}).get("ui_candidate_inventory", record["candidates"])
    if rows:
        table(["Workshop", "Queue", "Work", "Lead", "ETA", "Spare", "Cost", "Defect", "Score", "Restriction"],
              [[r["name"] + (" / chosen" if r["workshop_id"] == record["chosen_workshop"] else ""),
                f"{r['queue_days']:.2f}", f"{r['processing_days']:.2f}", str(r["lead_days"]), r["eta_date"],
                str(r["days_to_spare"]), f"{r['total_cost']:,.2f}", f"{r['expected_defect_rate']:.1%}", f"{r['score']:.6f}", r.get("exclusion_reason", "")]
               for r in rows], numeric=range(1, 9),
              classes=["chosen" if r["workshop_id"] == record["chosen_workshop"] else "excluded" if r.get("exclusion_reason") else "" for r in rows])
        st.caption("All profile-eligible workshops, ordered by score. Durations in days; costs in simulator units.")
    else:
        st.caption("No ranked candidates until the request can be allocated.")
    with st.expander("Ineligible"):
        rejected = record["ineligible"] or [r for r in record.get("tool_outputs", {}).get("eligibility", []) if not r["eligible"]]
        excluded = [{"workshop": row["name"], "reason": row["reason"]} for row in rejected]
        excluded += [{"workshop": row["name"], "reason": row["exclusion_reason"]} for row in rows if row.get("exclusion_reason")]
        if excluded:
            table(["Workshop", "Exact reason"], [[r["workshop"], r["reason"]] for r in excluded])
        else:
            st.write("No evaluated exclusions for this request.")
    with st.expander("Tool outputs"):
        raw_json({"tool_calls": record.get("tool_outputs", {}).get("call_trace", []),
                  "decision_record": record, "parsed_request": response.parsed_request.to_dict()})
    with st.expander("Full explanation"):
        st.write(response.explanation_text)


def log_page(workshops):
    st.title("Decision log")
    try:
        rows = records.load()
    except (OSError, ValueError) as error:
        banner(str(error), "refuse")
        return
    if not rows:
        st.write("No confirmed allocations yet.")
        return
    left, right = st.columns(2)
    ids = sorted({r.get("decision_record", {}).get("chosen_workshop") for r in rows} - {None})
    senders = sorted({r.get("sender") for r in rows} - {None, ""})
    with left:
        workshop = st.selectbox("Workshop", [None, *ids], key="desk_log_workshop",
                               format_func=lambda wid: "All workshops" if wid is None else f"{wid} / {workshops[wid].name}" if wid in workshops else wid)
    with right:
        sender = st.selectbox("Sender", [None, *senders], key="desk_log_sender", format_func=lambda v: v or "All senders")
    selected = filtered_records(rows, workshop, sender)
    st.caption(f"{len(selected)} audit entries / newest first")
    for index, row in enumerate(selected):
        decision = row.get("decision_record", {})
        wid = decision.get("chosen_workshop")
        name = workshops[wid].name if wid in workshops else wid or "No allocation"
        label = f"{row.get('timestamp', '')} / {row.get('sender') or 'Unknown sender'} / {decision.get('order_id', '')} / {name}"
        with st.expander(label, expanded=index == 0):
            st.write(row.get("explanation_text", ""))
            raw_json(row)


def main():
    st.set_page_config(page_title="Track 2 Dispatch", layout="wide", initial_sidebar_state="expanded")
    html(CSS)
    try:
        orders, workshops, messages = load_inputs()
    except (OSError, ValueError) as error:
        banner(f"Could not load the register: {error}", "refuse")
        return
    state = st.session_state
    if "desk_allocator" not in state:
        state.update(desk_allocator=Allocator(PRESETS["lateness"]), desk_queues={wid: w.queue0 for wid, w in workshops.items()},
                     desk_queue_date=TODAY, desk_revision=0, desk_saved={}, desk_message="", desk_preset="lateness", desk_today=TODAY)
    # Streamlit removes widget keys while the log page hides those widgets.
    # Restore them from a non-widget snapshot when returning to the desk.
    for key, value in state.get("desk_controls", {}).items():
        if key not in state:
            state[key] = value
    with st.sidebar:
        st.radio("Workspace", ["Dispatch", "Decision log"], key="desk_page")
        st.caption("Track 2 / subcontractor desk")
    if state["desk_page"] == "Decision log":
        log_page(workshops)
        return
    title, today_col, objective_col, weights_col = st.columns([1.05, .9, 1.5, 2.3], vertical_alignment="center")
    with title:
        st.title("Dispatch desk")
    with today_col:
        today = st.date_input("Today", key="desk_today", min_value=state["desk_queue_date"], on_change=invalidate)
    with objective_col:
        preset = st.selectbox("Objective", list(PRESETS), key="desk_preset", on_change=invalidate,
                              format_func=lambda value: value.replace("_", " ").capitalize())
    config = PRESETS[preset]
    with weights_col:
        html('<div class="weights" aria-label="Read-only objective weights">' + ''.join(
            f'<div><small>{label}</small><strong>{getattr(config, "w_" + name):g}</strong></div>'
            for name, label in (("lateness", "Lateness"), ("defect", "Defect"), ("fairness", "Fairness"), ("robustness", "Robustness"), ("cost", "Cost"))) + '</div>')
    queues = projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    left, center, right = st.columns([1.08, 3, 1.08], gap="medium")
    with left:
        st.subheader("Inbox")
        st.text_area("Request", key="desk_message", height=142, placeholder="Select an inbox request or type a new one.", on_change=invalidate)
        dispatch_col, new_col = st.columns([1.2, 1])
        with dispatch_col:
            dispatch = st.button("Dispatch", type="primary", width="stretch", disabled=not state["desk_message"].strip())
        with new_col:
            st.button("New", help="Clear the editor for a new request", width="stretch", on_click=select_message, args=("",))
        st.caption(f"{len(messages)} requests / select to load")
        with st.container(height=360, key="inbox_list", border=False):
            for message in messages:
                rid = message.split()[0]
                speaker_body = message.split("]", 1)[1].strip()
                short = speaker_body[:72] + ("…" if len(speaker_body) > 72 else "")
                st.button(f"{rid} / {short}", key="inbox_" + rid, help=message, width="stretch", on_click=select_message, args=(message,))
    state["desk_controls"] = {key: state[key] for key in ("desk_today", "desk_preset", "desk_message")}
    current_signature = signature(state["desk_message"], today, config, orders, workshops, queues, state["desk_revision"])
    with center:
        st.subheader("Decision")
        if dispatch:
            invalidate()
            try:
                with st.spinner("Checking request and workshop options"):
                    state["desk_preview"] = make_preview(state["desk_message"], today, config, orders, workshops, queues, state["desk_allocator"], state["desk_revision"])
            except Exception as error:
                # Show actionable local errors, without echoing provider request headers.
                from intake import IntakeError
                state["desk_error"] = str(error) if isinstance(error, (IntakeError, ValueError)) else f"Request could not be processed ({type(error).__name__}). Check the API connection and try Dispatch again."
        if state.get("desk_error"):
            banner(state["desk_error"], "refuse")
        preview = state.get("desk_preview")
        if preview:
            result_panel(preview, current_signature, workshops)
        elif not state.get("desk_error"):
            html('<div class="empty-state">Select a request, then Dispatch.<br><br>The recommendation, return date and reason will appear here.</div>')
    with right:
        flags = set(state["desk_allocator"].shock_monitor.flags)
        if state.get("desk_preview"):
            flags.update(f["workshop_id"] for f in state["desk_preview"].response.decision_record["shock_flags"])
        register_panel(workshops, queues, flags)


if __name__ == "__main__":
    main()
