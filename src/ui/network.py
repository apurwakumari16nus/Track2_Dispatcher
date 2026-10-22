"""Workshop Network: who can take this batch, and what happens when it is routed.

Read-only. Eligibility, ETA and cost come from tools.py with this session's
projected queues; the recommendation is a copy of the session allocator's
decide() (see network_model). Nothing is allocated, saved or sent, and the
model is never called. The map is a schematic of the register, not geography.

Every visual is a pure function of the routing state (see routing.py). Route
this batch plays the evaluation phase by phase with a ticking fragment; demo
mode (demo_scenarios.py) loads scripted batches and plays the outcome too.
"""

from __future__ import annotations

from datetime import date, timedelta
import math

import streamlit as st

import desk
from objectives import PRESETS
from ui import explain
from ui import network_model as nm
from ui import routing as rt
from ui.components import esc, html, icon, state_line, status_pill
from ui.demo_scenarios import BY_KEY, SCENARIOS
from ui.state import bind, one_of, text

PHOTOS = "app/static/brand/workshops"   # One 4:3 photo per workshop ID; see static/brand/CREDITS.md.
MARK = "app/static/brand/threadline-mark.png"
TONE_PILL = {"rec": "info", "ok": "ok", "warn": "warn", "late": "warn", "out": "muted", "down": "risk"}
VIEW = (800, 600)
HUB = (400, 292)
OUTCOMES = {"plan": "On plan", "rework": "Rework", "closure": "Closure"}
CATEGORIES = ("TOPS", "ACCESSORIES")
TICK = 1.1  # seconds per phase during playback
NODE_PILL = {rt.Node.EVALUATING: ("Checking", "info"), rt.Node.SHORTLISTED: ("Shortlisted", "ok"), rt.Node.SELECTED: ("Routed here", "info"),
             rt.Node.REJECTED: ("Not selected", "muted"), rt.Node.SUSPENDED: ("Suspended", "risk"), rt.Node.BLOCKED: ("Needs decision", "warn"),
             rt.Node.IN_PROGRESS: ("In production", "info"), rt.Node.DELAYED: ("Delayed", "risk"), rt.Node.COMPLETED: ("Back at factory", "ok")}


def photo(wid: str) -> str:
    return f"{PHOTOS}/{wid}.webp"


def node_xy(i: int, n: int) -> tuple[float, float]:
    angle = -math.pi / 2 + i * 2 * math.pi / n
    return HUB[0] + 300 * math.cos(angle), HUB[1] + 200 * math.sin(angle)


def curve(x: float, y: float) -> str:
    """A gentle quadratic from the hub, bowed perpendicular to the spoke."""
    hx, hy = HUB
    mx, my, dx, dy = (hx + x) / 2, (hy + y) / 2, x - hx, y - hy
    return f"M{hx},{hy} Q{mx - dy * .12:.1f},{my + dx * .12:.1f} {x:.1f},{y:.1f}"


def reverse_curve(x: float, y: float) -> str:
    hx, hy = HUB
    mx, my, dx, dy = (hx + x) / 2, (hy + y) / 2, x - hx, y - hy
    return f"M{x:.1f},{y:.1f} Q{mx - dy * .12:.1f},{my + dx * .12:.1f} {hx},{hy}"


# State --------------------------------------------------------------------------

def pick(wid):
    st.session_state["net_pick"] = wid


def route_to(wid):
    st.session_state["net_target"] = wid
    st.session_state["net_pick"] = wid


def start_play(through_outcome: bool):
    state = st.session_state
    state.update(net_phase=rt.Phase.IDLE.value, net_playing=True, net_fresh=True, net_through=through_outcome)


def load_scenario(today):
    """Load the chosen demo batch into the batch bar and play it through."""
    state = st.session_state
    s = BY_KEY[state.get("net_demo_scn") or SCENARIOS[0].key]
    state.update(net_category=s.category, net_pieces=s.pieces, net_due=today + timedelta(days=s.due_in_days),
                 net_scenario=s.outcome, net_spot=s.spotlight, net_from=f"Demo: {s.title}", net_sig=None)
    start_play(True)


def step(delta: int):
    state = st.session_state
    seq = state.get("net_seq") or [p.value for p in rt.EVALUATION]
    phase = state.get("net_phase") or seq[-1]
    index = seq.index(phase) if phase in seq else len(seq) - 1
    state.update(net_playing=False, net_fresh=False, net_phase=seq[max(0, min(len(seq) - 1, index + delta))])


def reset_route():
    st.session_state.update(net_playing=False, net_fresh=False, net_phase=rt.Phase.IDLE.value)


def defaults(state, today):
    hand = state.pop("net_handoff", None)
    if hand:  # Arrived from a Dispatch recommendation: prefill and replay the routing.
        # An unknown category is kept as "not chosen" (None) with a notice; it is never swapped for another one.
        known = hand["category"] in CATEGORIES
        state["net_category"] = hand["category"] if known else None
        state["net_category_note"] = None if known else f"Dispatch passed the category {hand['category']!r}, which the network does not route."
        state["net_pieces"] = hand["pieces"]
        state["net_due"], state["net_from"] = hand["due"], hand["label"]
        state.pop("net_target", None)
        state.pop("net_pick", None)
        start_play(bool(state.get("net_demo")))
    # First visit of a session: an example batch. Later visits keep whatever the user or Dispatch set.
    state.setdefault("net_category", "TOPS")
    state.setdefault("net_pieces", 1500)
    state.setdefault("net_due", today + timedelta(days=14))


