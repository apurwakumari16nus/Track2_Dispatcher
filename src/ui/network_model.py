"""Workshop Network view model. Presentation data only, every value derived.

Eligibility, ETA and cost come from tools.py; the recommendation comes from a
copy of the session allocator (decide() commits history, so the session's own
allocator is never touched). Capacity outlook, risks and the what-if scenarios
apply the course simulator's written rules to the same numbers. Nothing here
is stored, sent or confirmed.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

import tools
from ui import explain

FIT = {  # key: (label, tone)
    "recommended": ("Recommended", "rec"),
    "strong": ("Strong fit", "ok"),
    "tight": ("Tight fit", "warn"),
    "late": ("Misses the date", "late"),
    "out": ("Cannot take it", "out"),
    "down": ("Suspended", "down"),
}
FAIL_KIND = {"suspended": "Suspended", "cannot": "Skill mismatch", "cap": "Batch too large"}
REWORK_FACTOR = 1.5   # simulate.py: a defective batch has half of it redone
CLOSURE_DAYS = 14     # simulate.py --shock: a workshop closes for two weeks
WEEKS = 4


def fail_kind(reason: str) -> str:
    if reason == "suspended" or reason.startswith("status"):
        return "suspended"
    return "cannot" if reason.startswith("cannot make") else "cap"


def tier(value, cuts, labels):
    return next((label for cut, label in zip(cuts, labels) if value <= cut), labels[-1])


def tags(w) -> list[str]:
    """Factual tags from the register."""
    out = [" and ".join(sorted(m.capitalize() for m in w.makes))]
    out.append(tier(w.capacity, (100, 200, 300), ("Small batches", "Mid capacity", "High capacity", "Very high capacity")))
    out.append(tier(w.cost, (0.9, 1.2, 1.4), ("Lowest cost", "Low cost", "Mid cost", "Premium cost")))
    out.append(tier(w.defect_rate, (0.03, 0.06, 0.09), ("Top quality", "Good quality", "Fair quality", "Rework prone")))
    if w.max_batch:
        out.append(f"Trial cap {w.max_batch:,} pieces")
    if w.lead_days >= 4:
        out.append(f"{w.lead_days}-day transport")
    return out


def capacity_outlook(queue_days: float, capacity: int, batch_days: float | None) -> list[dict]:
    """Four weeks of production days: already booked, this batch, spare. Workshops work 7 days a week."""
    weeks = []
    for n in range(WEEKS):
        start, end = 7 * n, 7 * n + 7
        booked = max(0.0, min(queue_days, end) - start)
        mine = 0.0
        if batch_days:
            mine = max(0.0, min(queue_days + batch_days, end) - max(queue_days, start))
        spare = max(0.0, 7 - booked - mine)
        weeks.append({"week": n + 1, "booked": booked, "batch": mine, "spare": spare,
                      "spare_pieces": round(spare * capacity), "booked_pieces": round(booked * capacity)})
    return weeks


def risks(w, row, flagged: bool, pieces: int) -> list[tuple[str, str]]:
    """(tone, sentence) operational risks, worst first."""
    out = []
    if w.status != "ACTIVE":
        out.append(("risk", "Suspended. It may not take new work."))
    if flagged:
        out.append(("risk", "Queue grew faster than expected. The monitor flags it as suspect."))
    if row and row["days_to_spare"] < 0:
        out.append(("risk", f"Returns {explain.days(-row['days_to_spare'])} after the due date."))
    elif row and row["days_to_spare"] <= 1:
        out.append(("warn", "No schedule buffer. Any slip makes it late."))
    if w.defect_rate >= 0.09:
        out.append(("warn", f"{w.defect_rate:.0%} of batches come back for rework, which adds half the processing time."))
    if row and row["queue_days"] >= 5:
        out.append(("warn", f"Long queue: {row['queue_days']:.1f} days before work starts."))
    if w.max_batch and pieces > 0.8 * w.max_batch and pieces <= w.max_batch:
        out.append(("warn", f"Close to its {w.max_batch:,}-piece trial cap."))
    if w.lead_days >= 4:
        out.append(("info", f"{w.lead_days} days of pickup and delivery on every batch."))
    return out


def versus(e: dict, best: dict | None, best_name: str) -> str:
    """One line against the recommendation, from the two estimates."""
    back = f"Back {explain.short_date(e['eta_date'])}"
    if best is None:
        return back + "."
    days = round(e["total_days"] - best["total_days"], 1)
    cost = e["total_cost"] - best["total_cost"]
    span = lambda d: f"{d:g} day" if d == 1 else f"{d:g} days"
    when = (f"{span(days)} after {best_name}" if days > 0 else f"{span(-days)} before {best_name}" if days < 0
            else f"the same day as {best_name}")
    money = f", costs {abs(cost):,.0f} {'more' if cost > 0 else 'less'}" if cost else ", same cost"
    return f"{back}, {when}{money}."


def evaluate(batch: dict, workshops, queues, today: date, allocator, config, flags) -> dict:
    """Everything the page shows for one batch query."""
    checks = {row["workshop_id"]: row for row in tools.check_eligibility(batch, workshops)}
    est = {wid: {**tools.estimate_eta(batch, wid, workshops, queues, today), **tools.estimate_cost(batch, wid, workshops)}
           for wid, row in checks.items() if row["eligible"]}
    trial = deepcopy(allocator)
    trial.config = config
    record = trial.decide({**batch, "order_id": batch.get("order_id") or "NETWORK-QUERY", "sent_date": today},
                          workshops, queues, today=today).to_dict()
    chosen = record.get("chosen_workshop")
    order = [row["workshop_id"] for row in explain.selection_order(record)]
    rows = {}
    for wid, w in workshops.items():
        e, check = est.get(wid), checks[wid]
        if not check["eligible"]:
            kind = fail_kind(check["reason"])
            fit = "down" if kind == "suspended" else "out"
            text = explain.reason_text(check["reason"])
            reason = text if text.lower().startswith(FAIL_KIND[kind].lower()) else f"{FAIL_KIND[kind]}. {text}"
        elif wid == chosen:
            fit, reason = "recommended", (explain.why_won(record) or {}).get("sentence", record.get("reason_chosen", ""))
        else:
            spare = e["days_to_spare"]
            fit = "late" if spare < 0 else "tight" if spare < 2 else "strong"
            reason = versus(e, est.get(chosen), workshops[chosen].name if chosen else "")
        batch_days = e["processing_days"] if e else None
        outlook = capacity_outlook(queues[wid], w.capacity, batch_days)
        rows[wid] = {
            "id": wid, "name": w.name, "w": w, "fit": fit, "label": FIT[fit][0], "tone": FIT[fit][1], "reason": reason,
            "eligible": bool(e), "kind": None if e else fail_kind(check["reason"]), "eta": e, "rank": order.index(wid) + 1 if wid in order else None,
            "quality": 1 - w.defect_rate, "queue": queues[wid], "outlook": outlook, "flagged": wid in flags,
            "util_now": min(1.0, (outlook[0]["booked"] + outlook[0]["batch"]) / 7),
            "risks": risks(w, e, wid in flags, batch["pieces"]), "tags": tags(w), "note": (w.notes or "").strip(),
        }
    ok = [r for r in rows.values() if r["eligible"]]
    on_time = [r for r in ok if r["eta"]["days_to_spare"] >= 0]
    pick = lambda rs, key: min(rs, key=key) if rs else None
    return {
        "record": record, "chosen": chosen, "rows": rows,
        "category": batch["category"], "pieces": batch["pieces"], "due": batch["due_date"],
        "eligible": ok, "on_time": on_time,
        "fastest": pick(ok, lambda r: (r["eta"]["total_days"], r["id"])),
        "cheapest": pick(ok, lambda r: (r["eta"]["total_cost"], r["id"])),
        "reliable": pick(ok, lambda r: (r["w"].defect_rate, r["id"])),
        "unavailable": [r for r in rows.values() if not r["eligible"]],
    }


def plan(row: dict, today: date, scenario: str = "plan") -> dict:
    """Stage dates for one routed batch, with the simulator's rework or closure rule applied."""
    e = row["eta"]
    queue, work, lead = e["queue_days"], e["processing_days"], e["lead_days"]
    note, state = "", "On plan"
    if scenario == "rework":
        work *= REWORK_FACTOR
        state, note = "Returned for rework", "Half the batch is redone (simulator rule), so production runs 50% longer."
    elif scenario == "closure":
        work += CLOSURE_DAYS
        state, note = "Bottleneck", f"The workshop closes for {CLOSURE_DAYS} days mid-job (simulator shock rule). Work pauses."
    start, finish = queue, queue + work
    back = today + timedelta(days=round(finish + lead))
    due = date.fromisoformat(e["due_date"])
    late = (back - due).days
    if scenario != "plan" and late > 0:
        state = "Delayed" if scenario == "closure" else state
    stages = [("Received", today, "Batch handed over at Sweater Co Factory"),
              ("Queued", today, f"{queue:.1f} days of existing work ahead" if queue else "No queue, starts at once"),
              ("In production", today + timedelta(days=round(start)),
               f"{e['processing_days']:.1f} production days plus a {CLOSURE_DAYS}-day closure" if scenario == "closure"
               else f"{work:.1f} production days at {row['w'].capacity:,} pieces a day"),
              ("In transit", today + timedelta(days=round(finish)), f"{explain.days(lead)} of pickup and delivery"),
              ("Back at factory", back, "Checked on return")]
    return {"stages": stages, "back": back, "late": late, "state": state, "note": note, "due": due}
