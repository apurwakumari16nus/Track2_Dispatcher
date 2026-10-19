"""Read-only explanations derived from recorded decision evidence.

Nothing here scores, ranks or selects. Every value comes from the decision
record (candidate rows, score terms, eligibility results, tool call trace,
post-checks and the faithfulness result). The selection order mirrors
Allocator.decide so "why" and "why not" describe the rule that actually ran.
UI sentences display rounded copies of recorded values; the numerical
faithfulness check applies to the recorded template explanation.
"""

from __future__ import annotations

from datetime import date
import math

from objectives import ObjectiveConfig, PRESETS

TERMS = ("lateness", "defect", "fairness", "robustness", "cost")
TERM_LABELS = {"lateness": "Lateness", "defect": "Defects", "fairness": "Fairness",
               "robustness": "Robustness", "cost": "Cost"}
TERM_NOTES = {
    "lateness": "late/(late+30) + 0.01·t/(t+30). On time, only the small speed tie-break remains.",
    "defect": "Batch defect probability from the workshop profile.",
    "fairness": "Share of this session's previously allocated pieces.",
    "robustness": "(queue-anomaly flag + 0.25 × share) / 1.25.",
    "cost": "Cost per piece / highest cost per piece in the register.",
}
OBJECTIVE_LABELS = {
    "lateness": "Minimise lateness", "defect": "Minimise defects", "fairness": "Fair allocation",
    "robustness": "Robust to failure", "hybrid_lateness_fairness": "Hybrid: lateness and fairness",
    "hybrid_lateness_defect": "Hybrid: lateness and quality", "cheapest_on_time": "Cheapest that makes the date",
}
PREFERENCE_LABELS = {"fastest": "fastest turnaround", "cheapest": "cheapest that makes the date",
                     "lowest_defect": "lowest defect rate"}
TOLERANCE = 1e-12


def objective_label(name: str) -> str:
    return OBJECTIVE_LABELS.get(name, name.replace("_", " ").capitalize())


def effective_config(name: str) -> ObjectiveConfig:
    """The weights behind a recorded objective name (mirrors agent._objective)."""
    if name == "cheapest_on_time":
        return ObjectiveConfig(w_cost=1, name="cheapest_on_time")
    return PRESETS[name]


def short_date(value) -> str:
    if not value:
        return "n/a"
    day = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{day.day} {day:%b}"


def long_date(value) -> str:
    if not value:
        return "n/a"
    day = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{day.day} {day:%b %Y}"


def days(n) -> str:
    n = int(n)
    return f"{n} day" if abs(n) == 1 else f"{n} days"


def late_days(row) -> int:
    return max(0, -int(row["days_to_spare"]))


def inventory(record: dict) -> list[dict]:
    """All profile-eligible rows with scores, including request/date exclusions."""
    return record.get("tool_outputs", {}).get("ui_candidate_inventory") or record.get("candidates", [])


def chosen_row(record: dict) -> dict | None:
    return next((row for row in record.get("candidates", []) if row["workshop_id"] == record.get("chosen_workshop")), None)


def selection_order(record: dict) -> list[dict]:
    """Permitted candidates in the order Allocator.decide would pick them."""
    rows = list(record.get("candidates", []))
    if not rows:
        return []
    on_time = [row for row in rows if row["days_to_spare"] >= 0]
    if not on_time:
        return sorted(rows, key=lambda r: (-r["days_to_spare"], r["total_days"], r["score"], r["workshop_id"]))
    ordered = sorted(rows, key=lambda r: (r["score"], r["total_days"], r["workshop_id"]))
    if record.get("constraints_applied", {}).get("must_make_date"):
        ordered = [row for row in ordered if row["days_to_spare"] >= 0]
    return ordered


def runner_up(record: dict) -> dict | None:
    order = selection_order(record)
    return order[1] if len(order) > 1 else None


