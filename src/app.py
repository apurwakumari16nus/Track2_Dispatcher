"""Quick Response Subcontracting Desk. Run: uv run streamlit run src/app.py

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
from desk import (TODAY, Preview, confirm_preview, filtered_records, init_session, load_inputs, make_preview,  # noqa: F401
                  projected_queues, reset_session, signature)
from ui import audit, dispatch, explain, lab, network
from ui.components import banner, esc, html, inject_css

PAGES = ["Dispatch", "Workshop Network", "Simulation Lab", "Audit Trail"]
# Streamlit drops a widget's state on runs where it is not drawn (other pages).
# These values are restored when the page that owns them is shown again.
KEEP = ("desk_today", "desk_preset", "desk_message", "inbox_search",
        "net_category", "net_pieces", "net_due", "net_view",
        "lab_seed", "lab_focus", "lab_scenario", "lab_metric", "lab_late", "lab_order",
        "sb_lateness", "sb_defect", "sb_fairness", "sb_robustness", "sb_cost",
        "audit_log", "audit_q", "audit_sender", "audit_workshop", "audit_kind", "audit_day")


def sidebar(state, orders, workshops, messages):
    source = rehearsal.SOURCES[state["desk_source"]]
    live = rehearsal.live_status()
    with st.sidebar:
        html('<div class="brand"><div class="brand-mark">QR</div><div><div class="brand-name">Subcontracting Desk</div>'
             '<div class="brand-sub">Track 2 · Group 01</div></div></div>')
        with st.container(key="nav"):
            st.radio("Navigate", PAGES, key="desk_page", label_visibility="collapsed")
        html('<div class="side-label">Extraction source</div>')
        st.radio("Extraction source", list(rehearsal.SOURCES), key="desk_source", label_visibility="collapsed",
                 format_func=lambda key: rehearsal.SOURCES[key].label, on_change=dispatch.invalidate)
        html(f'<div class="side-foot" style="margin-top:.2rem">{esc(source.description)}</div>')
        today = max(state["desk_today"], state["desk_queue_date"])
        prompt = intake.build_system_prompt(today, orders, workshops)
        recorded = rehearsal.recorded_coverage(prompt, messages)
        lines = [("ok", f"{len(workshops)} workshops loaded"),
                 ("ok", f"Queues as of {explain.long_date(state['desk_queue_date'])}"),
                 ("info", explain.objective_label(state["desk_preset"])),
                 ("ok" if live["ready"] else "risk", f"Model {live['model']}" if live["ready"] else "Live model not configured"),
                 ("ok" if recorded else "warn", f"{recorded} of {len(messages)} replies recorded")]
        html('<div class="side-label">System status</div><div class="side-status">'
             + "".join(f'<div><span class="dot {tone}"></span>{esc(text)}</div>' for tone, text in lines) + "</div>")
        html('<div class="side-label">Demo</div>')
        st.button("Reset demo session", key="demo_reset", width="stretch", on_click=reset_session, args=(state, workshops),
                  help="Restores the 1 April queues, clears previews and confirmations in this session, and empties the "
                       "rehearsal audit log. The live audit log is never touched.")
        html('<div class="side-foot">Model reads · Python decides · Human confirms.<br>Confirming never contacts a workshop.</div>')


def sanitise(state, workshops):
    """Drop restored filter values that are no longer valid options."""
    if state.get("desk_page") not in PAGES:
        state["desk_page"] = "Dispatch"
    if state.get("desk_source") not in rehearsal.SOURCES:
        state["desk_source"] = "live"


def main():
    st.set_page_config(page_title="Subcontracting Desk", page_icon=":material/hub:", layout="wide",
                       initial_sidebar_state="expanded")
    inject_css()
    try:
        orders, workshops, messages = load_inputs()
    except (OSError, ValueError) as error:
        html(banner("Could not load the register", str(error), "risk"))
        return
    state = st.session_state
    for key, value in state.get("kept_controls", {}).items():
        if key not in state:
            state[key] = value
    init_session(state, workshops)
    sanitise(state, workshops)
    sidebar(state, orders, workshops, messages)
    page = state["desk_page"]
    if page == "Workshop Network":
        network.render(workshops)
    elif page == "Simulation Lab":
        lab.render(workshops)
    elif page == "Audit Trail":
        audit.render(workshops)
    else:
        dispatch.render(orders, workshops, messages)
    state["kept_controls"] = {key: state[key] for key in KEEP if key in state}
    if page != "Simulation Lab":
        lab.prewarm()  # Cached once per server; the page is already drawn.


if __name__ == "__main__":
    main()
