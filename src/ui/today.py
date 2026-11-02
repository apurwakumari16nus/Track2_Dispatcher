"""Today: what needs the dispatcher now, and every batch out at a workshop until it comes back.

Three lanes (needs a decision, due back today or overdue, back after the
customer date), then the due-back timeline: one row per workshop, a bar per
batch from the day it was sent to its booked return date. Workshops cannot
report status, so arrivals are recorded here by the dispatcher (batches.py).
The "as of" date only changes this view; it never moves the desk's scenario
date or any queue.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

import batches
import desk
import inbox_store
from ui import explain
from ui.components import esc, html, icon, status_pill

TONES = {"overdue": "risk", "due_today": "warn", "at_risk": "warn", "on_track": "info", "received": "conf"}
LIVE_OPEN = ("Received", "Needs reply", "Recommended")


def open_request(message: str):
    from ui import dispatch
    dispatch.select_message(message)
    st.session_state["desk_page"] = "Dispatch"


def open_thread(thread_id: str):
    from ui import dispatch
    dispatch.select_live(thread_id)
    st.session_state["desk_page"] = "Dispatch"


def mark(key: str, asof: date, path, undo: bool = False):
    batches.record_arrival(key, by="Dispatcher", scenario_date=asof, path=path, undo=undo)


def card_line(b: dict, asof: date) -> str:
    st_ = batches.status(b, asof)
    when = (f"due back {explain.short_date(b['back'].isoformat())}" if st_ != "overdue"
            else f"{explain.days((asof - b['back']).days)} past {explain.short_date(b['back'].isoformat())}")
    late = (f" · customer date {explain.short_date(b['due'].isoformat())}" if b["due"] else "")
    return (f'<div class="tb-item"><div class="tb-top"><b class="id">{esc(b["order_id"] or "")}</b>{status_pill(batches.STATUSES[st_], TONES[st_])}</div>'
            f'<div class="tb-body">{b["pieces"]:,} {esc((b["product"] or "pieces").lower())} at <b>{esc(b["workshop"])}</b></div>'
            f'<div class="tb-meta">{esc(when)}{esc(late)}</div></div>')


def lanes(messages, out, asof, path):
    state = st.session_state
    outcomes = state.get("desk_outcomes", {})
    from ui.dispatch import envelope
    pending = [m for m in messages if envelope(m)[0] not in outcomes]
    live = [t for t in inbox_store.threads() if t["status"] in LIVE_OPEN]
    back = [b for b in out if batches.status(b, asof) in ("overdue", "due_today")]
    risk = [b for b in out if batches.status(b, asof) == "at_risk"]
    cols = st.columns(3, gap="medium")
    with cols[0], st.container(key="tb_decide"):
        html(f'<div class="tb-head">{icon("inbox")}<b>Needs a decision</b><span>{len(pending) + len(live)}</span></div>'
             '<div class="tb-sub">Requests nobody has decided yet</div>')
        for t in live[:3]:
            text_col, go = st.columns([0.8, 0.2], vertical_alignment="center")
            text_col.markdown(f'<div class="tb-item"><div class="tb-top"><b>{esc(t["sender"])}</b>{status_pill(t["status"], "warn" if t["status"] == "Needs reply" else "info")}</div>'
                              f'<div class="tb-body">{esc(t["text"][:90])}</div></div>', unsafe_allow_html=True)
            go.button("Open", key=f"tb_live_{t['id']}", on_click=open_thread, args=(t["id"],), type="tertiary")
        for m in pending[: max(0, 5 - len(live[:3]))]:
            rid, time, sender, body = envelope(m)
            text_col, go = st.columns([0.8, 0.2], vertical_alignment="center")
            text_col.markdown(f'<div class="tb-item"><div class="tb-top"><b>{esc(sender)}</b><span class="tb-rid">{esc(rid)} · {esc(time)}</span></div>'
                              f'<div class="tb-body">{esc(body[:90])}</div></div>', unsafe_allow_html=True)
            go.button("Open", key=f"tb_req_{rid}", on_click=open_request, args=(m,), type="tertiary")
        if len(pending) > 5:
            html(f'<div class="tb-more">{len(pending) - 5} more in the Dispatch inbox</div>')
        if not pending and not live:
            html('<div class="tb-empty">Every request has a decision.</div>')
    with cols[1], st.container(key="tb_back"):
        html(f'<div class="tb-head">{icon("assignment_return")}<b>Due back today or overdue</b><span>{len(back)}</span></div>'
             '<div class="tb-sub">Check the goods arrived, then mark them received</div>')
        for b in sorted(back, key=lambda b: b["back"]):
            html(card_line(b, asof))
            st.button("Mark received", key=f"tb_rcv_{b['key']}", on_click=mark, args=(b["key"], asof, path), icon=":material/check:")
        if not back:
            html(f'<div class="tb-empty">Nothing is due back on or before {esc(explain.short_date(asof.isoformat()))}.</div>')
    with cols[2], st.container(key="tb_risk"):
        html(f'<div class="tb-head">{icon("warning")}<b>Back after the customer date</b><span>{len(risk)}</span></div>'
             '<div class="tb-sub">Booked to return later than the order is due</div>')
        for b in sorted(risk, key=lambda b: b["due"] or b["back"]):
            html(card_line(b, asof))
        if not risk:
            html('<div class="tb-empty">Every open batch is booked to return by its customer date.</div>')


def timeline(out, asof, workshops, path):
    shown = [b for b in out if st.session_state.get("tl_received") or not b["received"]]
    html('<div class="title" style="margin-top:1.6rem">Due-back timeline</div>'
         '<div class="meta" style="font-size:0.9333rem">Each bar runs from the day a batch was sent to the date it is booked to come back. '
         'The diamond is the customer date; the line is the board date.</div>')
    st.toggle("Show received batches", key="tl_received")
    if not shown:
        html('<div class="tb-empty" style="margin-top:0.6rem">No batch is out at a workshop. Confirm a decision on the Dispatch page and it appears here.</div>')
        return
    days_ = [d for b in shown for d in (b["sent"], b["back"], b["due"]) if d] + [asof]
    start, end = min(days_) - timedelta(days=1), max(days_) + timedelta(days=2)
    span = (end - start).days

    def x(d: date) -> float:
        return (d - start).days / span * 100

    ticks = f'<span class="tl-tick now" style="left:{x(asof):.2f}%">Board date</span>' + "".join(f'<span class="tl-tick" style="left:{x(start + timedelta(days=i)):.2f}%">{(start + timedelta(days=i)).day} '
                    f'{(start + timedelta(days=i)):%b}</span>' for i in range(0, span + 1, max(1, span // 10)))
    rows = []
    order = {wid: n for n, wid in enumerate(workshops)}
    for wid in sorted({b["workshop_id"] for b in shown}, key=lambda w: order.get(w, 99)):
        bars = []
        mine = sorted([b for b in shown if b["workshop_id"] == wid], key=lambda b: (b["sent"] or asof, b["back"] or asof))
        for lane, b in enumerate(mine):
            status = batches.status(b, asof)
            left, right = x(b["sent"] or asof), x((b["back"] or asof) + timedelta(days=1))
            label = f'{b["order_id"]} · {b["pieces"]:,}'
            tip = (f'{b["order_id"]}: {b["pieces"]:,} pieces, sent {explain.short_date(str(b["sent"]))}, back {explain.short_date(str(b["back"]))}'
                   + (f', customer date {explain.short_date(str(b["due"]))}' if b["due"] else "") + f'. {batches.STATUSES[status]}.'
                   + (" Override." if b["override"] else "") + (" Split part." if b["split"] else ""))
            due = (f'<i class="tl-due" style="left:{x(b["due"]):.2f}%;top:{lane * 1.9 + 0.95}rem" title="Customer date"></i>' if b["due"] else "")
            bars.append(f'<div class="tl-bar {status}" style="left:{left:.2f}%;width:{max(right - left, 1.5):.2f}%;top:{lane * 1.9 + 0.3}rem" '
                        f'title="{esc(tip)}"><span>{esc(label)}</span></div>{due}')
        rows.append(f'<div class="tl-row"><div class="tl-name"><b>{esc(workshops[wid].name if wid in workshops else wid)}</b>'
                    f'<small>{len(mine)} batch{"es" if len(mine) != 1 else ""}</small></div>'
                    f'<div class="tl-track" style="height:{len(mine) * 1.9 + 0.6}rem"><i class="tl-now" style="left:{x(asof):.2f}%"></i>{"".join(bars)}</div></div>')
    legend = "".join(f'<span><i class="tl-key {k}"></i>{esc(v)}</span>' for k, v in batches.STATUSES.items())
    html(f'<div class="tl"><div class="tl-axis"><div></div><div class="tl-scale">{ticks}</div></div>'
         f'<div class="tl-body">{"".join(rows)}</div>'
         f'<div class="tl-legend">{legend}<span><i class="tl-key due"></i>Customer date</span></div></div>')
    still_out = [b for b in out if not b["received"]]
    arrived = [b for b in out if b["received"]]
    left, right = st.columns([3, 2], gap="medium")
    with left:
        if still_out:
            pick = st.selectbox("Mark a batch received", [b["key"] for b in still_out], key="tl_pick",
                                format_func=lambda k: next(f'{b["order_id"]} at {b["workshop"]}, {b["pieces"]:,} pieces, due back '
                                                           f'{explain.short_date(str(b["back"]))}' for b in still_out if b["key"] == k))
            st.button("Mark received", key="tl_mark", on_click=mark, args=(pick, asof, path), icon=":material/check:", type="primary")
    with right:
        if arrived:
            last = arrived[-1]
            html(f'<div class="meta">Last arrival recorded: {esc(last["order_id"])} at {esc(last["workshop"])}, '
                 f'by {esc(last["received"]["by"])} on {esc(explain.short_date(last["received"]["scenario_date"]))}.</div>')
            st.button("Undo that arrival", key="tl_undo", on_click=mark, args=(last["key"], asof, path, True), type="tertiary")


def render(workshops, messages):
    state = st.session_state
    source = state.get("desk_source", "live")
    log_path = desk.audit_path(source)
    path = batches.received_path(log_path)
    base = state.get("desk_today", desk.TODAY)
    if "today_asof" not in state:
        state["today_asof"] = base
    head, pick = st.columns([3, 1], vertical_alignment="bottom")
    with head:
        html('<div class="kicker"><span>Today</span></div>'
             '<div class="home-title" style="margin-top:0.8rem">What needs you today</div>'
             f'<div class="home-sub">Decisions waiting, batches due back, and work booked to return late. Reads the '
             f'{esc(desk.audit_log_name(source))} log, so the desk and the group chat show up together.</div>')
    with pick:
        asof = st.date_input("Board date", key="today_asof", format="DD/MM/YYYY",
                             help="Move this forward to see what would be due back or overdue. It does not change the desk's scenario date.")
    out = batches.out_batches(log_path)
    counts = {k: sum(batches.status(b, asof) == k for b in out) for k in batches.STATUSES}
    html('<div class="tb-sum">' + "".join(
        f'<div class="tb-kpi {k}"><strong>{counts[k]}</strong><small>{esc(v)}</small></div>' for k, v in batches.STATUSES.items()) + "</div>")
    lanes(messages, out, asof, path)
    timeline(out, asof, workshops, path)