def weighted_gaps(chosen: dict, other: dict, config: ObjectiveConfig) -> dict[str, float]:
    """Per-term weighted score difference (other minus chosen); positive favours chosen."""
    return {term: getattr(config, f"w_{term}") * (other["score_terms"][term] - chosen["score_terms"][term]) for term in TERMS}


def _term_phrase(term: str, chosen: dict, other: dict) -> str:
    if term == "lateness":
        if late_days(chosen) != late_days(other):
            return f"it is {days(late_days(other) - late_days(chosen))} less late"
        gap = other["total_days"] - chosen["total_days"]
        return f"it finishes {gap:.1f} days sooner ({chosen['total_days']:.1f} vs {other['total_days']:.1f} days)"
    if term == "defect":
        return f"its defect probability is lower ({chosen['expected_defect_rate']:.0%} vs {other['expected_defect_rate']:.0%})"
    if term == "fairness":
        return (f"it holds a smaller share of this session's allocated pieces "
                f"({chosen['score_terms']['fairness']:.0%} vs {other['score_terms']['fairness']:.0%})")
    if term == "robustness":
        if other.get("shock_flagged") and not chosen.get("shock_flagged"):
            return f"{other['name']} is flagged for an unexplained queue jump"
        return "it carries less concentration and anomaly risk"
    return f"it costs less per piece ({chosen['cost_per_piece']:g} vs {other['cost_per_piece']:g})"


def decisive_reason(chosen: dict, other: dict, config: ObjectiveConfig) -> tuple[str, str | None]:
    """(phrase, deciding term) explaining why chosen ranks above other."""
    gap = other["score"] - chosen["score"]
    if abs(gap) <= TOLERANCE:
        if not math.isclose(other["total_days"], chosen["total_days"], rel_tol=0, abs_tol=TOLERANCE):
            return "the scores tie and it finishes sooner, which breaks the tie", None
        return "the scores and durations tie, so workshop order breaks the tie", None
    gaps = weighted_gaps(chosen, other, config)
    term = max(gaps, key=gaps.get)
    return _term_phrase(term, chosen, other), term


def why_won(record: dict) -> dict | None:
    """One-sentence, data-derived reason for the recommendation, or None."""
    chosen = chosen_row(record)
    if chosen is None:
        return None
    config = effective_config(record["objective_name"])
    order = selection_order(record)
    other = order[1] if len(order) > 1 else None
    label = objective_label(record["objective_name"]).lower()
    due = short_date(chosen["due_date"])
    if record.get("awkward_case") == "none_makes_date":
        sentence = (f"No permitted workshop can return this by {due}. {chosen['name']} is the least-late option, "
                    f"back {short_date(chosen['eta_date'])}, {days(late_days(chosen))} late.")
        if other is not None and late_days(other) > late_days(chosen):
            sentence = sentence[:-1] + f", {days(late_days(other) - late_days(chosen))} less late than {other['name']}."
        return {"kind": "least_late", "sentence": sentence, "chosen": chosen, "runner_up": other, "term": None}
    if other is None:
        scope = " that makes the date" if record.get("constraints_applied", {}).get("must_make_date") else ""
        return {"kind": "only", "sentence": f"{chosen['name']} is the only permitted workshop{scope}.",
                "chosen": chosen, "runner_up": None, "term": None}
    phrase, term = decisive_reason(chosen, other, config)
    if record["objective_name"] == "cheapest_on_time":
        sentence = f"{chosen['name']} is the cheapest permitted workshop that still makes {due} ({chosen['cost_per_piece']:g} per piece vs {other['cost_per_piece']:g} at {other['name']})."
    else:
        sentence = f"{chosen['name']} beats {other['name']} under {label} because {phrase}."
    return {"kind": "score", "sentence": sentence, "chosen": chosen, "runner_up": other, "term": term}


