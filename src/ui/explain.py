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
    "lateness": "Late days dominate. When every option is on time, a small speed term, 0.01 × t/(t+30), separates them.",
    "defect": "Batch defect probability from the workshop profile.",
    "fairness": "Share of this session's previously allocated pieces.",
    "robustness": "Queue anomaly flag plus a quarter of the share, scaled to 0 to 1.",
    "cost": "Cost per piece relative to the most expensive workshop.",
}
OBJECTIVE_LABELS = {
    "lateness": "Minimise lateness", "defect": "Minimise defects", "fairness": "Fair allocation",
    "robustness": "Robust to failure", "hybrid_lateness_fairness": "Lateness and fairness",
    "hybrid_lateness_defect": "Lateness and quality", "cheapest_on_time": "Cheapest that makes the date",
}
PREFERENCE_LABELS = {"fastest": "Fastest turnaround", "cheapest": "Cheapest that makes the date",
                     "lowest_defect": "Lowest defect rate"}
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


def deciding_term(chosen: dict, other: dict, config: ObjectiveConfig) -> str | None:
    """The weighted term contributing most to the score gap, or None for a score tie."""
    if abs(other["score"] - chosen["score"]) <= TOLERANCE:
        return None
    gaps = weighted_gaps(chosen, other, config)
    return max(gaps, key=gaps.get)


def comparison_sentence(chosen: dict, other: dict, config: ObjectiveConfig) -> str:
    """Why chosen ranks above other, in one sentence of recorded values."""
    c, o = chosen["name"], other["name"]
    term = deciding_term(chosen, other, config)
    if term is None:
        if not math.isclose(other["total_days"], chosen["total_days"], rel_tol=0, abs_tol=TOLERANCE):
            return f"{c} and {o} have the same score, and {c} finishes sooner, which breaks the tie."
        return f"{c} and {o} have the same score and duration, so workshop order breaks the tie."
    if term == "lateness":
        if late_days(chosen) != late_days(other):
            return f"{c} is {days(late_days(other) - late_days(chosen))} less late than {o}."
        return f"{c} finishes {other['total_days'] - chosen['total_days']:.1f} days before {o}."
    if term == "defect":
        return f"{c} has the lower defect probability: {chosen['expected_defect_rate']:.0%} against {other['expected_defect_rate']:.0%} at {o}."
    if term == "fairness":
        return (f"{c} has received a smaller share of this session's work: "
                f"{chosen['score_terms']['fairness']:.0%} against {other['score_terms']['fairness']:.0%} at {o}.")
    if term == "robustness":
        if other.get("shock_flagged") and not chosen.get("shock_flagged"):
            return f"{o} is flagged for an unexplained queue jump. {c} is not."
        return f"{c} carries less concentration risk than {o}."
    return f"{c} costs less per piece: {chosen['cost_per_piece']:g} against {other['cost_per_piece']:g} at {o}."


def why_won(record: dict) -> dict | None:
    """One data-derived sentence for the recommendation, or None."""
    chosen = chosen_row(record)
    if chosen is None:
        return None
    config = effective_config(record["objective_name"])
    order = selection_order(record)
    other = order[1] if len(order) > 1 else None
    due = short_date(chosen["due_date"])
    if record.get("awkward_case") == "none_makes_date":
        sentence = (f"No permitted workshop can return this by {due}. {chosen['name']} is the least late: "
                    f"back {short_date(chosen['eta_date'])}, {days(late_days(chosen))} late.")
        if other is not None and late_days(other) > late_days(chosen):
            sentence += f" The next option, {other['name']}, is {days(late_days(other))} late."
        return {"kind": "least_late", "sentence": sentence, "chosen": chosen, "runner_up": other, "term": "lateness"}
    if other is None:
        scope = " that makes the date" if record.get("constraints_applied", {}).get("must_make_date") else ""
        return {"kind": "only", "sentence": f"{chosen['name']} is the only permitted workshop{scope}.",
                "chosen": chosen, "runner_up": None, "term": None}
    term = deciding_term(chosen, other, config)
    if record["objective_name"] == "cheapest_on_time":
        sentence = (f"{chosen['name']} is the cheapest permitted workshop that still makes {due}: "
                    f"{chosen['cost_per_piece']:g} per piece against {other['cost_per_piece']:g} at {other['name']}.")
    else:
        sentence = comparison_sentence(chosen, other, config)
    return {"kind": "score", "sentence": sentence, "chosen": chosen, "runner_up": other, "term": term}


