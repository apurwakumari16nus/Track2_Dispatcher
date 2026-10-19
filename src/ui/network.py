"""Workshop Network: the queryable register, using the same tools as dispatch.

Read-only. Eligibility, ETA and cost come from tools.py with this session's
projected queues; nothing is allocated and the model is never called.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

import desk
import tools
from ui import explain
from ui.components import esc, html, load_bar, page_head, table, tag


def render(workshops):
    state = st.session_state
    today = max(state["desk_today"], state["desk_queue_date"])
    state.setdefault("net_category", "TOPS")
    state.setdefault("net_pieces", 1500)
    state.setdefault("net_due", today + timedelta(days=14))
    if state["net_due"] < today:
        state["net_due"] = today
    page_head("Workshop network", "Who can take this batch, and when would it be back?")
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    flags = set(state["desk_allocator"].shock_monitor.flags)

    with st.container(key="net_filters"):
        a, b, c, d = st.columns([1.1, 1, 1, 1.3], vertical_alignment="bottom")
        with a:
            category = st.segmented_control("Category", ["TOPS", "ACCESSORIES"], key="net_category", required=True,
                                            format_func=str.capitalize)
        with b:
            pieces = st.number_input("Batch size", min_value=1, max_value=1_000_000, step=100, key="net_pieces")
        with c:
            due = st.date_input("Target date", key="net_due", min_value=today, format="DD/MM/YYYY")
        with d:
            html(f'<div class="meta">Estimates from {esc(explain.long_date(today))} using the session queues</div>')

    batch = {"category": category, "pieces": int(pieces), "due_date": due}
    checks = {row["workshop_id"]: row for row in tools.check_eligibility(batch, workshops)}
    estimates = {wid: {**tools.estimate_eta(batch, wid, workshops, queues, today), **tools.estimate_cost(batch, wid, workshops)}
                 for wid, row in checks.items() if row["eligible"]}
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    capable = sum(w.status == "ACTIVE" and category in w.makes for w in workshops.values())
    on_time = [e for e in estimates.values() if e["days_to_spare"] >= 0]
    stats = [(len(workshops), "workshops"), (active, "active"), (capable, f"can make {category.lower()}"),
             (len(estimates), "can take this batch"), (len(on_time), f"back by {explain.short_date(due)}")]
    html('<div class="grid g5">' + "".join(f'<div class="stat"><strong>{n}</strong><small>{esc(label)}</small></div>' for n, label in stats) + "</div>")
    fastest = min(estimates.values(), key=lambda e: e["total_days"], default=None)
    if fastest:
        html(f'<div class="answer">Fastest for {int(pieces):,} {esc(category.lower())}: <b>{esc(workshops[fastest["workshop_id"]].name)}</b>, '
             f'back {esc(explain.short_date(fastest["eta_date"]))}.</div>')
    else:
        html('<div class="answer">No active workshop can take this batch as one job.</div>')

    top = max(max(queues.values(), default=0), 4)
    order = sorted(workshops, key=lambda wid: (wid not in estimates, estimates.get(wid, {}).get("total_days", 0), wid))
    rows, classes = [], []
    for wid in order:
        w, estimate = workshops[wid], estimates.get(wid)
        label, tone = explain.workshop_status(checks[wid], estimate, wid in flags)
        status = tag(label, tone) + (" " + tag("Suspect queue", "warn") if wid in flags else "")
        if estimate:
            spare = estimate["days_to_spare"]
            ret = f"<b>{esc(explain.short_date(estimate['eta_date']))}</b><small>{esc(explain.days(abs(spare)))} {'late' if spare < 0 else 'spare'}</small>"
            cost = f"{estimate['total_cost']:,.0f}<small>{w.cost:g} per piece</small>"
        else:
            ret = f'<span class="meta">{esc(explain.reason_text(checks[wid]["reason"]))}</span>'
            cost = f'<span class="meta">{w.cost:g} per piece</span>'
        rows.append([f"<b>{esc(w.name)}</b><small>{esc(wid)}</small>", status,
                     esc(" and ".join(sorted(m.lower() for m in w.makes)).capitalize()), f"{w.capacity:,} a day",
                     load_bar(queues[wid], top), ret, cost, f"{w.defect_rate:.0%}",
                     f"{w.max_batch:,}" if w.max_batch else '<span class="meta">None</span>'])
        classes.append("" if estimate else "dim")
    html(table(["Workshop", "Status", "Makes", "Capacity", "Queue", "Return estimate", "Cost", "Defect", "Batch limit"],
               rows, right=(), classes=classes))
    html('<div class="meta">Estimates are queue plus pieces divided by capacity plus transport, rounded to a day. '
         'They exclude sampled rework and unannounced closures. Queues are session projections from the 1 April snapshot.</div>')