def comparison(chosen: dict, other: dict) -> list[dict]:
    """Chosen minus runner-up on the facts a dispatcher compares."""
    return [
        {"label": "Back by", "chosen": short_date(chosen["eta_date"]), "other": short_date(other["eta_date"]),
         "delta": other["total_days"] - chosen["total_days"], "unit": "days sooner", "better": other["total_days"] > chosen["total_days"]},
        {"label": "Days to spare", "chosen": str(chosen["days_to_spare"]), "other": str(other["days_to_spare"]),
         "delta": chosen["days_to_spare"] - other["days_to_spare"], "unit": "more days of margin", "better": chosen["days_to_spare"] > other["days_to_spare"]},
        {"label": "Total cost", "chosen": f"{chosen['total_cost']:,.0f}", "other": f"{other['total_cost']:,.0f}",
         "delta": other["total_cost"] - chosen["total_cost"], "unit": "cheaper", "better": chosen["total_cost"] < other["total_cost"]},
        {"label": "Defect risk", "chosen": f"{chosen['expected_defect_rate']:.0%}", "other": f"{other['expected_defect_rate']:.0%}",
         "delta": other["expected_defect_rate"] - chosen["expected_defect_rate"], "unit": "lower defect risk", "better": chosen["expected_defect_rate"] < other["expected_defect_rate"]},
        {"label": "Queue now", "chosen": f"{chosen['queue_days']:.1f} d", "other": f"{other['queue_days']:.1f} d",
         "delta": other["queue_days"] - chosen["queue_days"], "unit": "days shorter queue", "better": chosen["queue_days"] < other["queue_days"]},
    ]


def score_breakdown(rows: list[dict], config: ObjectiveConfig) -> list[dict]:
    """Weighted contribution of every term for each row, from recorded score_terms."""
    result = []
    for row in rows:
        parts = [{"term": term, "label": TERM_LABELS[term], "weight": getattr(config, f"w_{term}"),
                  "value": row["score_terms"][term],
                  "contribution": getattr(config, f"w_{term}") * row["score_terms"][term],
                  "active": getattr(config, f"w_{term}") > 0} for term in TERMS]
        result.append({"workshop_id": row["workshop_id"], "name": row["name"], "score": row["score"], "parts": parts})
    return result


INELIGIBLE_HEADLINES = {"suspended": "Suspended", "cannot": "Cannot make this category", "batch": "Batch exceeds cap"}


def eligibility_rows(record: dict) -> list[dict]:
    """Latest eligibility tool result for the batch, falling back to ineligible rows."""
    rows = record.get("tool_outputs", {}).get("eligibility")
    if rows:
        return rows
    return [{**row, "eligible": False} for row in record.get("ineligible", [])]


def ineligible_headline(reason: str) -> str:
    if reason == "suspended":
        return "Suspended"
    if reason.startswith("cannot make"):
        return "Cannot make " + reason.split("cannot make ", 1)[1]
    if reason.startswith("batch of"):
        return "Batch exceeds its cap"
    return reason


def constraint_sources(record: dict, workshop_id: str, name: str) -> list[str]:
    """Attributed statements that mention this workshop, e.g. 'keep it away' with who said it."""
    out = []
    for statement in record.get("constraints_applied", {}).get("statements", []) or []:
        text = statement.get("text", "")
        if workshop_id.casefold() in text.casefold() or name.casefold() in text.casefold():
            who = statement.get("imposed_by") or "unknown"
            relay = f", relayed by {statement['relayed_by']}" if statement.get("relayed_by") else ""
            out.append(f"“{text}” (imposed by {who}{relay})")
    return out