def deciding_metrics(record: dict, chosen: dict, other: dict) -> list[dict]:
    """Only the facts the selection rule actually used, winner against another option."""
    config = effective_config(record["objective_name"])
    if record.get("awkward_case") == "none_makes_date":
        keys = ["late", "eta"]
    elif record["objective_name"] == "cheapest_on_time":
        keys = ["cpp", "cost", "spare"]
    else:
        term = deciding_term(chosen, other, config)
        keys = {None: ["score", "total"], "lateness": ["late", "total"] if late_days(chosen) != late_days(other) else ["total", "eta"],
                "defect": ["defect"], "fairness": ["share"], "robustness": ["flag", "share"], "cost": ["cpp", "cost"]}[term]
    specs = {
        "total": ("Total time", lambda r: r["total_days"], lambda v: f"{v:.1f} days", lambda d: f"{d:.1f} days sooner", True),
        "eta": ("Back by", lambda r: r["total_days"], None, None, True),
        "late": ("Days late", lambda r: late_days(r), lambda v: days(v), lambda d: f"{days(d)} less late", True),
        "defect": ("Defect probability", lambda r: r["expected_defect_rate"], lambda v: f"{v:.0%}", lambda d: f"{d:.0%} lower", True),
        "share": ("Share of session work", lambda r: r["score_terms"]["fairness"], lambda v: f"{v:.0%}", lambda d: f"{d:.0%} smaller", True),
        "flag": ("Queue anomaly flag", lambda r: float(bool(r.get("shock_flagged"))), lambda v: "Flagged" if v else "Clear", lambda d: "Clear vs flagged", True),
        "cpp": ("Cost per piece", lambda r: r["cost_per_piece"], lambda v: f"{v:g}", lambda d: f"{d:g} less", True),
        "cost": ("Total cost", lambda r: r["total_cost"], lambda v: f"{v:,.0f}", lambda d: f"{d:,.0f} less", True),
        "spare": ("Days to spare", lambda r: -r["days_to_spare"], lambda v: days(-v), lambda d: f"{days(d)} more", True),
        "score": ("Configured score", lambda r: r["score"], lambda v: f"{v:.5f}", lambda d: f"{d:.5f} lower", True),
    }
    rows = []
    for key in keys:
        label, value, fmt, diff, lower_better = specs[key]
        a, b = value(chosen), value(other)
        if key == "eta":
            rows.append({"label": label, "winner": short_date(chosen["eta_date"]), "other": short_date(other["eta_date"]),
                         "difference": "Same date" if chosen["eta_date"] == other["eta_date"] else "Earlier", "better": chosen["eta_date"] < other["eta_date"]})
            continue
        gap = b - a
        same = abs(gap) <= 1e-9
        rows.append({"label": label, "winner": fmt(a), "other": fmt(b),
                     "difference": "Same" if same else diff(abs(gap)) if gap > 0 else "Other option better", "better": None if same else gap > 0})
    return rows


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


def eligibility_rows(record: dict) -> list[dict]:
    """Latest eligibility tool result for the batch, falling back to ineligible rows."""
    rows = record.get("tool_outputs", {}).get("eligibility")
    if rows:
        return rows
    return [{**row, "eligible": False} for row in record.get("ineligible", [])]


def ineligible_headline(reason: str) -> str:
    """Short label for an eligibility tool reason."""
    if reason == "suspended":
        return "Suspended"
    if reason.startswith("cannot make"):
        return "Cannot produce " + reason.split("cannot make ", 1)[1].lower()
    if reason.startswith("batch of"):
        return "Trial batch cap exceeded"
    return reason


def reason_text(reason: str) -> str:
    """Plain-language version of an eligibility tool reason, keeping its numbers."""
    if reason == "suspended":
        return "Suspended after an audit. It may not take new work."
    if reason.startswith("cannot make"):
        return "It is not equipped to make " + reason.split("cannot make ", 1)[1].lower() + "."
    if reason.startswith("batch of"):
        pieces, cap = reason.split("batch of ", 1)[1].split(" exceeds ")
        return f"Trial batch cap exceeded: {pieces} pieces against a cap of {cap.split('-piece')[0]}."
    return reason


