"""Guided demo: one request, R09, from the inbox to its saved audit record.

A small explicit state machine. Each step names its page, the real UI element it
points at (a stable st.container key), what the visitor does, the real
application condition that completes it, and what it explains. A step never
completes because someone pressed Next: "event" steps advance when the app
reaches their condition (a request selected, an evaluation finished, a decision
confirmed, a record opened); "review" steps show a Continue button that is only
enabled once the evidence they explain exists.

Isolation. Starting the demo stores the desk's working state and gives the demo
a fresh session (1 April queues, nothing confirmed). Exiting restores it.
Restarting gives the demo a fresh session again; it never erases anything.
Confirmations made in the demo are flagged guided_demo and written to the
rehearsal log, never the live log, whichever source read the request.

Extraction source. Rehearsal (the default) replays a recorded model reply for
R09 if one exists, otherwise the labelled test fixture: no API call. Live uses
the configured model. The UI always says which one ran. Everything after the
extraction is the normal deterministic engine.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import streamlit as st

from ui.components import esc, html

REQUEST_ID = "R09"
WORKING_KEYS = ("desk_allocator", "desk_queues", "desk_queue_date", "desk_revision", "desk_saved", "desk_outcomes", "desk_splits",
                "desk_message", "desk_preview", "desk_error", "desk_exec", "desk_today", "desk_preset", "desk_source", "desk_page",
                "net_handoff", "net_category", "net_pieces", "net_due", "net_from", "net_target", "net_pick", "net_sig",
                "audit_log", "audit_focus", "audit_opened")
PAGES = {"Dispatch", "Workshop Network", "Simulation Lab", "Audit Trail"}


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    page: str
    target: str                      # st.container key of the real element to highlight
    kind: str                        # "event": advances on its condition; "review": Continue once ready
    ready: Callable[[dict], bool]    # the real application condition
    before: Callable[[dict], str]    # explanation while waiting for the action
    after: Callable[[dict], str]     # explanation once the condition holds
    action: str                      # the one thing to do
    opens: str | None = None         # which Dispatch detail panel this step opens
    side: str = "right"              # where the coach sits so it never covers the target
    target_after: str | None = None  # what to point at once the action is done
    also: tuple = ()                 # other pages where the step legitimately continues

    def on(self, page) -> bool:
        return page == self.page or page in self.also


# Readers over real state -----------------------------------------------------------

def _g(state) -> dict:
    return state.get("guide") or {}


def _preview(state):
    preview = state.get("desk_preview")
    if preview is None or preview.response.parsed_request.raw_text != _g(state).get("line"):
        return None
    return preview


def _chosen(state):
    preview = _preview(state)
    if preview is None:
        return None
    record = preview.response.decision_record
    return next((c for c in record.get("candidates", []) if c["workshop_id"] == record.get("chosen_workshop")), None)


def _saved_row(state):
    preview = _preview(state)
    return state.get("desk_saved", {}).get(preview.token) if preview else None


def _short(iso) -> str:
    from ui import explain
    return explain.short_date(iso) if iso else "unknown"


# Explanations, built only from the real preview -------------------------------------

def _story(state) -> str:
    return ("Boss has forwarded an urgent order from Cotton Club: 150 vests, needed fast. Sweater Co subcontracts finishing work, "
            "so the desk must pick the workshop that can return the batch in time. The request is the highlighted inbox line.")


def _extract_after(state) -> str:
    preview = _preview(state)
    raw = preview.response.parsed_request.raw_llm_json or {}
    source = {"live": "The live model", "cached": "A recorded reply from the model (no API call)",
              "fixture": "A labelled test fixture, not the model,"}.get(preview.source, "The extraction")
    facts = [f"order <b>{esc(raw.get('order_id') or 'not stated')}</b>", f"<b>{esc(raw.get('pieces') or 'no')}</b> pieces",
             f"deadline written as <b>{esc(raw.get('due_date_text') or 'not stated')}</b>",
             f"preference <b>{esc(raw.get('preference') or 'none')}</b>"]
    return (f"{source} turned the message into fields: {', '.join(facts)}. It copied facts only: it did not choose a workshop or "
            "calculate a date or a price. The full extraction is open below.")


def _checks_after(state) -> str:
    parsed = _preview(state).response.parsed_request
    checks = [c for c in parsed.post_checks if c.get("layer") == "python"]
    ready = parsed.behaviour in {"allocate", "refuse"}
    return (f"Python ran <b>{len(checks)}</b> checks against orders.csv: the order exists, the deadline is a real date and still ahead, "
            "the order is not in packing, and every field needed to allocate is present. "
            + ("Result: <b>ready to allocate</b>." if ready else f"Result: <b>{esc(parsed.reason)}</b>."))


def _workshops_after(state) -> str:
    preview = _preview(state)
    record = preview.response.decision_record
    eligible = record.get("tool_outputs", {}).get("eligibility") or []
    out = [f"{e['name']} ({esc(e['reason'])})" for e in eligible if not e["eligible"]]
    chosen = _chosen(state)
    return (f"<b>{sum(e['eligible'] for e in eligible)} of {len(eligible)}</b> workshops can take this batch. "
            + (f"Excluded: {esc('; '.join(out))}. " if out else "")
            + "The rest are ranked by queue, return date and cost under the objective. "
            + (f"<b>{esc(chosen['name'])}</b> ranks first. " if chosen else "")
            + "Open the network to see the same ranking on the map.")


def _network_after(state) -> str:
    chosen = _chosen(state)
    if chosen is None:
        return "Click another workshop on the map to inspect it."
    return (f"The panel shows <b>{esc(chosen['name'])}</b>: back <b>{esc(_short(chosen['eta_date']))}</b>, cost "
            f"<b>{chosen['total_cost']:,.0f}</b>. You opened another workshop: <b>inspecting</b> one is only looking. "
            "The engine's <b>recommendation</b> is still not a decision: only your confirmation on Dispatch assigns the batch.")


def _confirm_before(state) -> str:
    chosen = _chosen(state)
    name = chosen["name"] if chosen else "the recommended workshop"
    return (f"The engine recommends {esc(name)}, but nothing is assigned until you approve it. The model never approves anything. "
            "Press the highlighted button to confirm. In the demo it is written to the rehearsal log.")


def _verify_after(state) -> str:
    row = _saved_row(state) or {}
    record = row.get("decision_record", {})
    return (f"This is the saved record: request, chosen workshop <b>{esc(record.get('chosen_workshop'))}</b>, the candidates and "
            "the evidence check, with your confirmation. The session queue for that workshop has been updated, once.")


def _audit_open(state) -> bool:
    row = _saved_row(state)
    return bool(row) and state.get("desk_page") == "Audit Trail" and state.get("audit_opened") == row.get("timestamp")


STEPS = [
    Step("receive", "Receive the request", "Dispatch", f"inb_{REQUEST_ID}", "event",
         lambda s: s.get("desk_message") == _g(s).get("line"), _story, _story, "Select the highlighted request in the inbox.", side="right"),
    Step("understand", "Understand the request", "Dispatch", "desk_dispatch", "review",
         lambda s: _preview(s) is not None,
         lambda s: ("Press <b>Evaluate request</b>. The language model reads the message and returns structured fields. "
                    "It does not choose the workshop."),
         _extract_after, "Press Evaluate request, then read what the model extracted.", opens="extract", side="right",
         target_after="detail_extract"),
    Step("validate", "Validate the information", "Dispatch", "detail_checks", "review",
         lambda s: _preview(s) is not None, _checks_after, _checks_after, "Read the checks, then continue.", opens="checks", side="right"),
    Step("evaluate", "Evaluate the workshops", "Dispatch", "desk_trace", "event",
         lambda s: s.get("desk_page") == "Workshop Network" and REQUEST_ID in str(s.get("net_from") or ""),
         _workshops_after, _workshops_after, "Press See it on the network.", opens="workshops", side="right"),
    Step("recommendation", "Understand the recommendation", "Workshop Network", "net_detail", "review",
         lambda s: _chosen(s) is not None and s.get("net_pick") not in (None, (_chosen(s) or {}).get("workshop_id")),
         lambda s: ("The highlighted panel is the recommended workshop with its return date, cost and reason. "
                    "Now click any other workshop on the map to inspect it."),
         _network_after, "Click another workshop on the map, then go back to confirm.", side="left"),
    Step("confirm", "Confirm the decision", "Dispatch", "desk_confirm", "event",
         lambda s: _saved_row(s) is not None, _confirm_before, _confirm_before, "Press the highlighted button.", side="right"),
    Step("verify", "Verify the result", "Dispatch", "desk_view_audit", "review",
         _audit_open,
         lambda s: "The decision is recorded. Press <b>View audit record</b> to open it in the Audit Trail.",
         _verify_after, "Press View audit record, then read the record.", side="left", also=("Audit Trail",)),
    Step("complete", "Complete", "Audit Trail", "", "review", lambda s: True,
         lambda s: "", lambda s: "", "", side="left"),
]


# Lifecycle -------------------------------------------------------------------------

def active() -> bool:
    return bool(_g(st.session_state).get("running"))


def current() -> Step | None:
    g = _g(st.session_state)
    return STEPS[g["step"]] if g.get("running") and 0 <= g.get("step", -1) < len(STEPS) else None


def opens(panel: str) -> bool:
    step = current()
    return bool(step and step.opens == panel and step.ready(st.session_state))


def _fresh_desk(state, workshops, source):
    from desk import TODAY
    from allocator import Allocator
    from objectives import PRESETS
    state.update(desk_allocator=Allocator(PRESETS["lateness"]), desk_queues={wid: w.queue0 for wid, w in workshops.items()},
                 desk_queue_date=TODAY, desk_revision=0, desk_saved={}, desk_outcomes={}, desk_splits={}, desk_today=TODAY,
                 desk_preset="lateness", desk_message="", desk_source=source, desk_page="Dispatch")
    for key in ("desk_preview", "desk_error", "desk_exec", "net_handoff", "net_from", "net_target", "net_pick", "net_sig",
                "audit_focus", "audit_opened"):
        state.pop(key, None)


def choose_source(prefer_live: bool) -> str:
    """Live only on request and when configured; otherwise a recorded reply if one exists for R09, else the fixture."""
    import intake
    import rehearsal
    from desk import TODAY, load_inputs
    if prefer_live and rehearsal.live_status()["ready"]:
        return "live"
    orders, workshops, messages = load_inputs()
    line = next(m for m in messages if m.startswith(REQUEST_ID + " "))
    prompt = intake.build_system_prompt(TODAY, orders, workshops)
    return "cached" if rehearsal.find_recorded(prompt, line) else "fixture"


def start(workshops, messages, prefer_live: bool = False):
    state = st.session_state
    g = _g(state)
    snapshot = g.get("snapshot") or {k: deepcopy(state[k]) for k in WORKING_KEYS if k in state}
    source = choose_source(prefer_live)
    line = next(m for m in messages if m.startswith(REQUEST_ID + " "))
    _fresh_desk(state, workshops, source)
    state["guide"] = {"running": True, "step": 0, "line": line, "source": source, "snapshot": snapshot, "intro": False}


def exit_demo():
    state = st.session_state
    snapshot = _g(state).get("snapshot") or {}
    for key in WORKING_KEYS:
        state.pop(key, None)
    state.update(deepcopy(snapshot))
    state.setdefault("desk_page", "Dispatch")
    state.pop("guide", None)


def open_intro():
    st.session_state["guide"] = {**_g(st.session_state), "intro": True}


def close_intro():
    g = _g(st.session_state)
    if not g.get("running"):
        st.session_state.pop("guide", None)
    else:
        g["intro"] = False


VERIFY = next(i for i, s in enumerate(STEPS) if s.key == "verify")


def can_go_back(state) -> bool:
    """Previous is allowed until a decision is confirmed; after that it stops at verification (a confirmation is never undone)."""
    g = _g(state)
    return g.get("step", 0) > 0 and not (_saved_row(state) and g["step"] - 1 < VERIFY)


def move(delta: int):
    state = st.session_state
    g = _g(state)
    if delta < 0 and not can_go_back(state):
        return
    target = max(0, min(len(STEPS) - 1, g["step"] + delta))
    g["step"] = target
    if not STEPS[target].on(state.get("desk_page")) and STEPS[target].page in PAGES:
        state["desk_page"] = STEPS[target].page


def go(page: str):
    st.session_state["desk_page"] = page


def advance_if_done():
    """Event steps advance as soon as the real condition holds (checked on every run)."""
    state = st.session_state
    g = _g(state)
    while g.get("running") and g["step"] < len(STEPS) - 1:
        step = STEPS[g["step"]]
        if step.kind == "event" and step.ready(state):
            g["step"] += 1
            continue
        break


def stale() -> bool:
    """True when a fragment-only rerun changed the step's state, so the coach drawn outside it is out of date."""
    g = _g(st.session_state)
    if st.session_state.get("_app_run") or not g.get("running") or "drawn" not in g:
        return False
    return g["drawn"] != [g["step"], bool(STEPS[g["step"]].ready(st.session_state))]