# Page ---------------------------------------------------------------------------

def render(workshops):
    state = st.session_state
    today = max(state["desk_today"], state["desk_queue_date"])
    defaults(state, today)
    head, tools_col = st.columns([1.5, 1], vertical_alignment="bottom")
    with head:
        html('<div class="kicker"><span>Workshop network</span></div>'
             '<div class="home-title" style="margin-top:0.8rem">Find the right workshop, faster</div>'
             '<div class="home-sub">Explore the vetted network, see live capacity, and route each batch to the workshop that fits it best.</div>')
    with tools_col, st.container(key="net_tools"):
        query = bind(st.text_input, "Search workshops", key="net_q", fallback="", accept=text,
                     placeholder="Search workshop, product or note", label_visibility="collapsed", icon=":material/search:")
        with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", key="net_toggles"):
            demo = bind(st.toggle, "Demo mode", key="net_demo", fallback=False, accept=lambda v: isinstance(v, bool),
                        help="Scripted batches for screen recording. Routing stays the live engine.")
            view = bind(st.segmented_control, "View", ["Network", "List"], key="net_view", fallback="Network", required=True,
                        label_visibility="collapsed",
                        format_func=lambda v: {"Network": ":material/hub: Network", "List": ":material/view_agenda: List"}[v])
    with st.container(key="net_bar"):
        a, b, c, d, e = st.columns([1.25, .95, 1, 1.25, 1.05], vertical_alignment="bottom")
        with a:
            category = bind(st.segmented_control, "Category", CATEGORIES, key="net_category", fallback=None, allow_none=True,
                            required=True, format_func=str.capitalize)
        with b:
            pieces = bind(st.number_input, "Batch size", key="net_pieces", fallback=1500,
                          accept=lambda v: isinstance(v, int) and 1 <= v <= 1_000_000, min_value=1, max_value=1_000_000, step=100)
        with c:
            due = bind(st.date_input, "Due date", key="net_due", fallback=today, accept=lambda v: isinstance(v, date) and v >= today,
                       min_value=today, format="DD/MM/YYYY")
        with d:
            source = state.get("net_from")
            html(f'<div class="nb-meta"><small>Objective, set in Dispatch</small><b>{esc(explain.objective_label(state["desk_preset"]))}</b>'
                 + (f'<span>From {esc(source)}</span>' if source else "") + "</div>")
        with e:
            st.button("Route this batch", key="net_route", type="primary", width="stretch", icon=":material/route:",
                      on_click=start_play, args=(bool(demo),))

    if category is None:
        html(state_line("warn", "Choose a category to route this batch",
                        (state.get("net_category_note") or "Tops or Accessories decides which workshops are eligible.")))
        return
    state.pop("net_category_note", None)
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], today)
    flags = set(state["desk_allocator"].shock_monitor.flags)
    batch = {"category": category, "pieces": int(pieces), "due_date": due}
    model = nm.evaluate(batch, workshops, queues, today, state["desk_allocator"], PRESETS[state["desk_preset"]], flags)
    signature = (category, int(pieces), str(due), state["desk_preset"], state["desk_revision"])
    if state.get("net_sig") != signature:
        state["net_sig"] = signature
        state["net_target"] = model["chosen"]
        state["net_pick"] = model["chosen"] or next(iter(workshops))
        if not state.get("net_fresh"):  # A new batch drops any finished playback back to the plain view.
            state.update(net_phase=None, net_playing=False)
    if state.get("net_fresh") and not state.get("net_playing"):
        state["net_fresh"] = False
    q = query.strip().casefold()
    match = {wid for wid, r in model["rows"].items()
             if not q or q in " ".join([r["name"], wid, r["note"], " ".join(r["tags"])]).casefold()}

    answers(model, category, int(pieces), due, workshops)
    if demo:
        demo_bar(today)
    tick = TICK if state.get("net_playing") else None
    st.fragment(live, run_every=tick)(model, match, today, workshops, view)
    html('<div class="meta" style="margin-top:0.5333rem">Estimates are queue plus pieces divided by capacity plus transport, rounded to a day, '
         'from the session queues. Photos illustrate each workshop\'s character; they are not photographs of these workshops.</div>')


