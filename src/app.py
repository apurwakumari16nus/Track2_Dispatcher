"""Threadline by Sweater Co, the subcontracting desk. Run: uv run streamlit run src/app.py

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
from ui import audit, dispatch, explain, guide, lab, network
from ui.components import banner, esc, html, icon, inject_css, mode_ribbon

PAGES = ["Dispatch", "Workshop Network", "Simulation Lab", "Audit Trail"]
ICONS = {"Dispatch": ":material/send:", "Workshop Network": ":material/hub:", "Simulation Lab": ":material/science:",
         "Audit Trail": ":material/verified_user:"}
# Page values that must survive navigation are kept under their own session keys,
# never under widget keys (see ui/state.py), so no restore step is needed here.
SOURCE_LABELS = {"live": "Live model", "cached": "Rehearsal: recorded model replies", "fixture": "Rehearsal: test fixtures"}


def system_details(state, orders, workshops, messages):
    live = rehearsal.live_status()
    with st.popover("System details", icon=":material/tune:", width="stretch"):
        html('<div class="title" style="font-size:1.1667rem">System details</div>'
             '<div class="meta" style="font-size:0.9333rem;margin-bottom:0.4rem">How requests are read. Allocation logic is always live.</div>')
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
        html('<dl class="kv" style="grid-template-columns:10.6667rem 1fr;font-size:0.9333rem;margin:0.4rem 0 0.5333rem">'
             + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")
        st.toggle("Presentation mode", key="presentation_mode",
                  help="Larger type for projectors and screen recording; hides developer detail and Streamlit chrome. Calculations do not change.")
        st.button("Reset demo session", key="demo_reset", width="stretch", on_click=reset_session, args=(state, workshops),
                  help="Restores the 1 April queues, clears decisions in this session and empties the rehearsal log. "
                       "The live audit log is never touched.")


def status_card(state, workshops) -> str:
    """System status for the shell. Every row is a real check of this session."""
    source, live = state["desk_source"], rehearsal.live_status()
    if source in ("cached", "fixture"):
        dot, head, reading, tone = "rehearsal", "Rehearsal mode", ("Recorded replies" if source == "cached" else "Test fixtures"), "warn"
    elif live["ready"]:
        dot, head, reading, tone = "live", "System ready", "Live model", "ok"
    else:
        dot, head, reading, tone = "off", "Model not configured", "Not set", "off"
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    queue = state["desk_queue_date"]
    rows = [("Request reading", reading, tone), ("Workshops", f"{active} of {len(workshops)} active", "ok"),
            ("Allocation", "Python", "ok"), ("Queues as of", f"{queue.day} {queue:%b}", "ok"),
            ("Confirmed", str(len(state["desk_saved"])), "ok")]
    marks = {"ok": "check_circle", "warn": "error", "off": "cancel"}
    lines = "".join(f'<div class="sc-row {t}">{icon(marks[t])}<span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v, t in rows)
    return f'<div class="side-card"><div class="sc-head"><i class="{dot}"></i>{esc(head)}</div>{lines}</div>'


def sidebar(state, orders, workshops, messages):
    with st.sidebar:
        html('<div class="brand"><img class="brand-mark" src="app/static/brand/threadline-mark.png" alt="">'
             '<div><div class="brand-word">Thread<span>line</span></div><div class="brand-sub">by Sweater Co</div></div></div>'
             '<div class="side-label">Operations</div>')
        with st.container(key="nav"):
            st.radio("Navigate", PAGES, key="desk_page", label_visibility="collapsed", format_func=lambda p: f"{ICONS[p]} {p}")
        with st.container(key="side_foot"):
            html(status_card(state, workshops))
            st.button("Guided demo", key="demo_start", icon=":material/play_circle:", width="stretch",
                      on_click=guide.open_intro, help="Follow one request from the inbox to its audit record.")
            system_details(state, orders, workshops, messages)
            html(f'<div class="user-card"><div class="uc-av">{icon("person")}</div><div><b>Dispatcher</b>'
                 '<small>You approve every decision</small></div></div>')


def mode_banner(state):
    source = state["desk_source"]
    if source == "cached":
        html(mode_ribbon("Rehearsal mode", "Uses verified cached extraction, not a live model call.", "Allocation logic remains live"))
    elif source == "fixture":
        html(mode_ribbon("Rehearsal mode", "Uses test fixture extraction, not model output.", "Allocation logic remains live"))


def main():
    st.set_page_config(page_title="Threadline by Sweater Co", page_icon=str(ROOT / "src/static/brand/threadline-mark.png"),
                       layout="wide", initial_sidebar_state="expanded")
    state = st.session_state
    try:
        orders, workshops, messages = load_inputs()
    except (OSError, ValueError) as error:
        inject_css()
        html(banner("Could not load the register", " " + str(error), "risk"))
        return
    init_session(state, workshops)
    if state.get("desk_page") not in PAGES:
        state["desk_page"] = "Dispatch"
    if state.get("desk_source") not in rehearsal.SOURCES:
        state["desk_source"] = "live"
    inject_css(presentation=state.get("presentation_mode", False))
    sidebar(state, orders, workshops, messages)
    page = state["desk_page"]
    state["_app_run"] = True   # Cleared below; a fragment-only rerun sees False.
    mode_banner(state)
    if page == "Workshop Network":
        network.render(workshops)
    elif page == "Simulation Lab":
        lab.render(workshops)
    elif page == "Audit Trail":
        audit.render(workshops)
    else:
        dispatch.render(orders, workshops, messages)
    guide.render(workshops, messages)
    state["_app_run"] = False
    if page != "Simulation Lab":
        lab.prewarm()  # Cached once per server; the page is already drawn.


if __name__ == "__main__":
    main()