# Coach panel -----------------------------------------------------------------------

def render(workshops, messages):
    """Draw the coach (or the start card) and highlight the current step's real target."""
    state = st.session_state
    g = _g(state)
    if g.get("intro") and not g.get("running"):
        intro_card(workshops, messages)
        return
    if not g.get("running"):
        return
    advance_if_done()
    step = STEPS[g["step"]]
    on_page = step.on(state.get("desk_page"))
    ready = step.ready(state)
    target = step.target_after if ready and step.target_after else step.target
    if target and on_page:
        highlight(target)
    g["drawn"] = [g["step"], bool(ready)]
    n = len(STEPS)
    with st.container(key=f"guide_{step.side}"):
        html(f'<div class="gd-top"><span>Guided demo · step {g["step"] + 1} of {n}</span>'
             f'<span class="gd-src">{esc({"live": "Live model", "cached": "Recorded reply", "fixture": "Test fixture"}[g["source"]])}</span></div>'
             f'<div class="gd-bar"><i style="width:{(g["step"] + (1 if ready else .5)) / n * 100:.0f}%"></i></div>'
             f'<div class="gd-title">{esc(step.title)}</div>')
        if step.key == "complete":
            summary()
        else:
            html(f'<div class="gd-text">{(step.after if ready else step.before)(state)}</div>')
            if not on_page:
                html(f'<div class="gd-do">This step happens on {esc(step.page)}.</div>')
                st.button(f"Go to {step.page}", key="guide_go", on_click=go, args=(step.page,), type="primary")
            elif not (ready and step.kind == "review"):
                html(f'<div class="gd-do">{icon_arrow()}{esc(step.action)}</div>')
        with st.container(key="guide_nav", horizontal=True, vertical_alignment="center"):
            st.button("Previous", key="guide_prev", on_click=move, args=(-1,), disabled=not can_go_back(state))
            if step.kind == "review" and step.key != "complete":
                label = "Back to Dispatch to confirm" if step.key == "recommendation" else "Continue"
                st.button(label, key="guide_next", type="primary", on_click=move, args=(1,), disabled=not (ready and on_page))
            st.button("Exit demo", key="guide_exit", on_click=exit_demo, type="tertiary")