def live(model, match, today, workshops, view):
    """Everything that moves during a routing run. Reruns alone on each playback tick."""
    state = st.session_state
    target = state.get("net_target")
    if target is None or target not in model["rows"] or not model["rows"][target]["eligible"]:
        target = state["net_target"] = model["chosen"]
    outcome = state.get("net_scenario") if state.get("net_scenario") in OUTCOMES else "plan"
    through = bool(state.get("net_through"))
    seq = rt.sequence(model, target, outcome, through)
    state["net_seq"] = [p.value for p in seq]
    if state.get("net_playing"):
        if state.get("net_fresh"):
            state["net_fresh"] = False
        else:
            current = state.get("net_phase")
            index = [p.value for p in seq].index(current) + 1 if current in state["net_seq"] else len(seq) - 1
            state["net_phase"] = seq[min(index, len(seq) - 1)].value
            if index >= len(seq) - 1:  # Last phase: stop ticking and land on the spotlight, if the scenario has one.
                state["net_playing"] = False
                spot = state.pop("net_spot", None)
                state["net_pick"] = spot or target or state.get("net_pick")
                st.rerun()
    phase = rt.Phase(state["net_phase"]) if state.get("net_phase") else None
    playing = bool(state.get("net_playing"))
    row = model["rows"].get(target) if target else None
    plan = nm.plan(row, today, outcome) if row else None
    left, right = st.columns([1.55, 1], gap="medium")
    with left:
        if view == "List":
            list_view(model, match)
        else:
            network_map(model, target, state.get("net_pick"), match, phase, playing, plan, workshops)
            if phase is not None:   # During a routing run the tracker is the story, so it stays open.
                route_card(model, target, today, phase, plan)
            else:
                name = model["rows"][target]["name"] if target else "this batch"
                with st.expander(f"Route to {name} and what-if outcomes", key="net_route_more"):
                    route_card(model, target, today, phase, plan)
    with right:
        if phase is not None and not rt.at_least(phase, rt.Phase.RECOMMENDED):
            evaluating_panel(model, phase, today)
        else:
            detail(model, state.get("net_pick") or target or next(iter(workshops)), target, today, phase)
    from ui import guide
    if guide.stale():  # A click inside this fragment completed a guided-demo step: redraw the coach too.
        st.rerun(scope="app")


def demo_bar(today):
    state = st.session_state
    seq = state.get("net_seq") or []
    phase = state.get("net_phase")
    at = (seq.index(phase) + 1) if phase in seq else len(seq)
    with st.container(key="net_demo_bar"):
        info, pick_col, play_col, ctl = st.columns([1.15, 1.25, .9, 1.4], vertical_alignment="center")
        with info:
            html('<div class="db-label"><b>Demo playback</b><span>Scripted batches, live routing engine. '
                 'Outcomes after routing follow the simulator\'s rules.</span></div>')
        with pick_col:
            bind(st.selectbox, "Scenario", [s.key for s in SCENARIOS], key="net_demo_scn", fallback=SCENARIOS[0].key,
                 format_func=lambda k: BY_KEY[k].title, label_visibility="collapsed")
        with play_col:
            st.button("Play scenario", key="net_demo_play", type="primary", width="stretch", icon=":material/play_arrow:",
                      on_click=load_scenario, args=(today,))
        with ctl, st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", key="net_steps"):
            html(f'<div class="db-phase">Step {at} of {len(seq) or "-"}</div>')
            st.button("", key="net_step_back", icon=":material/skip_previous:", on_click=step, args=(-1,), help="Previous step")
            st.button("", key="net_step_next", icon=":material/skip_next:", on_click=step, args=(1,), help="Next step")
            st.button("", key="net_reset", icon=":material/restart_alt:", on_click=reset_route, help="Reset to the start")
        html(f'<div class="db-story">{esc(BY_KEY[state.get("net_demo_scn") or SCENARIOS[0].key].story)}</div>')


def answers(model, category, pieces, due, workshops):
    noun = category.lower()
    capable = sum(w.status == "ACTIVE" and category in w.makes for w in workshops.values())
    chosen = model["rows"].get(model["chosen"])
    head = (f'<em>{len(model["eligible"])} of {len(workshops)}</em> can take {pieces:,} {esc(noun)}. '
            f'<em>{len(model["on_time"])}</em> return by {esc(explain.short_date(due))}.') if model["eligible"] \
        else f'No active workshop can take {pieces:,} {esc(noun)} as one job.'
    fastest, cheapest = model["fastest"], model["cheapest"]
    # One line of facts instead of a row of cards: the map and the panel carry the rest.
    facts = [("Recommended", chosen["name"] if chosen else "None", "rec"),
             (f"Fastest for {pieces:,} {noun}", f'{fastest["name"]}, back {explain.short_date(fastest["eta"]["eta_date"])}' if fastest else "None", ""),
             ("Cheapest", f'{cheapest["name"]}, {cheapest["eta"]["total_cost"]:,.0f}' if cheapest else "None", ""),
             ("Cannot take it", str(len(model["unavailable"])) if model["unavailable"] else "None", "muted")]
    stats = (f'{len(workshops)} workshops, {sum(w.status == "ACTIVE" for w in workshops.values())} active, {capable} can make {esc(noun)}.')
    html(f'<div class="net-answer"><div class="na-head">{head}</div><div class="na-line">'
         + "".join(f'<span class="{t}"><small>{esc(k)}</small><b>{esc(v)}</b></span>' for k, v, t in facts)
         + f'<span class="na-stats">{stats}</span></div></div>')


# Network map ----------------------------------------------------------------------

