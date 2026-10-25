"""Dispatch session logic shared by the Streamlit pages. No rendering here.

Dispatch is a preview. Only confirm_preview writes an audit row, and only after
validation; the caller adopts the prospective allocator/queues afterwards.
This module never contacts a workshop. Queue figures are nominal local-session
projections from the workshops.csv snapshot of 1 April 2026.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from agent import Agent, AgentResponse
from allocator import Allocator
import faithfulness
import intake
from objectives import ObjectiveConfig, PRESETS, score_candidate, score_terms
import records
from simulate import load_workshops
import tools
import tracing

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 4, 1)
REHEARSAL_LOG = ROOT / "records" / "rehearsal_decisions.jsonl"


@dataclass
class Preview:
    response: AgentResponse
    signature: str
    token: str
    accepted_allocator: Allocator | None
    accepted_queues: dict
    today: date
    block_reason: str | None
    agent_calls: int | None = None
    source: str = "live"
    trace_id: str | None = None


def load_inputs():
    orders = pd.read_csv(ROOT / "data/orders.csv")
    workshops = load_workshops()
    messages = [line for line in (ROOT / "data/dispatch_requests.txt").read_text(encoding="utf-8").splitlines() if line.startswith("R")]
    return orders, workshops, messages


def projected_queues(queues, anchor, today):
    if today < anchor:
        raise ValueError("Choose a date on or after the current queue snapshot date.")
    elapsed = (today - anchor).days
    return {wid: max(0.0, value - elapsed) for wid, value in queues.items()}


def signature(message, today, config, orders, workshops, queues, revision, source="live", answers=None):
    profiles = {wid: {**asdict(w), "makes": sorted(w.makes)} for wid, w in workshops.items()}
    data = [message, today.isoformat(), asdict(config), orders.to_csv(index=False), profiles, queues, revision, source]
    if answers:   # Only present when the dispatcher answered a clarification, so earlier signatures are unchanged.
        data.append({k: (v.get("value") if isinstance(v, dict) else v) for k, v in answers.items()})
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def make_preview(message, today, config, orders, workshops, queues, allocator, revision=0, source="live", answers=None):
    """Prepare all reviewable evidence and prospective state, without persistence.

    The caller chooses where the raw extraction comes from (intake.extraction_source);
    source only labels the preview and is part of its signature.
    """
    with tracing.span("prepare"):
        current_signature = signature(message, today, config, orders, workshops, queues, revision, source, answers)
        worker = Agent(config)
        worker.allocator = deepcopy(allocator)
        worker.allocator.config = config
    accepted, next_queues = None, dict(queues)
    with tools.trace_calls() as calls:
        with intake.dispatcher_answers(answers):
            response = worker.handle(message, today, orders, workshops, queues)
        agent_calls = len(calls)
        with tracing.span("verification"):
            parsed, record = response.parsed_request, response.decision_record
            block = None
            if parsed.behaviour not in {"allocate", "refuse"}:
                block = "This request needs a reply, not an allocation."
            elif record["chosen_workshop"] is None:
                block = "There is no whole-batch allocation to confirm."
            if any(row.get("current_stage") == "PACKING" for row in record.get("tool_outputs", {}).get("order_options", [])):
                block = "Resolve the packing-stage clarification before allocating."
            complete = all(getattr(parsed, k) is not None for k in ("order_id", "category", "pieces", "due_date"))
            if complete and parsed.behaviour in {"allocate", "refuse"}:
                effective = (ObjectiveConfig(w_cost=1, name="cheapest_on_time") if record["objective_name"] == "cheapest_on_time"
                             else PRESETS[record["objective_name"]])
                accepted = deepcopy(allocator)
                accepted.config = effective
                batch = {"order_id": parsed.order_id, "pieces": parsed.pieces, "category": parsed.category,
                         "due_date": parsed.due_date, "sent_date": today}
                constraints = record["constraints_applied"]
                verified = accepted.decide(batch, workshops, queues, today,
                                          exclude=constraints["exclude"], must_make_date=constraints["must_make_date"])
                if verified.chosen_workshop != record["chosen_workshop"] or verified.candidates != record["candidates"]:
                    raise ValueError("The allocation changed during preparation; dispatch again.")
                permitted = {row["workshop_id"]: row for row in record["candidates"]}
                all_rows = tools.candidates(batch, workshops, queues, today)
                state = {"pieces_by_workshop": allocator.pieces_by_workshop, "shock_monitor": accepted.shock_monitor,
                         "workshops": workshops}
                any_on_time = any(row["days_to_spare"] >= 0 for row in record["candidates"])
                for row in all_rows:
                    wid = row["workshop_id"]
                    row.update(score_terms=score_terms(row, state), score=score_candidate(row, effective, state))
                    row["exclusion_reason"] = ("Excluded by request" if wid not in permitted else
                        "Misses required due date" if constraints["must_make_date"] and any_on_time and row["days_to_spare"] < 0 else "")
                record["tool_outputs"]["ui_candidate_inventory"] = sorted(all_rows, key=lambda row: (row["score"], row["total_days"], row["workshop_id"]))
                if verified.chosen_workshop:
                    probe = tools.overload_probe(batch, verified.chosen_workshop, workshops, queues)
                    next_queues[verified.chosen_workshop] = probe["queue_after"]
                accepted.config = config
            else:
                block = block or "Confirm all order details before allocating."
    response.decision_record["tool_outputs"]["call_trace"] = deepcopy(calls)
    with tracing.span("explanation_check"):
        response.faithfulness = faithfulness.check(response.explanation_text, response.decision_record)
    if not response.faithfulness["passed"]:
        block = "The explanation failed its numerical evidence check."
    # Preparing a copy must not present the request as confirmed in the UI/log.
    response.allocation_committed = False
    active = tracing.current()
    tracing.note(tool_calls=agent_calls, behaviour=response.parsed_request.behaviour,
                 chosen_workshop=response.decision_record.get("chosen_workshop"), blocked=bool(block))
    return Preview(response, current_signature, uuid4().hex, accepted, next_queues, today, block, agent_calls, source,
                   active.trace_id if active else None)


@dataclass(frozen=True)
class ConfirmState:
    """Whether a preview may be confirmed now. One rule for the button and the write."""

    state: str  # "confirmed", "stale", "blocked" or "ready"
    reason: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "ready"


def confirm_state(preview, current_signature, saved) -> ConfirmState:
    if preview.token in saved:
        return ConfirmState("confirmed", "Decision confirmed. Audit record created. Queue updated.")
    if preview.signature != current_signature:
        return ConfirmState("stale", "Inputs changed after this preview. Run the decision again.")
    if preview.block_reason or preview.accepted_allocator is None:
        return ConfirmState("blocked", preview.block_reason or "No allocation is available.")
    if not (preview.response.faithfulness or {}).get("passed"):
        return ConfirmState("blocked", "The explanation failed its numerical evidence check.")
    return ConfirmState("ready")


def confirm_preview(preview, current_signature, saved, *, append=None, guided_demo=False, batch_review=False, channel="desk", by=None):
    """Validate first; append once; caller adopts new state only after success.

    guided_demo marks a confirmation made inside the guided demo; it is stored in
    the record and the caller writes it to the rehearsal log (see audit_path)."""
    status = confirm_state(preview, current_signature, saved)
    if status.state == "confirmed":
        return saved[preview.token]
    if not status.ready:
        raise ValueError(status.reason)
    response = deepcopy(preview.response)
    response.allocation_committed = True
    response.explanation_text = "CONFIRMED ALLOCATION. The dispatcher accepted this recommendation.\n\nOriginal preview:\n" + response.explanation_text
    response.decision_record["constraints_applied"]["confirmation"] = {
        "confirmed": True, "preview_token": preview.token,
        "accepted_lateness": bool(response.already_late or response.awkward_case == "none_makes_date"),
        "accepted_alternative": response.parsed_request.behaviour == "refuse",
        "extraction_source": preview.source,
        "trace_id": preview.trace_id,
        "guided_demo": bool(guided_demo),
        "batch_review": bool(batch_review),
        "changes": deepcopy(response.parsed_request.answers_applied),
        "channel": channel, "confirmed_by": by,
    }
    row = (append or records.append)(response)
    saved[preview.token] = row
    return row


def split_defect_rate(split, workshops) -> float:
    """Expected defect rate of a split: each workshop's rate weighted by its pieces."""
    total = sum(p["pieces"] for p in split["parts"])
    return sum(workshops[p["workshop_id"]].defect_rate * p["pieces"] for p in split["parts"]) / total


