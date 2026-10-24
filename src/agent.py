"""Dispatch orchestration with deterministic explanations and explicit previews.

handle() is a one-request convenience API. Reuse Agent(config) for a run so
fairness history and the shock monitor persist. Only ordinary allocation choices
update that session's history; refusal alternatives and awkward cases are
previews. Neither interface dispatches externally, mutates queues, writes logs,
or calls an LLM outside intake. Call records.append(response) to persist it.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import json

from allocator import Allocator, DecisionRecord
import faithfulness
import intake
from objectives import ObjectiveConfig, PRESETS
import tools
import tracing


@dataclass
class AgentResponse:
    decision_record: dict
    parsed_request: intake.ParsedRequest
    explanation_text: str
    already_late: bool
    awkward_case: str | None
    faithfulness: dict
    allocation_committed: bool = False

    def to_dict(self) -> dict:
        return {"decision_record": deepcopy(self.decision_record),
                "parsed_request": self.parsed_request.to_dict(),
                "explanation_text": self.explanation_text,
                "already_late": self.already_late, "awkward_case": self.awkward_case,
                "faithfulness": deepcopy(self.faithfulness),
                "allocation_committed": self.allocation_committed}

    @property
    def decision_record_json(self) -> str:
        return json.dumps(self.decision_record, allow_nan=False)


def _objective(parsed, config):
    if parsed.preference == "fastest":
        return PRESETS["lateness"]
    if parsed.preference == "lowest_defect":
        return PRESETS["defect"]
    if parsed.preference == "cheapest":
        return ObjectiveConfig(w_cost=1, name="cheapest_on_time")
    return config


def _clarification(parsed, options):
    questions = []
    if not parsed.order_id:
        if options:
            choices = "; ".join(f"{r['order_id']} ({r['customer']}, {r['product']}, {r['pieces']} pieces)" for r in options)
            questions.append(f"Which order do you mean: {choices}?")
        else:
            questions.append("No in-progress order matches the supplied references. Please provide the order ID or the customer and product for the intended order.")
    if any(r["current_stage"] == "PACKING" for r in options) and parsed.order_id:
        questions.append("The order is already in PACKING. Should it remain there, or do you confirm sending it outside?")
    if parsed.date_not_confirmed:
        questions.append("What is the confirmed new deadline? The old deadline will not be substituted.")
    elif parsed.due_date is None:
        questions.append("What is the confirmed due date, including the year?")
    if parsed.unresolved_workshops:
        # Do not echo unverified free text (including potentially invented numbers).
        questions.append("Which workshop IDs do the unrecognized workshop references mean? Please use the workshop directory.")
    if parsed.pieces is None and parsed.order_id:
        questions.append("How many pieces should be sent?")
    if parsed.category is None and parsed.order_id:
        questions.append("Is the batch TOPS or ACCESSORIES?")
    if parsed.is_question_only and not questions:
        questions.append("Do you want an order-status answer, or are you asking to allocate this order?")
    if not questions:
        questions.append("Please confirm the order details and whether outside allocation is intended.")
    return " ".join(questions) + " No allocation has been made."


def _decline(parsed):
    if parsed.reason == "order not found":
        return ("The supplied order table does not contain the named order. I need a corrected order ID "
                "or an authoritative order record before proceeding. No allocation has been made.")
    needed = {
        "allocation_history": "historical dispatch records linking the requested customer/order and period to workshop assignments",
        "customer_quote": "the customer sales quotation or pricing record for the order",
        "worker_names": "a worker roster and worker-to-order assignment records",
    }.get(parsed.question_topic, "the source records containing the requested information")
    return f"I need {needed}. The supplied order and workshop tables do not hold that information. No allocation has been made."


def _choice_text(record, alternative=False):
    if record.chosen_workshop is None:
        return "No eligible whole-batch workshop remains after exclusions. Escalate for human review."
    cand = next(c for c in record.candidates if c["workshop_id"] == record.chosen_workshop)
    label = "Best alternative under the selected objective" if alternative else "Recommended workshop"
    reason = "Least-late whole-batch fallback" if record.awkward_case == "none_makes_date" else "Lowest score among permitted candidates"
    return (f"{label}: {cand['name']} ({cand['workshop_id']}). {reason}; score {cand['score']}. "
            f"Estimated completion {cand['eta_date']}, due {cand['due_date']}; "
            f"total {cand['total_days']} days, including queue {cand['queue_days']} days, "
            f"processing {cand['processing_days']} days and lead {cand['lead_days']} days. "
            f"Days to spare: {cand['days_to_spare']}. Estimated total cost: {cand['total_cost']}; "
            f"cost per piece: {cand['cost_per_piece']}. Expected batch defect probability: {cand['expected_defect_rate']}.")


def _split_text(split):
    if not split["available"]:
        return "Split preview: no legal two-workshop split is available under the current quantities, restrictions and exclusions."
    parts = "; ".join(f"{p['name']} ({p['workshop_id']}): {p['pieces']} pieces, ETA {p['eta_date']}, lead {p['lead_days']} days" for p in split["parts"])
    text = (f"Split preview: {parts}. Both parts complete by {split['eta_date']}; "
            f"combined elapsed time {split['total_days']} days; combined cost {split['total_cost']}; "
            f"days to spare {split['days_to_spare']}. Each part includes its own lead time; the parts run in parallel. ")
    if split["single"] is None:
        text += "A legal split exists although no whole-batch option is available. "
    elif split["faster"]:
        text += f"This is faster than the whole-batch recommendation by {split['days_saved']} estimated days. "
        if not split["earlier_eta"]:
            text += "The rounded calendar ETA is unchanged. "
    else:
        text += "This is not faster than the whole-batch recommendation. "
    if split["single"] and not split["faster_than_fastest_single"]:
        text += "It also does not beat the fastest eligible whole-batch option. "
    return text + "This is an estimate only; no split has been committed."


class Agent:
    """Session-owned history; do not share one instance between unrelated runs."""

    def __init__(self, config: ObjectiveConfig):
        self.config = config
        self.allocator = Allocator(config)

    def handle(self, message, today: date, orders_df, workshops, queues) -> AgentResponse:
        parsed = intake.parse_request(message, today, orders_df, workshops)
        effective = _objective(parsed, self.config)
        exclude = list(parsed.excluded_workshops)
        must_make_date = parsed.must_make_date or parsed.preference == "cheapest"
        with tracing.span("order_lookup"):
            lookups = tools.order_options(orders_df, parsed.candidate_order_ids or ([parsed.order_id] if parsed.order_id else []))
        if parsed.behaviour not in {"allocate", "refuse"}:
            tracing.skipped("allocation", f"behaviour is {parsed.behaviour}")
        record = DecisionRecord(
            order_id=parsed.order_id or "", chosen_workshop=None, objective_name=effective.name,
            candidates=[], ineligible=[], reason_chosen="No allocation decision requested",
            constraints_applied={}, awkward_case=None, timestamp=f"{today.isoformat()}T00:00:00",
        )
        evidence = {"order_options": lookups}
        preview = None
        if parsed.behaviour == "clarify":
            text = _clarification(parsed, lookups)
        elif parsed.behaviour == "decline":
            text = _decline(parsed)
        elif parsed.behaviour in {"allocate", "refuse"}:
            prefix = ""
            if parsed.behaviour == "refuse":
                if parsed.category is None or parsed.pieces is None:
                    raise ValueError("Refusal lacks the fields needed to verify workshop eligibility")
                eligibility = tools.check_eligibility({"category": parsed.category, "pieces": parsed.pieces}, workshops)
                rejected = next((r for r in eligibility if r["workshop_id"] == parsed.suggested_workshop and not r["eligible"]), None)
                if rejected is None:
                    raise ValueError("Refusal must be supported by the eligibility tool")
                evidence["eligibility"] = eligibility
                prefix = f"{rejected['name']} ({rejected['workshop_id']}) cannot take this batch: {rejected['reason']}. "
                exclude = list(dict.fromkeys([*exclude, rejected["workshop_id"]]))
            complete = all(getattr(parsed, k) is not None for k in ("order_id", "category", "pieces", "due_date")) and not parsed.unresolved_workshops
            if not complete:
                text = prefix + "An alternative needs confirmed order details first. " + _clarification(parsed, lookups)
            else:
                batch = {"order_id": parsed.order_id, "category": parsed.category, "pieces": parsed.pieces,
                         "sent_date": today, "due_date": parsed.due_date}
                preview = deepcopy(self.allocator)
                preview.config = effective
                with tracing.span("allocation"):
                    record = preview.decide(batch, workshops, queues, today, exclude=exclude, must_make_date=must_make_date)
                with tracing.span("eligibility"):
                    evidence["eligibility"] = tools.check_eligibility(batch, workshops)
                text = prefix + _choice_text(record, alternative=parsed.behaviour == "refuse")
                with tracing.span("evidence"):
                    if record.chosen_workshop:
                        evidence["queue"] = tools.queue_check(record.chosen_workshop, workshops, queues)
                        evidence["overload"] = tools.overload_probe(batch, record.chosen_workshop, workshops, queues)
                    split = (tools.estimate_split(batch, workshops, queues, today, exclude, record.chosen_workshop)
                             if parsed.split_allowed else None)
                if parsed.split_allowed:
                    evidence["split"] = split
                    text += " " + _split_text(split)
                    for option in record.options:
                        if option["action"] == "consider_split":
                            option["description"] = "See tool_outputs.split for the evaluated split preview."
                if parsed.behaviour == "refuse":
                    text += " This alternative is an offer only; no allocation has been made."
                    if any(r["current_stage"] == "PACKING" for r in lookups):
                        text += " The order is already in PACKING; confirm outside dispatch before accepting an alternative."
        else:
            raise ValueError(f"Unknown intake behaviour: {parsed.behaviour}")

        record.tool_outputs = evidence
        record.constraints_applied.update({
            "exclude": exclude, "must_make_date": must_make_date,
            "preference": parsed.preference, "split_allowed": parsed.split_allowed,
            "reported_by": parsed.sender, "statements": deepcopy(parsed.constraints),
            "objective_override": effective.name if parsed.preference else None,
        })
        warnings = []
        if parsed.already_late:
            warnings.append("ALREADY LATE: the requested deadline is today or in the past.")
        if record.awkward_case == "none_makes_date":
            warnings.append("AWKWARD CASE: none_makes_date. No eligible whole-batch option meets the deadline. Accept lateness explicitly or review splitting before proceeding.")
        elif record.awkward_case == "no_eligible":
            warnings.append("AWKWARD CASE: no_eligible. No whole-batch allocation has been made.")
        text = "\n".join([*warnings, text])
        serialized = record.to_dict()
        with tracing.span("explanation_check"):
            audit = faithfulness.check(text, serialized)
        if not audit["passed"]:
            raise ValueError(f"Explanation contains unsupported numbers: {audit['unmatched']}")
        committed = (preview is not None and parsed.behaviour == "allocate"
                     and record.chosen_workshop is not None and not record.awkward_case and not parsed.already_late)
        if committed:
            # Only commit once the full response passes the evidence check.
            preview.config = self.config
            self.allocator = preview
        return AgentResponse(serialized, parsed, text, parsed.already_late, record.awkward_case, audit, committed)


def handle(message, today, orders_df, workshops, queues, config) -> AgentResponse:
    """Handle one request with fresh history. For a run, reuse Agent(config)."""
    return Agent(config).handle(message, today, orders_df, workshops, queues)