def network_map(model, target, picked, match, phase, playing, plan, workshops):
    rows = model["rows"]
    ids = list(workshops)
    shown = phase or rt.Phase.RECOMMENDED  # The plain view is the routed result.
    defs, lines, nodes, buttons = [], [], [], []
    route_path, back_path, tx, ty = "", "", 0.0, 0.0
    for i, wid in enumerate(ids):
        r = rows[wid]
        x, y = node_xy(i, len(ids))
        path = curve(x, y)
        state = rt.node_state(r, shown, target)
        edge = rt.edge_state(state)
        if wid == target and rt.at_least(shown, rt.Phase.RECOMMENDED):
            route_path, back_path, tx, ty = path, reverse_curve(x, y), x, y
        dim = "" if wid in match else " dim"
        fit = f" fit-{r['tone']}" if state == rt.Node.SHORTLISTED else ""
        rec = " rec" if wid == model["chosen"] and wid == target else ""
        lines.append(f'<path class="ln e-{edge.value}{rec}{dim}" d="{path}" pathLength="100" style="--i:{i}"/>')
        below = y >= HUB[1] - 10
        ly = y + 50 if below else y - 58
        sub = rt.node_caption(r, state, shown, plan if wid == target else None)
        badge = ""
        if state in (rt.Node.REJECTED, rt.Node.SUSPENDED) and not r["eligible"]:
            badge = "✕"
        elif state == rt.Node.BLOCKED or state == rt.Node.DELAYED:
            badge = "!"
        elif state == rt.Node.COMPLETED:
            badge = "✓"
        elif r["rank"] and rt.ranks_visible(shown):
            badge = str(r["rank"])
        badge_svg = (f'<g class="badge b-{state.value}" style="--r:{r["rank"] or 0}"><rect x="{x + 15:.1f}" y="{y - 35:.1f}" width="20" height="20" rx="6"/>'
                     f'<text x="{x + 25:.1f}" y="{y - 21:.1f}">{badge}</text></g>') if badge else ""
        defs.append(f'<clipPath id="nc-{wid}"><circle cx="{x:.1f}" cy="{y:.1f}" r="27"/></clipPath>')
        sel = f'<circle class="sel" cx="{x:.1f}" cy="{y:.1f}" r="40"/>' if wid == picked and shown not in rt.EVALUATION else ""
        flag = f'<circle class="flag" cx="{x - 25:.1f}" cy="{y - 25:.1f}" r="6"/>' if r["flagged"] else ""
        spin = f'<circle class="spin" cx="{x:.1f}" cy="{y:.1f}" r="36" pathLength="100"/>' if state == rt.Node.IN_PROGRESS else ""
        nodes.append(f'<g class="nd n-{state.value}{fit}{rec}{dim}" style="--i:{i}">{sel}{spin}'
                     f'<circle class="ring0" cx="{x:.1f}" cy="{y:.1f}" r="31"/><circle class="ring" cx="{x:.1f}" cy="{y:.1f}" r="31"/>'
                     f'<image href="{photo(wid)}" x="{x - 27:.1f}" y="{y - 27:.1f}" width="54" height="54" preserveAspectRatio="xMidYMid slice" clip-path="url(#nc-{wid})"/>'
                     f'{badge_svg}{flag}<text class="nm" x="{x:.1f}" y="{ly:.1f}">{esc(r["name"])}</text>'
                     f'<text class="sb" x="{x:.1f}" y="{ly + 16:.1f}">{esc(sub)}</text></g>')
        buttons.append((wid, r["name"], x / VIEW[0] * 100, y / VIEW[1] * 100))
    hx, hy = HUB
    summary = f'{model["pieces"]:,} {model["category"].lower()}, due {explain.short_date(str(model["due"]))}'
    # The mark keeps its own colours on a pearl disc: its navy stem would vanish on a dark one.
    hub = (f'<g class="hub{" arriving" if shown == rt.Phase.IDLE else ""}"><circle class="halo" cx="{hx}" cy="{hy}" r="64"/>'
           f'<circle class="rim" cx="{hx}" cy="{hy}" r="54"/><circle class="core" cx="{hx}" cy="{hy}" r="48"/>'
           f'<image href="{MARK}" x="{hx - 28}" y="{hy - 26}" width="56" height="50"/>'
           f'<text class="hub-n" x="{hx}" y="{hy + 74}">Sweater Co Factory</text><text class="hub-s" x="{hx}" y="{hy + 90}">{esc(summary)}</text></g>')
    moving = ""
    if playing and route_path and shown == rt.Phase.RECOMMENDED:
        moving = f'<circle class="packet go" r="7" style="offset-path:path(\'{route_path}\')"/>'
    elif playing and back_path and shown == rt.Phase.RETURNED:
        moving = f'<circle class="packet back" r="7" style="offset-path:path(\'{back_path}\')"/>'
    word, tone = rt.tracker(shown)[1:] if rt.at_least(shown, rt.Phase.RECOMMENDED) else ("", "")
    if shown == rt.Phase.RECOMMENDED and target:
        word, tone = ("Recommended", "rec") if target == model["chosen"] else ("Routing preview", "info")
    pill = ""
    if route_path or (shown == rt.Phase.BLOCKED and target):
        if shown == rt.Phase.BLOCKED:
            x, y = node_xy(ids.index(target), len(ids))
            tx, ty = x, y
        # Above the node when its name sits below, and below it when the name sits above, so nothing overlaps.
        width, py = 26 + len(word) * 7.2, (ty - 64 if ty >= HUB[1] - 10 else ty + 42)
        pill = (f'<g class="state-pill t-{tone}"><rect x="{tx - width / 2:.1f}" y="{py:.1f}" width="{width:.1f}" height="22" rx="11"/>'
                f'<text x="{tx:.1f}" y="{py + 15:.1f}">{esc(word)}</text></g>')
    width = 40 + len(summary) * 6.6
    request = (f'<g class="request"><rect x="{hx - width / 2:.1f}" y="{hy - 116}" width="{width:.1f}" height="28" rx="14"/>'
               f'<text x="{hx}" y="{hy - 97}">New batch: {esc(summary)}</text></g>') if shown == rt.Phase.IDLE else ""
    cls = f"tl-map p-{shown.value}" + (" live" if playing else "")
    svg = (f'<svg class="{cls}" viewBox="0 0 {VIEW[0]} {VIEW[1]}" role="img" '
           f'aria-label="Sweater Co Factory connected to its eight partner workshops, {esc(shown.value.replace("_", " "))}">'
           f'<defs><linearGradient id="routeGrad" x1="0" x2="1"><stop offset="0" stop-color="#3278E9"/><stop offset="1" stop-color="#68CAFA"/></linearGradient><linearGradient id="recGrad" x1="0" x2="1"><stop offset="0" stop-color="#0F9F8A"/><stop offset="1" stop-color="#68CAFA"/></linearGradient>'
           f'<radialGradient id="hubPearl" cx=".38" cy=".3" r=".78"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".62" stop-color="#F4F8FD"/><stop offset="1" stop-color="#DCE6F2"/></radialGradient>{"".join(defs)}</defs>'
           f'{"".join(lines)}{hub}{request}{"".join(nodes)}{moving}{pill}</svg>')
    style = "".join(f'.st-key-netmap .st-key-node_{wid}{{left:{px:.2f}%;top:{py:.2f}%}}' for wid, _, px, py in buttons)
    with st.container(key="netmap"):
        html(f"<style>{style}</style>{svg}")
        for wid, name, _, _ in buttons:
            st.button(f"Open {name}", key=f"node_{wid}", on_click=pick, args=(wid,))
    through = bool(st.session_state.get("net_through"))
    steps = rt.steps(model, shown, target, st.session_state.get("net_scenario", "plan"), through, plan)
    flow = ('<ol class="flow">' + "".join(f'<li class="{s}">{esc(t)}</li>' for s, t in steps) + "</ol>") if phase is not None else ""
    html(legend() + flow)   # The step list only while a routing run plays; the plain view is the result.


