"""What to do when a workshop's situation changes: a plan the dispatcher can approve in one step.

Given an incident, works out every batch it touches: what happens if the batch
stays, and where the same engine would send it instead, with the queue moving as
each batch is placed so later estimates stay honest. Pure: it reads the world and
returns a plan. Only control.approve writes anything.

A batch already in production stays put by default, because half-made work does
not move. Everything else moves only when that is genuinely better for the
customer date, or when the workshop has given no return date at all.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import math

import ops
import tools
from ui import explain

MOVABLE = ("booked", "offered", "accepted", "declined")


def _changed(world, incident):
    workshops = deepcopy(world.workshops)
    for name, value in incident.get("changes", {}).items():
        setattr(workshops[incident["workshop_id"]], name, value)
    return workshops


def _stay(world, incident, job):
    """When the batch comes back if it stays: a date, or None when the workshop has not said."""
    kind, back, today = incident["type"], job["back"], world.today
    if kind == "declined":
        return None
    if kind == "delay":
        if incident.get("back"):
            return date.fromisoformat(incident["back"])
        return back + timedelta(days=incident["delay_days"]) if incident.get("delay_days") else None
    if kind == "closed":
        if not incident.get("until"):
            return None
        return back + timedelta(days=max(0, (date.fromisoformat(incident["until"]) - today).days))
    if kind == "capacity":
        was, new = world.workshops[job["workshop_id"]].capacity, incident.get("changes", {}).get("capacity")
        return back + timedelta(days=math.ceil(job["pieces"] / new - job["pieces"] / was)) if new else None
    return back


def _spare(job, day):
    return (job["due"] - day).days if job["due"] and day else None


def plan(world, incident) -> dict:
    wid = incident["workshop_id"]
    keys = incident.get("jobs", [])
    jobs = sorted((world.jobs[k] for k in keys if k in world.jobs), key=lambda j: (j["due"] or j["back"], j["order_id"] or ""))
    workshops = _changed(world, incident)
    queues, allocator = dict(world.queues), deepcopy(world.allocator)
    for job in jobs:   # Their work is leaving this workshop's queue or waiting; it must not count against the alternatives.
        if job["workshop_id"] == wid:
            queues[wid] = max(0.0, queues.get(wid, 0.0) - job["pieces"] / world.base[wid].capacity)
    rows = []
    for job in jobs:
        stay_on = _stay(world, incident, job)
        stay_spare = _spare(job, stay_on)
        row = {"job": job["key"], "order_id": job["order_id"], "customer": job["customer"], "product": job["product"], "pieces": job["pieces"],
               "stage": job["stage"], "stage_label": ops.STAGES[job["stage"]], "due": job["due"], "was": {"workshop": job["workshop"], "back": job["back"]},
               "stay": {"back": stay_on, "days_to_spare": stay_spare, "note": "Cannot take it" if incident["type"] == "declined" else None if stay_on else "No date given"},
               "move": None, "action": "wait", "tell_client": False, "why": "", "can_keep": incident["type"] != "declined"}
        movable = job["stage"] in MOVABLE
        best = None
        if movable:
            batch = {"order_id": job["order_id"], "pieces": job["pieces"], "category": job["category"], "due_date": job["due"] or job["back"],
                     "sent_date": world.today}
            record = allocator.decide(batch, workshops, queues, world.today, exclude=[wid])
            if record.chosen_workshop:
                best = next(c for c in record.candidates if c["workshop_id"] == record.chosen_workshop)
                row["move"] = {"workshop_id": best["workshop_id"], "name": best["name"], "back": best["eta_date"], "days_to_spare": best["days_to_spare"],
                               "cost": best["total_cost"], "cost_change": round(best["total_cost"] - job["pieces"] * (job["rate"] or 0), 2),
                               "defect": best["expected_defect_rate"]}
        better = best is not None and (stay_on is None or (stay_spare is not None and stay_spare < 0 and best["days_to_spare"] > stay_spare))
        if better:
            row["action"] = "move"
            row["why"] = (f"{best['name']} is the best alternative." if incident["type"] == "declined" else "The workshop has not said when it reopens." if stay_on is None else
                          f"Staying misses {explain.short_date(job['due'])}. {best['name']} is the best alternative.")
            queues[best["workshop_id"]] = tools.overload_probe(batch, best["workshop_id"], workshops, queues)["queue_after"]
        elif not movable:
            row["why"] = "Already finished, so it stays." if job["stage"] == "ready" else "Already in production, so it stays."
        elif best is None and stay_on is None:
            row["action"], row["why"] = "person", "No other workshop can take this batch."
        else:
            if best is not None:   # decide() booked it in this scratch copy; the batch is staying after all.
                allocator.pieces_by_workshop[best["workshop_id"]] -= job["pieces"]
            row["why"] = "Still makes the customer date." if (stay_spare or 0) >= 0 else "Moving would not be any better."
        final = (row["move"]["days_to_spare"] if row["action"] == "move" else stay_spare)
        row["tell_client"] = final is not None and final < 0 and bool(job["customer"])
        row["final_back"] = row["move"]["back"] if row["action"] == "move" else stay_on
        rows.append(row)
    missed = sum(1 for r in rows if r["tell_client"])
    moved = sum(1 for r in rows if r["action"] == "move")
    return {"incident": incident["id"], "workshop_id": wid, "rows": rows, "moves": moved, "stays": len(rows) - moved, "client_notices": missed,
            "change_label": incident.get("label"), "cost_change": round(sum(r["move"]["cost_change"] for r in rows if r["action"] == "move"), 2)}
