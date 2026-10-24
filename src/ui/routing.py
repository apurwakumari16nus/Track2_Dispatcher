"""Routing state model for the Workshop Network page.

A routing run moves through ordered phases. Every visual (node rings, route
lines, the stepper, the detail panel, the route tracker) is a pure function of
(view model, phase, routed workshop, outcome), so the same state always draws
the same page and any phase can be shown on its own (play, step or reset).

The evaluation phases replay what the real engine already decided. The phases
after routing (confirmed, in production, delayed, returned, completed) are a
playback of the plan under the simulator's written rules; nothing is sent.
"""

from __future__ import annotations

from enum import Enum

from ui import explain
from ui import network_model as nm


class Phase(str, Enum):
    IDLE = "idle"
    EVALUATING = "evaluating"
    FILTERING = "filtering"
    RANKING = "ranking"
    RECOMMENDED = "recommended"
    BLOCKED = "blocked"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    DELAYED = "delayed"
    RETURNED = "returned"
    COMPLETED = "completed"


class Node(str, Enum):
    NEUTRAL = "neutral"
    EVALUATING = "evaluating"
    SHORTLISTED = "shortlisted"
    SELECTED = "selected"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    SUSPENDED = "suspended"
    IN_PROGRESS = "in_progress"
    DELAYED = "delayed"
    COMPLETED = "completed"


class Edge(str, Enum):
    NEUTRAL = "neutral"
    SCANNING = "scanning"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    WINNING = "winning"
    WARNING = "warning"


EVALUATION = [Phase.IDLE, Phase.EVALUATING, Phase.FILTERING, Phase.RANKING]
OUTCOME_END = {"plan": Phase.COMPLETED, "closure": Phase.DELAYED, "rework": Phase.RETURNED}
AFTER_ROUTING = {Phase.CONFIRMED, Phase.IN_PROGRESS, Phase.DELAYED, Phase.RETURNED, Phase.COMPLETED}


def blocked(model, target) -> bool:
    """True when the routed workshop misses the date: the manager must decide."""
    row = model["rows"].get(target) if target else None
    return target is None or (row["eta"]["days_to_spare"] < 0)


def sequence(model, target, outcome: str = "plan", through_outcome: bool = True) -> list[Phase]:
    """The phases one routing run plays, in order."""
    steps = list(EVALUATION)
    if blocked(model, target):
        return steps + [Phase.BLOCKED]
    steps.append(Phase.RECOMMENDED)
    if through_outcome:
        steps += [Phase.CONFIRMED, Phase.IN_PROGRESS, OUTCOME_END[outcome]]
    return steps


def at_least(phase: Phase, other: Phase) -> bool:
    order = list(Phase)
    return order.index(phase) >= order.index(other)


def late(row) -> bool:
    return row["eligible"] and row["eta"]["days_to_spare"] < 0


def node_state(row, phase: Phase, target: str | None) -> Node:
    """One workshop's state at this phase."""
    if phase == Phase.IDLE:
        return Node.NEUTRAL
    if phase == Phase.EVALUATING:
        return Node.EVALUATING
    if not row["eligible"]:
        return Node.SUSPENDED if row["kind"] == "suspended" else Node.REJECTED
    if row["id"] == target and phase not in (Phase.FILTERING, Phase.RANKING):
        return {Phase.BLOCKED: Node.BLOCKED, Phase.IN_PROGRESS: Node.IN_PROGRESS, Phase.DELAYED: Node.DELAYED,
                Phase.RETURNED: Node.DELAYED, Phase.COMPLETED: Node.COMPLETED}.get(phase, Node.SELECTED)
    return Node.REJECTED if late(row) and not (target and row["id"] == target) else Node.SHORTLISTED


def edge_state(node: Node) -> Edge:
    return {Node.NEUTRAL: Edge.NEUTRAL, Node.EVALUATING: Edge.SCANNING, Node.SHORTLISTED: Edge.SHORTLISTED,
            Node.REJECTED: Edge.REJECTED, Node.SUSPENDED: Edge.REJECTED, Node.BLOCKED: Edge.WARNING,
            Node.DELAYED: Edge.WARNING}.get(node, Edge.WINNING)