def legend() -> str:
    items = [("rec", "Recommended"), ("ok", "Can take it"), ("late", "Misses the date"), ("out", "Cannot take it")]
    return ('<div class="tl-legend">' + "".join(f'<span><i class="{t}"></i>{esc(k)}</span>' for t, k in items)
            + '<span class="hint">Numbers are the engine\'s ranking. Click a workshop for details.</span></div>')


# Route tracker --------------------------------------------------------------------

def route_card(model, target, today, phase, plan):
    state = st.session_state
    with st.container(key="net_stage"):
        if not target:
            html('<div class="title" style="font-size:1.2333rem">No route</div><div class="meta" style="font-size:0.9667rem;margin-top:0.2667rem">'
                 'No active workshop can take this batch as one job. Try a smaller batch, or preview a split in Dispatch.</div>')
            return
        r = model["rows"][target]
        top, ctl = st.columns([1.6, 1], vertical_alignment="center")
        with ctl:
            outcome = bind(st.segmented_control, "Outcome", list(OUTCOMES), key="net_scenario", fallback="plan", required=True,
                           format_func=OUTCOMES.get, label_visibility="collapsed")
        statuses, word, tone = rt.tracker(phase)
        if phase is None:  # Plain view: a plan preview with the chosen outcome applied.
            if outcome != "plan" and plan["late"] > 0:
                word, tone = plan["state"], "risk"
            elif outcome == "rework":
                word, tone = "Rework, still on time", "warn"
            else:
                word, tone = ("On plan", "ok") if plan["late"] <= 0 else ("Late", "risk")
            statuses = [s if not (outcome == "closure" and n == 2 or outcome == "rework" and n == 4) else "alert"
                        for n, s in enumerate(statuses)]
        waiting = phase is not None and not rt.at_least(phase, rt.Phase.CONFIRMED) and phase != rt.Phase.BLOCKED
        with top:
            html(f'<div class="rc-head"><div><small>Active batch route</small><b>Sweater Co Factory to {esc(r["name"])}</b></div>'
                 f'{status_pill(word, tone)}</div>')
        cells = []
        for n, ((name, when, sub), status) in enumerate(zip(plan["stages"], statuses)):
            cells.append(f'<div class="rs {status}" style="--n:{n}"><span class="rs-dot"></span><b>{esc(name)}</b>'
                         f'<em>{esc(explain.short_date(when.isoformat()))}</em><small>{esc(sub)}</small></div>')
        verdict = (f'Back {explain.short_date(plan["back"].isoformat())}, '
                   + (f'{explain.days(-plan["late"])} before the due date.' if plan["late"] < 0 else "on the due date." if plan["late"] == 0
                      else f'{explain.days(plan["late"])} after the due date.'))
        html(f'<div class="rstages{" waiting" if waiting else ""}">{"".join(cells)}</div><div class="rc-foot"><b>{esc(verdict)}</b>'
             + (f'<span>{esc(plan["note"])}</span>' if plan["note"] else "") + "</div>")
        if phase == rt.Phase.BLOCKED or (outcome != "plan" and plan["late"] > 0 and (phase is None or rt.at_least(phase, rt.Phase.DELAYED))):
            backup = next((x for x in sorted(model["on_time"], key=lambda x: x["rank"] or 99) if x["id"] != target), None)
            if backup:
                html(f'<div class="rc-alt">{icon("alt_route")}<div><b>Reassign option: {esc(backup["name"])}</b>'
                     f'<span>Back {esc(explain.short_date(backup["eta"]["eta_date"]))} on today\'s queues, '
                     f'{explain.days(backup["eta"]["days_to_spare"])} to spare. You decide; nothing moves automatically.</span></div></div>')
                st.button(f"Route preview to {backup['name']}", key="net_reassign", on_click=route_to, args=(backup["id"],))
            else:
                html('<div class="rc-alt">' + icon("report") + '<div><b>No on-time alternative</b><span>Accept the least-late option, '
                     'preview a split in Dispatch, or escalate to the planner.</span></div></div>')
        html('<div class="meta" style="margin-top:0.4rem">Outcomes apply the course simulator\'s rules to this plan. They are previews, not forecasts.</div>')