def confirm_split(preview, current_signature, saved, split, workshops, queues, allocator, *, append=None, guided_demo=False,
                  channel="desk", by=None):
    """The dispatcher chose the two-workshop split instead of the single workshop.

    Same rules as confirm_preview (validated first, written once). Returns
    (row, next_queues, next_allocator): each part adds its own pieces to its own
    workshop's queue, using the split estimate's queue_after from the same tools."""
    status = confirm_state(preview, current_signature, saved)
    if status.state == "confirmed":
        return saved[preview.token], None, None
    if not status.ready:
        raise ValueError(status.reason)
    if not split.get("available"):
        raise ValueError("No legal two-workshop split is available for this batch.")
    response = deepcopy(preview.response)
    response.allocation_committed = True
    # Names only: the part sizes, dates and costs live in split_allocation, so the logged text adds no unchecked numbers.
    names = " and ".join(p["name"] for p in split["parts"])
    response.explanation_text = (f"CONFIRMED SPLIT. The dispatcher chose a two-workshop split between {names}; "
                                 "the parts are in split_allocation.\n\n"
                                 "Original single-workshop preview:\n" + response.explanation_text)
    parts = [{k: p.get(k) for k in ("workshop_id", "name", "pieces", "eta_date", "total_days", "days_to_spare", "total_cost")}
             for p in split["parts"]]
    response.decision_record["split_allocation"] = {"parts": parts, "eta_date": split["eta_date"], "total_cost": split["total_cost"],
                                                    "days_to_spare": split["days_to_spare"],
                                                    "expected_defect_rate": split_defect_rate(split, workshops),
                                                    "instead_of": response.decision_record.get("chosen_workshop")}
    response.decision_record["constraints_applied"]["confirmation"] = {
        "confirmed": True, "preview_token": preview.token, "split": True,
        "accepted_lateness": split["days_to_spare"] < 0, "accepted_alternative": False,
        "extraction_source": preview.source, "trace_id": preview.trace_id, "guided_demo": bool(guided_demo),
        "batch_review": False, "changes": deepcopy(response.parsed_request.answers_applied), "channel": channel, "confirmed_by": by,
    }
    row = (append or records.append)(response)
    saved[preview.token] = row
    next_queues = dict(queues)
    next_allocator = deepcopy(allocator)
    for part in split["parts"]:
        next_queues[part["workshop_id"]] = part["queue"]["queue_after"]
        next_allocator.pieces_by_workshop[part["workshop_id"]] = next_allocator.pieces_by_workshop.get(part["workshop_id"], 0) + part["pieces"]
    return row, next_queues, next_allocator


