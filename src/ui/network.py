"""Workshop Network: the queryable register, using the same tools as dispatch.

Read-only. Eligibility, ETA and cost come from tools.py with this session's
projected queues; nothing is allocated and the model is never called. The map
is a schematic of the register (the factory and its eight partners), not
geography: line style encodes the answer to the current query.
"""

from __future__ import annotations

from datetime import timedelta
import math

import streamlit as st

import desk
import tools
from ui import explain
from ui.components import esc, html, page_head, status_pill, table

# Node state -> (line class, node class). "hit" is the only state that wears the beam.
STATES = {"hit": ("ln hit", "nd hit"), "late": ("ln late", "nd late"), "off": ("ln off", "nd off"), "down": ("ln down", "nd down")}


def node_state(check, estimate) -> str:
    if not check["eligible"]:
        return "down" if check["reason"] == "suspended" else "off"
    return "late" if estimate["days_to_spare"] < 0 else "hit"


def network_svg(order, workshops, states, flags, fastest_id) -> str:
    """Schematic hub-and-spoke map: factory at the centre, workshops on an ellipse."""
    cx, cy, rx, ry = 230, 182, 168, 128
    defs, lines, nodes = [], [], []
    for i, wid in enumerate(order):
        angle = -math.pi / 2 + i * 2 * math.pi / len(order)
        x, y = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
        line_cls, node_cls = STATES[states[wid]]
        if states[wid] == "hit":
            defs.append(f'<linearGradient id="beam{i}" gradientUnits="userSpaceOnUse" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}">'
                        '<stop offset="0" stop-color="#48D9E6" stop-opacity=".25"/><stop offset="1" stop-color="#28C8AC"/></linearGradient>')
            lines.append(f'<line class="{line_cls}" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="url(#beam{i})"/>'
                         f'<line class="ln flow" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>')
        else:
            lines.append(f'<line class="{line_cls}" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>')
        below = y >= cy
        ty = y + 34 if below else y - 26
        ring = '<circle class="best" cx="{0:.1f}" cy="{1:.1f}" r="24"/>'.format(x, y) if wid == fastest_id else ""
        flag = f'<circle class="flag" cx="{x + 13:.1f}" cy="{y - 13:.1f}" r="5"/>' if wid in flags else ""
        nodes.append(f'<g>{ring}<circle class="{node_cls}" cx="{x:.1f}" cy="{y:.1f}" r="16"/>'
                     f'<text class="nid" x="{x:.1f}" y="{y + 4:.1f}">{esc(wid)}</text>{flag}'
                     f'<text class="nname {states[wid]}" x="{x:.1f}" y="{ty:.1f}">{esc(workshops[wid].name)}</text></g>')
    hub = (f'<circle class="hub-halo" cx="{cx}" cy="{cy}" r="44"/><circle class="hub" cx="{cx}" cy="{cy}" r="33"/>'
           f'<text class="hub-t" x="{cx}" y="{cy + 3.5}">FACTORY</text>')
    return (f'<svg class="net-svg" viewBox="0 0 460 370" role="img" aria-label="Schematic map of the factory and its eight partner workshops">'
            f'<defs>{"".join(defs)}</defs>{"".join(lines)}{hub}{"".join(nodes)}</svg>')


