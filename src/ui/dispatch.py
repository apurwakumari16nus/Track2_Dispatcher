"""Dispatch: inbox, request, recommendation, alternatives, confirmation, inspector.

Rendering only. Extraction runs through intake.extraction_source; everything
after the raw reply is the unchanged agent/allocator/tools/faithfulness path in
desk.make_preview. Stage progress reflects real stage transitions and the
recorded tool trace, never model reasoning.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json

import streamlit as st

import desk
import intake
from objectives import PRESETS
import rehearsal
import tools
from ui import explain
from ui.components import TERM_CLASS, banner, esc, h3, html, json_block, score_bars, table, tag

VERDICTS = {"allocate": ("Recommendation ready", "info"), "clarify": ("Needs a reply", "warn"),
            "refuse": ("Requested workshop refused", "risk"), "decline": ("Cannot answer", "muted")}
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


# Stage progress -------------------------------------------------------------------

def stages_html(stages) -> str:
    marks = {"done": "✓", "blocked": "!", "skipped": "", "active": "", "idle": ""}
    cells = "".join(f'<div class="stage {status}"><div class="ic">{marks.get(status, "")}</div>'
                    f'<div style="min-width:0"><b>{esc(label)}</b><span>{esc(detail if status != "skipped" else "Not needed")}</span></div></div>'
                    for _, label, detail, status in stages)
    return f'<div class="stages" role="list" aria-label="Decision stages">{cells}</div>'


def live_stages(active: str):
    keys = [key for key, _, _ in explain.STAGES]
    index = keys.index(active)
    return [(key, label, detail, "done" if i < index else "active" if i == index else "idle")
            for i, (key, label, detail) in enumerate(explain.STAGES)]


# Page ---------------------------------------------------------------------------

def render(orders, workshops, messages):
    state = st.session_state
    title, date_col, objective_col, health_col = st.columns([2.3, .72, 1, .95], vertical_alignment="bottom")
    with title:
        html('<div class="page-title">Quick Response Subcontracting Desk</div>'
             '<div class="page-sub">Turn a request into a checked workshop decision.</div>')
    with date_col:
        today = st.date_input("Scenario date", key="desk_today", min_value=state["desk_queue_date"], on_change=invalidate,
                              format="DD/MM/YYYY")
    with objective_col:
        preset = st.selectbox("Objective", list(PRESETS), key="desk_preset", on_change=invalidate,
                              format_func=explain.objective_label)
    with health_col:
        system_health(workshops, messages)
    config = PRESETS[preset]
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)

    inbox_col, work_col = st.columns([1, 2.55], gap="large")
    with inbox_col:
        inbox(messages)
    with work_col:
        workspace(orders, workshops, today, config, queues)


def system_health(workshops, messages):
    state = st.session_state
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    live = rehearsal.live_status()
    source = rehearsal.SOURCES[state["desk_source"]]
    html('<div data-testid="stWidgetLabel"><p style="font-size:13px;color:var(--text-2);font-weight:600;margin:0 0 6px">System health</p></div>')
    with st.popover(f"Ready, {len(workshops)} workshops", icon=":material/check_circle:", width="stretch"):
        language = (source.label if source.rehearsal else f"Live model, {live['model']}" if live["ready"] else "Not configured")
        rows = [("Allocation engine", "Ready"), ("Workshops", f"{len(workshops)} on the register, {active} active"),
                ("Queues", f"As of {explain.long_date(state['desk_queue_date'])}"),
                ("Language intake", language), ("Confirmed this session", str(len(state["desk_saved"])))]
        html('<dl class="kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")
        if not source.rehearsal and not live["ready"]:
            html('<div class="note" style="margin-top:10px">Language intake needs a model in .env, or a rehearsal source '
                 'in System settings. Allocation, the register and the Simulation Lab work without it.</div>')


def inbox(messages):
    state = st.session_state
    html(f'<div class="inbox-head"><div class="h3">Inbox</div><div class="meta">{len(messages)} requests, 1 Apr 2026</div></div>')
    query = st.text_input("Search inbox", placeholder="Search sender, order or text", key="inbox_search", label_visibility="collapsed")
    filtered = [m for m in messages if query.casefold() in m.casefold()]
    outcomes = state.get("desk_outcomes", {})
    with st.container(height=690, key="inbox_list", border=False):
        for message in filtered:
            rid, time, sender, body = envelope(message)
            colour = {"Confirmed": "green", "Needs reply": "orange", "Cannot answer": "gray"}.get(outcomes.get(rid), "blue")
            status = f"   :{colour}[{outcomes[rid]}]" if rid in outcomes else ""
            st.button(f"**{sender}**  {time}{status}\n{body}", key="inbox_" + rid, width="stretch",
                      type="primary" if state["desk_message"] == message else "secondary",
                      on_click=select_message, args=(message,))
        if not filtered:
            html(banner("No match", " Clear the search to see all requests.", "muted"))


def workspace(orders, workshops, today, config, queues):
    state = st.session_state
    message = state["desk_message"]
    with st.container(key="composer"):
        rid, time, sender, body = envelope(message)
        head_col, new_col, run_col = st.columns([3, 1, 1.1], vertical_alignment="center")
        with head_col:
            if rid:
                html(f'<div class="req-head"><div class="avatar">{esc(sender[:1])}</div><div><b>{esc(sender)}</b><br>'
                     f'<span>{esc(time)}, request {esc(rid)}</span></div></div>')
            else:
                html('<div class="req-head"><div class="avatar">+</div><div><b>New request</b><br>'
                     '<span>Type the chat message, or pick one from the inbox</span></div></div>')
        with new_col:
            st.button("New request", key="desk_new", width="stretch", on_click=select_message, args=("",))
        with run_col:
            run = st.button("Run decision", key="desk_dispatch", type="primary", width="stretch", disabled=not message.strip())
        if rid:
            html(f'<div class="bubble">{esc(body)}</div>')
            with st.expander("Edit request text"):
                st.text_area("Request", key="desk_message", height=84, label_visibility="collapsed", on_change=invalidate)
        else:
            st.text_area("Request", key="desk_message", height=84, label_visibility="collapsed", on_change=invalidate,
                         placeholder="For example: ORD-045, 150 vests for Cotton Club, due Apr 09. Fastest turnaround please.")

    current_signature = desk.signature(message, today, config, orders, workshops, queues, state["desk_revision"], state["desk_source"])
    progress = st.empty()
    if run and message.strip():
        run_decision(progress, orders, workshops, today, config, queues)
    preview = state.get("desk_preview")
    if state.get("desk_error"):
        progress.empty()
        error_card(state["desk_error"])
    elif preview:
        result(preview, current_signature, workshops, orders, queues, progress)
    elif message.strip():
        html('<div class="note" style="padding:4px 2px">Run the decision to check the order and every workshop. Nothing is recorded until you confirm.</div>')
    else:
        html('<div class="card soft" style="padding:28px 28px"><div class="say">Pick a request to begin.</div>'
             '<div class="ask">Python verifies the request and ranks eligible workshops. You approve the final decision.</div></div>')


def run_decision(progress, orders, workshops, today, config, queues):
    state = st.session_state
    invalidate()
    progress.markdown(stages_html(live_stages("understand")), unsafe_allow_html=True)

    def reply_arrived():
        progress.markdown(stages_html(live_stages("validate")), unsafe_allow_html=True)

    call = rehearsal.make_source(state["desk_source"], on_reply=reply_arrived)
    try:
        with intake.extraction_source(call):
            preview = desk.make_preview(state["desk_message"], today, config, orders, workshops, queues,
                                        state["desk_allocator"], state["desk_revision"], state["desk_source"])
    except Exception as error:
        known = isinstance(error, (intake.IntakeError, ValueError))
        state["desk_error"] = {"text": str(error) if known else f"{type(error).__name__}. Check the connection and run again.",
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
    progress.markdown(stages_html(explain.stage_status(steps)), unsafe_allow_html=True)
    summary(parsed)
    if status.state == "stale":
        html(banner("Inputs changed", " The request, date, objective or queue changed after this decision. Run it again before confirming.", "warn"))
    if response.already_late:
        html(banner("Already late", f" The due date, {explain.long_date(parsed.due_date)}, is on or before the scenario date, "
                    f"{explain.long_date(preview.today)}. Any return will be late.", "risk"))
    chosen = explain.chosen_row(record)
    if parsed.behaviour == "refuse":
        rejected = next((r for r in record.get("tool_outputs", {}).get("eligibility", [])
                         if r["workshop_id"] == parsed.suggested_workshop and not r["eligible"]), None)
        if rejected:
            html(banner(f"{rejected['name']} cannot accept this batch.", f" Reason: {explain.reason_text(rejected['reason'])}"
                        + (" The best permitted alternative is below." if chosen else ""), "risk"))
    if record.get("awkward_case") == "none_makes_date" and chosen:
        html(banner(f"No eligible workshop can meet {explain.short_date(parsed.due_date)}.",
                    f" Earliest achievable: {explain.short_date(chosen['eta_date'])} at {chosen['name']}. You decide what happens next.", "warn"))

    if chosen is not None:
        rec_col, alt_col = st.columns([1.18, 1], gap="medium")
        with rec_col:
            recommendation(preview, chosen, record, parsed, workshops, status)
        with alt_col:
            alternatives(record, workshops)
        if record.get("awkward_case") == "none_makes_date" or record.get("tool_outputs", {}).get("split"):
            options_card(preview, record, parsed, workshops, queues)
        inspector(preview, record, response, workshops, steps)
    elif parsed.behaviour == "clarify":
        clarify_card(response, parsed, record)
        inspector(preview, record, response, workshops, steps)
    elif parsed.behaviour == "decline":
        decline_card(response, parsed, orders)
        inspector(preview, record, response, workshops, steps)
    else:
        html(banner("No eligible workshop remains", " Every workshop is excluded or ineligible for this batch. Leave it unconfirmed and escalate.", "risk"))
        alternatives(record, workshops)
        inspector(preview, record, response, workshops, steps)


def summary(parsed):
    items = [("Order", parsed.order_id), ("Customer", parsed.customer), ("Product", parsed.product),
             ("Pieces", f"{parsed.pieces:,}" if parsed.pieces else None),
             ("Due", explain.long_date(parsed.due_date) if parsed.due_date else None),
             ("Preference", explain.PREFERENCE_LABELS.get(parsed.preference))]
    verdict, tone = VERDICTS[parsed.behaviour]
    html('<div class="summary">' + tag(verdict, tone) + "".join(f'<span>{esc(k)} <b>{esc(v)}</b></span>' for k, v in items if v) + "</div>")


def recommendation(preview, chosen, record, parsed, workshops, status):
    state = st.session_state
    awkward = record.get("awkward_case") == "none_makes_date"
    label = ("Least-late option" if awkward else "Best permitted alternative" if parsed.behaviour == "refuse" else "Recommended")
    passed = (preview.response.faithfulness or {}).get("passed")
    evidence = tag("Evidence verified", "dark-ok") if passed else tag("Evidence check failed", "risk")
    won = explain.why_won(record)
    spare = chosen["days_to_spare"]
    metrics = [("Back by", explain.short_date(chosen["eta_date"]), f"Due {explain.short_date(chosen['due_date'])}", ""),
               ("Days late" if spare < 0 else "Spare", explain.days(abs(spare)), f"{chosen['total_days']:.1f} days in total", "late" if spare < 0 else ""),
               ("Cost", f"{chosen['total_cost']:,.0f}", f"{chosen['cost_per_piece']:g} per piece", ""),
               ("Defect risk", f"{chosen['expected_defect_rate']:.0%}", "Per batch", "")]
    tiles = "".join(f'<div class="{cls}"><small>{esc(a)}</small><strong>{esc(b)}</strong><em>{esc(c)}</em></div>' for a, b, c, cls in metrics)
    makes = " and ".join(sorted(m.lower() for m in workshops[chosen["workshop_id"]].makes))
    objective = explain.objective_label(record["objective_name"])
    if parsed.preference:
        objective += f", from the request ({explain.PREFERENCE_LABELS.get(parsed.preference, parsed.preference).lower()})"
    state_cls = "rec-done" if status.state == "confirmed" else "rec-late" if awkward else ""
    with st.container(key="rec"):
        html(f'<div class="{state_cls}"><div class="rec-top"><span class="rec-label">{esc(label)}</span>{evidence}</div>'
             f'<div class="rec-name">{esc(chosen["name"])}</div><div class="rec-sub">Workshop {esc(chosen["workshop_id"])}, makes {esc(makes)}</div>'
             f'<div class="rec-metrics">{tiles}</div>'
             f'<div class="rec-why"><small>Why this won</small><p>{esc(won["sentence"] if won else record["reason_chosen"])}</p></div>'
             f'<div class="rec-foot"><span>Objective: {esc(objective)}</span></div></div>')
        if status.state == "confirmed":
            done_col, link_col = st.columns([1.5, 1], vertical_alignment="center")
            with done_col:
                html('<div class="confirm-note"><b>Decision confirmed.</b> Audit record created. Queue updated.<br>'
                     f'No message has been sent to {esc(chosen["name"])}.</div>')
            with link_col:
                st.button("View in Audit Trail", key="desk_view_audit", width="stretch", on_click=open_audit)
        else:
            confirm_label = ("Accept late return" if awkward else "Accept alternative" if parsed.behaviour == "refuse" else "Confirm allocation")
            if st.button(confirm_label, key="desk_confirm", type="primary", width="stretch", disabled=not status.ready):
                confirm(preview)
            note = status.reason if not status.ready else "Confirming records the decision and updates the session queue. No workshop is contacted."
            html(f'<div class="confirm-note">{esc(note)}</div>')
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
    excluded = [(kind, row) for kind, row in rows if kind != "permitted"]
    with st.container(key="alternatives"):
        html(f'<div class="inbox-head"><div class="h3">Top alternatives</div><div class="meta">{len(permitted)} permitted of {len(workshops)}</div></div>')
        lines = ['<div class="alt head"><span>Workshop</span><span class="r">Return</span><span class="r">Spare</span><span class="r">Cost</span><span>Status</span></div>']
        for row in permitted[:4]:
            spare = row["days_to_spare"]
            status = tag("Selected", "info") if row["workshop_id"] == chosen else tag("Late", "warn") if spare < 0 else tag("On time", "ok")
            lines.append(f'<div class="alt{" chosen" if row["workshop_id"] == chosen else ""}"><span class="nm"><b>{esc(row["name"])}</b><span>{esc(row["workshop_id"])}</span></span>'
                         f'<span class="r">{esc(explain.short_date(row["eta_date"]))}</span><span class="r {"neg" if spare < 0 else ""}">{spare:+d}</span>'
                         f'<span class="r">{row["total_cost"]:,.0f}</span><span>{status}</span></div>')
        html(f'<div class="alts">{"".join(lines)}</div>')
        with st.expander(f"View all workshops ({len(workshops)})"):
            full_table(record, workshops, rows)
        if excluded:
            with st.expander(f"Excluded workshops ({len(excluded)})"):
                for kind, row in excluded:
                    reason = (row.get("exclusion_reason") or "Not permitted") if kind == "excluded" else explain.ineligible_headline(row.get("reason", ""))
                    detail = (explain.reason_text(row["reason"]) if kind == "ineligible" else
                              " ".join(explain.constraint_sources(record, row["workshop_id"], row["name"])) if reason == "Excluded by request" else
                              f"Back {explain.short_date(row['eta_date'])}, {explain.days(explain.late_days(row))} late." if kind == "excluded" else "")
                    html(f'<div style="display:flex;justify-content:space-between;gap:12px;padding:6px 0"><div><b>{esc(row["name"])}</b>'
                         f'<div class="note">{esc(detail)}</div></div>{tag(reason, "risk" if kind == "ineligible" else "warn")}</div>')


def full_table(record, workshops, rows):
    chosen = record.get("chosen_workshop")
    body, classes = [], []
    for kind, row in rows:
        wid = row["workshop_id"]
        if kind in {"permitted", "excluded"}:
            spare = row["days_to_spare"]
            status = "Selected" if wid == chosen else row.get("exclusion_reason") or ("Late" if spare < 0 else "Eligible")
            body.append([f"<b>{esc(row['name'])}</b><small>{esc(wid)}</small>", esc(status), f"{row['queue_days']:.1f}",
                         f"{row['processing_days']:.1f}", str(row["lead_days"]), esc(explain.short_date(row["eta_date"])),
                         f'<span class="{"neg" if spare < 0 else ""}">{spare:+d}</span>', f"{row['total_cost']:,.0f}",
                         f"{row['expected_defect_rate']:.0%}"])
            classes.append("chosen" if wid == chosen else "dim" if kind == "excluded" else "")
        else:
            body.append([f"<b>{esc(row['name'])}</b><small>{esc(wid)}</small>", esc(explain.ineligible_headline(row.get("reason", "")))] + ["n/a"] * 7)
            classes.append("dim")
    html(table(["Workshop", "Status", "Queue d", "Making d", "Transport d", "Return", "Spare", "Cost", "Defect"], body,
               right=range(2, 9), classes=classes))


def options_card(preview, record, parsed, workshops, queues):
    state = st.session_state
    split = record.get("tool_outputs", {}).get("split") or state["desk_splits"].get(preview.token)
    awkward = record.get("awkward_case") == "none_makes_date"
    with st.container(key="options"):
        if awkward:
            h3("Your options", "The system will not decide this for you.")
            html('<div class="grid g3" style="margin-top:8px">'
                 '<div class="card flat"><b>Accept the late return</b><div class="note">Use the button on the recommendation. The record marks the lateness as accepted.</div></div>'
                 '<div class="card flat"><b>Preview a split</b><div class="note">Fastest legal two-workshop split. A preview only.</div></div>'
                 '<div class="card flat"><b>Escalate</b><div class="note">Leave it unconfirmed and raise it with the planner or customer.</div></div></div>')
        if split is None and awkward:
            if st.button("Preview a two-workshop split", key="desk_split"):
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
    parts = "".join(f'<div class="card flat"><b>{esc(p["name"])}</b><div class="note">{p["pieces"]:,} pieces, back {esc(explain.short_date(p["eta_date"]))}, '
                    f'cost {p["total_cost"]:,.0f}</div></div>' for p in split["parts"])
    single = split.get("single")
    compare = ""
    if single:
        compare = (f'Whole batch at {esc(single["name"])}: back {esc(explain.short_date(single["eta_date"]))}. '
                   + (f'The split saves {split["days_saved"]:.1f} days' if split.get("faster") else "The split is not faster")
                   + ("" if split.get("earlier_eta") or not split.get("faster") else ", but the return date is the same") + ".")
    html(f'<div style="margin-top:12px"><div class="inbox-head"><div class="h3">Split preview</div>{tag("Preview only", "muted")}</div>'
         f'<div class="note" style="margin:4px 0 10px">Both parts run in parallel. Completion is the later part: {esc(explain.short_date(split["eta_date"]))}, '
         f'{split["days_to_spare"]:+d} days to spare, combined cost {split["total_cost"]:,.0f}. {compare}</div><div class="grid g2">{parts}</div></div>')


def clarify_card(response, parsed, record):
    state = st.session_state
    options = record.get("tool_outputs", {}).get("order_options", [])
    prompt = explain.clarify_prompt(parsed.to_dict(), options)
    source = rehearsal.SOURCES[state["desk_source"]]
    with st.container(key="clarify"):
        html(f'<div class="say">I need one detail before I can continue.</div><div class="ask">{esc(prompt["question"])}</div>')
        if prompt["missing"]:
            html('<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">' + "".join(tag(m, "warn") for m in prompt["missing"]) + "</div>")
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
        note = "Nothing has been allocated. The reply is added to the request; run the decision again to read it."
        if source.rehearsal:
            note += " Rehearsal covers the original inbox lines only, so a reply needs the live model."
        html(f'<div class="option-note" style="margin-top:6px">{esc(note)}</div>')


def decline_card(response, parsed, orders):
    if parsed.reason == "order not found":
        needed = f"An order record for {parsed.order_id or 'the named order'}. It is not among the {len(orders)} orders in orders.csv."
    else:
        needed = DATA_NEEDED.get(parsed.question_topic, "The source records that hold this information.")
    with st.container(key="decline"):
        html('<div class="say">This information is not available in the supplied data.</div>'
             '<div class="ask">The desk answers from orders, workshop profiles and the inbox. It does not guess.</div>'
             f'<div class="grid g2" style="margin-top:14px"><div class="card flat"><b>Missing source</b><div class="note">{esc(needed)}</div></div>'
             f'<div class="card flat"><b>Sources available</b><div class="note">orders.csv ({len(orders)} orders), workshops.csv (8 profiles), '
             'the 30-message inbox.</div></div></div>')


# Decision inspector -------------------------------------------------------------

def inspector(preview, record, response, workshops, steps):
    with st.expander("Decision details", expanded=False, key="decision_details"):
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
    cells = ['<div class="h">Measure</div>', f'<div class="h">{esc(winner)}</div>', f'<div class="h">{esc(other)}</div>', '<div class="h">Difference</div>']
    for row in rows:
        cls = " same" if row["better"] is None else ""
        cells += [f'<div class="l">{esc(row["label"])}</div>', f'<div class="w">{esc(row["winner"])}</div>',
                  f'<div class="o">{esc(row["other"])}</div>', f'<div class="d{cls}">{esc(row["difference"])}</div>']
    return f'<div class="compare">{"".join(cells)}</div>'


def why_tab(record):
    chosen = explain.chosen_row(record)
    if chosen is None:
        html('<div class="note">There is no recommendation to explain until the request can be allocated.</div>')
        return
    won = explain.why_won(record)
    html(f'<p style="font-size:16px;margin:4px 0 12px">{esc(won["sentence"])}</p>')
    other = won.get("runner_up")
    if other is not None:
        html(compare_grid(explain.deciding_metrics(record, chosen, other), chosen["name"], other["name"]))
        html(f'<div class="note" style="margin-top:10px">Objective: {esc(explain.objective_label(record["objective_name"]))}. '
             f'Only the measures this objective uses are shown. {esc(other["name"])} is the next option under the same rule.</div>')
    else:
        html('<div class="note">No other permitted workshop remained, so there is nothing to compare.</div>')


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
    reason = explain.why_not(record, pick, workshops)
    items = "".join(f"<li>{esc(d)}</li>" for d in reason["detail"])
    html(f'<div class="reason"><div class="rh">{esc(workshops[pick].name)} {tag(reason["headline"], reason["tone"])}</div>'
         + (f"<ul>{items}</ul>" if items else "") + "</div>")
    if chosen is not None and reason.get("row") is not None and reason["status"] in {"outscored", "later", "misses_date"}:
        html('<div style="height:10px"></div>' + compare_grid(explain.deciding_metrics(record, chosen, reason["row"]), chosen["name"], workshops[pick].name))


def breakdown_tab(record):
    chosen = explain.chosen_row(record)
    if chosen is None:
        html('<div class="note">Scores exist only once workshops are evaluated.</div>')
        return
    config = explain.effective_config(record["objective_name"])
    chips = "".join(f'<span class="weight{"" if getattr(config, "w_" + t) else " off"}"><i class="{TERM_CLASS[t]}"></i>{esc(explain.TERM_LABELS[t])} '
                    f'<b>{getattr(config, "w_" + t):g}</b>{"" if getattr(config, "w_" + t) else " inactive"}</span>' for t in explain.TERMS)
    html(f'<div class="note" style="margin-bottom:8px">Weights for {esc(explain.objective_label(record["objective_name"]))}. '
         f'Each bar is the weighted penalty read from the recorded score terms. Lower wins.</div><div class="weights">{chips}</div>')
    order = explain.selection_order(record)[:6]
    html('<div style="height:12px"></div>' + score_bars(explain.score_breakdown(order, config), chosen["workshop_id"], explain.TERMS, explain.TERM_LABELS))
    note = ("Every option is late, so the least-late rule chose the workshop, not the weighted score."
            if record.get("awkward_case") == "none_makes_date" else explain.TERM_NOTES["lateness"] if config.w_lateness else "")
    if note:
        html(f'<div class="note" style="margin-top:10px">{esc(note)}</div>')


def trace_tab(response, steps):
    audit = response.faithfulness or {}
    numbers = list(dict.fromkeys(audit.get("numbers_in_text", [])))
    html(f'<div class="note" style="margin-bottom:10px">Recorded program events, in order. These are tool calls and checks that actually ran. '
         f'Evidence check: {len(numbers)} values in the explanation, {len(audit.get("unmatched", []))} unsupported.</div>')
    marks = {"done": "✓", "pending": "○", "blocked": "!", "skipped": "○"}
    who = {"model": "Language model", "fixture": "Test fixture", "python": "Python", "human": "Dispatcher"}
    with st.container(key="trace"):
        for number, step in enumerate(steps, 1):
            label = f"{marks[step['status']]}  {step['title']}" + (", not needed" if step["status"] == "skipped" else "")
            with st.expander(label, expanded=False):
                html(f'<div class="note">{esc(step["summary"])}</div><div class="meta" style="margin-top:4px">Performed by {esc(who[step["actor"]])}</div>')
                if step.get("evidence") is not None:
                    with st.container(key=f"dev_trace_{number}"):
                        json_block(step["evidence"], height=260)
    with st.container(key="dev_explanation"):
        with st.expander("Recorded explanation"):
            st.text(response.explanation_text)
        st.download_button("Download decision record", json.dumps(response.to_dict(), indent=2, default=str),
                           file_name=f"{response.parsed_request.order_id or 'request'}-decision.json", mime="application/json",
                           key="desk_download")