def why_not(record: dict, workshop_id: str, workshops: dict) -> dict:
    """Deterministic reason this workshop is not the recommendation."""
    name = workshops[workshop_id].name if workshop_id in workshops else workshop_id
    chosen = chosen_row(record)
    if record.get("chosen_workshop") == workshop_id:
        return {"status": "chosen", "tone": "chosen", "headline": "This is the recommendation", "detail": []}
    eligibility = {row["workshop_id"]: row for row in eligibility_rows(record)}
    check = eligibility.get(workshop_id)
    if check is not None and not check["eligible"]:
        detail = [f"Eligibility tool result: {check['reason']}."]
        headline = "Suspended: may not take new work" if check["reason"] == "suspended" else ineligible_headline(check["reason"])
        return {"status": "ineligible", "tone": "blocked", "headline": headline, "detail": detail}
    rows = {row["workshop_id"]: row for row in inventory(record)}
    row = rows.get(workshop_id)
    if row is None:
        return {"status": "not_evaluated", "tone": "muted", "headline": "Not evaluated",
                "detail": ["No candidates were estimated because the request needs a reply before allocation."]}
    if row.get("exclusion_reason") == "Excluded by request":
        sources = constraint_sources(record, workshop_id, name)
        return {"status": "excluded", "tone": "blocked", "headline": "Excluded by request",
                "detail": sources or ["The request excluded this workshop."]}
    if row.get("exclusion_reason") == "Misses required due date":
        return {"status": "misses_date", "tone": "warn", "headline": "Misses the required date",
                "detail": [f"Back {short_date(row['eta_date'])}, {days(late_days(row))} after {short_date(row['due_date'])}. "
                           "The request requires meeting the date, and on-time options exist."]}
    if chosen is None:
        return {"status": "not_evaluated", "tone": "muted", "headline": "No recommendation", "detail": []}
    if record.get("awkward_case") == "none_makes_date":
        if late_days(row) > late_days(chosen):
            headline = f"More days late: {late_days(row)} vs {late_days(chosen)}"
        else:
            headline = "Same lateness, slower finish"
        return {"status": "later", "tone": "warn", "headline": headline,
                "detail": [f"Back {short_date(row['eta_date'])} vs {short_date(chosen['eta_date'])}. "
                           "When every option is late, the least-late option is recommended."]}
    phrase, term = decisive_reason(chosen, row, effective_config(record["objective_name"]))
    reason = phrase.replace("it ", chosen["name"] + " ", 1) if phrase.startswith("it ") else phrase
    return {"status": "outscored", "tone": "muted", "headline": "Higher configured score",
            "detail": [f"Score {row['score']:.5f} vs {chosen['score']:.5f} for {chosen['name']} (lower is better).",
                       f"Deciding difference: {reason}."],
            "term": term}


def workshop_status(check: dict, eta: dict | None, flagged: bool) -> tuple[str, str]:
    """(label, tone) for a register card: eligibility first, then timing."""
    if not check["eligible"]:
        reason = check["reason"]
        if reason == "suspended":
            return "Suspended", "blocked"
        if reason.startswith("cannot make"):
            return "Capability mismatch", "muted"
        return "Batch cap exceeded", "warn"
    if eta is None:
        return "Eligible", "ok"
    if eta["days_to_spare"] < 0:
        return "Late", "warn"
    return "On time", "ok"


# Execution trace -------------------------------------------------------------

ACTORS = {"model": "Language model", "python": "Python", "human": "Human"}


def _calls(record, names, calls=None):
    calls = record.get("tool_outputs", {}).get("call_trace", []) if calls is None else calls
    return [c for c in calls if c["tool"] in names]


def source_label(metadata: dict) -> tuple[str, str]:
    """(actor, label) for the extraction step, from recorded reply metadata."""
    source = metadata.get("extraction_source")
    model = metadata.get("recorded_model") or metadata.get("model") or "model"
    if source == "fixture" or metadata.get("provider") == "synthetic-fixture":
        return "fixture", "Synthetic test fixture (not model output)"
    if source == "cached":
        return "model", f"Recorded reply from {model}"
    return "model", f"Live reply from {model}"