def node_card(wid, w, check, estimate, state, flagged, queue, top, fastest_id) -> str:
    label, tone = explain.workshop_status(check, estimate, flagged)
    pills = status_pill(label, "beam-pill" if state == "hit" else tone)
    if wid == fastest_id:
        pills = status_pill("Fastest", "beam-pill") + " " + status_pill(label, "ok")
    if flagged:
        pills += " " + status_pill("Suspect queue", "warn")
    if estimate:
        spare = estimate["days_to_spare"]
        eta = (f'<div class="nc-eta">Back {esc(explain.short_date(estimate["eta_date"]))}'
               f'<span>{esc(explain.days(abs(spare)))} {"late" if spare < 0 else "spare"}, cost {estimate["total_cost"]:,.0f}</span></div>')
    else:
        eta = f'<div class="nc-eta none">{esc(explain.reason_text(check["reason"]))}</div>'
    width = min(queue / top, 1) * 100 if top else 0
    cls = {"hit": " hit", "off": " off", "down": " off down"}.get(state, "")
    makes = " and ".join(sorted(m.lower() for m in w.makes))
    return (f'<div class="node-card{cls}"><div class="nc-top"><div><div class="nc-name">{esc(w.name)}</div>'
            f'<div class="nc-id">{esc(wid)}, makes {esc(makes)}</div></div></div><div class="nc-pills">{pills}</div>{eta}'
            f'<div class="nc-grid"><div><small>Capacity</small><b>{w.capacity:,}/day</b></div><div><small>Per piece</small><b>{w.cost:g}</b></div>'
            f'<div><small>Defect</small><b>{w.defect_rate:.0%}</b></div></div>'
            f'<div><div class="nc-q"><small>Queue</small><span>{queue:.1f} days</span></div>'
            f'<div class="gauge"><span class="{"high" if queue >= 5 else ""}" style="width:{width:.0f}%"></span></div></div></div>')


def render(workshops):
    state = st.session_state
    today = max(state["desk_today"], state["desk_queue_date"])
    state.setdefault("net_category", "TOPS")
    state.setdefault("net_pieces", 1500)
    state.setdefault("net_due", today + timedelta(days=14))
    state.setdefault("net_view", "Map")
    if state["net_due"] < today:
        state["net_due"] = today
    head, bar = st.columns([1, 1.25], vertical_alignment="bottom")
    with head:
        page_head("Workshop network", "Who can take this batch?")
    with bar:
        with st.container(key="net_bar"):
            a, b, c, d = st.columns([1.25, 1, 1, 1.05], vertical_alignment="bottom")
            with a:
                category = st.segmented_control("Category", ["TOPS", "ACCESSORIES"], key="net_category", required=True,
                                                format_func=str.capitalize)
            with b:
                pieces = st.number_input("Batch size", min_value=1, max_value=1_000_000, step=100, key="net_pieces")
            with c:
                due = st.date_input("Target date", key="net_due", min_value=today, format="DD/MM/YYYY")
            with d:
                view = st.segmented_control("View", ["Map", "Table"], key="net_view", required=True)

    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    flags = set(state["desk_allocator"].shock_monitor.flags)
    batch = {"category": category, "pieces": int(pieces), "due_date": due}
    checks = {row["workshop_id"]: row for row in tools.check_eligibility(batch, workshops)}
    estimates = {wid: {**tools.estimate_eta(batch, wid, workshops, queues, today), **tools.estimate_cost(batch, wid, workshops)}
                 for wid, row in checks.items() if row["eligible"]}
    states = {wid: node_state(checks[wid], estimates.get(wid)) for wid in workshops}
    active = sum(w.status == "ACTIVE" for w in workshops.values())
    capable = sum(w.status == "ACTIVE" and category in w.makes for w in workshops.values())
    on_time = [e for e in estimates.values() if e["days_to_spare"] >= 0]
    fastest = min(estimates.values(), key=lambda e: (e["total_days"], e["workshop_id"]), default=None)
    fastest_id = fastest["workshop_id"] if fastest else None
    noun = category.lower()

    if fastest:
        headline = (f'<em>{len(estimates)} of {len(workshops)}</em> can take {int(pieces):,} {esc(noun)}. '
                    f'<em>{len(on_time)}</em> return by {esc(explain.short_date(due))}.')
        answer = (f'Fastest for {int(pieces):,} {esc(noun)}: <b>{esc(workshops[fastest_id].name)}</b>, back '
                  f'{esc(explain.short_date(fastest["eta_date"]))}.')
    else:
        headline = f'No active workshop can take {int(pieces):,} {esc(noun)} as one job.'
        answer = "Try a smaller batch, or split it in Dispatch."
    stats = [(len(workshops), "workshops"), (active, "active"), (capable, f"can make {noun}"),
             (len(estimates), "can take this batch"), (len(on_time), f"back by {explain.short_date(due)}")]
    chips = "".join(f'<div class="nstat"><strong>{n}</strong><small>{esc(label)}</small></div>' for n, label in stats)
    legend = ('<div class="legend"><span><i style="background:linear-gradient(90deg,#48D9E6,#28C8AC)"></i>Can take it on time</span>'
              '<span><i style="background:#F3B84B"></i>Can take it, late</span>'
              '<span><i class="dash" style="border-color:#B9C5D2"></i>Cannot take it</span>'
              '<span><i class="dash" style="border-color:#F56F67"></i>Suspended</span>'
              '<span><i class="ring"></i>Suspect queue</span></div>')
    order = sorted(workshops, key=lambda wid: (["hit", "late", "off", "down"].index(states[wid]),
                                               estimates.get(wid, {}).get("total_days", 0), wid))

    if view == "Map":
        html(f'<div class="net-hero"><div class="net-map">{network_svg(list(workshops), workshops, states, flags, fastest_id)}</div>'
             f'<div><div class="eyebrow">Register answer, from {esc(explain.long_date(today))}</div>'
             f'<div class="answer-big">{headline}</div><div class="answer">{answer}</div>'
             f'<div class="nstats">{chips}</div>{legend}</div></div>')
        top = max(max(queues.values(), default=0), 4)
        cards = [node_card(wid, workshops[wid], checks[wid], estimates.get(wid), states[wid], wid in flags, queues[wid], top, fastest_id)
                 for wid in order]
        html(f'<div class="grid g4" style="margin-top:6px">{"".join(cards)}</div>')
    else:
        html(f'<div class="answer" style="margin:4px 0 2px">{answer}</div><div class="nstats" style="margin-bottom:6px">{chips}</div>')
        register_table(order, workshops, checks, estimates, queues, flags)
    html('<div class="meta" style="margin-top:6px">Estimates are queue plus pieces divided by capacity plus transport, rounded to a day. '
         'They exclude sampled rework and unannounced closures. Queues are session projections from the 1 April snapshot.</div>')


