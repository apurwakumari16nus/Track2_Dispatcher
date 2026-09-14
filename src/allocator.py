"""Deterministic allocation decisions with explicit constraints and audit records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from objectives import ObjectiveConfig, score_candidate, score_terms
from tools import candidates as build_candidates
from tools import ShockMonitor, check_eligibility, overload_probe

if TYPE_CHECKING:
    from simulate import Workshop


@dataclass
class DecisionRecord:
    """JSON-ready via to_dict() or dataclasses.asdict().

    timestamp is the supplied dispatch date at midnight, without an invented
    timezone or wall-clock dependency. Candidates include all eligible shops
    remaining after exclusions, even when the date constraint rules some out.
    score_terms captures the history before this decision updates piece counts.
    """

    order_id: str
    chosen_workshop: str | None
    objective_name: str
    candidates: list[dict[str, Any]]
    ineligible: list[dict[str, Any]]
    reason_chosen: str
    constraints_applied: dict[str, Any]
    awkward_case: str | None
    timestamp: str
    options: list[dict[str, Any]] = field(default_factory=list)
    shock_flags: list[dict[str, Any]] = field(default_factory=list)
    shock_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Allocator:
    """Keep per-run allocation history; create a fresh instance for each run.

    Each successful decide() commits the batch's pieces exactly once; it is not
    a preview operation. Calls that return no choice leave piece counts intact.
    shock_monitor detects unexpected queue growth without knowing the simulator's
    target or closure dates. The allocator never mutates input batches or queues.
    """

    def __init__(self, config: ObjectiveConfig):
        self.config = config
        self.pieces_by_workshop: dict[str, int] = {}
        self.shock_monitor = ShockMonitor()
        self._day0: date | None = None
        self.last_decision: DecisionRecord | None = None

    def __call__(self, batch, workshops, queues) -> str:
        """Simulator adapter; inspect last_decision for the audit record.

        Raises ValueError when no legal allocation exists; use decide() to
        receive that case as a record with escalation options instead.
        """
        record = self.decide(batch, workshops, queues, today=batch["sent_date"])
        if record.chosen_workshop is None:
            raise ValueError(f"No eligible workshop for order {record.order_id}; escalate")
        return record.chosen_workshop

    def decide(
        self,
        batch: Mapping[str, Any],
        workshops: Mapping[str, Workshop],
        queues: Mapping[str, float],
        today: date | str,
        exclude: Sequence[str] | None = None,
        must_make_date: bool = False,
    ) -> DecisionRecord:
        """Score permissible shops, apply constraints, choose, then update history.

        Exclusions use tools.candidates' full name/ID matching. If every shop
        is excluded, return no_eligible. If ALL remaining shops miss the due
        date, return none_makes_date and choose by fewest late days, then speed,
        then score and ID, regardless of weights or must_make_date. This is an
        explicit fallback, not a claim that the date constraint was satisfied.

        Otherwise, must_make_date restricts selection to on-time candidates.
        Normal selection minimises (score, total_days, workshop_id), including
        when all weights are zero. Full candidate rows remain in the record.
        ETA uses tools.py's nominal date formula, including its rounding limits.
        """
        dispatch_date = date.fromisoformat(today) if isinstance(today, str) else today
        if self._day0 is None:
            self._day0 = dispatch_date
        day = (dispatch_date - self._day0).days
        detections = self.shock_monitor.observe(queues, day)
        exclusions = list(exclude or [])
        rows = build_candidates(batch, workshops, queues, dispatch_date, exclusions)
        state = {
            "pieces_by_workshop": self.pieces_by_workshop,
            "shock_monitor": self.shock_monitor,
            "workshops": workshops,
        }
        for cand in rows:
            cand["shock_flagged"] = self.shock_monitor.is_flagged(cand["workshop_id"])
            cand["score_terms"] = score_terms(cand, state)
            cand["score"] = score_candidate(cand, self.config, state)
        rows.sort(key=lambda cand: (cand["score"], cand["total_days"], cand["workshop_id"]))

        record = DecisionRecord(
            order_id=batch["order_id"],
            chosen_workshop=None,
            objective_name=self.config.name,
            candidates=rows,
            ineligible=[row for row in check_eligibility(batch, workshops) if not row["eligible"]],
            reason_chosen="",
            constraints_applied={
                "exclude": exclusions,
                "must_make_date": must_make_date,
                "date_constraint_satisfied": None,
            },
            awkward_case=None,
            timestamp=f"{dispatch_date.isoformat()}T00:00:00",
            shock_flags=[dict(flag) for flag in self.shock_monitor.flags.values()],
            shock_events=[{**flag, "status": "suspect"} for flag in detections]
            + [{**flag, "status": "cleared"} for flag in self.shock_monitor.cleared_flags],
        )
        if not rows:
            record.awkward_case = "no_eligible"
            record.options = [{
                "action": "escalate",
                "description": "No eligible workshop remains after exclusions; request human review.",
            }]
            self.last_decision = record
            return record

        on_time = [cand for cand in rows if cand["days_to_spare"] >= 0]
        if not on_time:
            record.awkward_case = "none_makes_date"
            chosen = min(rows, key=lambda cand: (
                -cand["days_to_spare"], cand["total_days"], cand["score"], cand["workshop_id"]
            ))
            record.options = [
                {
                    "action": "accept_lateness",
                    "workshop_id": chosen["workshop_id"],
                    "days_late": -chosen["days_to_spare"],
                },
                {
                    "action": "consider_split",
                    "description": "Request a split feasibility check; splitting is not implemented.",
                },
            ]
            reason_prefix = "Least-late fallback"
        else:
            chosen = (on_time if must_make_date else rows)[0]
            reason_prefix = "Lowest score among permitted candidates"

        record.chosen_workshop = chosen["workshop_id"]
        record.reason_chosen = (
            f"{reason_prefix}: score {chosen['score']:.6f}; "
            f"total days {chosen['total_days']:.2f}; "
            f"days to spare {chosen['days_to_spare']}; "
            f"defect probability {chosen['expected_defect_rate']:.4f}; "
            f"cost per piece {chosen['cost_per_piece']:.4f}."
        )
        record.constraints_applied["date_constraint_satisfied"] = chosen["days_to_spare"] >= 0
        workshop_id = chosen["workshop_id"]
        projected = overload_probe(batch, workshop_id, workshops, queues)
        self.shock_monitor.record_allocation(workshop_id, projected["queue_after"], day)
        self.pieces_by_workshop[workshop_id] = (
            self.pieces_by_workshop.get(workshop_id, 0) + batch["pieces"]
        )
        self.last_decision = record
        return record
