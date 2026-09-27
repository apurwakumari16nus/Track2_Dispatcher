"""Streamlit dispatch desk. Run: streamlit run src/app.py

Dispatch is a preview. Only the explicit confirmation callback writes an audit
row and commits local history/queues. This app does not contact a workshop.
Queue figures are nominal local-session projections from the CSV snapshot.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date, timedelta
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

CSS = "<style>" + (ROOT / "src" / "desk.css").read_text(encoding="utf-8") + "</style>"


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
    st.caption("Starting queues: workshops.csv, 1 April 2026. Current values include this session’s confirmed work and elapsed days.")
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
    parsed = response.parsed_request
    details = [parsed.order_id, parsed.customer, f"{parsed.pieces:,} pieces" if parsed.pieces else None,
               f"Due {parsed.due_date}" if parsed.due_date else None]
    html('<div class="request-facts">' + ' · '.join(escape(str(v)) for v in details if v) + '</div>')
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

    st.subheader("Compare workshops")
    rows = record.get("tool_outputs", {}).get("ui_candidate_inventory", record["candidates"])
    if rows:
        table(["Workshop", "Return date", "Days to spare", "Cost", "Defect", "Score", "Restriction"],
              [[r["name"] + (" / chosen" if r["workshop_id"] == record["chosen_workshop"] else ""),
                r["eta_date"],
                str(r["days_to_spare"]), f"{r['total_cost']:,.2f}", f"{r['expected_defect_rate']:.1%}", f"{r['score']:.6f}", r.get("exclusion_reason", "")]
               for r in rows], numeric=range(1, 6),
              classes=["chosen" if r["workshop_id"] == record["chosen_workshop"] else "excluded" if r.get("exclusion_reason") else "" for r in rows])
        st.caption("All profile-eligible workshops, ordered by score. Durations in days; costs in simulator units.")
    else:
        st.caption("No ranked candidates until the request can be allocated.")
    with st.expander("Delivery breakdown", expanded=False):
        if rows:
            table(["Workshop", "Queue days", "Processing days", "Transport days", "Total days", "Return date"],
                  [[r["name"], f"{r['queue_days']:.2f}", f"{r['processing_days']:.2f}",
                    str(r["lead_days"]), f"{r['total_days']:.2f}", r["eta_date"]] for r in rows], numeric=range(1, 5))
            st.caption("Return date follows the simulator's rounded total duration. These are estimates, not guarantees.")
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
    st.caption("Accepted allocations, their reasoning, and the people behind each constraint.")
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


def workshop_page(workshops, state):
    """Queryable register backed by the same eligibility and ETA tools as dispatch."""
    html('<div class="page-kicker">OPERATIONS / WORKSHOP REGISTER</div>')
    st.title("Find capacity, with confidence.")
    st.caption("Check what each workshop can make, whether it can accept your batch, and when it could return.")
    c1, c2, c3 = st.columns(3)
    with c1:
        category = st.selectbox("Product category", ["TOPS", "ACCESSORIES"])
    with c2:
        pieces = st.number_input("Batch size (pieces)", min_value=1, max_value=1000000, value=1500, step=100)
    with c3:
        due = st.date_input("Required return date", value=max(TODAY, state["desk_today"]) + timedelta(days=7), min_value=state["desk_queue_date"])
    today = max(state["desk_today"], state["desk_queue_date"])
    queues = projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    batch = {"category": category, "pieces": pieces, "due_date": due}
    checks = {r["workshop_id"]: r for r in tools.check_eligibility(batch, workshops)}
    st.caption(f"Estimates from {today:%d %b %Y}. Queue + processing + transport; these checks do not allocate work.")
    cols = st.columns(2, gap="medium")
    for index, (wid, w) in enumerate(workshops.items()):
        check = checks[wid]
        with cols[index % 2]:
            with st.container(border=True):
                tag = "Eligible" if check["eligible"] else check["reason"]
                html(f'<div class="workshop-heading"><span>{escape(wid)}</span><span class="eligibility {"eligible" if check["eligible"] else ""}">{escape(tag)}</span></div>'
                     f'<h3>{escape(w.name)}</h3><p class="workshop-categories">{escape(" / ".join(sorted(w.makes)))}</p>')
                a, b, c = st.columns(3)
                a.metric("Capacity / day", f"{w.capacity:,.0f}")
                b.metric("Queue days", f"{queues[wid]:.1f}")
                c.metric("Batch limit", f"{w.max_batch:,}" if w.max_batch else "No cap")
                if check["eligible"]:
                    eta = tools.estimate_eta(batch, wid, workshops, queues, today)
                    cost = tools.estimate_cost(batch, wid, workshops)
                    margin = eta["days_to_spare"]
                    timing = f"{margin} days to spare" if margin >= 0 else f"{abs(margin)} days late"
                    html(f'<div class="delivery-outcome {"on-time" if margin >= 0 else "late"}">Return {eta["eta_date"]} · {timing}</div>')
                    st.caption(f"Cost {cost['total_cost']:,.2f} simulator units · Defect exposure {w.defect_rate:.1%}")
                else:
                    st.caption("Not available for this batch. Adjust the category or quantity to explore alternatives.")


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
        html('<div class="brand"><span class="brand-mark">t2</span><div>Threadline<small>SUBCONTRACTING DESK</small></div></div>')
        st.radio("Workspace", ["Simulation", "Dispatch", "Workshop register", "Decision log"], key="desk_page", label_visibility="collapsed")
        st.divider()
        html('<div class="sidebar-note"><strong>Automatic decisions. Visible evidence.</strong><p>Simulation evaluates scheduling. Dispatch demonstrates language intake and auditable recommendations.</p></div>')
        st.caption("Track 2 · Quick-response subcontracting")
    if state["desk_page"] == "Simulation":
        from simulation_dashboard import dashboard
        dashboard(workshops)
        return
    if state["desk_page"] == "Decision log":
        log_page(workshops)
        return
    if state["desk_page"] == "Workshop register":
        workshop_page(workshops, state)
        return
    html('<div class="page-kicker">OPERATIONS / DISPATCH</div>')
    st.title("Dispatch desk")
    st.caption("The right workshop. A realistic return date. A decision you can explain.")
    today_col, objective_col, weights_col = st.columns([1, 1.5, 2.5], vertical_alignment="center")
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
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    html(f'<div class="workspace-summary"><span><strong>{len(messages)}</strong> inbox requests</span>'
         f'<span><strong>{active} / {len(workshops)}</strong> active workshops</span>'
         f'<span><strong>{len(state["desk_saved"])}</strong> confirmed this session</span>'
         '<span class="summary-note">Queues are session projections</span></div>')
    left, center = st.columns([1, 2.35], gap="large")
    with left:
        st.subheader("Inbox")
        query = st.text_input("Search inbox", placeholder="Search sender, order, or request…", key="inbox_search", label_visibility="collapsed")
        filtered = [m for m in messages if query.casefold() in m.casefold()]
        st.caption(f"{len(filtered)} requests · select to review")
        with st.container(height=590, key="inbox_list", border=False):
            for message in filtered:
                rid = message.split()[0]
                speaker_body = message.split("]", 1)[1].strip()
                short = speaker_body[:112] + ("…" if len(speaker_body) > 112 else "")
                st.button(f"{rid} · {short}", key="inbox_" + rid, width="stretch",
                          type="primary" if state["desk_message"] == message else "secondary",
                          on_click=select_message, args=(message,))
            if not filtered:
                st.info("No requests match this search.")
    with center:
        with st.container(border=True, key="request_composer"):
            html('<div class="section-label">01 <span>Request intake</span></div>')
            st.text_area("Request", key="desk_message", height=120, placeholder="Select a request from the inbox, or describe the order you need to send out.", on_change=invalidate)
            dispatch_col, new_col, note_col = st.columns([1.2, .7, 2], vertical_alignment="center")
            with dispatch_col:
                dispatch = st.button("Dispatch", type="primary", width="stretch", disabled=not state["desk_message"].strip())
            with new_col:
                st.button("New", help="Clear the editor for a new request", width="stretch", on_click=select_message, args=("",))
            with note_col:
                st.caption("Dispatch prepares a preview. You confirm the allocation.")
        state["desk_controls"] = {key: state[key] for key in ("desk_today", "desk_preset", "desk_message")}
        current_signature = signature(state["desk_message"], today, config, orders, workshops, queues, state["desk_revision"])
        html('<div class="section-label">02 <span>Review the decision</span></div>')
        if dispatch:
            invalidate()
            try:
                with st.status("Checking request and workshop options", expanded=True) as status:
                    st.write("Extracting order details, checking restrictions, and estimating each eligible workshop.")
                    state["desk_preview"] = make_preview(state["desk_message"], today, config, orders, workshops, queues, state["desk_allocator"], state["desk_revision"])
                    status.update(label="Request checked", state="complete", expanded=False)
            except Exception as error:
                from intake import IntakeError
                state["desk_error"] = str(error) if isinstance(error, (IntakeError, ValueError)) else f"Request could not be processed ({type(error).__name__}). Check the API connection and try Dispatch again."
        if state.get("desk_error"):
            banner(state["desk_error"], "refuse")
        preview = state.get("desk_preview")
        if preview:
            result_panel(preview, current_signature, workshops)
        elif not state.get("desk_error"):
            html('<div class="empty-state"><div class="empty-symbol">↗</div><h2>From request to ready.</h2>'
                 '<p>Select a message and dispatch it to compare workshops, see return dates, and review the recommendation.</p>'
                 '<div class="empty-steps"><span>01 &nbsp; Check request</span><span>02 &nbsp; Compare options</span><span>03 &nbsp; Confirm & record</span></div></div>')
            st.caption("First time here? Try R09 for an allocation, R01 for clarification, or R08 for an ineligible workshop.")
        with st.expander("Workshop queue snapshot"):
            flags = set(state["desk_allocator"].shock_monitor.flags)
            if preview:
                flags.update(f["workshop_id"] for f in preview.response.decision_record["shock_flags"])
            register_panel(workshops, queues, flags)


if __name__ == "__main__":
    main()