def register_table(order, workshops, checks, estimates, queues, flags):
    rows, classes = [], []
    for wid in order:
        w, estimate = workshops[wid], estimates.get(wid)
        label, tone = explain.workshop_status(checks[wid], estimate, wid in flags)
        status = status_pill(label, tone) + (" " + status_pill("Suspect queue", "warn") if wid in flags else "")
        if estimate:
            spare = estimate["days_to_spare"]
            ret = f"<b>{esc(explain.short_date(estimate['eta_date']))}</b><small>{esc(explain.days(abs(spare)))} {'late' if spare < 0 else 'spare'}</small>"
            cost = f"{estimate['total_cost']:,.0f}<small>{w.cost:g} per piece</small>"
        else:
            ret = f'<span class="meta">{esc(explain.reason_text(checks[wid]["reason"]))}</span>'
            cost = f'<span class="meta">{w.cost:g} per piece</span>'
        rows.append([f"<b>{esc(w.name)}</b><small>{esc(wid)}</small>", status,
                     esc(" and ".join(sorted(m.lower() for m in w.makes)).capitalize()), f"{w.capacity:,} a day",
                     f"{queues[wid]:.1f} days", ret, cost, f"{w.defect_rate:.0%}",
                     f"{w.max_batch:,}" if w.max_batch else '<span class="meta">None</span>'])
        classes.append("" if estimate else "dim")
    html(table(["Workshop", "Status", "Makes", "Capacity", "Queue", "Return estimate", "Cost", "Defect", "Batch limit"],
               rows, right=(3, 4, 7, 8), classes=classes))