def trace_steps(response: dict, *, agent_calls: int | None, replayed: bool, confirmed: bool, block_reason: str | None) -> list[dict]:
    """Observable program events for one preview, in execution order.

    agent_calls is the number of traced tool calls made by the agent itself;
    later calls belong to the app's independent replay and inventory.
    """
    parsed, record = response["parsed_request"], response["decision_record"]
    calls = record.get("tool_outputs", {}).get("call_trace", [])
    agent = calls[:agent_calls] if agent_calls is not None else calls
    replay = calls[agent_calls:] if agent_calls is not None else []
    behaviour = parsed["behaviour"]
    allocating = behaviour in {"allocate", "refuse"} and bool(record.get("candidates") or _calls(record, {"candidates"}, agent))
    skipped = "Not run: the request needs a reply before allocation."
    steps = []

    actor, label = source_label(parsed.get("llm_metadata") or {})
    raw = parsed.get("raw_llm_json") or {}
    facts = [f"{k.replace('_', ' ')} {raw[k]}" for k in ("order_id", "pieces", "category", "due_date_text", "preference") if raw.get(k)]
    steps.append({"key": "interpret", "title": "Request interpreted", "actor": actor, "status": "done",
                  "summary": label + (". Extracted " + ", ".join(facts) if facts else ". No order facts stated"),
                  "evidence": {"raw_extraction": raw, "reply_metadata": parsed.get("llm_metadata")}})

    checks = parsed.get("post_checks", [])
    changed = [c for c in checks if c.get("before") != c.get("after")]
    summary = f"{len(checks)} rule checks against orders.csv and workshops.csv"
    if changed:
        summary += "; behaviour set to " + changed[-1]["after"]["behaviour"] + f" ({changed[-1]['after']['reason']})"
    else:
        summary += f"; behaviour {behaviour}"
    steps.append({"key": "validate", "title": "Facts validated", "actor": "python", "status": "done",
                  "summary": summary, "evidence": checks})

    lookups = _calls(record, {"order_options"}, agent)
    options = record.get("tool_outputs", {}).get("order_options", [])
    if options:
        summary = "; ".join(f"{o['order_id']} {o['customer']} {o['product']} {o['pieces']} pcs, {o['current_stage'].lower()}" for o in options[:4])
        if len(options) > 4:
            summary += f"; and {len(options) - 4} more"
    else:
        summary = "No matching order row"
    steps.append({"key": "order", "title": "Order looked up", "actor": "python", "status": "done" if lookups else "skipped",
                  "summary": summary, "evidence": [c.get("output") for c in lookups]})

    eligibility = _calls(record, {"check_eligibility"}, agent)
    if allocating and eligibility:
        latest = eligibility[-1]["output"]
        ok = sum(r["eligible"] for r in latest)
        steps.append({"key": "eligibility", "title": "Eligibility checked", "actor": "python", "status": "done",
                      "summary": f"{ok} of {len(latest)} workshops can make, may take and fit this batch",
                      "evidence": latest})
    else:
        steps.append({"key": "eligibility", "title": "Eligibility checked", "actor": "python", "status": "skipped",
                      "summary": skipped if not allocating else "No eligibility call recorded", "evidence": [c.get("output") for c in eligibility]})

    estimates = _calls(record, {"estimate_eta", "estimate_cost"}, agent)
    steps.append({"key": "estimate", "title": "Delivery and cost estimated", "actor": "python",
                  "status": "done" if allocating and estimates else "skipped",
                  "summary": (f"{len(record.get('candidates', []))} permitted candidates: queue + processing + transport, pieces × price"
                              if allocating else skipped),
                  "evidence": [c.get("output") for c in estimates]})

    if allocating:
        ranked = record.get("reason_chosen") or "No permitted candidate"
        if record.get("chosen_workshop") is None:
            ranked = "No whole-batch candidate remains after exclusions; escalate"
        observe = _calls(record, {"ShockMonitor.observe"}, agent)
        steps.append({"key": "rank", "title": "Candidates scored and ranked", "actor": "python", "status": "done",
                      "summary": f"Objective {objective_label(record['objective_name'])}. {ranked}",
                      "evidence": {"candidates": record.get("candidates"), "shock_observation": [c.get("output") for c in observe],
                                   "constraints": record.get("constraints_applied")}})
    else:
        steps.append({"key": "rank", "title": "Candidates scored and ranked", "actor": "python", "status": "skipped",
                      "summary": skipped, "evidence": None})

    probes = _calls(record, {"queue_check", "overload_probe"}, agent)
    if probes:
        probe = record.get("tool_outputs", {}).get("overload")
        summary = (f"Queue at {probe['workshop_id']} would go from {probe['queue_before']:.1f} to {probe['queue_after']:.1f} days"
                   if probe else "Queue checked")
        steps.append({"key": "capacity", "title": "Capacity impact probed", "actor": "python", "status": "done",
                      "summary": summary, "evidence": [c.get("output") for c in probes]})
    split = record.get("tool_outputs", {}).get("split")
    if split is not None:
        if split.get("available"):
            parts = " + ".join(f"{part['pieces']} at {part['name']}" for part in split["parts"])
            summary = f"Fastest legal split: {parts}, back {short_date(split['eta_date'])}"
        else:
            summary = "No legal two-workshop split: " + split.get("reason", "")
        steps.append({"key": "split", "title": "Split evaluated", "actor": "python", "status": "done",
                      "summary": summary + ". Preview only.", "evidence": split})

    if replayed:
        steps.append({"key": "replay", "title": "Decision reproduced", "actor": "python", "status": "done",
                      "summary": "An independent replay on a fresh copy of the session state chose the same workshop with the same candidate scores",
                      "evidence": [c.get("output") for c in replay if c["tool"] in {"candidates", "overload_probe"}]})
    audit = response.get("faithfulness") or {}
    numbers = audit.get("numbers_in_text", [])
    if audit.get("passed"):
        summary = f"All {len(numbers)} numbers, dates and IDs in the explanation were found in tool outputs"
    else:
        summary = "Unsupported values: " + ", ".join(audit.get("unmatched", []))
    steps.append({"key": "verify", "title": "Explanation verified", "actor": "python",
                  "status": "done" if audit.get("passed") else "blocked", "summary": summary, "evidence": audit})

    if confirmed:
        human = ("done", "Confirmed by the dispatcher. Audit record written; session queue updated")
    elif block_reason:
        human = ("skipped", block_reason)
    else:
        human = ("pending", "Awaiting the dispatcher's confirmation. Nothing has been recorded yet")
    steps.append({"key": "confirm", "title": "Human confirmation", "actor": "human", "status": human[0],
                  "summary": human[1], "evidence": None})
    return steps


STAGES = [("interpret", "Interpret"), ("validate", "Validate"), ("eligibility", "Check eligibility"),
          ("estimate", "Estimate options"), ("rank", "Rank"), ("verify", "Verify evidence"), ("confirm", "Confirm")]
STAGE_MEMBERS = {"interpret": {"interpret"}, "validate": {"validate", "order"}, "eligibility": {"eligibility"},
                 "estimate": {"estimate"}, "rank": {"rank", "capacity", "split"}, "verify": {"replay", "verify"},
                 "confirm": {"confirm"}}


def stage_status(steps: list[dict]) -> list[tuple[str, str, str]]:
    """Collapse trace steps into the seven compact stages: (key, label, status)."""
    by_key = {step["key"]: step["status"] for step in steps}
    out = []
    for key, label in STAGES:
        statuses = [by_key[m] for m in STAGE_MEMBERS[key] if m in by_key]
        if not statuses:
            status = "skipped"
        elif "blocked" in statuses:
            status = "blocked"
        elif "pending" in statuses:
            status = "pending"
        elif "done" in statuses:
            status = "done"
        else:
            status = "skipped"
        out.append((key, label, status))
    return out