def icon_arrow() -> str:
    return '<span class="msym" aria-hidden="true">arrow_forward</span>'


def summary():
    state = st.session_state
    row = _saved_row(state) or {}
    record = row.get("decision_record", {})
    parsed = row.get("parsed_request", {})
    meta = parsed.get("llm_metadata") or {}
    source = {"live": f"the live model ({meta.get('served_model') or meta.get('model')})", "cached": "a recorded model reply",
              "fixture": "a labelled test fixture"}.get(_g(state).get("source"), "the extraction source")
    html('<div class="gd-text">You took one request from the inbox to a confirmed, recorded decision.</div>'
         '<dl class="gd-sum">'
         f'<dt>AI interpretation</dt><dd>{esc(source)} read the message into fields. Nothing else.</dd>'
         f'<dt>Python decisions</dt><dd>Validation, eligibility, return dates, costs and the ranking chose {esc(record.get("chosen_workshop"))}.</dd>'
         '<dt>Human approval</dt><dd>You confirmed it. Nothing was sent to the workshop.</dd>'
         '<dt>Recorded evidence</dt><dd>The audit record holds the request, candidates, evidence check and your confirmation, '
         'in the rehearsal log because this was a demo.</dd></dl>')
    with st.container(key="guide_end", horizontal=True):
        st.button("Restart", key="guide_restart", on_click=restart)
        st.button("More scenarios", key="guide_more", on_click=open_scenarios)


