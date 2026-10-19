"""Quick Response Desk. Run: uv run streamlit run src/app.py

Four areas: Dispatch (default), Workshop Network, Simulation Lab, Audit Trail.
The model only reads requests; Python validates, estimates, scores and selects;
a person confirms. Dispatch is a preview: only the explicit confirmation writes
an audit row and updates this session's queue. No workshop is ever contacted.
Session logic lives in desk.py; presentation lives in ui/.
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
# Streamlit drops a widget's state on runs where it is not drawn (other pages).
# These values are restored when the page that owns them is shown again.
KEEP = ("desk_today", "desk_preset", "desk_message", "inbox_search",
        "net_category", "net_pieces", "net_due",
        "lab_seed", "lab_focus", "lab_scenario", "lab_late", "lab_order",
        "sb_lateness", "sb_defect", "sb_fairness", "sb_robustness", "sb_cost",
        "audit_log", "audit_q", "audit_sender", "audit_workshop", "audit_kind", "audit_day")
DEMO = [("R09", "Normal allocation", "A complete request with a speed preference."),
        ("R01", "Clarification", "Two orders match. The desk asks which one."),
        ("R08", "Refused workshop", "The suggested workshop is over its batch cap."),
        ("R02", "Unanswerable request", "Asks for data the desk does not hold."),
        ("R30", "Impossible deadline", "No workshop can make the date."),
        ("R28", "Already late", "The due date has already passed.")]
SOURCE_LABELS = {"live": "Live model", "cached": "Rehearsal: recorded model replies", "fixture": "Rehearsal: test fixtures"}


def load_demo(message):
    st.session_state["desk_page"] = "Dispatch"
    dispatch.select_message(message)


def guided_demo(state, messages):
    lines = {m.split()[0]: m for m in messages}
    with st.popover("Guided demo", icon=":material/play_circle:", width="stretch"):
        html('<div class="h3">Guided demo</div><div class="note">Loads a supplied request into Dispatch. '
             'Every step uses the real decision engine; nothing is scripted.</div>')
        for rid, name, note in DEMO:
            if rid in lines:
                st.button(f"**{name}**  {rid}\n{note}", key=f"scenario_{rid}", width="stretch", on_click=load_demo, args=(lines[rid],))
        source = rehearsal.SOURCES[state["desk_source"]]
        html('<div class="note" style="margin-top:8px">Extraction: ' + esc(SOURCE_LABELS[source.key]) + '. Change it in System settings.</div>')
        saved = list(state["desk_saved"].values())
        steps = [("Choose Normal allocation", state["desk_message"] == lines.get("R09")),
                 ("Run decision and watch the five stages", bool(state.get("desk_outcomes", {}).get("R09"))),
                 ("Open Decision details, then Why this won", bool(state.get("desk_outcomes", {}).get("R09"))),
                 ("Confirm the allocation", any(r.get("parsed_request", {}).get("request_id") == "R09" for r in saved)),
                 ("Open Audit Trail and find the record", state.get("audit_visited", False))]
        html('<div class="h3" style="margin-top:14px;font-size:15px">Normal allocation walkthrough</div>'
             + "".join(f'<div class="note" style="display:flex;gap:10px"><span style="width:16px;color:{"var(--green-ink)" if done else "var(--text-4)"}">'
                       f'{"✓" if done else "○"}</span>{esc(text)}</div>' for text, done in steps))


def system_settings(state, orders, workshops, messages):
    live = rehearsal.live_status()
    with st.popover("System settings", icon=":material/tune:", width="stretch"):
        html('<div class="h3">System settings</div>')
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
                ("Workshops", f"{len(workshops)} loaded")]
        html('<dl class="kv" style="grid-template-columns:150px 1fr;font-size:13.5px">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")
        st.toggle("Presentation mode", key="presentation_mode",
                  help="Hides developer detail and Streamlit chrome for screen recording. Calculations do not change.")
        st.button("Reset demo session", key="demo_reset", width="stretch", on_click=reset_session, args=(state, workshops),
                  help="Restores the 1 April queues, clears decisions in this session and empties the rehearsal log. "
                       "The live audit log is never touched.")


def sidebar(state, orders, workshops, messages):
    with st.sidebar:
        html('<div class="wordmark"><i></i><b>Quick Response Desk</b><span>Subcontracting Operations</span></div>')
        with st.container(key="nav"):
            st.radio("Navigate", PAGES, key="desk_page", label_visibility="collapsed")
        html('<div class="side-spacer"></div>')
        guided_demo(state, messages)
        system_settings(state, orders, workshops, messages)


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
        state["audit_visited"] = True
        audit.render(workshops)
    else:
        dispatch.render(orders, workshops, messages)
    state["kept_controls"] = {key: state[key] for key in KEEP if key in state}
    if page != "Simulation Lab":
        lab.prewarm()  # Cached once per server; the page is already drawn.


if __name__ == "__main__":
    main()