def escalate(preview, to: str, note: str, *, append=None, guided_demo=False, channel="desk", by=None) -> dict:
    """Record that the dispatcher raised this request with a planner or the customer instead of deciding.
    Nothing is allocated, no queue changes and nothing is sent; the record says who it went to and why."""
    response = deepcopy(preview.response)
    response.allocation_committed = False
    response.decision_record["constraints_applied"]["confirmation"] = {
        "confirmed": False, "escalated": True, "escalated_to": to, "note": note.strip(), "preview_token": preview.token,
        "extraction_source": preview.source, "trace_id": preview.trace_id, "guided_demo": bool(guided_demo),
        "changes": deepcopy(response.parsed_request.answers_applied), "channel": channel, "escalated_by": by,
    }
    return (append or records.append)(response)


def queues_from_log(workshops, path=None) -> tuple[dict, Allocator, int]:
    """Queues and allocator history after every confirmed decision in one audit log, replayed in order on the
    1 April snapshot with the same queue tool the engine uses. This is how a second channel (the Telegram bot)
    and the desk see one shared workload. Escalations allocate nothing and are skipped."""
    queues = {wid: w.queue0 for wid, w in workshops.items()}
    allocator = Allocator(PRESETS["lateness"])
    confirmed = 0
    for row in records.load(path):
        record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
        confirmation = record.get("constraints_applied", {}).get("confirmation", {})
        if not confirmation.get("confirmed"):
            continue
        parts = (record.get("split_allocation") or {}).get("parts") or (
            [{"workshop_id": record.get("chosen_workshop"), "pieces": parsed.get("pieces")}] if record.get("chosen_workshop") else [])
        for part in parts:
            if part["workshop_id"] in workshops and part.get("pieces"):
                batch = {"pieces": int(part["pieces"]), "category": parsed.get("category")}
                queues[part["workshop_id"]] = tools.overload_probe(batch, part["workshop_id"], workshops, queues)["queue_after"]
                allocator.pieces_by_workshop[part["workshop_id"]] = allocator.pieces_by_workshop.get(part["workshop_id"], 0) + int(part["pieces"])
        confirmed += 1
    return queues, allocator, confirmed


def audit_path(source: str, demo: bool = False) -> Path | None:
    """Rehearsal and guided-demo confirmations stay out of the live audit log.

    A demo confirmation is a demonstration, not an operational decision, even when
    the live model read the request; the record still says which source it used."""
    return REHEARSAL_LOG if source != "live" or demo else None


def audit_log_name(source: str, demo: bool = False) -> str:
    return "live" if audit_path(source, demo) is None else "rehearsal"


def filtered_records(rows, workshop=None, sender=None):
    """Reverse append order, preserving the full persisted audit record."""
    return [row for row in reversed(rows)
            if (not workshop or row.get("decision_record", {}).get("chosen_workshop") == workshop)
            and (not sender or row.get("sender") == sender)]


SESSION_DEFAULTS = {"desk_message": "", "desk_preset": "lateness", "desk_page": "Dispatch", "desk_source": "live",
                    "presentation_mode": False}


def init_session(state, workshops) -> None:
    if "desk_allocator" not in state:
        state.update(desk_allocator=Allocator(PRESETS["lateness"]), desk_queues={wid: w.queue0 for wid, w in workshops.items()},
                     desk_queue_date=TODAY, desk_revision=0, desk_saved={}, desk_today=TODAY, desk_splits={}, desk_outcomes={})
    for key, value in SESSION_DEFAULTS.items():
        state.setdefault(key, value)


def reset_session(state, workshops, *, clear_rehearsal_log=True) -> None:
    """Fresh allocator, queues and previews. The live audit log is never touched."""
    for key in [k for k in state.keys() if k.startswith(("desk_", "inbox_", "net_", "audit_"))
                and k not in {"desk_page", "desk_source", "presentation_mode"}]:
        del state[key]
    if clear_rehearsal_log:
        REHEARSAL_LOG.unlink(missing_ok=True)
    init_session(state, workshops)