def node_caption(row, node: Node, phase: Phase, plan: dict | None) -> str:
    """The short line under a node's name."""
    if node == Node.NEUTRAL:
        return ""
    if node == Node.EVALUATING:
        return "Checking"
    if node in (Node.REJECTED, Node.SUSPENDED):
        if not row["eligible"]:
            return {"suspended": "Suspended", "cannot": "Skill mismatch", "cap": "Over batch limit"}[row["kind"]]
        return f"Misses due date, {explain.days(-row['eta']['days_to_spare'])} late"
    back = explain.short_date(row["eta"]["eta_date"])
    if node == Node.BLOCKED:
        return f"Least late, back {back}"
    if node == Node.IN_PROGRESS:
        return "In production"
    if node == Node.DELAYED and plan:
        word = "Returned for rework" if phase == Phase.RETURNED else "Delayed"
        return f"{word}, back {explain.short_date(plan['back'].isoformat())}"
    if node == Node.COMPLETED and plan:
        return f"Back at factory {explain.short_date(plan['back'].isoformat())}"
    return f"Back {back}"


def ranks_visible(phase: Phase) -> bool:
    return at_least(phase, Phase.RANKING)


def steps(model, phase: Phase, target: str | None, outcome: str, through_outcome: bool, plan: dict | None) -> list[tuple[str, str]]:
    """(status, text) for the stepper under the map: done, active or pending."""
    rows = model["rows"]
    out = [r for r in rows.values() if not r["eligible"]]
    late_rows = [r for r in rows.values() if late(r)]
    name = rows[target]["name"] if target else ""
    text = {
        Phase.IDLE: "Request arrives at Sweater Co Factory",
        Phase.EVALUATING: f"Check all {len(rows)} workshops",
        Phase.FILTERING: (f"{len(out) + len(late_rows)} filtered out: "
                          + ", ".join([f"{r['name']} ({nm.FAIL_KIND[r['kind']].lower()})" for r in out]
                                      + [f"{r['name']} (misses the date)" for r in late_rows])) if out or late_rows else "No workshop filtered out",
        Phase.RANKING: f"Engine ranks {len(model['eligible'])} candidates",
        Phase.RECOMMENDED: f"Routed to {name}",
        Phase.BLOCKED: "No workshop meets the date. The least late needs your decision",
        Phase.CONFIRMED: "Route confirmed by the dispatcher",
        Phase.IN_PROGRESS: f"In production at {name}",
    }
    if plan:
        back = explain.short_date(plan["back"].isoformat())
        text[Phase.COMPLETED] = f"Back at factory {back}"
        text[Phase.DELAYED] = f"Delayed by a closure, back {back}"
        text[Phase.RETURNED] = f"Returned for rework, back {back}"
    seq = sequence(model, target, outcome, through_outcome)
    here = seq.index(phase) if phase in seq else len(seq) - 1
    return [("done" if i < here else "active" if i == here else "pending", text.get(p, p.value)) for i, p in enumerate(seq)]


def tracker(phase: Phase | None) -> tuple[list[str], str, str]:
    """Route tracker stage statuses, pill word and pill tone at this phase. None means the static plan preview."""
    if phase is None:
        return ["done", "now", "", "", ""], "", ""
    if not at_least(phase, Phase.RECOMMENDED):
        return ["", "", "", "", ""], "Evaluating", "info"
    if phase == Phase.BLOCKED:
        return ["", "", "", "", ""], "Needs decision", "warn"
    if phase == Phase.RECOMMENDED:
        return ["", "", "", "", ""], "Routed", "info"
    return {
        Phase.CONFIRMED: (["done", "now", "", "", ""], "Confirmed", "info"),
        Phase.IN_PROGRESS: (["done", "done", "now", "", ""], "In production", "info"),
        Phase.COMPLETED: (["done", "done", "done", "done", "done"], "Back at factory", "ok"),
        Phase.DELAYED: (["done", "done", "alert", "", ""], "Delayed", "risk"),
        Phase.RETURNED: (["done", "done", "done", "done", "alert"], "Returned for rework", "warn"),
    }[phase]