def constraint_sources(record: dict, workshop_id: str, name: str) -> list[str]:
    """Attributed statements that mention this workshop, with who imposed them."""
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
        return {"status": "chosen", "tone": "info", "headline": "This is the recommendation", "detail": [], "row": chosen}
    eligibility = {row["workshop_id"]: row for row in eligibility_rows(record)}
    check = eligibility.get(workshop_id)
    if check is not None and not check["eligible"]:
        headline = "Suspended: may not take new work" if check["reason"] == "suspended" else ineligible_headline(check["reason"])
        return {"status": "ineligible", "tone": "risk", "headline": headline,
                "detail": [reason_text(check["reason"]), f"Eligibility tool result: {check['reason']}."], "row": None}
    rows = {row["workshop_id"]: row for row in inventory(record)}
    row = rows.get(workshop_id)
    if row is None:
        return {"status": "not_evaluated", "tone": "muted", "headline": "Not evaluated",
                "detail": ["No workshops were estimated because the request needs a reply first."], "row": None}
    if row.get("exclusion_reason") == "Excluded by request":
        sources = constraint_sources(record, workshop_id, name)
        return {"status": "excluded", "tone": "risk", "headline": "Excluded by the requester",
                "detail": sources or ["The request excluded this workshop."], "row": row}
    if row.get("exclusion_reason") == "Misses required due date":
        return {"status": "misses_date", "tone": "warn", "headline": "Misses the required date",
                "detail": [f"Back {short_date(row['eta_date'])}, {days(late_days(row))} after {short_date(row['due_date'])}. "
                           "The request requires meeting the date, and on-time options exist."], "row": row}
    if chosen is None:
        return {"status": "not_evaluated", "tone": "muted", "headline": "No recommendation", "detail": [], "row": row}
    if record.get("awkward_case") == "none_makes_date":
        headline = f"More days late: {late_days(row)} against {late_days(chosen)}" if late_days(row) > late_days(chosen) else "Same lateness, slower finish"
        return {"status": "later", "tone": "warn", "headline": headline,
                "detail": [f"Back {short_date(row['eta_date'])} against {short_date(chosen['eta_date'])} for {chosen['name']}. "
                           "When every option is late, the least-late option is recommended."], "row": row}
    config = effective_config(record["objective_name"])
    return {"status": "outscored", "tone": "muted", "headline": "Higher configured score",
            "detail": [f"Score {row['score']:.5f} against {chosen['score']:.5f} for {chosen['name']}. Lower is better.",
                       comparison_sentence(chosen, row, config)],
            "term": deciding_term(chosen, row, config), "row": row}


def workshop_status(check: dict, eta: dict | None, flagged: bool) -> tuple[str, str]:
    """(label, tone) for a register row: eligibility first, then timing."""
    if not check["eligible"]:
        reason = check["reason"]
        if reason == "suspended":
            return "Suspended", "risk"
        if reason.startswith("cannot make"):
            return "Cannot produce", "muted"
        return "Batch cap exceeded", "warn"
    if eta is None:
        return "Eligible", "ok"
    if eta["days_to_spare"] < 0:
        return "Late", "warn"
    return "On time", "ok"


MISSING = {"order_id": "Which order", "category": "Product category", "pieces": "Quantity",
           "due_date": "Due date", "workshop_resolution": "Workshop name"}


def clarify_prompt(parsed: dict, options: list[dict]) -> dict:
    """The single most important question to ask, from Python post-check results."""
    packing = any(o.get("current_stage") == "PACKING" for o in options) and parsed.get("order_id")
    if not parsed.get("order_id") and options:
        who = f"{parsed['customer']} " if parsed.get("customer") else ""
        question = f"Which {who}order do you mean?"
    elif not parsed.get("order_id"):
        question = "Which order is this? No in-progress order matches the details given."
    elif packing:
        question = "This order is already in packing. Should it still go outside?"
    elif parsed.get("date_not_confirmed"):
        question = "What is the confirmed new deadline?"
    elif parsed.get("due_date") is None:
        question = "What is the confirmed due date?"
    elif parsed.get("unresolved_workshops"):
        question = "Which workshop do you mean?"
    elif parsed.get("pieces") is None:
        question = "How many pieces should go out?"
    elif parsed.get("is_question_only"):
        question = "Do you want this order allocated, or only its status?"
    else:
        question = "Can you confirm the order details?"
    missing = [MISSING.get(f, f) for f in parsed.get("missing_fields", [])]
    if parsed.get("date_not_confirmed"):
        missing.append("Confirmed new deadline")
    return {"question": question, "missing": missing, "options": options if not parsed.get("order_id") else []}