# Detail panel --------------------------------------------------------------------

def evaluating_panel(model, phase, today):
    rows = model["rows"]
    out = [r for r in rows.values() if not r["eligible"]]
    late_rows = [r for r in rows.values() if rt.late(r)]
    ranked = sorted((r for r in rows.values() if r["rank"]), key=lambda r: r["rank"])
    with st.container(key="net_detail"):
        html('<div class="ev-panel"><div class="ev-hub"><img src="' + MARK + '" alt=""><div><small>Sweater Co Factory</small>'
             f'<b>{model["pieces"]:,} {esc(model["category"].lower())}</b></div></div>')
        if phase in (rt.Phase.IDLE, rt.Phase.EVALUATING):
            html(f'<div class="ev-title">{"Batch received" if phase == rt.Phase.IDLE else "Checking every workshop"}</div>'
                 '<ul class="ev-checks">' + "".join(f'<li class="{"on" if phase == rt.Phase.EVALUATING else ""}" style="--i:{i}">{esc(t)}</li>'
                 for i, t in enumerate(["Can it make this product?", "Is it active?", "Does the batch fit its limit?",
                                        "When would it be back?", "What would it cost?"])) + "</ul></div>")
        elif phase == rt.Phase.FILTERING:
            items = ([(r["name"], nm.FAIL_KIND[r["kind"]], "out") for r in out]
                     + [(r["name"], f"Misses the date, {explain.days(-r['eta']['days_to_spare'])} late", "late") for r in late_rows])
            html(f'<div class="ev-title">{len(items)} filtered out</div><ul class="ev-out">'
                 + "".join(f'<li class="{c}" style="--i:{i}"><b>{esc(n)}</b><span>{esc(why)}</span></li>' for i, (n, why, c) in enumerate(items))
                 + (f'</ul><div class="ev-keep">{len(model["on_time"])} shortlisted on time</div></div>' if items else "</ul></div>"))
        else:
            html(f'<div class="ev-title">Engine ranking, {esc(explain.objective_label(model["record"]["objective_name"]).lower())}</div><ol class="ev-rank">'
                 + "".join(f'<li class="{"late" if rt.late(r) else ""}" style="--i:{i}"><b>{r["rank"]}</b><span>{esc(r["name"])}</span>'
                           f'<em>{esc(explain.short_date(r["eta"]["eta_date"]))}</em></li>' for i, r in enumerate(ranked))
                 + "</ol></div>")


def card_state(model, r, target, phase) -> tuple[str, str, str]:
    """(variant, title, context) for the detail card. Suggested and committed states never share a look."""
    wid, n = r["id"], len(model["eligible"])
    objective = explain.objective_label(model["record"]["objective_name"]).lower()
    if not r["eligible"]:
        if r["kind"] == "suspended":
            return "block", "Suspended", "It may not take new work."
        return "block", "Cannot take this batch", nm.FAIL_KIND[r["kind"]]
    if wid == target and phase is not None and rt.at_least(phase, rt.Phase.BLOCKED):
        word = rt.tracker(phase)[1]
        variant = "warn" if phase in (rt.Phase.BLOCKED, rt.Phase.DELAYED, rt.Phase.RETURNED) else "sel"
        return variant, word, "Demo playback of the plan, not a live order."
    if wid == target and wid == model["chosen"]:
        if rt.late(r):
            return "warn", "Least-late option", f"No workshop meets the date. Engine rank 1 of {n}."
        return "rec", "Recommended for this batch", f"Engine rank 1 of {n}, {objective}. Not yet confirmed."
    if wid == target:
        return "sel", "Routing preview", f"Chosen by you. The engine recommends {model['rows'][model['chosen']]['name']}."
    if rt.late(r):
        return "warn", "Misses the due date", f"Engine rank {r['rank']} of {n}."
    return "info", "Eligible alternative", f"Engine rank {r['rank']} of {n}, {objective}."