def restart():
    from desk import load_inputs
    _, workshops, messages = load_inputs()
    snapshot = _g(st.session_state).get("snapshot")
    start(workshops, messages, prefer_live=_g(st.session_state).get("source") == "live")
    st.session_state["guide"]["snapshot"] = snapshot


def open_scenarios():
    exit_demo()
    st.session_state["guide"] = {"intro": True, "scenarios": True}


def intro_card(workshops, messages):
    """Start card, and the optional scenario library."""
    import rehearsal
    g = _g(st.session_state)
    live = rehearsal.live_status()
    with st.container(key="guide_right"):
        html('<div class="gd-top"><span>Guided demo</span></div><div class="gd-title">From a message to a confirmed decision</div>'
             '<div class="gd-text">Follow one request, R09, through the whole desk: the model reads it, Python checks and ranks the '
             'workshops, you confirm, and the record appears in the audit trail. About three minutes. Your current work is set aside '
             'and restored when you exit.</div>')
        with st.container(key="guide_start", horizontal=True):
            st.button("Start, no API call", key="guide_begin", type="primary", on_click=start, args=(workshops, messages, False),
                      help="Replays a recorded model reply for R09, or a labelled test fixture. The decision engine runs normally.")
            st.button("Start with the live model", key="guide_begin_live", on_click=start, args=(workshops, messages, True),
                      disabled=not live["ready"], help="One real model call to read R09." if live["ready"] else "No model is configured.")
            st.button("Close", key="guide_close", type="tertiary", on_click=close_intro)
        html('<div class="gd-sub">Other scenarios, one capability each</div>')
        for rid, name, hint in SCENARIOS:
            st.button(f"{rid} · {name}", key=f"guide_scn_{rid}", help=hint, on_click=load_scenario, args=(rid, messages), width="stretch")


