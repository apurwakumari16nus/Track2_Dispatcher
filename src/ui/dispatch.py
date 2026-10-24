"""Dispatch: one request, one recommendation, one human decision.

Rendering only. Extraction runs through intake.extraction_source; everything
after the raw reply is the unchanged agent/allocator/tools/faithfulness path in
desk.make_preview. The page answers five questions in order: which request,
what to do next, which workshop, why, and what confirming does. Everything else
(what the model extracted, what Python checked, every workshop, the technical
trace and timings) is one click away, never on screen by default.

Every evaluation runs inside tracing.trace(); the trace is saved to
records/traces.jsonl whether the request succeeds or fails, and is shown as a
timing bar under the progress strip.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re

import streamlit as st

import desk
import intake
from objectives import PRESETS
import rehearsal
import tools
import tracing
from ui import explain, guide
from ui.components import (banner, esc, html, icon, json_block, loom_art, process_strip, score_bars, section, state_line,
                           status_pill, table, thread_link, weight_bars)
from ui.state import bind, one_of, text

STATUS_WORDS = {"allocate": "Reviewed", "clarify": "Needs reply", "refuse": "Reviewed", "decline": "Cannot answer"}
DATA_NEEDED = {
    "allocation_history": "Historical dispatch records linking customers and orders to workshops.",
    "customer_quote": "Customer sales quotations or pricing records.",
    "worker_names": "A worker roster and worker-to-order assignments.",
}
# Plain-language names for the deterministic intake checks (intake._post_checks).
RULES = {"order_id_exists": "Order number exists in the order book", "resolve_order": "Order identified from customer and product",
         "question_data": "Request asks for an allocation", "order_fields": "Customer, product and quantity read from the order book",
         "due_date": "Due date is a confirmed calendar date", "already_late": "Due date is still ahead",
         "packing": "Order is not already in packing", "suggested_eligibility": "A named workshop can take the batch",
         "pieces_consistency": "Quantity matches the order book", "required_fields": "Every field needed to allocate is present"}
RESULT_WORDS = {"passed": "Passed", "not_needed": "Not needed", "not_given": "Not stated in the message", "resolved": "Resolved",
                "ambiguous": "Ambiguous", "no_matches": "No match", "allocation_request": "Yes", "information_only": "Information question only",
                "unavailable": "Data not held", "filled_from_csv": "Filled from orders.csv", "unconfirmed": "Changed date not confirmed",
                "unresolved": "Missing or unclear", "flagged": "Already due or late", "not_flagged": "Yes", "needs_confirmation": "In packing",
                "not_in_packing": "Yes", "no_resolved_order": "No order yet", "eligible": "Eligible", "ineligible": "Not eligible",
                "not_suggested": "None named", "mismatch_noted": "Differs; the message quantity is used", "no_mismatch": "Yes",
                "missing": "Missing", "checked": "Yes", "failed": "Failed"}
FILTERS = {"all": "All", "pending": "Pending", "reviewed": "Reviewed"}
OUTCOME_TONES = {"Confirmed": "conf", "Needs reply": "warn", "Cannot answer": "muted", "Reviewed": "info"}
AVATAR_TONES = ["#123A66", "#1F4E86", "#2A77E8", "#0E6B8C", "#3B4F7A"]
BRAND = "app/static/brand"
WORKSHOP_PHOTOS = Path(__file__).resolve().parents[1] / "static" / "brand" / "workshops"
HOME_STEPS = [("understand", "Understand", "Read the request"),
              ("validate", "Validate", "Check order and rules"),
              ("evaluate", "Evaluate", "Compare workshops"),
              ("decide", "Decide", "Choose and verify"),
              ("confirm", "Confirm", "You approve")]


# State helpers -----------------------------------------------------------------

def invalidate():
    for key in ("desk_preview", "desk_error", "desk_whynot", "desk_confirm_error", "desk_exec"):
        st.session_state.pop(key, None)


def select_message(message):
    st.session_state["desk_message"] = message
    invalidate()


def append_reply(text_value=None):
    reply = (text_value or st.session_state.get("desk_reply", "")).strip()
    if reply:
        st.session_state["desk_message"] = st.session_state["desk_message"].rstrip() + f" Reply from dispatcher: {reply}"
        st.session_state["desk_reply"] = ""
        invalidate()
        request_evaluation()   # The dispatcher answered: read the request again now, no second click.


def use_rehearsal():
    st.session_state["desk_source"] = "fixture"
    invalidate()


def open_audit():
    """Show the saved record: the right log, with the record opened (Audit reads audit_focus)."""
    state = st.session_state
    preview = state.get("desk_preview")
    row = state["desk_saved"].get(preview.token) if preview else None
    if row:
        confirmation = row.get("decision_record", {}).get("constraints_applied", {}).get("confirmation", {})
        state["audit_view"] = "decisions"
        state["audit_log"] = desk.audit_log_name(preview.source, demo=bool(confirmation.get("guided_demo")))
        state["audit_focus"] = row.get("timestamp")
    state["desk_page"] = "Audit Trail"


def request_evaluation():
    st.session_state["desk_run"] = True


def envelope(message: str) -> tuple[str, str, str, str]:
    """(request id, time, sender, body) from an inbox line; blanks for free text."""
    try:
        head, body = message.split("]", 1)
        rid, time = head.split("[", 1)
        sender, body_text = body.split(":", 1)
        return rid.strip(), time.strip(), sender.strip(), body_text.strip()
    except ValueError:
        return "", "", "", message.strip()


def order_on_file(message: str, orders):
    """Deterministic lookup of an order ID written in the message. No model involved."""
    match = re.search(r"\bORD-\d+\b", message, re.I)
    if not match:
        return None
    rows = orders[orders["order_id"].str.upper() == match.group(0).upper()]
    return rows.iloc[0] if len(rows) else None


def live_stages(active: str):
    keys = [key for key, _, _ in HOME_STEPS]
    index = keys.index(active)
    return [(key, label, sub, "done" if i < index else "active" if i == index else "idle")
            for i, (key, label, sub) in enumerate(HOME_STEPS)]


def home_stages(stages=None, confirm: str = "idle"):
    """Steps from the recorded trace. Verification folds into Decide; Confirm is the human step."""
    by = {key: status for key, _, _, status in (stages or [])}
    decide = "blocked" if "blocked" in (by.get("decide"), by.get("verify")) else by.get("decide", "idle")
    status = {**{key: by.get(key, "idle") for key in ("understand", "validate", "evaluate")}, "decide": decide, "confirm": confirm}
    return [(key, label, sub, status[key]) for key, label, sub in HOME_STEPS]


def plural(product: str) -> str:
    word = product.lower()
    return word[:-1] + "ves" if word.endswith("f") else word if word.endswith("s") else word + "s"


# Page ---------------------------------------------------------------------------

def render(orders, workshops, messages):
    state = st.session_state
    today, preset = header(workshops)
    config = PRESETS[preset]
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    inbox_col, work_col = st.columns([1, 2.6], gap="medium")
    with work_col:  # Drawn first so the inbox shows this run's outcome label.
        workspace(orders, workshops, today, config, queues)
    with inbox_col:
        inbox(messages)


def header(workshops):
    """Page title on the left; the two settings that change a decision, and system status, on the right."""
    state = st.session_state
    with st.container(key="topbar"):
        title, date_col, objective_col, ready_col = st.columns([2.6, .95, 1.25, 1.05], vertical_alignment="bottom")
        with title:
            html('<div class="kicker"><span>Dispatch</span></div>'
                 '<div class="home-title">Turn requests into confident workshop decisions</div>'
                 '<div class="home-sub">The model reads each request. Python checks the data, ranks every workshop and recommends one. You confirm.</div>')
        with date_col:
            today = bind(st.date_input, "Scenario date", key="desk_today", fallback=state["desk_queue_date"],
                         accept=lambda v: isinstance(v, date) and v >= state["desk_queue_date"],
                         min_value=state["desk_queue_date"], on_change=invalidate, format="DD/MM/YYYY")
        with objective_col:
            preset = bind(st.selectbox, "Objective", list(PRESETS), key="desk_preset", fallback="lateness", on_change=invalidate,
                          format_func=explain.objective_label)
        with ready_col, st.container(key="ready"):
            system_ready(workshops)
    return today, preset


def system_ready(workshops):
    state = st.session_state
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    source = rehearsal.SOURCES[state["desk_source"]]
    live = rehearsal.live_status()
    word = "Rehearsal" if source.rehearsal else "Live model" if live["ready"] else "Not configured"
    with st.popover(word, icon=":material/check_circle:" if (source.rehearsal or live["ready"]) else ":material/error:", width="stretch"):
        language = ("Rehearsal, " + ("recorded model replies" if source.key == "cached" else "test fixtures, not model output") if source.rehearsal
                    else f"Live model, {live['model']}" if live["ready"] else "Not configured")
        rows = [("Request reading", language), ("Allocation engine", "Python, always live"),
                ("Workshops", f"{len(workshops)} on the register, {active} active"),
                ("Queues", f"As of {explain.long_date(state['desk_queue_date'])}"),
                ("Confirmed this session", str(len(state["desk_saved"])))]
        html('<dl class="kv" style="grid-template-columns:11.3333rem 1fr;font-size:0.9667rem">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")


def inbox(messages):
    state = st.session_state
    outcomes = state.get("desk_outcomes", {})
    with st.container(key="inbox"):
        html(f'<div class="inbox-head"><div class="title">Inbox</div><div class="meta">{len(messages)} requests</div></div>')
        query = bind(st.text_input, "Search requests", key="inbox_search", fallback="", accept=text,
                     placeholder="Search name, order or text", label_visibility="collapsed", icon=":material/search:")
        rows = [(m, *envelope(m)) for m in messages if query.casefold() in m.casefold()]
        counts = {"all": len(rows), "pending": sum(r[1] not in outcomes for r in rows), "reviewed": sum(r[1] in outcomes for r in rows)}
        pick = bind(st.segmented_control, "Filter requests", list(FILTERS), key="inbox_filter", fallback="all", required=True,
                    format_func=lambda k: f"{FILTERS[k]}  {counts[k]}", label_visibility="collapsed")
        shown = [r for r in rows if pick == "all" or (pick == "pending") == (r[1] not in outcomes)]
        with st.container(height=640, key="inbox_list", border=False):
            for message, rid, time, sender, body in shown:
                word = outcomes.get(rid)
                pill = status_pill(word, OUTCOME_TONES.get(word, "info")) if word else ""
                tone = AVATAR_TONES[sum(map(ord, sender)) % len(AVATAR_TONES)]
                with st.container(key=f"inb_{rid}"):
                    html(f'<div class="inb{" sel" if state["desk_message"] == message else ""}">'
                         f'<div class="inb-av" style="background:{tone}">{esc(sender[:1])}</div><div class="inb-main">'
                         f'<div class="inb-top"><b>{esc(sender)}</b><span>{esc(rid)} · {esc(time)}</span></div>'
                         f'<div class="inb-body">{esc(body)}</div>{pill}</div></div>')
                    st.button(f"Open request {rid} from {sender}", key="inbox_" + rid, width="stretch",
                              on_click=select_message, args=(message,))
            if not shown:
                html('<div class="meta" style="padding:0.8rem 0.2667rem">No request matches. Clear the search or the filter.</div>')


def workspace(orders, workshops, today, config, queues):
    state = st.session_state
    message = state["desk_message"]
    scenario = state.get("guide_scenario")
    if scenario and not message.startswith(scenario["rid"] + " "):
        state.pop("guide_scenario")   # The dispatcher moved on to another request.
    elif scenario:
        html(banner(f"Scenario {scenario['rid']}.", f" {scenario['hint']} This is a rehearsal case from the library, not a new request.", "info"))
    run = request_surface(message, orders)
    current_signature = desk.signature(message, today, config, orders, workshops, queues, state["desk_revision"], state["desk_source"])
    progress = st.empty()
    progress.markdown(process_strip(home_stages()), unsafe_allow_html=True)
    timing_slot = st.container()
    body = st.container()
    if (run or state.pop("desk_run", False)) and message.strip():
        evaluate(progress, orders, workshops, today, config, queues)
    if state.get("desk_exec"):
        with timing_slot:
            timing(state["desk_exec"], workshops)
    preview = state.get("desk_preview")
    with body:
        if state.get("desk_error"):
            error_card(state["desk_error"])
        elif preview:
            result(preview, current_signature, workshops, orders, queues, progress)
        elif not message.strip():
            html('<div class="home-empty"><div class="he-copy"><div class="he-k">Ready when you are</div><div class="say">Select a request to begin.</div>'
                 '<p>Choose a message from the inbox or type one. Python verifies it and ranks the eligible workshops; you approve the final decision.</p>'
                 '<ol class="he-steps"><li><i>1</i><div><b>Read the request</b><span>Order, pieces, due date and preference, checked against the order book.</span></div></li>'
                 '<li><i>2</i><div><b>Rank the workshops</b><span>Eligibility, queue, return date and cost for each of the eight.</span></div></li>'
                 '<li><i>3</i><div><b>Confirm it yourself</b><span>Nothing is assigned or sent until you confirm.</span></div></li></ol></div>'
                 f'<div class="he-art">{loom_art()}</div></div>')


def request_surface(message, orders) -> bool:
    """The request being handled: who, what, the order on file, and one primary action."""
    rid, time, sender, body = envelope(message)
    on_file = order_on_file(message, orders)
    outcome = st.session_state.get("desk_outcomes", {}).get(rid)
    with st.container(key="request"):
        if rid:
            pill = status_pill(outcome, OUTCOME_TONES.get(outcome, "info")) if outcome else ""
            html(f'<div class="msg-head req-sel"><div class="avatar">{esc(sender[:1])}</div><div><b>{esc(sender)}</b><br>'
                 f'<span>{esc(time)}, request <span class="id">{esc(rid)}</span></span></div>{pill}</div>'
                 f'<div class="msg-text">{esc(body)}</div>')
            if on_file is not None:
                facts = [("Order", on_file["order_id"]), ("Customer", on_file["customer"]),
                         ("Batch", f'{int(on_file["pieces"]):,} {plural(str(on_file["product"]))}'),
                         ("Due", explain.long_date(str(on_file["due_date"]))), ("Stage", str(on_file["current_stage"]).capitalize())]
                html('<div class="req-facts">' + "".join(f'<span><small>{esc(k)}</small><b>{esc(v)}</b></span>' for k, v in facts)
                     + '<em>From orders.csv</em></div>')
        else:
            html('<div class="msg-head"><div class="avatar">+</div><div><b>New request</b><br>'
                 '<span>Type or paste the chat message</span></div></div>')
            bind(st.text_area, "Request", key="desk_message", fallback="", accept=text, height=96, label_visibility="collapsed",
                 on_change=invalidate, placeholder="For example: ORD-045, 150 vests for Cotton Club, due Apr 09. Fastest turnaround please.")
        run_col, edit_col, new_col = st.columns([1.15, 1.25, 1], vertical_alignment="center")
        with run_col:
            run = st.button("Evaluate request", key="desk_dispatch", type="primary", width="stretch",
                            icon=":material/bolt:", disabled=not message.strip())
        with edit_col:
            if rid:
                with st.popover("Edit the text", icon=":material/edit:", width="stretch"):
                    bind(st.text_area, "Request", key="desk_message", fallback="", accept=text, height=120, slot="edit",
                         label_visibility="collapsed", on_change=invalidate)
        with new_col:
            st.button("New request", key="desk_new", width="stretch", icon=":material/add:", on_click=select_message, args=("",))
    return run


def evaluate(progress, orders, workshops, today, config, queues):
    """Run one evaluation inside a trace. The trace is saved on success and on failure."""
    state = st.session_state
    invalidate()
    progress.markdown(process_strip(live_stages("understand"), live=True), unsafe_allow_html=True)

    def reply_arrived():
        progress.markdown(process_strip(live_stages("validate"), live=True), unsafe_allow_html=True)

    source = state["desk_source"]
    status = rehearsal.live_status()
    message = state["desk_message"]
    meta = {"kind": "evaluation", "source": source, "request_id": envelope(message)[0] or None,
            "message_sha": tracing.message_digest(message), "objective": config.name, "scenario_date": today.isoformat(),
            "provider": status["provider"] if source == "live" else None,
            "requested_model": status["model"] if source == "live" else None, "guided_demo": guide.active()}
    call = rehearsal.make_source(source, on_reply=reply_arrived)
    run = None
    try:
        with tracing.trace(**meta) as run, intake.extraction_source(call):
            preview = desk.make_preview(message, today, config, orders, workshops, queues,
                                        state["desk_allocator"], state["desk_revision"], source)
    except Exception as error:
        state["desk_error"] = describe_error(error)
        progress.markdown(process_strip(home_stages()), unsafe_allow_html=True)
        preview = None
    finally:
        if run is not None:
            row = run.to_dict()
            try:
                tracing.save(row)
            except OSError:
                row["meta"]["not_saved"] = True   # Diagnostics never block the dispatcher.
            state["desk_exec"] = row
    if preview is None:
        return
    state["desk_preview"] = preview
    rid = envelope(message)[0]
    if rid:
        state.setdefault("desk_outcomes", {})[rid] = STATUS_WORDS[preview.response.parsed_request.behaviour]


def describe_error(error) -> dict:
    """A named failure class, what it means, and what the dispatcher can do. Never a bare 'something went wrong'."""
    category = getattr(error, "category", None)
    if isinstance(error, intake.IntakeError) and category in intake.ERROR_CATEGORIES:
        title, action, retry = intake.ERROR_CATEGORIES[category]
        detail = str(error) if str(error) != title else ""
        return {"kind": category, "title": title, "action": action, "retry": retry, "detail": detail}
    if isinstance(error, ValueError):
        return {"kind": "engine", "title": "The decision engine stopped this request", "action": "Nothing was allocated. Evaluate again; "
                "if it repeats, handle the request manually.", "retry": True, "detail": str(error)}
    return {"kind": "system", "title": "Unexpected system error", "action": "Nothing was allocated. Try again; the execution trace "
            "records the failure for diagnosis.", "retry": True, "detail": type(error).__name__}


def error_card(error):
    state = st.session_state
    with st.container(key="desk_failure"):
        html(state_line("block" if error.get("kind") in {"auth", "bad_request", "system", "engine", "refusal"} else "warn",
                        error.get("title", "Request not processed"), error.get("action", "")))
        if error.get("detail"):
            html(f'<div class="meta" style="margin-top:0.4rem">{esc(error["detail"])}</div>')
        html('<div class="meta" style="margin-top:0.4rem">Nothing was allocated and nothing was written to the audit log.</div>')
        cols = st.columns([1, 1, 2])
        with cols[0]:
            if error.get("retry"):
                st.button("Try again", key="desk_retry", icon=":material/refresh:", on_click=request_evaluation, width="stretch")
        with cols[1]:
            if error.get("kind") in {"unconfigured", "auth", "bad_request", "provider_unavailable", "connection"} and state["desk_source"] == "live":
                st.button("Use rehearsal mode", key="desk_use_rehearsal", on_click=use_rehearsal, width="stretch")


# Result -------------------------------------------------------------------------

def result(preview, current_signature, workshops, orders, queues, progress):
    state = st.session_state
    response, record, parsed = preview.response, preview.response.decision_record, preview.response.parsed_request
    status = desk.confirm_state(preview, current_signature, state["desk_saved"])
    steps = explain.trace_steps(response.to_dict(), agent_calls=preview.agent_calls, replayed=preview.accepted_allocator is not None,
                                confirmed=status.state == "confirmed", block_reason=preview.block_reason)
    chosen = explain.chosen_row(record)
    confirm_step = ("skipped" if chosen is None else "done" if status.state == "confirmed" else "active" if status.ready
                    else "blocked" if status.state == "blocked" else "idle")
    progress.markdown(process_strip(home_stages(explain.stage_status(steps), confirm_step)), unsafe_allow_html=True)
    if status.state == "stale":
        html(banner("Inputs changed", " The request, date, objective or queue changed after this evaluation. Evaluate again before confirming.", "warn"))
    if response.already_late:
        html(banner("Already late", f" The due date, {explain.long_date(parsed.due_date)}, is on or before the scenario date, "
                    f"{explain.long_date(preview.today)}. Any return will be late.", "risk"))
    if parsed.behaviour == "refuse":
        rejected = next((r for r in record.get("tool_outputs", {}).get("eligibility", [])
                         if r["workshop_id"] == parsed.suggested_workshop and not r["eligible"]), None)
        if rejected:
            html(banner(f"{rejected['name']} cannot accept this batch.", f" {explain.reason_text(rejected['reason'])}"
                        + (" The best permitted alternative is recommended below." if chosen else ""), "risk"))
    if record.get("awkward_case") == "none_makes_date" and chosen:
        html(banner(f"No eligible workshop can meet {explain.short_date(parsed.due_date)}.",
                    f" Earliest achievable: {explain.short_date(chosen['eta_date'])} at {chosen['name']}. You decide what happens next.", "warn"))
    if chosen is not None:
        done = status.state == "confirmed"
        html(thread_link(f"Confirmed by you for {parsed.order_id or 'this request'}" if done else
                         f"Engine recommendation for {parsed.order_id or 'this request'}, waiting for you", confirmed=done))
        recommendation(preview, chosen, record, parsed, workshops, status)
        if record.get("awkward_case") == "none_makes_date" or record.get("tool_outputs", {}).get("split"):
            options_card(preview, record, parsed, workshops, queues)
    elif parsed.behaviour == "clarify":
        clarify_card(parsed, record, workshops, orders)
    elif parsed.behaviour == "decline":
        decline_card(parsed, orders, workshops)
    else:
        with st.container(key="desk_noeligible"):
            html(state_line("block", "No eligible workshop remains",
                            "Every workshop is excluded or cannot take this batch. Leave it unconfirmed and escalate."))
    details(preview, record, parsed, workshops, chosen)


def trace_on_network(parsed):
    """Open Workshop Network with this batch prefilled; the page replays the routing once."""
    state = st.session_state
    rid = envelope(state["desk_message"])[0]
    state["net_handoff"] = {"category": parsed.category, "pieces": int(parsed.pieces),
                            "due": date.fromisoformat(str(parsed.due_date)),
                            "label": " ".join(x for x in (f"request {rid}" if rid else "", parsed.order_id or "") if x)}
    state["desk_page"] = "Workshop Network"


def why_points(record, chosen, parsed) -> list[str]:
    """Short reasons, every value read from the recorded decision."""
    spare = chosen["days_to_spare"]
    points = [f"Back {explain.short_date(chosen['eta_date'])}, " + (f"{explain.days(spare)} before the due date" if spare >= 0
                                                                   else f"{explain.days(-spare)} late, the least late option")]
    runner = explain.runner_up(record)
    if runner is not None:
        first = explain.deciding_metrics(record, chosen, runner)
        if first:
            row = first[0]
            points.append(f"{row['label']}: {row['winner']} against {row['other']} at {runner['name']}")
    if parsed.category and parsed.pieces:
        points.append(f"Active, makes {parsed.category.lower()} and accepts a batch of {parsed.pieces:,} pieces")
    return points


def recommendation(preview, chosen, record, parsed, workshops, status):
    state = st.session_state
    awkward = record.get("awkward_case") == "none_makes_date"
    confirmed = status.state == "confirmed"
    name, wid = chosen["name"], chosen["workshop_id"]
    passed = (preview.response.faithfulness or {}).get("passed")
    if confirmed:
        stamp = (state["desk_saved"].get(preview.token) or {}).get("timestamp", "")[11:16]
        line = state_line("conf", f"Confirmed by you{f' at {stamp} UTC' if stamp else ''}", "Audit record saved. Queue updated.")
    elif awkward:
        line = state_line("warn", "Least-late option", "No permitted workshop meets the due date. You decide.")
    elif parsed.behaviour == "refuse":
        line = state_line("rec", "Best permitted alternative", "The requested workshop cannot take it. Not yet confirmed.")
    else:
        line = state_line("rec", "Recommended", "Suggested by the engine. Not yet confirmed.")
    won = explain.why_won(record)
    spare = chosen["days_to_spare"]
    makes = " and ".join(sorted(m.lower() for m in workshops[wid].makes))
    objective = explain.objective_label(record["objective_name"])
    if parsed.preference:
        objective += f", requested as {explain.PREFERENCE_LABELS.get(parsed.preference, parsed.preference).lower()}"
    metrics = [("Back by", explain.short_date(chosen["eta_date"]), ""),
               ("Days late" if spare < 0 else "Spare", explain.days(abs(spare)), "late" if spare < 0 else ""),
               ("Total cost", f"{chosen['total_cost']:,.0f}", ""),
               ("Defect risk", f"{chosen['expected_defect_rate']:.0%}", "")]
    tiles = "".join(f'<div class="{cls}"><small>{esc(k)}</small><strong>{esc(v)}</strong></div>' for k, v, cls in metrics)
    photo = (f'<div class="ws-ph"><img class="ws-photo" src="{BRAND}/workshops/{wid}.webp" alt="{esc(name)}"></div>'
             if (WORKSHOP_PHOTOS / f"{wid}.webp").exists() else "")
    evidence = (f'<div class="ws-ev {"ok" if passed else "bad"}">{icon("fact_check" if passed else "error")}'
                f'{"Every number checked against the tools" if passed else "Evidence check failed"}</div>')
    points = "".join(f"<li>{icon('check_circle')}<span>{esc(p)}</span></li>" for p in why_points(record, chosen, parsed))
    state_cls = "rec-done" if confirmed else "rec-late" if awkward else ""
    headline = (f"Assigned to {name}" if confirmed else f"Least late: {name}" if awkward
                else f"Assign to {name} instead" if parsed.behaviour == "refuse" else f"Assign to {name}")
    with st.container(key="rec"):
        main, card = st.columns([1.45, 1], gap="medium")
        with main:
            html(f'<div class="{state_cls}">{line}{batch_line(parsed)}'
                 f'<div class="rec-head">{esc(headline)}</div>'
                 f'<p class="rec-reason">{esc(won["sentence"] if won else record["reason_chosen"])}</p>'
                 f'<ul class="rec-list">{points}</ul>'
                 f'<div class="rec-obj">Objective: {esc(objective)}</div></div>')
        with card:
            html(f'<div class="ws-card">{photo}<div class="ws-top"><div><div class="ws-name">{esc(name)}</div>'
                 f'<div class="ws-sub">Workshop <span class="id">{esc(wid)}</span>, makes {esc(makes)}</div></div></div>'
                 f'<div class="ws-metrics">{tiles}</div>{evidence}</div>')
        with st.container(key="rec_actions", horizontal=True, vertical_alignment="center", gap="small"):
            if confirmed:
                st.button("View audit record", key="desk_view_audit", type="primary", on_click=open_audit, icon=":material/verified_user:")
            else:
                confirm_label = ("Accept late return" if awkward else "Accept alternative" if parsed.behaviour == "refuse"
                                 else f"Assign to {name}")
                st.button(confirm_label, key="desk_confirm", type="primary", disabled=not status.ready,
                          on_click=confirm, args=(preview,))
            if st.button("Why this decision?", key="desk_inspect", type="tertiary", icon=":material/insights:"):
                inspector(workshops)
            st.button("See it on the network", key="desk_trace", type="tertiary", icon=":material/hub:",
                      on_click=trace_on_network, args=(parsed,))
        if confirmed:
            note = f"Recorded in the {'rehearsal' if preview.source != 'live' or guide.active() else 'live'} audit log. No message was sent to {name}."
        elif not status.ready:
            note = status.reason
        else:
            note = ("Confirming writes one audit record and updates this session's queue for "
                    f"{name}. Nothing is sent to the workshop.")
        html(f'<div class="done-note">{esc(note)}</div>')
    if state.get("desk_confirm_error"):
        html(banner("Audit record not saved", " " + state["desk_confirm_error"], "risk"))


def batch_line(parsed) -> str:
    """Order, quantity and customer above the headline, read from the parsed request."""
    if not (parsed.pieces and parsed.product):
        return ""
    who = f" for {parsed.customer}" if parsed.customer else ""
    order = f'<span class="id">{esc(parsed.order_id)}</span>' if parsed.order_id else ""
    return f'<div class="rec-batch">{order}{esc(f"{parsed.pieces:,} {plural(parsed.product)}{who}")}</div>'


def confirm(preview):
    """The human decision. Idempotent: a second click or a rerun never writes or adopts state twice."""
    state = st.session_state
    if desk.confirm_state(preview, preview.signature, state["desk_saved"]).state == "confirmed":
        return
    path = desk.audit_path(preview.source, demo=guide.active())
    append = (lambda response: desk.records.append(response, path)) if path else None
    try:
        desk.confirm_preview(preview, preview.signature, state["desk_saved"], append=append, guided_demo=guide.active())
    except (ValueError, OSError) as error:
        state["desk_confirm_error"] = f"{error}"
        return
    state["desk_allocator"] = deepcopy(preview.accepted_allocator)
    state["desk_queues"] = dict(preview.accepted_queues)
    state["desk_queue_date"] = preview.today
    state["desk_revision"] += 1
    state.pop("desk_confirm_error", None)
    rid = envelope(preview.response.parsed_request.raw_text)[0]
    if rid:
        state.setdefault("desk_outcomes", {})[rid] = "Confirmed"


# Details on demand ------------------------------------------------------------------

def source_line(preview) -> str:
    meta = preview.response.parsed_request.llm_metadata or {}
    if preview.source == "live":
        served = meta.get("served_model") or meta.get("model")
        return f"Live model call to {served}." + (" The provider served a fallback model." if meta.get("fallback") else "")
    if preview.source == "cached":
        return f"Rehearsal: a recorded reply from {meta.get('recorded_model') or 'the configured model'}, replayed without an API call."
    return "Rehearsal: a hand-written test fixture. This is not model output and says nothing about model accuracy."


def details(preview, record, parsed, workshops, chosen):
    """How the request was decided, in pipeline order. Collapsed unless the guided demo opens one."""
    raw = parsed.raw_llm_json or {}
    with st.container(key="detail_extract"):
        with st.expander("What the model read", icon=":material/description:", expanded=guide.opens("extract")):
            html(f'<div class="meta">{esc(source_line(preview))} The model only copies facts from the message. '
                 'It does not choose a workshop or calculate anything.</div>')
            fields = [("Order", raw.get("order_id")), ("Customer", raw.get("customer")), ("Product", raw.get("product")),
                      ("Category", raw.get("category")), ("Pieces", raw.get("pieces")), ("Deadline as written", raw.get("due_date_text")),
                      ("Preference", raw.get("preference")), ("Workshop named", raw.get("suggested_workshop")),
                      ("Workshops excluded", ", ".join(raw.get("excluded_workshops") or []) or None),
                      ("Only a question", "Yes" if raw.get("is_question_only") else "No")]
            html(table(["Field", "Extracted"], [[esc(k), esc("Not stated" if v is None else v)] for k, v in fields]))
    with st.container(key="detail_checks"):
        with st.expander("What Python checked", icon=":material/rule:", expanded=guide.opens("checks")):
            rows = []
            for check in parsed.post_checks:
                if check.get("layer") != "python":
                    continue
                changed = check.get("before") != check.get("after")
                outcome = RESULT_WORDS.get(check.get("result"), str(check.get("result")).replace("_", " "))
                rows.append([esc(RULES.get(check["rule"], check["rule"].replace("_", " "))),
                             esc(outcome) + (f'<br><span class="meta">{esc(check["after"]["reason"])}</span>' if changed else "")])
            final = {"allocate": "Ready to allocate", "refuse": "Named workshop refused; an alternative is checked",
                     "clarify": "Needs a reply from the sender", "decline": "Cannot be answered from the supplied data"}[parsed.behaviour]
            html(f'<div class="meta">Every check is ordinary Python against orders.csv and workshops.csv. Result: <b>{esc(final)}</b>.</div>'
                 + table(["Check", "Result"], rows))
    with st.container(key="detail_workshops"):
        with st.expander("Workshops compared", icon=":material/hub:", expanded=guide.opens("workshops")):
            workshops_table(record, workshops, chosen)


def ordered_rows(record, workshops):
    """Every workshop once: permitted in decision order, then excluded, then ineligible."""
    order = explain.selection_order(record)
    seen = {row["workshop_id"] for row in order}
    rows = [("permitted", row) for row in order]
    rows += [("excluded", row) for row in explain.inventory(record) if row["workshop_id"] not in seen]
    seen |= {row["workshop_id"] for _, row in rows}
    rows += [("ineligible", row) for row in explain.eligibility_rows(record) if row["workshop_id"] not in seen and not row["eligible"]]
    seen |= {row["workshop_id"] for _, row in rows}
    rows += [("unknown", {"workshop_id": wid, "name": w.name, "reason": "not evaluated"}) for wid, w in workshops.items() if wid not in seen]
    return rows


def workshops_table(record, workshops, chosen):
    """One compact table: rank, return, difference from the recommendation, cost and the reason it was not chosen."""
    if not record.get("candidates") and not explain.eligibility_rows(record):
        html('<div class="meta">No workshop was evaluated: the request needs a reply before allocation.</div>')
        return
    body, classes = [], []
    rank = 0
    for kind, row in ordered_rows(record, workshops):
        wid = row["workshop_id"]
        if kind in {"permitted", "excluded"}:
            rank += kind == "permitted"
            spare = row["days_to_spare"]
            if chosen and wid == chosen["workshop_id"]:
                why = "Recommended"
            elif kind == "excluded":
                why = row.get("exclusion_reason") or "Excluded by request"
            else:
                verdict = explain.why_not(record, wid, workshops)
                why = verdict.get("headline") or verdict.get("result") or ""
            delta = "" if not chosen or wid == chosen["workshop_id"] else f'{row["total_days"] - chosen["total_days"]:+.1f} d, {row["total_cost"] - chosen["total_cost"]:+,.0f}'
            body.append([str(rank) if kind == "permitted" else "", f"<b>{esc(row['name'])}</b>", esc(explain.short_date(row["eta_date"])),
                         f'<span class="{"neg" if spare < 0 else ""}">{spare:+d}</span>', f"{row['total_cost']:,.0f}", esc(delta),
                         f'<span class="wrap">{esc(why)}</span>'])
            classes.append("chosen" if chosen and wid == chosen["workshop_id"] else "dim" if kind == "excluded" else "")
        else:
            body.append(["", f"<b>{esc(row['name'])}</b>", "", "", "", "",
                         f'<span class="wrap">{esc(explain.reason_text(row.get("reason", "")) if row.get("reason") != "not evaluated" else "Not evaluated")}</span>'])
            classes.append("dim")
    html('<div class="meta">Ranked by the engine under the current objective. Excluded and ineligible workshops are listed with the reason.</div>'
         + table(["Rank", "Workshop", "Back", "Spare", "Cost", "Against the pick", "Why"], body, right=(3, 4), classes=classes))


def timing(trace, workshops):
    """Measured server-side time for the last evaluation, split by stage. Real spans, no estimates."""
    stages = [s for s in trace.get("stages", []) if s["ms"] > 0]
    total = trace.get("total_ms") or 0.0
    if not total:
        return
    segments = "".join(f'<i class="tg-{s["key"]}" style="width:{max(s["ms"] / total * 100, 0.6):.2f}%" title="{esc(s["label"])}"></i>'
                       for s in stages)
    legend = "".join(f'<span><i class="tg-{s["key"]}"></i>{esc(s["label"])} <b>{fmt_ms(s["ms"])}</b></span>' for s in stages)
    llm = trace.get("meta", {}).get("llm") or {}
    live = trace["meta"].get("source") == "live"
    calls = f'{len(llm.get("attempts") or [1])} model call{"s" if len(llm.get("attempts") or [1]) > 1 else ""} · ' if live and llm else ""
    who = {"live": "live model", "cached": "recorded reply, no API call", "fixture": "test fixture, no API call"}.get(trace["meta"].get("source"), "")
    status = "failed after" if trace.get("status") == "error" else "completed in"
    with st.container(key="desk_timing"):
        html(f'<div class="tg"><div class="tg-head"><b>Evaluation {status} {fmt_ms(total)}</b>'
             f'<span>{esc(who)} · {esc(calls)}{trace["meta"].get("tool_calls") or 0} tool calls · trace <span class="id">{esc(trace["trace_id"])}</span></span></div>'
             f'<div class="tg-bar">{segments}</div><div class="tg-legend">{legend}</div></div>')
        if st.button("View execution trace", key="desk_trace_view", type="tertiary", icon=":material/timer:"):
            inspector(workshops, focus="timing")


def fmt_ms(ms: float) -> str:
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.0f} ms" if ms >= 10 else f"{ms:.1f} ms"


def options_card(preview, record, parsed, workshops, queues):
    state = st.session_state
    split = record.get("tool_outputs", {}).get("split") or state["desk_splits"].get(preview.token)
    awkward = record.get("awkward_case") == "none_makes_date"
    with st.container(key="options"):
        if awkward:
            section("Your options", "The system will not decide this for you.")
            html('<ul class="opt-list"><li><b>Accept the late return.</b> Use the button on the recommendation; the record marks the lateness as accepted.</li>'
                 '<li><b>Preview a split.</b> The fastest legal two-workshop split. A preview only.</li>'
                 '<li><b>Escalate.</b> Leave it unconfirmed and raise it with the planner or customer.</li></ul>')
        if split is None and awkward:
            if st.button("Preview a two-workshop split", key="desk_split", icon=":material/call_split:"):
                batch = {"order_id": parsed.order_id, "pieces": parsed.pieces, "category": parsed.category,
                         "due_date": parsed.due_date, "sent_date": preview.today}
                state["desk_splits"][preview.token] = tools.estimate_split(
                    batch, workshops, queues, preview.today, record["constraints_applied"]["exclude"], record["chosen_workshop"])
                st.rerun()
        if split is not None:
            split_view(split)


def split_view(split):
    if not split.get("available"):
        html(banner("Split preview", " No legal two-workshop split is available: " + split.get("reason", "") + ".", "muted"))
        return
    rows = [[f"<b>{esc(p['name'])}</b>", f"{p['pieces']:,}", esc(explain.short_date(p["eta_date"])), f"{p['total_cost']:,.0f}"] for p in split["parts"]]
    single = split.get("single")
    compare = ""
    if single:
        compare = (f' Whole batch at {esc(single["name"])}: back {esc(explain.short_date(single["eta_date"]))}. '
                   + (f'The split saves {split["days_saved"]:.1f} days' if split.get("faster") else "The split is not faster")
                   + ("" if split.get("earlier_eta") or not split.get("faster") else ", but the return date is the same") + ".")
    html(f'<div style="margin-top:0.8rem;display:flex;justify-content:space-between;align-items:center"><div class="title" style="font-size:1.1667rem">Split preview</div>'
         f'{status_pill("Preview only", "muted")}</div><div class="meta" style="margin:0.2667rem 0 0.6667rem">Both parts run in parallel. '
         f'Completion is the later part: {esc(explain.short_date(split["eta_date"]))}, {split["days_to_spare"]:+d} days to spare, combined cost '
         f'{split["total_cost"]:,.0f}.{compare}</div>' + table(["Workshop", "Pieces", "Back", "Cost"], rows, right=(1, 3)))


def clarify_card(parsed, record, workshops, orders):
    state = st.session_state
    options = record.get("tool_outputs", {}).get("order_options", [])
    prompt = explain.clarify_prompt(parsed.to_dict(), options)
    source = rehearsal.SOURCES[state["desk_source"]]
    with st.container(key="clarify"):
        html(state_line("warn", "Needs a reply before allocating", "Nothing has been allocated.")
             + f'<div class="say">I need one detail before I can continue.</div><div class="ask">{esc(prompt["question"])}</div>')
        if prompt["missing"]:
            html(f'<div class="cl-missing"><small>Missing</small>{esc(", ".join(m.lower() for m in prompt["missing"]))}</div>')
        if prompt["options"]:
            html('<div class="cl-sub">Choose the order. The request is evaluated again straight away.</div>')
            widths = [1.05, 1.6, 0.9, 1.1, 1, 1.05]
            due_dates = dict(zip(orders["order_id"].astype(str), orders["due_date"]))   # Read from orders.csv, as the facts line is.
            with st.container(key="clarify_options"):
                head = st.columns(widths, vertical_alignment="center")
                for col, title in zip(head, ["Order", "Product", "Pieces", "Due", "Stage", ""]):
                    with col:
                        html(f'<div class="cl-h">{esc(title)}</div>')
                for option in prompt["options"]:
                    with st.container(key=f"clopt_{option['order_id']}"):
                        cells = st.columns(widths, vertical_alignment="center")
                        due = due_dates.get(option["order_id"])
                        due = explain.short_date(str(due)[:10]) if due is not None and str(due) != "nan" else "Not set"
                        values = [f'<b class="id">{esc(option["order_id"])}</b>', esc(option["product"]), f'{option["pieces"]:,}',
                                  esc(due), esc(str(option["current_stage"]).capitalize())]
                        for col, value in zip(cells, values):
                            with col:
                                html(f'<div class="cl-c">{value}</div>')
                        with cells[-1]:
                            st.button("Use this", key=f"desk_option_{option['order_id']}", width="stretch",
                                      on_click=append_reply, args=(option["order_id"],))
        reply_col, add_col = st.columns([3, 1], vertical_alignment="bottom")
        with reply_col:
            st.text_input(f"Or reply as {parsed.sender or 'the sender'}", key="desk_reply", placeholder="Type the missing detail")
        with add_col:
            st.button("Add and evaluate", key="desk_add_reply", on_click=append_reply, type="primary", width="stretch",
                      disabled=not state.get("desk_reply", "").strip())
        note = "Your answer is added to the request and the request is read again."
        if source.rehearsal:
            note += " Rehearsal covers the original inbox lines only, so an answered request needs the live model."
        html(f'<div class="meta" style="margin-top:0.4rem">{esc(note)}</div>')
        if st.button("Why this decision?", key="desk_inspect", type="tertiary", icon=":material/insights:"):
            inspector(workshops)


def decline_card(parsed, orders, workshops):
    if parsed.reason == "order not found":
        needed = f"An order record for {parsed.order_id or 'the named order'}. It is not among the {len(orders)} orders in orders.csv."
    else:
        needed = DATA_NEEDED.get(parsed.question_topic, "The source records that hold this information.")
    with st.container(key="decline"):
        html(state_line("block", "Cannot be answered from the supplied data", "Nothing has been allocated.")
             + '<div class="say">This information is not available in the supplied data.</div>'
             '<div class="ask">The desk answers from orders, workshop profiles and the inbox. It does not guess.</div>'
             + table(["", ""], [["<b>Missing source</b>", esc(needed)],
                                ["<b>Sources available</b>", esc(f"orders.csv ({len(orders)} orders), workshops.csv (8 profiles), the 30-message inbox.")]]))
        if st.button("Why this decision?", key="desk_inspect", type="tertiary", icon=":material/insights:"):
            inspector(workshops)


# Decision inspector: a slide-over panel -------------------------------------------

@st.dialog("Decision inspector", width="large")
def inspector(workshops, focus: str = "why"):
    preview = st.session_state.get("desk_preview")
    if preview is None:
        html('<div class="inspector"></div>')
        st.write("Evaluate a request first.")
        return
    response, record = preview.response, preview.response.decision_record
    status = desk.confirm_state(preview, preview.signature, st.session_state["desk_saved"])
    steps = explain.trace_steps(response.to_dict(), agent_calls=preview.agent_calls, replayed=preview.accepted_allocator is not None,
                                confirmed=status.state == "confirmed", block_reason=preview.block_reason)
    chosen = explain.chosen_row(record)
    title = chosen["name"] if chosen else {"clarify": "Needs a reply", "decline": "Cannot answer"}.get(response.parsed_request.behaviour, "No recommendation")
    html(f'<div class="inspector"><div class="eyebrow">Why this decision</div><div class="ins-title">{esc(title)}</div>'
         f'<div class="ins-sub">{esc(explain.objective_label(record["objective_name"]))}. Every value below is read from the recorded decision.</div></div>')
    views = {"Why this won": lambda: why_tab(record), "Why not another": lambda: why_not_tab(record, workshops),
             "Score breakdown": lambda: breakdown_tab(record), "Evidence trace": lambda: trace_tab(response, steps),
             "Timing": lambda: timing_tab(st.session_state.get("desk_exec"))}
    names = list(views)
    if focus == "options":
        names.insert(0, names.pop(1))
    elif focus == "timing":
        names.insert(0, names.pop(names.index("Timing")))
    for tab, view in zip(st.tabs(names), names):
        with tab:
            views[view]()


def compare_grid(rows, winner, other) -> str:
    cells = ["<div>Measure</div>", f"<div>{esc(winner)}</div>", f"<div>{esc(other)}</div>", "<div>Difference</div>"]
    for row in rows:
        cells += [f'<div>{esc(row["label"])}</div>', f'<div class="w">{esc(row["winner"])}</div>', f'<div>{esc(row["other"])}</div>',
                  f'<div class="{"same" if row["better"] is None else "d"}">{esc(row["difference"])}</div>']
    return f'<div class="cmp">{"".join(cells)}</div>'


def why_tab(record):
    chosen = explain.chosen_row(record)
    if chosen is None:
        html('<p>No workshop is recommended until the request can be allocated.</p>')
        return
    won = explain.why_won(record)
    html(f'<div class="dk-card beam" style="margin:0.4rem 0 0.9333rem"><div class="eyebrow" style="color:var(--cyan)">Why this won</div>'
         f'<p style="font-size:1.1667rem;margin:0.4rem 0 0">{esc(won["sentence"])}</p></div>')
    other = won.get("runner_up")
    if other is not None:
        html(compare_grid(explain.deciding_metrics(record, chosen, other), chosen["name"], other["name"]))
        html(f'<p class="ev" style="margin-top:0.6667rem">Only the measures the {esc(explain.objective_label(record["objective_name"]).lower())} '
             f'rule used are shown. {esc(other["name"])} is the next option under the same rule.</p>')
    else:
        html('<p class="ev">No other permitted workshop remained, so there is nothing to compare.</p>')


def why_not_tab(record, workshops):
    chosen = explain.chosen_row(record)
    state = st.session_state
    others = [wid for wid in workshops if wid != record.get("chosen_workshop")]
    runner = explain.runner_up(record)
    pick = bind(st.pills, "Workshop", others, key="desk_whynot", fallback=runner["workshop_id"] if runner else others[0],
                format_func=lambda wid: workshops[wid].name, label_visibility="collapsed")
    verdict = explain.why_not(record, pick, workshops)
    tone = {"Eligible": "dark", "Not eligible": "dark-risk", "Excluded": "dark-risk"}.get(verdict["verdict"], "dark-muted")
    facts = "".join(f"<li>{esc(f)}</li>" for f in (verdict["facts"] or verdict["detail"]))
    result_line = f'<div class="dk-result"><b>Result</b> {esc(verdict["result"])}</div>' if verdict["result"] else ""
    html(f'<div class="dk-card" style="margin-top:0.4rem"><div class="dk-head"><b>{esc(verdict["name"])}</b>{status_pill(verdict["verdict"], tone)}</div>'
         f'<div class="ev" style="margin-top:0.2667rem">{esc(verdict["headline"])}</div><ul class="dk-list">{facts}</ul>{result_line}</div>')
    if chosen is not None and verdict.get("row") is not None and verdict["status"] in {"outscored", "later", "misses_date"}:
        html('<div style="height:0.8rem"></div>' + compare_grid(explain.deciding_metrics(record, chosen, verdict["row"]), chosen["name"], verdict["name"]))


def breakdown_tab(record):
    chosen = explain.chosen_row(record)
    if chosen is None:
        html('<p class="ev">Scores exist only once workshops are evaluated.</p>')
        return
    config = explain.effective_config(record["objective_name"])
    runner = explain.runner_up(record)
    html(f'<div class="eyebrow" style="color:var(--cyan);margin:0.2667rem 0 0.8rem">Objective weights, {esc(explain.objective_label(record["objective_name"]).lower())}</div>'
         + weight_bars(config, explain.TERMS, explain.TERM_LABELS))
    other = f'<span class="ev">{esc(runner["name"])} {runner["score"]:.5f}</span>' if runner else ""
    html(f'<div class="final" style="margin-top:1.0667rem"><b>Final score, lower wins</b><div style="text-align:right"><strong>{chosen["score"]:.5f}</strong><br>{other}</div></div>')
    order = explain.selection_order(record)[:6]
    html('<div class="eyebrow" style="color:var(--cyan);margin:1.3333rem 0 0.6667rem">Weighted contribution per candidate</div>'
         + score_bars(explain.score_breakdown(order, config), chosen["workshop_id"], explain.TERMS, explain.TERM_LABELS))
    note = ("Every option is late, so the least-late rule chose the workshop, not the weighted score."
            if record.get("awkward_case") == "none_makes_date" else explain.TERM_NOTES["lateness"] if config.w_lateness else "")
    if note:
        html(f'<p class="ev" style="margin-top:0.8rem">{esc(note)}</p>')


def timing_tab(trace):
    if not trace:
        html('<p class="ev">No timing was recorded for this evaluation.</p>')
        return
    meta, llm = trace.get("meta", {}), trace.get("meta", {}).get("llm") or {}
    usage = llm.get("usage") or {}
    rows = [("Trace ID", trace["trace_id"]), ("Started (UTC)", trace["started_utc"][:19].replace("T", " ")),
            ("Total server time", fmt_ms(trace["total_ms"])), ("Extraction source", meta.get("source")),
            ("Model requested", meta.get("requested_model") or "None (no API call)"),
            ("Model that answered", llm.get("served_model") or llm.get("recorded_model") or llm.get("model") or "None"),
            ("Provider call", fmt_ms(llm["provider_ms"]) if llm.get("provider_ms") is not None else "No API call"),
            ("HTTP attempts", str(len(llm.get("attempts") or [])) + (" (includes retries)" if len(llm.get("attempts") or []) > 1 else "") if llm.get("attempts") is not None else "Not applicable"),
            ("Tokens in / out", f'{usage.get("input_tokens", 0):,} / {usage.get("output_tokens", 0):,}' if usage else "Not applicable"),
            ("Cache read / write tokens", f'{usage.get("cache_read_input_tokens") or 0:,} / {usage.get("cache_creation_input_tokens") or 0:,}' if usage else "Not applicable")]
    html('<dl class="kv" style="grid-template-columns:12rem 1fr">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")
    spans = trace.get("spans", [])
    depth = {}
    for i, s in enumerate(spans):
        depth[i] = 0 if s["parent"] is None else depth.get(s["parent"], 0) + 1
    body = [[("&nbsp;" * 4 * depth[i]) + esc(s["name"]), esc(s["status"]), f'{s["ms"]:.1f}', f'{s["offset_ms"]:.1f}'] for i, s in enumerate(spans)]
    html('<p class="ev" style="margin-top:0.8rem">Spans in execution order. Durations include nested spans; the stage bar on the page uses '
         'each span\'s own time, so nothing is counted twice. Provider-internal inference time is not observable: the provider call '
         'includes the network.</p>' + table(["Span", "Status", "ms", "Starts at ms"], body, right=(2, 3), max_height=360))


def evidence_view(step) -> str:
    """Readable, deterministic evidence for one trace step. Raw data stays behind a toggle."""
    ev, key = step.get("evidence"), step["key"]

    def rows(pairs, right=()):
        return '<table class="ev-table">' + "".join(
            "<tr>" + "".join(f'<td class="{"r" if i in right else ""}">{esc(c)}</td>' for i, c in enumerate(p)) + "</tr>" for p in pairs) + "</table>"
    try:
        if key == "extract":
            raw = (ev or {}).get("structured_extraction", {})
            fields = ("order_id", "customer", "product", "category", "pieces", "due_date_text", "preference", "suggested_workshop", "excluded_workshops")
            return rows([(f.replace("_", " ").capitalize(), raw.get(f)) for f in fields if raw.get(f) not in (None, [], "")])
        if key == "validate":
            return rows([(c.get("rule", "").replace("_", " ").capitalize(), str(c.get("result", "")).replace("_", " ")) for c in ev or []])
        if key == "order":
            return rows([(o["order_id"], o["customer"], o["product"], f'{o["pieces"]:,} pcs', o["current_stage"].lower()) for out in ev or [] for o in out or []])
        if key == "eligibility":
            return rows([(r["name"], "Eligible" if r["eligible"] else explain.ineligible_headline(r["reason"])) for r in ev or []])
        if key == "candidates":
            return rows([(r["name"],) for r in ev or []])
        if key == "eta":
            seen = {}
            for out in ev or []:
                seen.setdefault(out["workshop_id"], out)
            return rows([(wid, f'{o["queue_days"]:.1f} + {o["processing_days"]:.1f} + {o["lead_days"]} days', explain.short_date(o["eta_date"]))
                         for wid, o in seen.items()], right=(1, 2))
        if key == "cost":
            seen = {o["workshop_id"]: o for o in ev or []}
            return rows([(wid, f'{o["cost_per_piece"]:g} per piece', f'{o["total_cost"]:,.0f}') for wid, o in seen.items()], right=(1, 2))
        if key == "score":
            return rows([(r["workshop_id"], f'{r["score"]:.5f}') for r in ev or []], right=(1,))
        if key == "select":
            return rows([("Chosen", ev.get("chosen_workshop")), ("Rule", (ev.get("reason") or "").split(":", 1)[0])])
        if key == "verify":
            return rows([("Values checked", len(ev.get("numbers_in_text", []))), ("Unsupported", len(ev.get("unmatched", [])))], right=(1,))
    except (KeyError, TypeError, AttributeError):
        return ""
    return ""


def trace_tab(response, steps):
    html('<p class="ev" style="margin:2px 0 0.6667rem">Recorded program events, in order. These are tool calls and checks that actually ran, not model reasoning.</p>')
    icons = {"done": ":material/radio_button_checked:", "pending": ":material/radio_button_unchecked:",
             "blocked": ":material/block:", "skipped": ":material/radio_button_unchecked:"}
    who = {"model": "Language model", "fixture": "Test fixture", "python": "Python", "human": "Dispatcher"}
    with st.container(key="trace"):
        for number, step in enumerate(steps, 1):
            label = step["title"] + (", not needed" if step["status"] == "skipped" else "")
            with st.container(key=f"tr_{step['status']}_{number}"), st.expander(label, expanded=False, icon=icons[step["status"]]):
                html(f'<p class="ev" style="margin:0">{esc(step["summary"])}</p><p class="ev" style="margin:2px 0 0;font-size:0.8667rem">'
                     f'Performed by {esc(who[step["actor"]])}</p>' + evidence_view(step))
                if step.get("evidence") is not None:
                    with st.container(key=f"dev_trace_{number}"):
                        if st.toggle("View raw evidence", key=f"raw_{number}"):
                            json_block(step["evidence"], height=240)
    with st.container(key="dev_download"):
        st.download_button("Download decision record", json.dumps(response.to_dict(), indent=2, default=str),
                           file_name=f"{response.parsed_request.order_id or 'request'}-decision.json", mime="application/json",
                           key="desk_download")