def detail(model, wid, target, today, phase):
    r = model["rows"][wid]
    w, e = r["w"], r["eta"]
    variant, title, context = card_state(model, r, target, phase)
    makes = " and ".join(sorted(m.lower() for m in w.makes))
    with st.container(key="net_detail"):
        html(state_line(variant, title, context)
             + f'<div class="tc-photo"><img src="{photo(wid)}" alt="Illustrative photo for {esc(r["name"])}" width="640" height="360">'
             f'<span class="ill">Illustrative photo</span><div class="tc-name"><b>{esc(r["name"])}</b>'
             f'<span><span class="id">{esc(wid)}</span>, makes {esc(makes)}. {esc(r["note"].capitalize())}</span></div></div>')
        if e:
            spare = e["days_to_spare"]
            due = f"{explain.days(abs(spare))} {'after' if spare < 0 else 'before'} the due date" if spare else "on the due date"
            html(f'<div class="tc-primary"><div class="{"late" if spare < 0 else ""}"><small>Earliest return</small>'
                 f'<b>{esc(explain.short_date(e["eta_date"]))}</b><span>{esc(due)}</span></div>'
                 f'<div><small>Estimated cost</small><b>{e["total_cost"]:,.0f}</b><span>{w.cost:g} a piece, {model["pieces"]:,} pieces</span></div></div>')
        else:
            html(f'<div class="tc-primary"><div class="na"><small>Earliest return</small><b>Not eligible</b>'
                 f'<span>{esc(r["reason"].split(". ", 1)[-1])}</span></div>'
                 f'<div><small>Price list</small><b>{w.cost:g}</b><span>a piece</span></div></div>')
        why_title = {"rec": "Why this workshop", "sel": "Why it ranks where it does", "warn": "What to know",
                     "block": "Why it cannot take the batch"}.get(variant, "Against the recommendation")
        html(f'<div class="tc-why is-{variant}"><small>{esc(why_title)}</small><p>{esc(r["reason"])}</p></div>')
        a, b = st.columns(2)
        with a:
            if st.button("View full profile", key="net_profile", width="stretch", icon=":material/badge:"):
                profile(r, today)
        with b:
            routed = wid == target
            st.button("Routed here" if routed else "Route here", key="net_select", type="primary", width="stretch",
                      icon=":material/check:" if routed else ":material/route:", disabled=routed or not r["eligible"],
                      on_click=route_to, args=(wid,), help=None if r["eligible"] else "This workshop cannot take the batch.")
        html('<p class="ev" style="margin:0.2667rem 0 0">Routing here is a preview. Only Dispatch confirms a decision.</p>')
        # Details on demand: the facts above decide; these explain.
        risks = f", {len(r['risks'])} risk flag{'s' if len(r['risks']) != 1 else ''}" if r["risks"] else ""
        with st.expander(f"Capacity, queue and rework{risks}"):
            facts = [("Capacity", f"{w.capacity:,}", "pieces a day"), ("Queue now", f"{r['queue']:.1f}", "days ahead"),
                     ("Rework rate", f"{w.defect_rate:.0%}", "of batches")]
            html('<dl class="tc-facts">' + "".join(f"<div><dt>{esc(k)}</dt><dd><b>{esc(v)}</b> {esc(u)}</dd></div>" for k, v, u in facts) + "</dl>")
            if r["eligible"]:
                html(outlook_chart(r, today))
            if r["risks"]:
                html('<div class="tc-sec">Operational risk</div><ul class="dp-risks">'
                     + "".join(f'<li class="{t}">{icon({"risk": "error", "warn": "warning", "info": "info"}[t])}<span>{esc(s)}</span></li>' for t, s in r["risks"][:3])
                     + "</ul>")


def readiness(r) -> str:
    """Three small indicators: queue load, rework rate, risk level."""
    queue = r["queue"]
    q_pct = min(queue / 7, 1)
    rework = r["w"].defect_rate
    worst = "risk" if any(t == "risk" for t, _ in r["risks"]) else "warn" if any(t == "warn" for t, _ in r["risks"]) else "ok"
    level = {"risk": "High", "warn": "Medium", "ok": "Low"}[worst]
    util = [min(1, (wk["booked"] + wk["batch"]) / 7) for wk in r["outlook"]]
    pts = " ".join(f"{6 + i * 26},{30 - u * 24:.1f}" for i, u in enumerate(util))
    dots = "".join(f'<circle cx="{6 + i * 26}" cy="{30 - u * 24:.1f}" r="2.6"/>' for i, u in enumerate(util))
    return ('<div class="rd">'
            f'<div><small>Queue load</small><b>{queue:.1f} days</b><i class="meter"><span style="width:{q_pct * 100:.0f}%"></span></i></div>'
            f'<div><small>Rework rate</small><b>{rework:.0%}</b><i class="meter {"hot" if rework >= .09 else ""}"><span style="width:{min(rework / .15, 1) * 100:.0f}%"></span></i></div>'
            f'<div><small>Utilisation, 4 weeks</small><svg class="spark" viewBox="0 0 90 34"><polyline points="{pts}"/>{dots}</svg></div>'
            f'<div><small>Risk</small><b class="lvl {worst}">{level}</b><span>{len(r["risks"])} flag{"s" if len(r["risks"]) != 1 else ""}</span></div></div>')