# A small library of single-capability scenarios. Each is verified by tests/test_guide.py.
SCENARIOS = [("R01", "Ambiguous order: the desk asks which one", "Evaluate it. No allocation; the desk lists the candidate orders."),
             ("R08", "A named workshop refuses", "Evaluate it. FreshStart cannot take the batch; a permitted alternative is offered."),
             ("R02", "Unanswerable question", "Evaluate it. The desk names the missing data source and allocates nothing."),
             ("R30", "Impossible deadline", "Evaluate it. No workshop makes the date; you choose late return, split or escalate.")]


def load_scenario(rid, messages):
    state = st.session_state
    line = next(m for m in messages if m.startswith(rid + " "))
    hint = next(h for r, _, h in SCENARIOS if r == rid)
    from ui import dispatch
    dispatch.select_message(line)
    state["desk_page"] = "Dispatch"
    state["guide_scenario"] = {"rid": rid, "hint": hint}
    state.pop("guide", None)


def highlight(target: str):
    """Outline the real element by its stable container key and bring it into view once per step."""
    html(f'<style>.st-key-{target} {{ outline: 3px solid var(--ice); outline-offset: 4px; border-radius: 14px;'
         f' box-shadow: 0 0 0 8px rgba(104,202,250,.22) !important; }}</style>')
    state = st.session_state
    g = _g(state)
    marker = f"{g.get('step')}:{target}"
    if g.get("scrolled") == marker:
        return
    g["scrolled"] = marker
    import streamlit.components.v1 as components
    components.html(
        "<script>try{const d=window.parent.document;const el=d.querySelector('.st-key-" + target + "');"
        "const m=window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches;"
        "if(el){el.scrollIntoView({block:'center',behavior:m?'auto':'smooth'});}}catch(e){}</script>", height=0)
