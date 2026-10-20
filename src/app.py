"""Quick Response Desk. Run: uv run streamlit run src/app.py

Four areas: Dispatch (default), Workshop Network, Simulation Lab, Audit Trail.
The model only reads requests; Python validates, estimates, scores and selects;
a person confirms. Evaluating a request is a preview: only the explicit
confirmation writes an audit row and updates this session's queue. No workshop
is ever contacted. Session logic lives in desk.py; presentation lives in ui/.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "harness"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st

import intake
import rehearsal
from desk import (TODAY, ConfirmState, Preview, confirm_preview, confirm_state, filtered_records,  # noqa: F401
                  init_session, load_inputs, make_preview, projected_queues, reset_session, signature)
from ui import audit, dispatch, explain, lab, network
from ui.components import banner, esc, html, inject_css

PAGES = ["Dispatch", "Workshop Network", "Simulation Lab", "Audit Trail"]
ICONS = {"Dispatch": ":material/send:", "Workshop Network": ":material/hub:", "Simulation Lab": ":material/science:",
         "Audit Trail": ":material/verified_user:"}
# Streamlit drops a widget's state on runs where it is not drawn (other pages).
# These values are restored when the page that owns them is shown again.
KEEP = ("desk_today", "desk_preset", "desk_message", "inbox_search",
        "net_category", "net_pieces", "net_due", "net_view",
        "lab_seed", "lab_focus", "lab_scenario", "lab_late", "lab_order",
        "sb_lateness", "sb_defect", "sb_fairness", "sb_robustness", "sb_cost",
        "audit_log", "audit_q", "audit_sender", "audit_workshop", "audit_kind", "audit_day")
TOUR = [("R09", "Normal allocation", "Press Evaluate request, open Why this decision, then confirm."),
        ("R01", "Clarification", "Press Evaluate request. The desk asks which order is meant."),
        ("R08", "Refused workshop", "Press Evaluate request. FreshStart is refused with its reason."),
        ("R02", "Unanswerable request", "Press Evaluate request. The desk names the missing data."),
        ("R30", "Impossible deadline", "Press Evaluate request, then preview a two-workshop split."),
        (None, "Audit trail", "Open the confirmed record and its evidence.")]
SOURCE_LABELS = {"live": "Live model", "cached": "Rehearsal: recorded model replies", "fixture": "Rehearsal: test fixtures"}


def tour_go(step, messages):
    state = st.session_state
    state["demo_step"] = step
    rid = TOUR[step][0]
    if rid is None:
        state["desk_page"] = "Audit Trail"
        return
    line = next((m for m in messages if m.startswith(rid + " ")), "")
    state["desk_page"] = "Dispatch"
    dispatch.select_message(line)


def tour_exit():
    st.session_state.pop("demo_step", None)


def demo_controller(messages):
    """Floating product-tour controller. Every step runs the real decision engine."""
    step = st.session_state.get("demo_step")
    if step is None:
        return
    rid, name, hint = TOUR[step]
    with st.container(key="demo_ctl", horizontal=True):
        html(f'<div class="demo-label"><em>DEMO {step + 1} OF {len(TOUR)}</em><b>{esc(name)}</b>'
             f'{(" " + esc(rid)) if rid else ""}<small>{esc(hint)}</small></div>')
        st.button("Previous", key="demo_prev", on_click=tour_go, args=(max(step - 1, 0), messages), disabled=step == 0)
        if step < len(TOUR) - 1:
            st.button("Next", key="demo_next", on_click=tour_go, args=(step + 1, messages))
        st.button("Exit", key="demo_exit", on_click=tour_exit)


def system_details(state, orders, workshops, messages):
    live = rehearsal.live_status()
    with st.popover("System details", icon=":material/tune:", width="stretch"):
        html('<div class="title" style="font-size:17px">System details</div>'
             '<div class="meta" style="font-size:13px;margin-bottom:6px">How requests are read. Allocation logic is always live.</div>')
        st.radio("Request reading", list(rehearsal.SOURCES), key="desk_source", format_func=SOURCE_LABELS.get,
                 on_change=dispatch.invalidate,
                 captions=["Reads each request with the configured model.",
                           "Replays earlier replies from the configured model. No API call.",
                           "Hand-written test extractions. Not model output."])
        today = max(state["desk_today"], state["desk_queue_date"])
        recorded = rehearsal.recorded_coverage(intake.build_system_prompt(today, orders, workshops), messages)
        rows = [("Language model", live["model"] if live["ready"] else "Not configured"),
                ("Recorded replies", f"{recorded} of {len(messages)} inbox requests"),
                ("Queue snapshot", explain.long_date(state["desk_queue_date"])),
                ("Confirmed this session", str(len(state["desk_saved"])))]
        html('<dl class="kv" style="grid-template-columns:160px 1fr;font-size:13.5px;margin:6px 0 8px">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")
        st.toggle("Presentation mode", key="presentation_mode",
                  help="Hides developer detail and Streamlit chrome for screen recording. Calculations do not change.")
        st.button("Reset demo session", key="demo_reset", width="stretch", on_click=reset_session, args=(state, workshops),
                  help="Restores the 1 April queues, clears decisions in this session and empties the rehearsal log. "
                       "The live audit log is never touched.")


def sidebar(state, orders, workshops, messages):
    with st.sidebar:
        html('<div class="wordmark"><b><i></i>QUICK RESPONSE</b><span>Subcontracting Desk</span></div>')
        with st.container(key="nav"):
            st.radio("Navigate", PAGES, key="desk_page", label_visibility="collapsed", format_func=lambda p: f"{ICONS[p]} {p}")
        html('<div class="side-spacer"></div>')
        st.button("Guided demo", key="demo_start", icon=":material/play_circle:", width="stretch",
                  on_click=tour_go, args=(0, messages))
        system_details(state, orders, workshops, messages)


def mode_banner(state):
    source = state["desk_source"]
    if source == "cached":
        html('<div class="mode-banner"><b>REHEARSAL MODE</b><span>Uses verified cached extraction. Allocation logic remains live.</span></div>')
    elif source == "fixture":
        html('<div class="mode-banner"><b>REHEARSAL MODE</b><span>Uses test fixture extraction, not model output. Allocation logic remains live.</span></div>')


def main():
    st.set_page_config(page_title="Quick Response Desk", page_icon=":material/hub:", layout="wide",
                       initial_sidebar_state="expanded")
    state = st.session_state
    try:
        orders, workshops, messages = load_inputs()
    except (OSError, ValueError) as error:
        inject_css()
        html(banner("Could not load the register", " " + str(error), "risk"))
        return
    for key, value in state.get("kept_controls", {}).items():
        if key not in state:
            state[key] = value
    init_session(state, workshops)
    if state.get("desk_page") not in PAGES:
        state["desk_page"] = "Dispatch"
    if state.get("desk_source") not in rehearsal.SOURCES:
        state["desk_source"] = "live"
    inject_css(presentation=state.get("presentation_mode", False))
    sidebar(state, orders, workshops, messages)
    mode_banner(state)
    page = state["desk_page"]
    if page == "Workshop Network":
        network.render(workshops)
    elif page == "Simulation Lab":
        lab.render(workshops)
    elif page == "Audit Trail":
        audit.render(workshops)
    else:
        dispatch.render(orders, workshops, messages)
    demo_controller(messages)
    state["kept_controls"] = {key: state[key] for key in KEEP if key in state}
    if page != "Simulation Lab":
        lab.prewarm()  # Cached once per server; the page is already drawn.


if __name__ == "__main__":
    main()
