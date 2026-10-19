"""Dispatch: inbox, request, recommendation, decision explorer, confirmation.

Rendering only. Extraction runs through intake.extraction_source; everything
after the raw reply is the unchanged agent/allocator/tools/faithfulness path
in desk.make_preview. The stepper reflects real stage transitions and the
recorded tool trace, never model reasoning.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import json

import streamlit as st

import desk
import intake
from objectives import PRESETS
import rehearsal
import tools
from ui import explain
from ui.components import banner, chip, esc, html, json_block, pill, score_bars, section, table

VERDICTS = {"allocate": ("ALLOCATE", "info"), "clarify": ("NEEDS CLARIFICATION", "warn"),
            "refuse": ("REFUSED", "risk"), "decline": ("CANNOT ANSWER", "muted")}
SCENARIOS = [("R09", "Normal allocation"), ("R01", "Clarification"), ("R08", "Refused workshop"),
             ("R02", "Unanswerable"), ("R30", "Impossible deadline"), ("R28", "Already late")]
MISSING_LABELS = {"order_id": "Which order", "category": "Product category", "pieces": "Quantity",
                  "due_date": "Due date", "workshop_resolution": "Workshop name"}
DATA_NEEDED = {
    "allocation_history": "Historical dispatch records linking customers and orders to workshops",
    "customer_quote": "Customer sales quotations or pricing records",
    "worker_names": "A worker roster and worker-to-order assignments",
}


# State helpers -----------------------------------------------------------------

def invalidate():
    for key in ("desk_preview", "desk_error", "desk_whynot", "desk_confirm_error"):
        st.session_state.pop(key, None)


def select_message(message, autorun=False):
    st.session_state["desk_message"] = message
    st.session_state["desk_autorun"] = autorun
    invalidate()


def append_reply():
    reply = st.session_state.get("desk_reply", "").strip()
    if reply:
        st.session_state["desk_message"] = st.session_state["desk_message"].rstrip() + f" Reply from dispatcher: {reply}"
        st.session_state["desk_reply"] = ""
        invalidate()


def envelope(message: str) -> tuple[str, str, str, str]:
    """(request id, time, sender, body) from an inbox line; blanks for free text."""
    try:
        head, body = message.split("]", 1)
        rid, time = head.split("[", 1)
        sender, text = body.split(":", 1)
        return rid.strip(), time.strip(), sender.strip(), text.strip()
    except ValueError:
        return "", "", "", message.strip()


# Stepper ------------------------------------------------------------------------

def stepper_html(stages) -> str:
    marks = {"done": "✓", "blocked": "!", "pending": "", "skipped": "", "active": "", "idle": ""}
    cells = "".join(
        f'<div class="step {status}{" human" if key == "confirm" else ""}"><i>{marks.get(status, "")}</i><span>{esc(label)}</span></div>'
        for key, label, status in stages)
    return f'<div class="stepper" aria-label="Execution stages">{cells}</div>'


def live_stages(active: str):
    order = [key for key, _ in explain.STAGES]
    index = order.index(active)
    return [(key, label, "done" if i < index else "active" if i == index else "idle")
            for i, (key, label) in enumerate(explain.STAGES)]


# Page ---------------------------------------------------------------------------

def render(orders, workshops, messages):
    state = st.session_state
    source = rehearsal.SOURCES[state["desk_source"]]
    if source.rehearsal:
        html(f'<div class="mode-banner"><span><b>{esc(source.badge)}</b>&nbsp;&nbsp;{esc(source.description)}</span>'
             f'<span>Confirmations go to the rehearsal audit log.</span></div>')

    head, date_col, objective_col = st.columns([2.6, .72, 1.05], vertical_alignment="bottom")
    with head:
        html('<div class="eyebrow">Dispatch</div><div class="page-title">Quick Response Subcontracting Desk</div>'
             '<div class="page-lede">Turn a chat request into a checked workshop decision. The model reads the message; '
             'Python checks, estimates, scores and selects; you confirm.</div>')
    with date_col:
        today = st.date_input("Scenario date", key="desk_today", min_value=state["desk_queue_date"], on_change=invalidate,
                              format="DD/MM/YYYY")
    with objective_col:
        preset = st.selectbox("Objective", list(PRESETS), key="desk_preset", on_change=invalidate,
                              format_func=explain.objective_label)
    config = PRESETS[preset]
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    flags = set(state["desk_allocator"].shock_monitor.flags)
    live = rehearsal.live_status()
    source_chip = (chip(source.label, dot="warn") if source.rehearsal else
                   chip(f"Live model · {live['model']}", dot="ok") if live["ready"] else chip("Live model not configured", dot="risk"))
    html('<div class="chips">'
         + chip(f"workshops · {active} active", str(len(workshops)), dot="ok")
         + chip(f"Queue snapshot {explain.long_date(state['desk_queue_date'])} loaded", dot="ok")
         + chip(f"{explain.objective_label(preset)} active", dot="info")
         + source_chip
         + chip("confirmed this session", str(len(state["desk_saved"])), dot="ok" if state["desk_saved"] else None)
         + (chip("suspect workshop flagged", str(len(flags)), dot="warn") if flags else "")
         + "</div>")

    inbox_col, work_col = st.columns([1, 3.05], gap="large")
    with inbox_col:
        inbox(messages)
    with work_col:
        workspace(orders, workshops, messages, today, config, queues, source)


def inbox(messages):
    state = st.session_state
    html('<div class="section-title">Inbox</div><div class="section-note">SweaterCo group chat · morning of 1 Apr 2026</div>')
    query = st.text_input("Search inbox", placeholder="Search sender, order or text", key="inbox_search", label_visibility="collapsed")
    filtered = [m for m in messages if query.casefold() in m.casefold()]
    outcomes = state.get("desk_outcomes", {})
    with st.container(height=640, key="inbox_list", border=False):
        for message in filtered:
            rid, time, sender, body = envelope(message)
            short = body[:96] + ("…" if len(body) > 96 else "")
            tag = f"  ·  {outcomes[rid]}" if rid in outcomes else ""
            st.button(f"**{rid}**  {sender} · {time}{tag}\n{short}", key="inbox_" + rid, width="stretch",
                      type="primary" if state["desk_message"] == message else "secondary",
                      on_click=select_message, args=(message,))
        if not filtered:
            html(banner("No match", "No request contains that text. Clear the search to see all 30.", "muted"))


def workspace(orders, workshops, messages, today, config, queues, source):
    state = st.session_state
    with st.container(key="composer"):
        rid, time, sender, _ = envelope(state["desk_message"])
        label = f"{rid} · {sender} · {time}" if rid else "New request"
        html(f'<div class="hero-label"><span class="eyebrow">Current request</span><span class="muted" style="font-size:13px">{esc(label)}</span></div>')
        text_col, action_col = st.columns([4.2, 1], vertical_alignment="center")
        with text_col:
            st.text_area("Request", key="desk_message", height=88, label_visibility="collapsed", on_change=invalidate,
                         placeholder="Select a request from the inbox, or type the chat message to dispatch.")
        with action_col:
            dispatch = st.button("Dispatch", key="desk_dispatch", type="primary", width="stretch",
                                 disabled=not state["desk_message"].strip())
            st.button("New request", key="desk_new", width="stretch", on_click=select_message, args=("",))
        with st.container(horizontal=True, key="scenarios", gap="small"):
            html('<span class="muted" style="font-size:13px;padding-top:9px">Scenarios</span>')
            lines = {m.split()[0]: m for m in messages}
            for scenario, name in SCENARIOS:
                if scenario in lines:
                    st.button(f"{scenario} {name}", key=f"scenario_{scenario}", on_click=select_message,
                              args=(lines[scenario], True), type="tertiary")

    current_signature = desk.signature(state["desk_message"], today, config, orders, workshops, queues,
                                       state["desk_revision"], state["desk_source"])
    progress = st.empty()
    autorun = state.pop("desk_autorun", False) and bool(state["desk_message"].strip())
    if (dispatch or autorun) and state["desk_message"].strip():
        run_dispatch(progress, orders, workshops, today, config, queues, source)

    preview = state.get("desk_preview")
    if state.get("desk_error"):
        progress.markdown(stepper_html([(k, l, "blocked" if k == "interpret" else "idle") for k, l in explain.STAGES]), unsafe_allow_html=True)
        error_card(state["desk_error"], source)
    elif preview:
        result(preview, current_signature, workshops, orders, queues, progress)
    else:
        progress.markdown(stepper_html([(k, l, "idle") for k, l in explain.STAGES]), unsafe_allow_html=True)
        empty_state()


def run_dispatch(progress, orders, workshops, today, config, queues, source):
    state = st.session_state
    invalidate()
    progress.markdown(stepper_html(live_stages("interpret")), unsafe_allow_html=True)

    def reply_arrived():
        progress.markdown(stepper_html(live_stages("validate")), unsafe_allow_html=True)

    call = rehearsal.make_source(source.key, on_reply=reply_arrived)
    try:
        with intake.extraction_source(call):
            preview = desk.make_preview(state["desk_message"], today, config, orders, workshops, queues,
                                        state["desk_allocator"], state["desk_revision"], source.key)
    except Exception as error:
        known = isinstance(error, (intake.IntakeError, ValueError))
        state["desk_error"] = (str(error) if known else
                               f"The request could not be processed ({type(error).__name__}). Check the API connection and dispatch again.")
        return
    state["desk_preview"] = preview
    rid = envelope(state["desk_message"])[0]
    if rid:
        state.setdefault("desk_outcomes", {})[rid] = VERDICTS[preview.response.parsed_request.behaviour][0].capitalize()


def empty_state():
    html('<div class="empty"><div class="eyebrow">Ready</div><h3>Select a request to see who should make it.</h3>'
         '<p>Dispatch reads the message, checks the order and every workshop, estimates when each could return the batch, '
         'and recommends one. Nothing is recorded until you confirm.</p>'
         '<div class="lanes"><div class="lane model"><b>Model reads</b><span>Extracts order, quantity, date, preferences and who imposed each constraint. No arithmetic, no decisions.</span></div>'
         '<div class="lane python"><b>Python decides</b><span>Validates facts, checks eligibility, estimates queue + processing + transport, scores and selects.</span></div>'
         '<div class="lane human"><b>You confirm</b><span>Review the evidence. Confirmation writes the audit record and updates this session\'s queue.</span></div></div></div>')


def error_card(message, source):
    html(banner("Request not processed", message, "risk"))
    if not source.rehearsal and not rehearsal.live_status()["ready"]:
        html(banner("Next step", "Add the API key and model to .env and restart, or choose a rehearsal extraction source in the sidebar.", "info"))


# Result -------------------------------------------------------------------------

def result(preview, current_signature, workshops, orders, queues, progress):
    state = st.session_state
    response, record = preview.response, preview.response.decision_record
    parsed = response.parsed_request
    confirmed = preview.token in state["desk_saved"]
    steps = explain.trace_steps(response.to_dict(), agent_calls=preview.agent_calls,
                                replayed=preview.accepted_allocator is not None, confirmed=confirmed,
                                block_reason=preview.block_reason)
    progress.markdown(stepper_html(explain.stage_status(steps)), unsafe_allow_html=True)

    verdict, tone = VERDICTS[parsed.behaviour]
    facts = [parsed.order_id, parsed.customer, parsed.product, f"{parsed.pieces:,} pcs" if parsed.pieces else None,
             f"due {explain.long_date(parsed.due_date)}" if parsed.due_date else None]
    html('<div class="chips verdict-row">' + pill(verdict, tone) + "".join(f'<span class="chip">{esc(f)}</span>' for f in facts if f) + "</div>")

    stale = preview.signature != current_signature and not confirmed
    if stale:
        html(banner("Inputs changed", "The request, date, objective, source or queue changed after this preview. Dispatch again before confirming.", "warn"))
    if response.already_late:
        html(banner("Already late", f"The due date, {explain.long_date(parsed.due_date)}, is on or before the scenario date, "
                    f"{explain.long_date(preview.today)}. Any return will be late.", "risk"))
    if parsed.behaviour == "refuse":
        rejected = next((r for r in record.get("tool_outputs", {}).get("eligibility", [])
                         if r["workshop_id"] == parsed.suggested_workshop and not r["eligible"]), None)
        if rejected:
            html(banner("Requested workshop refused", f"{rejected['name']} ({rejected['workshop_id']}) cannot take this batch: "
                        f"{rejected['reason']}. The best permitted alternative is shown below.", "risk"))
    if record.get("awkward_case") == "none_makes_date":
        html(banner("No eligible workshop meets the requested date",
                    f"Nothing permitted can return this by {explain.long_date(parsed.due_date)}. A human decision is required: "
                    "accept the least-late return, preview a split, or escalate.", "warn"))

    chosen = explain.chosen_row(record)
    if chosen is not None:
        hero_col, side_col = st.columns([1.32, 1], gap="medium")
        with hero_col:
            hero(preview, chosen, record, parsed, workshops, confirmed, stale)
        with side_col:
            candidate_panel(record, workshops)
        if record.get("awkward_case") == "none_makes_date" or record.get("tool_outputs", {}).get("split"):
            options_card(preview, record, parsed, workshops, queues)
    elif parsed.behaviour == "clarify":
        clarify_card(response, parsed, record)
    elif parsed.behaviour == "decline":
        decline_card(response, parsed, orders)
    else:
        html(banner("Escalate", "No eligible whole-batch workshop remains after the request's exclusions. "
                    "Leave this unconfirmed and escalate to a person with the options below.", "risk"))
        candidate_panel(record, workshops)
    explorer(preview, record, response, parsed, workshops, steps)


def hero(preview, chosen, record, parsed, workshops, confirmed, stale):
    state = st.session_state
    awkward = record.get("awkward_case") == "none_makes_date"
    label = ("Least-late option · human decision required" if awkward else
             "Best permitted alternative" if parsed.behaviour == "refuse" else "Recommended")
    audit = preview.response.faithfulness
    evidence = pill("Evidence check passed", "ok") if audit.get("passed") else pill("Evidence check failed", "risk")
    why = explain.why_won(record)
    spare = chosen["days_to_spare"]
    metrics = [
        ("Earliest return" if awkward else "Back by", explain.short_date(chosen["eta_date"]), f"due {explain.short_date(chosen['due_date'])}"),
        ("Days late" if spare < 0 else "Spare", explain.days(abs(spare)), f"{chosen['total_days']:.1f} days total"),
        ("Cost", f"{chosen['total_cost']:,.0f}", f"{chosen['cost_per_piece']:g} per piece"),
        ("Defect risk", f"{chosen['expected_defect_rate']:.0%}", "batch probability"),
    ]
    amber = ' style="color:var(--amber)"'
    tiles = "".join(f'<div><small>{esc(a)}</small><strong{amber if a == "Days late" else ""}>{esc(b)}</strong><em>{esc(c)}</em></div>'
                    for a, b, c in metrics)
    objective = explain.objective_label(record["objective_name"])
    if parsed.preference:
        objective += f" · request preference “{explain.PREFERENCE_LABELS.get(parsed.preference, parsed.preference)}” applied"
    elif record["objective_name"] != state["desk_preset"]:
        objective += " · applied from the request"
    lit = " hero-confirmed" if confirmed else " hero-warn" if awkward else ""
    with st.container(key="hero"):
        html(f'<div class="{lit.strip()}"><div class="hero-label">{pill(label, "warn" if awkward else "info")}{evidence}</div>'
             f'<div class="hero-name">{esc(chosen["name"])}<small>{esc(chosen["workshop_id"])} · {esc(" + ".join(sorted(workshops[chosen["workshop_id"]].makes)))}</small></div>'
             f'<div class="hero-metrics">{tiles}</div>'
             f'<div class="why"><b>Why this won</b><p>{esc(why["sentence"] if why else record["reason_chosen"])}</p></div>'
             f'<div class="objective-line">Objective: {esc(objective)}</div></div>')
        button_col, note_col = st.columns([1, 1.45], vertical_alignment="center")
        confirm_label = ("Confirmed" if confirmed else "Accept late return and confirm" if awkward else
                         "Accept alternative and confirm" if parsed.behaviour == "refuse" else "Confirm allocation")
        with button_col:
            if st.button(confirm_label, key="desk_confirm", type="primary", width="stretch",
                         disabled=confirmed or bool(preview.block_reason) or stale or not audit.get("passed")):
                confirm(preview)
        with note_col:
            if confirmed:
                row = state["desk_saved"][preview.token]
                stamp = row.get("timestamp", "")[:19].replace("T", " ")
                log = "rehearsal audit log" if preview.source != "live" else "audit log"
                html(f'<div class="section-note" style="color:var(--green)">Confirmed · Audit record created · Session queue updated</div>'
                     f'<div class="section-note">Saved {esc(stamp)} UTC to the {log}. No message has been sent to {esc(chosen["name"])}.</div>')
            elif preview.block_reason:
                html(f'<div class="section-note">{esc(preview.block_reason)}</div>')
            elif stale:
                html('<div class="section-note">Dispatch again to confirm the current inputs.</div>')
            else:
                html('<div class="section-note"><b style="color:var(--text-2)">Preview only.</b> Confirming records this decision and '
                     'updates this session\'s queue. No workshop is contacted.</div>')
    if state.get("desk_confirm_error"):
        html(banner("Audit record not saved", state["desk_confirm_error"], "risk"))


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
    """Every workshop once: permitted in selection order, then excluded, then ineligible."""
    order = explain.selection_order(record)
    seen = {row["workshop_id"] for row in order}
    rows = [("permitted", row) for row in order]
    rows += [("excluded", row) for row in explain.inventory(record) if row["workshop_id"] not in seen]
    seen |= {row["workshop_id"] for _, row in rows}
    rows += [("ineligible", row) for row in explain.eligibility_rows(record) if row["workshop_id"] not in seen and not row["eligible"]]
    seen |= {row["workshop_id"] for _, row in rows}
    rows += [("unknown", {"workshop_id": wid, "name": w.name}) for wid, w in workshops.items() if wid not in seen]
    return rows


def candidate_panel(record, workshops):
    chosen = record.get("chosen_workshop")
    out = ['<div class="cand head"><span>Workshop</span><span class="r">Back</span><span class="r">Spare</span><span class="r">Cost</span></div>']
    for kind, row in ordered_rows(record, workshops):
        wid = row["workshop_id"]
        if kind == "permitted":
            sub = "Recommended" if wid == chosen else ("Late" if row["days_to_spare"] < 0 else "Eligible · on time")
            spare = row["days_to_spare"]
            out.append(f'<div class="cand{" chosen" if wid == chosen else ""}"><span class="nm"><b>{esc(row["name"])}</b><em>{esc(wid)} · {esc(sub)}</em></span>'
                       f'<span class="r">{esc(explain.short_date(row["eta_date"]))}</span>'
                       f'<span class="r {"late" if spare < 0 else "ok"}">{spare:+d}</span>'
                       f'<span class="r">{row["total_cost"]:,.0f}</span></div>')
        elif kind == "excluded":
            reason = row.get("exclusion_reason") or "Not permitted"
            out.append(f'<div class="cand dim"><span class="nm"><b>{esc(row["name"])}</b><em>{esc(wid)} · {esc(reason)}</em></span>'
                       f'<span class="r">{esc(explain.short_date(row["eta_date"]))}</span><span class="r">{row["days_to_spare"]:+d}</span>'
                       f'<span class="r">{row["total_cost"]:,.0f}</span></div>')
        else:
            reason = explain.ineligible_headline(row["reason"]) if kind == "ineligible" else "Not evaluated"
            out.append(f'<div class="cand dim"><span class="nm"><b>{esc(row["name"])}</b><em>{esc(wid)} · {esc(reason)}</em></span>'
                       f'<span class="r">n/a</span><span class="r">n/a</span><span class="r">n/a</span></div>')
    with st.container(key="panel_candidates"):
        html('<div class="hero-label"><span class="section-title">Candidate comparison</span>'
             + pill(f"{len(record.get('candidates', []))} permitted", "muted", soft=True) + '</div>'
             '<div class="section-note" style="margin-bottom:8px">All eight workshops. Permitted options in decision order; exclusions stay visible.</div>'
             f'<div class="cands">{"".join(out)}</div>')


def options_card(preview, record, parsed, workshops, queues):
    state = st.session_state
    split = record.get("tool_outputs", {}).get("split") or state["desk_splits"].get(preview.token)
    awkward = record.get("awkward_case") == "none_makes_date"
    with st.container(key="panel_options", border=False):
        if awkward:
            section("Human decision required", "Choose one. The system will not decide this for you.")
            html('<div class="grid c3">'
                 '<div class="lane human"><b>Accept lateness</b><span>Use the confirm button above. The audit record marks the late return as accepted.</span></div>'
                 '<div class="lane python"><b>Preview a split</b><span>Estimate the fastest legal two-workshop split. Preview only; splits cannot be confirmed here.</span></div>'
                 '<div class="lane model" style="border-color:rgba(255,112,104,.3)"><b style="color:var(--coral)">Escalate</b><span>Leave this unconfirmed and raise it with the planner or customer.</span></div></div>')
        if split is None and awkward:
            if st.button("Estimate a two-workshop split", key="desk_split"):
                batch = {"order_id": parsed.order_id, "pieces": parsed.pieces, "category": parsed.category,
                         "due_date": parsed.due_date, "sent_date": preview.today}
                state["desk_splits"][preview.token] = tools.estimate_split(
                    batch, workshops, queues, preview.today, record["constraints_applied"]["exclude"], record["chosen_workshop"])
                st.rerun()
        if split is not None:
            split_card(split)


def split_card(split):
    if not split.get("available"):
        html(banner("Split preview", "No legal two-workshop split is available: " + split.get("reason", "") + ".", "muted"))
        return
    parts = "".join(f'<div class="lane python"><b>{esc(p["name"])} · {p["pieces"]:,} pcs</b><span>Back {esc(explain.short_date(p["eta_date"]))} · '
                    f'{p["total_days"]:.1f} days · cost {p["total_cost"]:,.0f}</span></div>' for p in split["parts"])
    single = split.get("single")
    compare = ""
    if single:
        compare = (f'Whole batch at {esc(single["name"])}: back {esc(explain.short_date(single["eta_date"]))}. '
                   + (f'The split saves {split["days_saved"]:.1f} days' if split.get("faster") else "The split is not faster")
                   + ("" if split.get("earlier_eta") or not split.get("faster") else ", but the rounded return date is unchanged") + ".")
    html(f'<div class="card"><div class="hero-label"><span class="section-title">Split preview</span>{pill("Preview only", "muted")}</div>'
         f'<div class="section-note" style="margin:4px 0 12px">Both parts run in parallel; each pays its own transport. Completion is the later part: '
         f'{esc(explain.short_date(split["eta_date"]))}, {split["days_to_spare"]:+d} days to spare, combined cost {split["total_cost"]:,.0f}.</div>'
         f'<div class="grid c2">{parts}</div><div class="section-note" style="margin-top:10px">{compare}</div></div>')


def clarify_card(response, parsed, record):
    state = st.session_state
    missing = [MISSING_LABELS.get(f, f) for f in parsed.missing_fields]
    options = record.get("tool_outputs", {}).get("order_options", [])
    if parsed.date_not_confirmed:
        missing.append("Confirmed new deadline")
    if any(o.get("current_stage") == "PACKING" for o in options) and parsed.order_id:
        missing.append("Confirm outside dispatch (order is in packing)")
    if parsed.is_question_only and not missing:
        missing.append("Whether allocation is wanted")
    sender = parsed.sender or "the sender"
    cards = "".join(
        f'<div class="lane python"><b>{esc(o["order_id"])}</b><span>{esc(o["customer"])} · {esc(o["product"])} · {o["pieces"]:,} pcs · {esc(o["current_stage"].lower())}</span></div>'
        for o in options)
    with st.container(key="hero"):
        html(f'<div class="hero-warn"><div class="hero-label">{pill("Needs clarification", "warn")}{pill("No allocation made", "muted")}</div>'
             f'<div class="hero-name" style="font-size:30px">Ask {esc(sender)} before allocating</div>'
             f'<div class="section-note" style="margin:6px 0 12px">Missing or unconfirmed: </div>'
             f'<div class="chips">{"".join(pill(m, "warn", soft=True) for m in missing) or pill("Details", "warn", soft=True)}</div>'
             + (f'<div class="section-note" style="margin:16px 0 8px">{len(options)} in-progress orders match. The system will not guess.</div>'
                f'<div class="grid c3">{cards}</div>' if options and not parsed.order_id else "")
             + f'<div class="why" style="margin:16px 0 8px"><b>Question to send</b><p>{esc(response.explanation_text)}</p></div></div>')
        reply_col, button_col = st.columns([3, 1], vertical_alignment="bottom")
        with reply_col:
            st.text_input(f"Reply from {sender}", key="desk_reply", placeholder="For example: ORD-024, due 15 Apr")
        with button_col:
            st.button("Add reply to request", key="desk_add_reply", on_click=append_reply, width="stretch",
                      disabled=not state.get("desk_reply", "").strip())
        html('<div class="section-note">The reply is appended to the request text. Dispatch again to re-read it. '
             'Edited text needs the live model; rehearsal sources only cover the original inbox lines.</div>')


def decline_card(response, parsed, orders):
    if parsed.reason == "order not found":
        needed = f"An authoritative order record for {parsed.order_id or 'the named order'}. It is not among the {len(orders)} orders in orders.csv."
    else:
        needed = DATA_NEEDED.get(parsed.question_topic, "The source records that contain the requested information.")
    with st.container(key="hero"):
        html(f'<div class="hero-muted"><div class="hero-label">{pill("Cannot answer from this data", "muted")}{pill("Nothing invented", "ok")}</div>'
             f'<div class="hero-name" style="font-size:30px">This needs data the desk does not hold</div>'
             f'<div class="grid c2" style="margin-top:16px"><div class="lane" style="border-color:rgba(255,112,104,.3)"><b style="color:var(--coral)">Missing source</b><span>{esc(needed)}</span></div>'
             f'<div class="lane"><b style="color:var(--text-2)">Sources available</b><span>orders.csv ({len(orders)} orders: customer, product, pieces, dates, stage) · '
             'workshops.csv (8 profiles) · the 30-message inbox. No dispatch history, quotes or worker rosters.</span></div></div>'
             f'<div class="why" style="margin-top:16px"><b>Reply</b><p>{esc(response.explanation_text)}</p></div></div>')


# Decision explorer --------------------------------------------------------------

def explorer(preview, record, response, parsed, workshops, steps):
    summary, candidates, why, evidence, trace = st.tabs(["Summary", "Candidates", "Why this won", "Evidence", "Execution trace"])
    with summary:
        summary_tab(preview, record, response, parsed)
    with candidates:
        candidates_tab(record, workshops, preview.today)
    with why:
        why_tab(record, workshops)
    with evidence:
        evidence_tab(record, response, preview)
    with trace:
        trace_tab(steps)


def summary_tab(preview, record, response, parsed):
    constraints = parsed.constraints or []
    said = [("Sender", parsed.sender or "Unknown"), ("Order", parsed.order_id or "Not identified"),
            ("Customer and product", " · ".join(v for v in (parsed.customer, parsed.product) if v) or "Not stated"),
            ("Category", parsed.category or "Unknown"), ("Pieces", f"{parsed.pieces:,}" if parsed.pieces else "Unknown"),
            ("Due date", explain.long_date(parsed.due_date) + (f" (from “{parsed.due_date_text}”)" if parsed.due_date_text else " (from orders.csv)") if parsed.due_date else "Not confirmed"),
            ("Preference", explain.PREFERENCE_LABELS.get(parsed.preference, "None stated")),
            ("Split allowed", "Yes" if parsed.split_allowed else "No")]
    applied = record.get("constraints_applied", {})
    status = [("Behaviour", VERDICTS[parsed.behaviour][0].capitalize()), ("Reason", parsed.reason),
              ("Objective applied", explain.objective_label(record["objective_name"])),
              ("Excluded workshops", ", ".join(applied.get("exclude") or []) or "None"),
              ("Must make the date", "Yes" if applied.get("must_make_date") else "No"),
              ("Awkward case", {"none_makes_date": "No option makes the date", "no_eligible": "No eligible workshop"}.get(record.get("awkward_case"), "None")),
              ("Extraction", explain.source_label(parsed.llm_metadata or {})[1])]
    left, right = st.columns(2, gap="medium")
    with left:
        rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in said)
        cons = "".join(f'<li>“{esc(c.get("text"))}” · imposed by {esc(c.get("imposed_by") or "unknown")}'
                       + (f', relayed by {esc(c["relayed_by"])}' if c.get("relayed_by") else "") + "</li>" for c in constraints)
        notes = "".join(f"<li>{esc(n)}</li>" for n in parsed.notes)
        html(f'<div class="card"><h4>What the request says</h4><dl class="kv">{rows}</dl>'
             + (f'<h4 style="margin-top:16px">Constraints and who imposed them</h4><ul>{cons}</ul>' if cons else "")
             + (f'<h4 style="margin-top:16px">Checks noted</h4><ul>{notes}</ul>' if notes else "") + "</div>")
    with right:
        rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in status)
        html(f'<div class="card"><h4>Decision status</h4><dl class="kv">{rows}</dl></div>')
    audit = response.faithfulness
    html(f'<div class="card" style="margin-top:4px"><div class="hero-label"><h4 style="margin:0">Recorded explanation</h4>'
         f'{pill("Evidence check passed" if audit.get("passed") else "Evidence check failed", "ok" if audit.get("passed") else "risk")}</div>'
         f'<p style="white-space:pre-line;color:var(--text-2);margin:10px 0 0;font-size:14.5px">{esc(response.explanation_text)}</p></div>')


def candidates_tab(record, workshops, today):
    rows = ordered_rows(record, workshops)
    evaluated = [row for kind, row in rows if kind in {"permitted", "excluded"}]
    if not evaluated:
        html(banner("No candidates estimated", "Candidates are estimated only once the request has a confirmed order, quantity, category and date.", "muted"))
        return
    chosen = record.get("chosen_workshop")
    due_offset = (date.fromisoformat(evaluated[0]["due_date"]) - today).days
    scale = max([row["total_days"] for row in evaluated] + [due_offset, 1]) * 1.06
    section("Delivery estimate per workshop", "Queue + processing + transport from the scenario date. The amber line is the due date.")
    bars = []
    for kind, row in rows:
        cls = " chosen" if row["workshop_id"] == chosen else " dim" if kind != "permitted" else ""
        if kind in {"permitted", "excluded"}:
            q, p, t = row["queue_days"], row["processing_days"], row["lead_days"]
            segs = (f'<span class="tl-seg q" style="left:0;width:{q / scale:.2%}"></span>'
                    f'<span class="tl-seg p" style="left:{q / scale:.2%};width:{p / scale:.2%}"></span>'
                    f'<span class="tl-seg t" style="left:{(q + p) / scale:.2%};width:{t / scale:.2%}"></span>')
            due = f'<span class="tl-due" style="left:{max(0, due_offset) / scale:.2%}"></span>'
            note = row.get("exclusion_reason")
            bars.append(f'<div class="tl-row{cls}"><span class="nm">{esc(row["name"])}{" · " + esc(note) if note else ""}</span>'
                        f'<div class="tl-track">{segs}{due}</div><span class="val">{esc(explain.short_date(row["eta_date"]))}</span></div>')
        else:
            reason = explain.ineligible_headline(row.get("reason", "not evaluated"))
            bars.append(f'<div class="tl-row dim"><span class="nm">{esc(row["name"])}</span><span class="tl-blocked">Not estimated: {esc(reason)}</span><span class="val">n/a</span></div>')
    html('<div class="card"><div class="tl">' + "".join(bars) + '</div><div class="legend" style="margin-top:12px">'
         '<span><i style="background:rgba(100,136,255,.75)"></i>Current queue</span><span><i style="background:var(--cyan)"></i>Processing</span>'
         '<span><i style="background:var(--teal)"></i>Transport</span><span><i style="background:var(--amber)"></i>Due date</span></div></div>')
    section("Full comparison", "Rounded for reading. Exact values are in the decision record on the Evidence tab.")
    body, classes = [], []
    for kind, row in rows:
        wid = row["workshop_id"]
        if kind in {"permitted", "excluded"}:
            status = "Recommended" if wid == chosen else row.get("exclusion_reason") or ("Late" if row["days_to_spare"] < 0 else "Eligible")
            spare = row["days_to_spare"]
            body.append([f"<b>{esc(row['name'])}</b><small>{esc(wid)}</small>", esc(status), f"{row['queue_days']:.1f}",
                         f"{row['processing_days']:.1f}", str(row["lead_days"]), f"{row['total_days']:.1f}",
                         esc(explain.short_date(row["eta_date"])), f'<span class="{"neg" if spare < 0 else "pos"}">{spare:+d}</span>',
                         f"{row['total_cost']:,.0f}", f"{row['expected_defect_rate']:.0%}", f"{row['score']:.5f}"])
            classes.append("chosen" if wid == chosen else "dim" if kind == "excluded" else "")
        else:
            reason = explain.ineligible_headline(row.get("reason", "not evaluated"))
            body.append([f"<b>{esc(row['name'])}</b><small>{esc(wid)}</small>", esc(reason)] + ["n/a"] * 9)
            classes.append("dim")
    html(table(["Workshop", "Status", "Queue d", "Process d", "Transport d", "Total d", "Back", "Spare", "Cost", "Defect", "Score"],
               body, right=range(2, 11), classes=classes))


def why_tab(record, workshops):
    chosen = explain.chosen_row(record)
    if chosen is None:
        html(banner("No recommendation", "There is nothing to compare until the request can be allocated.", "muted"))
        return
    config = explain.effective_config(record["objective_name"])
    won = explain.why_won(record)
    html(f'<div class="card"><div class="why"><b>Why this won</b><p>{esc(won["sentence"])}</p></div></div>')
    other = won.get("runner_up")
    left, right = st.columns([1, 1.15], gap="medium")
    with left:
        if other is not None:
            section(f"{chosen['name']} vs runner-up {other['name']}", "Runner-up is the next option under the same selection rule.")
            cells = ['<div class="h">Fact</div>', f'<div class="h">{esc(chosen["name"])}</div>', f'<div class="h">{esc(other["name"])}</div>', '<div class="h">Difference</div>']
            for item in explain.comparison(chosen, other):
                delta = item["delta"]
                if abs(delta) < 1e-9:
                    text, cls = "Same", ""
                elif item["better"]:
                    size = abs(delta)
                    if item["label"] == "Defect risk":
                        text = f"{size:.0%} lower defect risk".replace(".0%", "%")
                    elif item["label"] == "Days to spare":
                        text = f"{explain.days(size)} more margin"
                    elif item["label"] == "Total cost":
                        text = f"{size:,.0f} cheaper"
                    else:
                        text = f"{size:,.1f} {item['unit']}"
                    cls = " better"
                else:
                    text, cls = "Runner-up better", ""
                cells += [f'<div class="lbl">{esc(item["label"])}</div>', f'<div class="c">{esc(item["chosen"])}</div>',
                          f'<div class="o">{esc(item["other"])}</div>', f'<div class="d{cls}">{esc(text)}</div>']
            html(f'<div class="vs">{"".join(cells)}</div>')
        else:
            html(banner("No runner-up", "Only one permitted workshop remained, so there is no score comparison.", "muted"))
        section("Objective weights", "From the configuration. Terms with zero weight do not affect this decision.")
        weights = "".join(f'<div class="weight{"" if getattr(config, "w_" + t) > 0 else " off"}"><small><i class="term-{t}"></i>{esc(explain.TERM_LABELS[t])}</small>'
                          f'<strong>{getattr(config, "w_" + t):g}</strong></div>' for t in explain.TERMS)
        html(f'<div class="weights">{weights}</div>')
    with right:
        order = explain.selection_order(record)[:6]
        section("Score decomposition", "Weighted penalty per term, read from the recorded score terms. Lower wins.")
        note = ("Every option is late, so selection used the least-late rule (fewest late days, then fastest), not the weighted score."
                if record.get("awkward_case") == "none_makes_date" else
                "When every option is on time, lateness reduces to a small speed term, 0.01 × t/(t+30), so faster wins.")
        html(score_bars(explain.score_breakdown(order, config), chosen["workshop_id"], explain.TERMS, explain.TERM_LABELS, note))
    section("Why not this workshop?", "Pick any other workshop to see the deterministic reason it was not recommended.")
    others = [wid for wid in workshops if wid != chosen["workshop_id"]]
    state = st.session_state
    default = other["workshop_id"] if other is not None else others[0]
    if state.get("desk_whynot") not in others:
        state["desk_whynot"] = default
    pick = st.pills("Workshop", others, key="desk_whynot", format_func=lambda wid: workshops[wid].name, label_visibility="collapsed")
    if pick:
        reason = explain.why_not(record, pick, workshops)
        items = "".join(f"<li>{esc(d)}</li>" for d in reason["detail"])
        html(f'<div class="reason {reason["tone"]}"><div class="rh">{esc(workshops[pick].name)} {pill(reason["headline"], {"blocked": "risk", "warn": "warn", "chosen": "info"}.get(reason["tone"], "muted"), soft=True)}</div>'
             + (f"<ul>{items}</ul>" if items else "") + "</div>")


def evidence_tab(record, response, preview):
    audit = response.faithfulness
    numbers = audit.get("numbers_in_text", [])
    unmatched = set(audit.get("unmatched", []))
    chips_html = "".join(pill(n, "risk" if n in unmatched else "ok", soft=True) for n in dict.fromkeys(numbers))
    head = (f"All {len(numbers)} numbers, dates and IDs in the explanation trace to tool outputs." if audit.get("passed")
            else f"{len(unmatched)} values are not supported by tool outputs. Confirmation is blocked.")
    html(f'<div class="card"><div class="hero-label"><h4 style="margin:0">Evidence check</h4>'
         f'{pill("Passed" if audit.get("passed") else "Failed", "ok" if audit.get("passed") else "risk")}</div>'
         f'<p style="margin:10px 0">{esc(head)}</p><div class="chips">{chips_html or pill("No numbers in text", "muted", soft=True)}</div>'
         '<div class="section-note" style="margin-top:12px">Every number, date and ID in the recorded explanation must appear in the candidates, '
         'eligibility results or tool outputs. This checks numerical support, not whether the decision is right; decision quality is evaluated separately.</div></div>')
    left, right = st.columns(2, gap="medium")
    with left:
        with st.expander("Structured extraction and Python checks"):
            json_block(response.parsed_request.to_dict(), height=420)
    with right:
        with st.expander("Decision record"):
            slim = {k: v for k, v in record.items() if k != "tool_outputs"}
            slim["tool_outputs"] = {k: v for k, v in record.get("tool_outputs", {}).items() if k != "call_trace"}
            json_block(slim, height=420)
    st.download_button("Download full preview record (JSON)", json.dumps(response.to_dict(), indent=2, default=str),
                       file_name=f"{response.parsed_request.order_id or 'request'}-preview.json", mime="application/json",
                       key="desk_download")


def trace_tab(steps):
    html('<div class="section-note" style="margin-bottom:6px">Recorded program events for this preview, in order. '
         'These are tool calls and checks that actually ran, not model reasoning.</div>')
    for number, step in enumerate(steps, 1):
        actor = step["actor"]
        who = {"model": "Language model", "fixture": "Synthetic fixture", "python": "Python", "human": "Human"}[actor]
        tone = {"done": "ok", "pending": "human", "blocked": "risk", "skipped": "muted"}[step["status"]]
        status = {"done": "Done", "pending": "Waiting", "blocked": "Blocked", "skipped": "Not run"}[step["status"]]
        html(f'<div class="trace-step {actor} {step["status"]}"><div class="n">{number}</div>'
             f'<div><div class="t">{esc(step["title"])}</div><div class="s">{esc(step["summary"])}</div></div>'
             f'<div class="chips">{pill(who, {"model": "model", "fixture": "warn", "python": "python", "human": "human"}[actor], soft=True)}{pill(status, tone)}</div></div>')
        if step.get("evidence"):
            with st.expander(f"Evidence for step {number}", expanded=False):
                json_block(step["evidence"], height=320)
