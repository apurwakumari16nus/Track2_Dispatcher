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
from ui.components import banner, chip, esc, html, page_head, pill, table

TONE_CLASS = {"ok": "ok", "warn": "warn", "blocked": "risk", "muted": "muted"}


def render(workshops):
    state = st.session_state
    today = max(state["desk_today"], state["desk_queue_date"])
    state.setdefault("net_category", "TOPS")
    state.setdefault("net_pieces", 1500)
    state.setdefault("net_due", today + timedelta(days=14))
    state.setdefault("net_view", "Cards")
    if state["net_due"] < today:
        state["net_due"] = today
    page_head("Workshop network", "Who can take this batch, and when would it be back?",
              "Capability, permission, capacity and the current queue for all eight workshops. "
              "Change the batch to re-run the same eligibility and delivery tools that dispatch uses.")
    with st.container(key="net_filters"):
        a, b, c, d, e = st.columns([1.1, 1, 1, 1.25, .9], vertical_alignment="bottom")
        with a:
            category = st.segmented_control("Category", ["TOPS", "ACCESSORIES"], key="net_category", required=True,
                                            format_func=str.capitalize)
        with b:
            pieces = st.number_input("Batch size (pieces)", min_value=1, max_value=1_000_000, step=100, key="net_pieces")
        with c:
            due = st.date_input("Required back by", key="net_due", min_value=today, format="DD/MM/YYYY")
        with d:
            html(f'<div class="section-note">Estimating from</div><div style="font-size:15px;font-weight:620;padding:8px 0 4px">'
                 f'{esc(explain.long_date(today))}</div><div class="section-note">Scenario date and session queues from Dispatch</div>')
        with e:
            view = st.segmented_control("View", ["Cards", "Matrix"], key="net_view", required=True)
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    flags = set(state["desk_allocator"].shock_monitor.flags)
    batch = {"category": category, "pieces": int(pieces), "due_date": due}
    checks = {row["workshop_id"]: row for row in tools.check_eligibility(batch, workshops)}
    estimates = {wid: {**tools.estimate_eta(batch, wid, workshops, queues, today), **tools.estimate_cost(batch, wid, workshops)}
                 for wid, row in checks.items() if row["eligible"]}
    on_time = sorted((e for e in estimates.values() if e["days_to_spare"] >= 0), key=lambda e: e["total_days"])
    fastest = min(estimates.values(), key=lambda e: e["total_days"], default=None)
    answer = (f"<b>{len(estimates)} of {len(workshops)}</b> workshops can take {int(pieces):,} {category.lower()}. "
              f"<b>{len(on_time)}</b> would return them by {esc(explain.short_date(due))}.")
    if fastest:
        answer += f" Fastest: <b>{esc(workshops[fastest['workshop_id']].name)}</b>, back {esc(explain.short_date(fastest['eta_date']))}."
    html(f'<div class="answer">{answer}</div>')
    counts = {}
    for wid in workshops:
        label, _ = explain.workshop_status(checks[wid], estimates.get(wid), wid in flags)
        counts[label] = counts.get(label, 0) + 1
    html('<div class="chips">' + "".join(chip(label, str(n)) for label, n in counts.items())
         + (chip("flagged for a queue anomaly", str(len(flags)), dot="warn") if flags else "") + "</div>")
    top_queue = max(max(queues.values(), default=0), 1)
    if view == "Matrix":
        matrix(workshops, checks, estimates, queues, flags)
    else:
        cards = [card(workshops[wid], checks[wid], estimates.get(wid), queues[wid], top_queue, wid in flags) for wid in workshops]
        for start in range(0, len(cards), 4):
            html('<div class="grid c4">' + "".join(cards[start:start + 4]) + "</div>")
    html('<div class="section-note">Estimates are nominal: queue + pieces ÷ capacity + transport, rounded to a calendar day. '
         'They exclude sampled rework and unannounced closures. Queues are this session\'s projections from the 1 April snapshot, '
         'not a live feed.</div>')


def card(workshop, check, estimate, queue, top_queue, flagged):
    label, tone = explain.workshop_status(check, estimate, flagged)
    status = pill(label, TONE_CLASS[tone]) + (pill("Suspect", "warn") if flagged else "")
    if estimate:
        late = estimate["days_to_spare"] < 0
        eta = (f'<div class="ws-eta {"late" if late else "ok"}">Back {esc(explain.short_date(estimate["eta_date"]))}'
               f'<em>{esc(explain.days(abs(estimate["days_to_spare"])))} {"late" if late else "spare"} · cost {estimate["total_cost"]:,.0f}</em></div>')
    else:
        eta = f'<div class="ws-eta none">Not available: {esc(explain.ineligible_headline(check["reason"]).lower())}</div>'
    share = min(queue / top_queue, 1)
    cap = f"{workshop.max_batch:,}" if workshop.max_batch else "No cap"
    return (f'<div class="ws {tone}"><div class="ws-top"><div><div class="ws-name">{esc(workshop.name)}</div>'
            f'<div class="ws-id">{esc(workshop.workshop_id)} · {esc(" + ".join(sorted(workshop.makes)).title())}</div></div>'
            f'<div class="chips" style="justify-content:flex-end">{status}</div></div>{eta}'
            f'<div class="load"><div class="load-top"><span>Queue</span><b>{queue:.1f} days</b></div>'
            f'<div class="load-bar"><span class="{"high" if queue >= 4 else ""}" style="width:{max(share, .02):.0%}"></span></div></div>'
            f'<div class="ws-grid"><div><small>Capacity</small><b>{workshop.capacity:,}/day</b></div>'
            f'<div><small>Transport</small><b>{workshop.lead_days} d</b></div>'
            f'<div><small>Batch cap</small><b>{cap}</b></div><div><small>Cost</small><b>{workshop.cost:g}/pc</b></div>'
            f'<div><small>Defect risk</small><b>{workshop.defect_rate:.0%}</b></div><div><small>Status</small><b>{esc(workshop.status.capitalize())}</b></div></div>'
            f'<div class="section-note" style="font-size:12.5px">“{esc(workshop.notes)}”</div></div>')


def matrix(workshops, checks, estimates, queues, flags):
    rows, classes = [], []
    for wid, workshop in workshops.items():
        estimate = estimates.get(wid)
        label, tone = explain.workshop_status(checks[wid], estimate, wid in flags)
        rows.append([f"<b>{esc(workshop.name)}</b><small>{esc(wid)}</small>", pill(label, TONE_CLASS[tone], soft=True),
                     esc(" + ".join(sorted(workshop.makes)).title()), f"{workshop.capacity:,}", f"{queues[wid]:.1f}",
                     str(workshop.lead_days), f"{workshop.max_batch:,}" if workshop.max_batch else "None",
                     f"{workshop.cost:g}", f"{workshop.defect_rate:.0%}",
                     esc(explain.short_date(estimate["eta_date"])) if estimate else "n/a",
                     f'<span class="{"neg" if estimate["days_to_spare"] < 0 else "pos"}">{estimate["days_to_spare"]:+d}</span>' if estimate else "n/a",
                     f"{estimate['total_cost']:,.0f}" if estimate else "n/a"])
        classes.append("" if estimate else "dim")
    html(table(["Workshop", "For this batch", "Makes", "Capacity/day", "Queue d", "Transport d", "Batch cap", "Cost/pc",
                "Defect", "Back", "Spare", "Batch cost"], rows, right=range(3, 12), classes=classes))
    if flags:
        html(banner("Suspect flag", "A flagged workshop showed an unexplained queue jump after work was sent. "
                    "It stays eligible; the robustness objective penalises it.", "warn"))