# Evidence trace -------------------------------------------------------------

def _calls(record, names, calls=None):
    calls = record.get("tool_outputs", {}).get("call_trace", []) if calls is None else calls
    return [c for c in calls if c["tool"] in names]


def source_label(metadata: dict) -> tuple[str, str]:
    """(actor, label) for the extraction step, from recorded reply metadata."""
    source = metadata.get("extraction_source")
    model = metadata.get("recorded_model") or metadata.get("model") or "model"
    if source == "fixture" or metadata.get("provider") == "synthetic-fixture":
        return "fixture", "Test fixture extraction, not model output"
    if source == "cached":
        return "model", f"Recorded reply from {model}"
    return "model", f"Live reply from {model}"


def trace_steps(response: dict, *, agent_calls: int | None, replayed: bool, confirmed: bool, block_reason: str | None) -> list[dict]:
    """Observable program events for one preview, in execution order.

    agent_calls is the number of traced tool calls made by the agent itself;
    later calls belong to the app's independent replay and inventory.
    Statuses: done, skipped (not needed for this request), blocked, pending.
    """
    parsed, record = response["parsed_request"], response["decision_record"]
    calls = record.get("tool_outputs", {}).get("call_trace", [])
    agent = calls[:agent_calls] if agent_calls is not None else calls
    replay = calls[agent_calls:] if agent_calls is not None else []
    behaviour = parsed["behaviour"]
    allocating = behaviour in {"allocate", "refuse"} and bool(record.get("candidates") or _calls(record, {"candidates"}, agent))
    skipped = "Not needed: the request needs a reply first."
    steps = []

    def add(key, title, actor, status, summary, evidence=None):
        steps.append({"key": key, "title": title, "actor": actor, "status": status, "summary": summary, "evidence": evidence})

    actor, label = source_label(parsed.get("llm_metadata") or {})
    raw = parsed.get("raw_llm_json") or {}
    facts = [f"{k.replace('_', ' ')} {raw[k]}" for k in ("order_id", "pieces", "category", "due_date_text", "preference") if raw.get(k)]
    add("extract", "Request extracted", actor, "done",
        label + (". Found " + ", ".join(facts) + "." if facts else ". No order facts stated."),
        {"structured_extraction": raw, "reply_metadata": parsed.get("llm_metadata")})

    checks = parsed.get("post_checks", [])
    changed = [c for c in checks if c.get("before") != c.get("after")]
    outcome = changed[-1]["after"] if changed else {"behaviour": behaviour, "reason": parsed.get("reason")}
    add("validate", "Request validated", "python", "done",
        f"{len(checks)} rule checks. Request type: {outcome['behaviour']} ({outcome['reason']}).", checks)

    lookups = _calls(record, {"order_options"}, agent)
    options = record.get("tool_outputs", {}).get("order_options", [])
    if options:
        summary = ", ".join(f"{o['order_id']} {o['customer']} {o['product']} {o['pieces']} pcs" for o in options[:3])
        summary += f" and {len(options) - 3} more" if len(options) > 3 else ""
    else:
        summary = "No matching order in orders.csv."
    add("order", "Order verified", "python", "done" if lookups else "skipped", summary, [c.get("output") for c in lookups])

    eligibility = _calls(record, {"check_eligibility"}, agent)
    if allocating and eligibility:
        latest = eligibility[-1]["output"]
        add("eligibility", "Eligibility checked", "python", "done",
            f"{sum(r['eligible'] for r in latest)} of {len(latest)} workshops can make, may take and fit this batch.", latest)
        excluded = record.get("constraints_applied", {}).get("exclude") or []
        add("candidates", f"{len(record.get('candidates', []))} candidates remain", "python", "done",
            "After request exclusions: " + (", ".join(excluded) if excluded else "none") + ".",
            [{"workshop_id": r["workshop_id"], "name": r["name"]} for r in record.get("candidates", [])])
        etas = _calls(record, {"estimate_eta"}, agent)
        add("eta", "Return dates calculated", "python", "done" if etas else "skipped",
            "Queue + pieces ÷ capacity + transport, for every candidate.", [c.get("output") for c in etas])
        costs = _calls(record, {"estimate_cost"}, agent)
        add("cost", "Costs calculated", "python", "done" if costs else "skipped",
            "Pieces × price per piece, for every candidate.", [c.get("output") for c in costs])
        config = effective_config(record["objective_name"])
        weights = ", ".join(f"{TERM_LABELS[t].lower()} {getattr(config, 'w_' + t):g}" for t in TERMS if getattr(config, "w_" + t))
        add("score", "Objective scores calculated", "python", "done",
            f"{objective_label(record['objective_name'])}: {weights or 'no weights'}.",
            [{"workshop_id": r["workshop_id"], "score": r["score"], "score_terms": r["score_terms"]} for r in record.get("candidates", [])])
        chosen = chosen_row(record)
        add("select", "Winner selected", "python", "done",
            (f"{chosen['name']}. {record['reason_chosen'].split(':', 1)[0]}." if chosen else
             "No whole-batch candidate remains after exclusions. Escalate."),
            {"chosen_workshop": record.get("chosen_workshop"), "reason": record.get("reason_chosen"),
             "constraints": record.get("constraints_applied"), "awkward_case": record.get("awkward_case")})
    else:
        for key, title in (("eligibility", "Eligibility checked"), ("candidates", "Candidates"), ("eta", "Return dates calculated"),
                           ("cost", "Costs calculated"), ("score", "Objective scores calculated"), ("select", "Winner selected")):
            add(key, title, "python", "skipped", skipped)

    probes = _calls(record, {"overload_probe"}, agent)
    probe = record.get("tool_outputs", {}).get("overload")
    if probes and probe:
        add("capacity", "Queue impact projected", "python", "done",
            f"Queue at {probe['workshop_id']} would go from {probe['queue_before']:.1f} to {probe['queue_after']:.1f} days.",
            [c.get("output") for c in probes])
    split = record.get("tool_outputs", {}).get("split")
    if split is not None:
        if split.get("available"):
            parts = " and ".join(f"{part['pieces']} at {part['name']}" for part in split["parts"])
            summary = f"Fastest legal split: {parts}, back {short_date(split['eta_date'])}. Preview only."
        else:
            summary = "No legal two-workshop split: " + split.get("reason", "") + "."
        add("split", "Split evaluated", "python", "done", summary, split)
    if replayed:
        add("replay", "Decision reproduced", "python", "done",
            "An independent replay on a fresh copy of the session state chose the same workshop with the same scores.",
            [c.get("output") for c in replay if c["tool"] in {"candidates", "overload_probe"}])
    audit = response.get("faithfulness") or {}
    numbers = audit.get("numbers_in_text", [])
    add("verify", "Numerical explanation verified", "python", "done" if audit.get("passed") else "blocked",
        f"All {len(numbers)} numbers, dates and IDs in the explanation match tool outputs." if audit.get("passed")
        else "Unsupported values: " + ", ".join(audit.get("unmatched", [])), audit)

    if confirmed:
        add("confirm", "Confirmed by the dispatcher", "human", "done", "Audit record written. Session queue updated.")
    elif block_reason:
        add("confirm", "Human confirmation", "human", "skipped", block_reason)
    else:
        add("confirm", "Human confirmation", "human", "pending", "Waiting for the dispatcher. Nothing is recorded yet.")
    return steps


STAGES = [("understand", "Understand", "Structured extraction"), ("validate", "Validate", "Order and request type"),
          ("evaluate", "Evaluate workshops", "Eligibility and estimates"), ("decide", "Decide", "Scoring and ranking"),
          ("verify", "Verify", "Evidence check")]
STAGE_MEMBERS = {"understand": {"extract"}, "validate": {"validate", "order"},
                 "evaluate": {"eligibility", "candidates", "eta", "cost"}, "decide": {"score", "select", "capacity", "split"},
                 "verify": {"replay", "verify"}}


def stage_status(steps: list[dict]) -> list[tuple[str, str, str, str]]:
    """Collapse trace steps into five processing stages: (key, label, detail, status).

    Human confirmation is deliberately not a processing stage.
    """
    by_key = {step["key"]: step["status"] for step in steps}
    out = []
    for key, label, detail in STAGES:
        statuses = [by_key[m] for m in STAGE_MEMBERS[key] if m in by_key]
        if "blocked" in statuses:
            status = "blocked"
        elif "done" in statuses:
            status = "done"
        else:
            status = "skipped"
        out.append((key, label, detail, status))
    return out
