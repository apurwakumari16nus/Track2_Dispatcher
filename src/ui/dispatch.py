"""Dispatch: request, recommendation, alternatives, confirmation, inspector.

Rendering only. Extraction runs through intake.extraction_source; everything
after the raw reply is the unchanged agent/allocator/tools/faithfulness path in
desk.make_preview. The process strip reflects real stage transitions and the
recorded tool trace, never model reasoning. Technical evidence lives in the
Decision inspector, a slide-over panel opened on request.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re

import streamlit as st

import desk
import intake
from objectives import PRESETS
import rehearsal
import tools
from ui import explain
from ui.components import (banner, candidate_row, decision_stage, esc, fact, html, json_block, score_bars, section,
                           status_pill, table, weight_bars)

STATUS_WORDS = {"allocate": "Reviewed", "clarify": "Needs reply", "refuse": "Reviewed", "decline": "Cannot answer"}
DATA_NEEDED = {
    "allocation_history": "Historical dispatch records linking customers and orders to workshops.",
    "customer_quote": "Customer sales quotations or pricing records.",
    "worker_names": "A worker roster and worker-to-order assignments.",
}


# State helpers -----------------------------------------------------------------

def invalidate():
    for key in ("desk_preview", "desk_error", "desk_whynot", "desk_confirm_error"):
        st.session_state.pop(key, None)


def select_message(message):
    st.session_state["desk_message"] = message
    invalidate()


def append_reply(text=None):
    reply = (text or st.session_state.get("desk_reply", "")).strip()
    if reply:
        st.session_state["desk_message"] = st.session_state["desk_message"].rstrip() + f" Reply from dispatcher: {reply}"
        st.session_state["desk_reply"] = ""
        invalidate()


def use_rehearsal():
    st.session_state["desk_source"] = "fixture"
    invalidate()


def open_audit():
    st.session_state["desk_page"] = "Audit Trail"


def envelope(message: str) -> tuple[str, str, str, str]:
    """(request id, time, sender, body) from an inbox line; blanks for free text."""
    try:
        head, body = message.split("]", 1)
        rid, time = head.split("[", 1)
        sender, text = body.split(":", 1)
        return rid.strip(), time.strip(), sender.strip(), text.strip()
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
    keys = [key for key, _, _ in explain.STAGES]
    index = keys.index(active)
    return [(key, label, detail, "done" if i < index else "active" if i == index else "idle")
            for i, (key, label, detail) in enumerate(explain.STAGES)]


# Page ---------------------------------------------------------------------------

def render(orders, workshops, messages):
    state = st.session_state
    head, bar = st.columns([1.05, 1], vertical_alignment="bottom")
    with head:
        html('<div class="eyebrow">Dispatch</div><div class="display">Quick Response Subcontracting Desk</div>')
    with bar:
        with st.container(key="cmdbar"):
            date_col, objective_col, ready_col = st.columns([1, 1.35, 1.05], vertical_alignment="bottom")
            with date_col:
                today = st.date_input("Scenario date", key="desk_today", min_value=state["desk_queue_date"], on_change=invalidate,
                                      format="DD/MM/YYYY")
            with objective_col:
                preset = st.selectbox("Objective", list(PRESETS), key="desk_preset", on_change=invalidate,
                                      format_func=explain.objective_label)
            with ready_col:
                system_ready(workshops)
    config = PRESETS[preset]
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    inbox_col, work_col = st.columns([1, 2.65], gap="large")
    with work_col:  # Drawn first so the inbox shows this run's outcome label.
        workspace(orders, workshops, today, config, queues)
    with inbox_col:
        inbox(messages)


def system_ready(workshops):
    state = st.session_state
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    html('<div class="ready-label">System</div>')
    with st.popover("System ready", icon=":material/check_circle:", width="stretch"):
        source = rehearsal.SOURCES[state["desk_source"]]
        live = rehearsal.live_status()
        language = ("Rehearsal, " + ("recorded replies" if source.key == "cached" else "test fixtures") if source.rehearsal
                    else f"Live model, {live['model']}" if live["ready"] else "Not configured")
        rows = [("Allocation engine", "Ready"), ("Workshops", f"{len(workshops)} on the register, {active} active"),
                ("Queues", f"As of {explain.long_date(state['desk_queue_date'])}"), ("Request reading", language),
                ("Confirmed this session", str(len(state["desk_saved"])))]
        html('<dl class="kv" style="grid-template-columns:170px 1fr;font-size:14px">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")


def inbox(messages):
    state = st.session_state
    html(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:14px"><div class="title">Inbox</div>'
         f'<div class="meta">{len(messages)} requests</div></div>')
    query = st.text_input("Search inbox", placeholder="Search sender, order or text", key="inbox_search", label_visibility="collapsed")
    filtered = [m for m in messages if query.casefold() in m.casefold()]
    outcomes = state.get("desk_outcomes", {})
    with st.container(height=700, key="inbox_list", border=False):
        for message in filtered:
            rid, time, sender, body = envelope(message)
            colour = {"Confirmed": "green", "Needs reply": "orange", "Cannot answer": "gray"}.get(outcomes.get(rid), "blue")
            status = f"   :{colour}[{outcomes[rid]}]" if rid in outcomes else ""
            st.button(f"**{sender}**  {time}{status}\n{body}", key="inbox_" + rid, width="stretch",
                      type="primary" if state["desk_message"] == message else "secondary",
                      on_click=select_message, args=(message,))
        if not filtered:
            html('<div class="meta" style="padding:12px 4px">No request matches. Clear the search to see all.</div>')


def workspace(orders, workshops, today, config, queues):
    state = st.session_state
    message = state["desk_message"]
    run = request_surface(message, orders)
    current_signature = desk.signature(message, today, config, orders, workshops, queues, state["desk_revision"], state["desk_source"])
    progress = st.empty()
    if run and message.strip():
        evaluate(progress, orders, workshops, today, config, queues)
    preview = state.get("desk_preview")
    if state.get("desk_error"):
        progress.empty()
        error_card(state["desk_error"])
    elif preview:
        result(preview, current_signature, workshops, orders, queues, progress)
    elif not message.strip():
        html('<div class="empty"><i></i><div class="say">Select a request to begin.</div>'
             '<div class="ask">Python verifies the request and ranks eligible workshops. You approve the final decision.</div></div>')


def request_surface(message, orders) -> bool:
    rid, time, sender, body = envelope(message)
    on_file = order_on_file(message, orders)
    with st.container(key="request"):
        if rid:
            html(f'<div class="msg-head"><div class="avatar">{esc(sender[:1])}</div><div><b>{esc(sender)}</b><br>'
                 f'<span>{esc(time)}, request {esc(rid)}</span></div></div><div class="msg-text">{esc(body)}</div>')
        else:
            html('<div class="msg-head"><div class="avatar">+</div><div><b>New request</b><br>'
                 '<span>Type or paste the chat message</span></div></div><div style="height:10px"></div>')
            st.text_area("Request", key="desk_message", height=96, label_visibility="collapsed", on_change=invalidate,
                         placeholder="For example: ORD-045, 150 vests for Cotton Club, due Apr 09. Fastest turnaround please.")
        if on_file is not None:
            html('<div class="facts"><span class="eyebrow">On file</span>'
                 + fact("Order", on_file["order_id"]) + fact("Customer", on_file["customer"]) + fact("Product", on_file["product"])
                 + fact("Pieces", f"{int(on_file['pieces']):,}") + fact("Due", explain.long_date(str(on_file["due_date"])))
                 + fact("Stage", str(on_file["current_stage"]).capitalize()) + "</div>")
        edit_col, new_col, run_col = st.columns([2.6, .9, 1.15], vertical_alignment="center")
        with edit_col:
            if rid:
                with st.expander("Edit message"):
                    st.text_area("Request", key="desk_message", height=84, label_visibility="collapsed", on_change=invalidate)
        with new_col:
            st.button("New request", key="desk_new", width="stretch", on_click=select_message, args=("",))
        with run_col:
            return st.button("Evaluate request", key="desk_dispatch", type="primary", width="stretch",
                             icon=":material/bolt:", disabled=not message.strip())


def evaluate(progress, orders, workshops, today, config, queues):
    state = st.session_state
    invalidate()
    progress.markdown(decision_stage(live_stages("understand")), unsafe_allow_html=True)

    def reply_arrived():
        progress.markdown(decision_stage(live_stages("validate")), unsafe_allow_html=True)

    call = rehearsal.make_source(state["desk_source"], on_reply=reply_arrived)
    try:
        with intake.extraction_source(call):
            preview = desk.make_preview(state["desk_message"], today, config, orders, workshops, queues,
                                        state["desk_allocator"], state["desk_revision"], state["desk_source"])
    except Exception as error:
        known = isinstance(error, (intake.IntakeError, ValueError))
        state["desk_error"] = {"text": str(error) if known else f"{type(error).__name__}. Check the connection and try again.",
                               "kind": ("unconfigured" if "for live intake" in str(error) else
                                        "rehearsal" if isinstance(error, rehearsal.RehearsalMiss) else "other")}
        return
    state["desk_preview"] = preview
    rid = envelope(state["desk_message"])[0]
    if rid:
        state.setdefault("desk_outcomes", {})[rid] = STATUS_WORDS[preview.response.parsed_request.behaviour]


def error_card(error):
    kind = error.get("kind") if isinstance(error, dict) else "other"
    text = error.get("text") if isinstance(error, dict) else str(error)
    if kind == "unconfigured":
        html(banner("Language intake unavailable", " Configure the model in .env, or switch to rehearsal mode.", "warn"))
        st.button("Switch to rehearsal mode", key="desk_use_rehearsal", on_click=use_rehearsal)
    elif kind == "rehearsal":
        html(banner("No rehearsal extraction for this text", " " + text, "warn"))
    else:
        html(banner("Request not processed", " " + text, "risk"))


# Result -------------------------------------------------------------------------

def result(preview, current_signature, workshops, orders, queues, progress):
    state = st.session_state
    response, record, parsed = preview.response, preview.response.decision_record, preview.response.parsed_request
    status = desk.confirm_state(preview, current_signature, state["desk_saved"])
    steps = explain.trace_steps(response.to_dict(), agent_calls=preview.agent_calls, replayed=preview.accepted_allocator is not None,
                                confirmed=status.state == "confirmed", block_reason=preview.block_reason)
    progress.markdown(decision_stage(explain.stage_status(steps)), unsafe_allow_html=True)
    if status.state == "stale":
        html(banner("Inputs changed", " The request, date, objective or queue changed after this evaluation. Evaluate again before confirming.", "warn"))
    if response.already_late:
        html(banner("Already late", f" The due date, {explain.long_date(parsed.due_date)}, is on or before the scenario date, "
                    f"{explain.long_date(preview.today)}. Any return will be late.", "risk"))
    chosen = explain.chosen_row(record)
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
        hero_col, alt_col = st.columns([1.6, 1], gap="medium")
        with hero_col:
            recommendation(preview, chosen, record, parsed, workshops, status)
        with alt_col:
            alternatives(record, workshops)
        if record.get("awkward_case") == "none_makes_date" or record.get("tool_outputs", {}).get("split"):
            options_card(preview, record, parsed, workshops, queues)
    elif parsed.behaviour == "clarify":
        clarify_card(parsed, record, workshops)
    elif parsed.behaviour == "decline":
        decline_card(parsed, orders, workshops)
    else:
        html(banner("No eligible workshop remains", " Every workshop is excluded or ineligible for this batch. Leave it unconfirmed and escalate.", "risk"))
        alternatives(record, workshops)


def recommendation(preview, chosen, record, parsed, workshops, status):
    state = st.session_state
    awkward = record.get("awkward_case") == "none_makes_date"
    confirmed = status.state == "confirmed"
    label = ("Confirmed" if confirmed else "Least-late option" if awkward else
             "Best permitted alternative" if parsed.behaviour == "refuse" else "Recommended workshop")
    passed = (preview.response.faithfulness or {}).get("passed")
    evidence = status_pill("Evidence verified", "dark") if passed else status_pill("Evidence check failed", "dark-risk")
    won = explain.why_won(record)
    spare = chosen["days_to_spare"]
    metrics = [(explain.short_date(chosen["eta_date"]), "Back by", ""),
               (explain.days(abs(spare)), "Days late" if spare < 0 else "Spare", "late" if spare < 0 else ""),
               (f"{chosen['total_cost']:,.0f}", "Cost", ""),
               (f"{chosen['expected_defect_rate']:.0%}", "Defect risk", "")]
    tiles = "".join(f'<div class="{cls}"><strong>{esc(v)}</strong><small>{esc(k)}</small></div>' for v, k, cls in metrics)
    makes = " and ".join(sorted(m.lower() for m in workshops[chosen["workshop_id"]].makes))
    objective = explain.objective_label(record["objective_name"])
    if parsed.preference:
        objective += f", requested as {explain.PREFERENCE_LABELS.get(parsed.preference, parsed.preference).lower()}"
    state_cls = "rec-done" if confirmed else "rec-late" if awkward else ""
    with st.container(key="rec"):
        html(f'<div class="{state_cls}"><div class="rec-top"><span class="rec-eyebrow">{esc(label)}</span>{evidence}</div>'
             f'<div class="rec-name">{esc(chosen["name"])}</div><div class="rec-sub">Workshop {esc(chosen["workshop_id"])}, makes {esc(makes)}</div>'
             f'<div class="rec-metrics">{tiles}</div>'
             f'<div class="rec-why"><small>Why this won</small><p>{esc(won["sentence"] if won else record["reason_chosen"])}</p>'
             f'<div class="rec-obj">Objective: {esc(objective)}</div></div></div>')
        html('<div style="height:6px"></div>')
        if confirmed:
            note_col, audit_col, why_col = st.columns([1.5, 1, 1], vertical_alignment="center")
            with note_col:
                html('<div class="done-note"><b>Audit record saved. Queue updated.</b><br>'
                     f'No message has been sent to {esc(chosen["name"])}.</div>')
            with audit_col:
                st.button("View audit record", key="desk_view_audit", width="stretch", on_click=open_audit)
        else:
            confirm_label = ("Accept late return" if awkward else "Accept alternative" if parsed.behaviour == "refuse" else "Confirm allocation")
            confirm_col, why_col = st.columns([1.6, 1], vertical_alignment="center")
            with confirm_col:
                if st.button(confirm_label, key="desk_confirm", type="primary", width="stretch", icon=":material/task_alt:",
                             disabled=not status.ready):
                    confirm(preview)
        with why_col:
            if st.button("Why this decision?", key="desk_inspect", width="stretch", icon=":material/insights:"):
                inspector(workshops)
        if not confirmed:
            note = status.reason if not status.ready else "You approve the decision. Nothing is sent to the workshop."
            html(f'<div class="done-note" style="margin-top:4px">{esc(note)}</div>')
    if state.get("desk_confirm_error"):
        html(banner("Audit record not saved", " " + state["desk_confirm_error"], "risk"))


def confirm(preview):
    state = st.session_state
    path = desk.audit_path(preview.source)
    append = (lambda response: desk.records.append(response, path)) if path else None
    try:
        desk.confirm_preview(preview, preview.signature, state["desk_saved"], append=append)
    except (ValueError, OSError) as error:
        state["desk_confirm_error"] = f"{error}"
    else:
        state["desk_allocator"] = deepcopy(preview.accepted_allocator)
        state["desk_queues"] = dict(preview.accepted_queues)
        state["desk_queue_date"] = preview.today
        state["desk_revision"] += 1
        state.pop("desk_confirm_error", None)
        rid = envelope(preview.response.parsed_request.raw_text)[0]
        if rid:
            state.setdefault("desk_outcomes", {})[rid] = "Confirmed"
    st.rerun()


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


def alternatives(record, workshops):
    chosen = record.get("chosen_workshop")
    rows = ordered_rows(record, workshops)
    permitted = [row for kind, row in rows if kind == "permitted"]
    others = [row for row in permitted if row["workshop_id"] != chosen][:3]
    with st.container(key="alts"):
        html(f'<div style="display:flex;flex-wrap:wrap;gap:2px 12px;justify-content:space-between;align-items:baseline"><div class="title" style="font-size:18px">Alternatives</div>'
             f'<div class="meta">{len(permitted)} of {len(workshops)} workshops permitted</div></div>')
        lines = ['<div class="alt head"><span>Workshop</span><span class="r">Back</span><span class="r">Spare</span><span class="r">Cost</span></div>']
        for row in others:
            spare = row["days_to_spare"]
            lines.append(candidate_row(row["name"], "Late" if spare < 0 else "On time", explain.short_date(row["eta_date"]), spare,
                                       f"{row['total_cost']:,.0f}", "warn" if spare < 0 else "ok"))
        if not others:
            lines.append('<div class="meta" style="padding:12px 4px">No other permitted workshop.</div>')
        html("".join(lines))
        with st.expander(f"View all candidates ({len(workshops)})"):
            full_table(record, workshops, rows)


def full_table(record, workshops, rows):
    chosen = record.get("chosen_workshop")
    body, classes = [], []
    for kind, row in rows:
        wid = row["workshop_id"]
        if kind in {"permitted", "excluded"}:
            spare = row["days_to_spare"]
            status = "Selected" if wid == chosen else row.get("exclusion_reason") or ("Late" if spare < 0 else "Eligible")
            body.append([f"<b>{esc(row['name'])}</b>", esc(status), esc(explain.short_date(row["eta_date"])),
                         f'<span class="{"neg" if spare < 0 else ""}">{spare:+d}</span>', f"{row['total_cost']:,.0f}"])
            classes.append("chosen" if wid == chosen else "dim" if kind == "excluded" else "")
        else:
            body.append([f"<b>{esc(row['name'])}</b>", f'<span class="wrap">{esc(explain.ineligible_headline(row.get("reason", "")))}</span>', "n/a", "n/a", "n/a"])
            classes.append("dim")
    html(table(["Workshop", "Status", "Back", "Spare", "Cost"], body, right=(2, 3, 4), classes=classes))


def options_card(preview, record, parsed, workshops, queues):
    state = st.session_state
    split = record.get("tool_outputs", {}).get("split") or state["desk_splits"].get(preview.token)
    awkward = record.get("awkward_case") == "none_makes_date"
    with st.container(key="options"):
        if awkward:
            section("Your options", "The system will not decide this for you.")
            html('<div class="grid g3" style="margin-top:10px">'
                 '<div class="card soft"><b>Accept the late return</b><div class="meta" style="font-size:13.5px;margin-top:4px">Use the button on the recommendation. The record marks the lateness as accepted.</div></div>'
                 '<div class="card soft"><b>Preview a split</b><div class="meta" style="font-size:13.5px;margin-top:4px">Fastest legal two-workshop split. A preview only.</div></div>'
                 '<div class="card soft"><b>Escalate</b><div class="meta" style="font-size:13.5px;margin-top:4px">Leave it unconfirmed and raise it with the planner or customer.</div></div></div>')
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
    parts = "".join(f'<div class="card soft"><b>{esc(p["name"])}</b><div class="meta" style="font-size:13.5px;margin-top:4px">'
                    f'{p["pieces"]:,} pieces, back {esc(explain.short_date(p["eta_date"]))}, cost {p["total_cost"]:,.0f}</div></div>' for p in split["parts"])
    single = split.get("single")
    compare = ""
    if single:
        compare = (f'Whole batch at {esc(single["name"])}: back {esc(explain.short_date(single["eta_date"]))}. '
                   + (f'The split saves {split["days_saved"]:.1f} days' if split.get("faster") else "The split is not faster")
                   + ("" if split.get("earlier_eta") or not split.get("faster") else ", but the return date is the same") + ".")
    html(f'<div style="margin-top:14px;display:flex;justify-content:space-between;align-items:center"><div class="title" style="font-size:17px">Split preview</div>'
         f'{status_pill("Preview only", "muted")}</div><div class="meta" style="font-size:13.5px;margin:4px 0 10px">Both parts run in parallel. '
         f'Completion is the later part: {esc(explain.short_date(split["eta_date"]))}, {split["days_to_spare"]:+d} days to spare, combined cost '
         f'{split["total_cost"]:,.0f}. {compare}</div><div class="grid g2">{parts}</div>')


def clarify_card(parsed, record, workshops):
    state = st.session_state
    options = record.get("tool_outputs", {}).get("order_options", [])
    prompt = explain.clarify_prompt(parsed.to_dict(), options)
    source = rehearsal.SOURCES[state["desk_source"]]
    with st.container(key="clarify"):
        html(f'<div class="say">I need one detail before I can continue.</div><div class="ask">{esc(prompt["question"])}</div>')
        if prompt["missing"]:
            html('<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">' + "".join(status_pill(m, "warn") for m in prompt["missing"]) + "</div>")
        if prompt["options"]:
            cols = st.columns(min(len(prompt["options"]), 3))
            for i, option in enumerate(prompt["options"]):
                with cols[i % len(cols)]:
                    st.button(f"**{option['order_id']}**  {option['product']}, {option['pieces']:,} pieces, {option['current_stage'].lower()}",
                              key=f"desk_option_{option['order_id']}", width="stretch", on_click=append_reply, args=(option["order_id"],))
        reply_col, add_col = st.columns([3, 1], vertical_alignment="bottom")
        with reply_col:
            st.text_input(f"Reply from {parsed.sender or 'the sender'}", key="desk_reply", placeholder="Type the missing detail")
        with add_col:
            st.button("Add to request", key="desk_add_reply", on_click=append_reply, width="stretch",
                      disabled=not state.get("desk_reply", "").strip())
        note = "Nothing has been allocated. The reply is added to the request; evaluate again to read it."
        if source.rehearsal:
            note += " Rehearsal covers the original inbox lines only, so a reply needs the live model."
        html(f'<div class="meta" style="font-size:13px;margin-top:6px">{esc(note)}</div>')
    if st.button("Why this decision?", key="desk_inspect", icon=":material/insights:"):
        inspector(workshops)


def decline_card(parsed, orders, workshops):
    if parsed.reason == "order not found":
        needed = f"An order record for {parsed.order_id or 'the named order'}. It is not among the {len(orders)} orders in orders.csv."
    else:
        needed = DATA_NEEDED.get(parsed.question_topic, "The source records that hold this information.")
    with st.container(key="decline"):
        html('<div class="say">This information is not available in the supplied data.</div>'
             '<div class="ask">The desk answers from orders, workshop profiles and the inbox. It does not guess.</div>'
             f'<div class="grid g2" style="margin-top:16px"><div class="card soft"><b>Missing source</b><div class="meta" style="font-size:13.5px;margin-top:4px">{esc(needed)}</div></div>'
             f'<div class="card soft"><b>Sources available</b><div class="meta" style="font-size:13.5px;margin-top:4px">orders.csv ({len(orders)} orders), workshops.csv '
             '(8 profiles), the 30-message inbox.</div></div></div>')
    if st.button("Why this decision?", key="desk_inspect", icon=":material/insights:"):
        inspector(workshops)


# Decision inspector: a slide-over panel -------------------------------------------

@st.dialog("Decision inspector", width="large")
def inspector(workshops):
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
    why, why_not, breakdown, trace = st.tabs(["Why this won", "Why not another", "Score breakdown", "Evidence trace"])
    with why:
        why_tab(record)
    with why_not:
        why_not_tab(record, workshops)
    with breakdown:
        breakdown_tab(record)
    with trace:
        trace_tab(response, steps)


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
    html(f'<div class="dk-card beam" style="margin:6px 0 14px"><div class="eyebrow" style="color:var(--cyan)">Why this won</div>'
         f'<p style="font-size:17px;margin:6px 0 0">{esc(won["sentence"])}</p></div>')
    other = won.get("runner_up")
    if other is not None:
        html(compare_grid(explain.deciding_metrics(record, chosen, other), chosen["name"], other["name"]))
        html(f'<p class="ev" style="margin-top:10px">Only the measures the {esc(explain.objective_label(record["objective_name"]).lower())} '
             f'rule used are shown. {esc(other["name"])} is the next option under the same rule.</p>')
    else:
        html('<p class="ev">No other permitted workshop remained, so there is nothing to compare.</p>')


def why_not_tab(record, workshops):
    chosen = explain.chosen_row(record)
    state = st.session_state
    others = [wid for wid in workshops if wid != record.get("chosen_workshop")]
    runner = explain.runner_up(record)
    if state.get("desk_whynot") not in others:
        state["desk_whynot"] = runner["workshop_id"] if runner else others[0]
    pick = st.pills("Workshop", others, key="desk_whynot", format_func=lambda wid: workshops[wid].name, label_visibility="collapsed")
    if not pick:
        return
    verdict = explain.why_not(record, pick, workshops)
    tone = {"Eligible": "dark", "Not eligible": "dark-risk", "Excluded": "dark-risk"}.get(verdict["verdict"], "dark-muted")
    facts = "".join(f"<li>{esc(f)}</li>" for f in (verdict["facts"] or verdict["detail"]))
    result_line = f'<div class="dk-result"><b>Result</b> {esc(verdict["result"])}</div>' if verdict["result"] else ""
    html(f'<div class="dk-card" style="margin-top:6px"><div class="dk-head"><b>{esc(verdict["name"])}</b>{status_pill(verdict["verdict"], tone)}</div>'
         f'<div class="ev" style="margin-top:4px">{esc(verdict["headline"])}</div><ul class="dk-list">{facts}</ul>{result_line}</div>')
    if chosen is not None and verdict.get("row") is not None and verdict["status"] in {"outscored", "later", "misses_date"}:
        html('<div style="height:12px"></div>' + compare_grid(explain.deciding_metrics(record, chosen, verdict["row"]), chosen["name"], verdict["name"]))


def breakdown_tab(record):
    chosen = explain.chosen_row(record)
    if chosen is None:
        html('<p class="ev">Scores exist only once workshops are evaluated.</p>')
        return
    config = explain.effective_config(record["objective_name"])
    runner = explain.runner_up(record)
    html(f'<div class="eyebrow" style="color:var(--cyan);margin:4px 0 12px">Objective weights, {esc(explain.objective_label(record["objective_name"]).lower())}</div>'
         + weight_bars(config, explain.TERMS, explain.TERM_LABELS))
    other = f'<span class="ev">{esc(runner["name"])} {runner["score"]:.5f}</span>' if runner else ""
    html(f'<div class="final" style="margin-top:16px"><b>Final score, lower wins</b><div style="text-align:right"><strong>{chosen["score"]:.5f}</strong><br>{other}</div></div>')
    order = explain.selection_order(record)[:6]
    html('<div class="eyebrow" style="color:var(--cyan);margin:20px 0 10px">Weighted contribution per candidate</div>'
         + score_bars(explain.score_breakdown(order, config), chosen["workshop_id"], explain.TERMS, explain.TERM_LABELS))
    note = ("Every option is late, so the least-late rule chose the workshop, not the weighted score."
            if record.get("awkward_case") == "none_makes_date" else explain.TERM_NOTES["lateness"] if config.w_lateness else "")
    if note:
        html(f'<p class="ev" style="margin-top:12px">{esc(note)}</p>')


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
    html('<p class="ev" style="margin:2px 0 10px">Recorded program events, in order. These are tool calls and checks that actually ran, not model reasoning.</p>')
    icons = {"done": ":material/radio_button_checked:", "pending": ":material/radio_button_unchecked:",
             "blocked": ":material/block:", "skipped": ":material/radio_button_unchecked:"}
    who = {"model": "Language model", "fixture": "Test fixture", "python": "Python", "human": "Dispatcher"}
    with st.container(key="trace"):
        for number, step in enumerate(steps, 1):
            label = step["title"] + (", not needed" if step["status"] == "skipped" else "")
            with st.container(key=f"tr_{step['status']}_{number}"), st.expander(label, expanded=False, icon=icons[step["status"]]):
                html(f'<p class="ev" style="margin:0">{esc(step["summary"])}</p><p class="ev" style="margin:2px 0 0;font-size:12px">'
                     f'Performed by {esc(who[step["actor"]])}</p>' + evidence_view(step))
                if step.get("evidence") is not None:
                    with st.container(key=f"dev_trace_{number}"):
                        if st.toggle("View raw evidence", key=f"raw_{number}"):
                            json_block(step["evidence"], height=240)
    with st.container(key="dev_download"):
        st.download_button("Download decision record", json.dumps(response.to_dict(), indent=2, default=str),
                           file_name=f"{response.parsed_request.order_id or 'request'}-decision.json", mime="application/json",
                           key="desk_download")