def outlook_chart(r, today) -> str:
    """Four weeks of production capacity from the session queue: booked, this batch, spare. Pieces on every segment."""
    cap = r["w"].capacity
    week_cap = cap * 7
    rows = []
    for wk in r["outlook"]:
        start = today + timedelta(days=7 * (wk["week"] - 1))
        end = start + timedelta(days=6)
        parts = [("bk", wk["booked"], round(wk["booked"] * cap)), ("me", wk["batch"], round(wk["batch"] * cap)),
                 ("sp", wk["spare"], wk["spare_pieces"])]
        segs = "".join(f'<i class="{c}" style="flex:{d:.3f}" title="{n:,} pieces">{f"{n:,}" if d / 7 >= .2 else ""}</i>'
                       for c, d, n in parts if d > 0.01)
        rows.append(f'<div class="cw"><div class="cw-l"><b>Week {wk["week"]}</b><small>{start.day} {start:%b} to {end.day} {end:%b}</small></div>'
                    f'<div class="cw-t">{segs}</div><div class="cw-v"><b>{wk["spare_pieces"]:,}</b><small>spare</small></div></div>')
    totals = {k: sum(round(wk[f] * cap) if f != "spare_pieces" else wk[f] for wk in r["outlook"])
              for k, f in (("bk", "booked"), ("me", "batch"), ("sp", "spare_pieces"))}
    return ('<div class="an-card cap"><div class="cap-h"><div><div class="an-title">Capacity, next 4 weeks</div>'
            f'<div class="an-sub">{week_cap:,} pieces a week at {cap:,} a day, seven days a week.</div></div></div>'
            f'<div class="cws">{"".join(rows)}</div>'
            f'<div class="cap-key"><span><i class="bk"></i>Already booked <b>{totals["bk"]:,}</b></span>'
            f'<span><i class="me"></i>This batch <b>{totals["me"]:,}</b></span><span><i class="sp"></i>Spare <b>{totals["sp"]:,}</b></span></div>'
            '<div class="an-src">From the session queue and the register capacity. An estimate for comparison, not a booking or a promise from the workshop.</div></div>')


@st.dialog("Workshop profile", width="large")
def profile(r, today):
    w, e = r["w"], r["eta"]
    html(f'<div class="inspector"><div class="eyebrow">Workshop {esc(r["id"])}</div><div class="ins-title">{esc(r["name"])}</div>'
         f'<div class="ins-sub">{esc(r["note"].capitalize())}</div></div>')
    facts = [("Makes", " and ".join(sorted(m.lower() for m in w.makes))), ("Status", w.status.capitalize()),
             ("Capacity", f"{w.capacity:,} pieces a day"), ("Pickup and delivery", explain.days(w.lead_days)),
             ("Cost", f"{w.cost:g} per piece"), ("Defect rate", f"{w.defect_rate:.0%} of batches"),
             ("Batch limit", f"{w.max_batch:,} pieces" if w.max_batch else "None"), ("Queue now", f"{r['queue']:.1f} days"),
             ("Fit for this batch", r["label"]), ("Engine rank", str(r["rank"]) if r["rank"] else "Not eligible")]
    if e:
        facts += [("Earliest finish", explain.long_date(e["eta_date"])), ("Batch cost", f"{e['total_cost']:,.0f}")]
    html('<div class="dk-card" style="margin-top:0.5333rem"><dl class="kv" style="grid-template-columns:12.6667rem 1fr;font-size:0.9667rem">'
         + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in facts) + "</dl></div>"
         '<p class="ev" style="margin-top:0.6667rem">Every value is read from workshops.csv and the session queues. The photo illustrates the '
         'workshop\'s character and is credited in static/brand/CREDITS.md.</p>')


# List view -----------------------------------------------------------------------

def list_view(model, match):
    order = sorted(model["rows"].values(), key=lambda r: (["rec", "ok", "warn", "late", "out", "down"].index(r["tone"]), r["rank"] or 99, r["id"]))
    with st.container(key="net_list"):
        html('<div class="lv-head"><span>Workshop</span><span>Status</span><span class="r">Earliest finish</span>'
             '<span class="r">Spare this week</span><span class="r">Cost</span><span class="r">Quality</span></div>')
        shown = 0
        for r in order:
            if r["id"] not in match:
                continue
            shown += 1
            e = r["eta"]
            finish = (f'<b>{esc(explain.short_date(e["eta_date"]))}</b><small>{esc(explain.days(abs(e["days_to_spare"])))} '
                      f'{"late" if e["days_to_spare"] < 0 else "spare"}</small>') if e else '<b class="na">n/a</b>'
            cost = f'<b>{e["total_cost"]:,.0f}</b><small>{r["w"].cost:g} per piece</small>' if e else f'<b class="na">{r["w"].cost:g}</b><small>per piece</small>'
            with st.container(key=f"lv_{r['id']}"):
                html(f'<div class="lv{" sel" if st.session_state.get("net_pick") == r["id"] else ""}"><div class="lv-ws"><img src="{photo(r["id"])}" alt="">'
                     f'<div><b>{esc(r["name"])}</b><small>{esc(", ".join(r["tags"][:2]))}</small></div></div>'
                     f'<div>{status_pill(r["label"], TONE_PILL[r["tone"]])}</div><div class="r">{finish}</div>'
                     f'<div class="r"><b>{r["outlook"][0]["spare_pieces"]:,}</b><small>pieces</small></div><div class="r">{cost}</div>'
                     f'<div class="r"><b>{r["quality"]:.0%}</b><small>first pass</small></div>'
                     f'<div class="lv-why">{esc(r["reason"])}</div></div>')
                st.button(f"Open {r['name']}", key=f"lvb_{r['id']}", on_click=pick, args=(r["id"],))
        if not shown:
            html('<div class="meta" style="padding:0.9333rem 0.2667rem">No workshop matches the search.</div>')
