"""Pure allocation functions plus a stateful queue-anomaly monitor.

Estimates describe normal processing without a sampled defect or hidden closure.
Inputs follow the simulator's schema; missing keys raise KeyError. Dates in tool
results are ISO strings so results can be logged directly as JSON.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulate import Workshop


def _as_date(value: date | str) -> date:
    """Accept a simulator date or its ISO representation."""
    return date.fromisoformat(value) if isinstance(value, str) else value


def check_eligibility(
    batch: Mapping[str, Any], workshops: Mapping[str, Workshop]
) -> list[dict[str, Any]]:
    """Explain eligibility in the same rule order as eligible_workshops()."""
    results = []
    for workshop in workshops.values():
        if workshop.status != "ACTIVE":
            reason = "suspended"
        elif batch["category"] not in workshop.makes:
            reason = f"cannot make {batch['category']}"
        elif workshop.max_batch is not None and batch["pieces"] > workshop.max_batch:
            reason = f"batch of {batch['pieces']} exceeds {workshop.max_batch}-piece cap"
        else:
            reason = "ok"
        results.append({
            "workshop_id": workshop.workshop_id,
            "name": workshop.name,
            "eligible": reason == "ok",
            "reason": reason,
        })
    return results


def queue_check(
    workshop_id: str,
    workshops: Mapping[str, Workshop],
    queues: Mapping[str, float],
) -> dict[str, Any]:
    """Read the current queue; never fall back to the initial queue0 value."""
    workshop = workshops[workshop_id]
    return {
        "workshop_id": workshop_id,
        "queue_days": queues[workshop_id],
        "capacity_per_day": workshop.capacity,
        "lead_days": workshop.lead_days,
    }


def estimate_eta(
    batch: Mapping[str, Any],
    workshop_id: str,
    workshops: Mapping[str, Workshop],
    queues: Mapping[str, float],
    today: date | str,
) -> dict[str, Any]:
    """Estimate nominal completion using today + round(queue + work + lead).

    Defect probability is reported without inflating processing time. This tool
    does not enforce eligibility. See docs/tool_spec.md for the simulator's
    absolute-day rounding caveat at half-day ties.
    """
    workshop = workshops[workshop_id]
    queue_days = queues[workshop_id]
    processing_days = batch["pieces"] / workshop.capacity
    total_days = queue_days + processing_days + workshop.lead_days
    eta_date = _as_date(today) + timedelta(days=round(total_days))
    due_date = _as_date(batch["due_date"])
    return {
        "workshop_id": workshop_id,
        "queue_days": queue_days,
        "processing_days": processing_days,
        "lead_days": workshop.lead_days,
        "total_days": total_days,
        "eta_date": eta_date.isoformat(),
        "due_date": due_date.isoformat(),
        "days_to_spare": (due_date - eta_date).days,
        "expected_defect_rate": workshop.defect_rate,
    }


def estimate_cost(
    batch: Mapping[str, Any], workshop_id: str, workshops: Mapping[str, Workshop]
) -> dict[str, Any]:
    """Use the simulator's per-piece charge without adding rework fees."""
    workshop = workshops[workshop_id]
    return {
        "workshop_id": workshop_id,
        "cost_per_piece": workshop.cost,
        "total_cost": batch["pieces"] * workshop.cost,
    }


def overload_probe(
    batch: Mapping[str, Any],
    workshop_id: str,
    workshops: Mapping[str, Workshop],
    queues: Mapping[str, float],
) -> dict[str, Any]:
    """Project the queue immediately after dispatch, without mutating it.

    Only processing occupies the production queue. Transport lead time does not
    delay the next batch's processing. Defect rework and closures are excluded.
    """
    workshop = workshops[workshop_id]
    queue_before = queues[workshop_id]
    processing_days = batch["pieces"] / workshop.capacity
    return {
        "workshop_id": workshop_id,
        "queue_before": queue_before,
        "queue_after": queue_before + processing_days,
        "delay_added_to_next_batch_days": processing_days,
    }


def candidates(
    batch: Mapping[str, Any],
    workshops: Mapping[str, Workshop],
    queues: Mapping[str, float],
    today: date | str,
    exclude: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank eligible, non-excluded workshops by nominal total days.

    Exclusions match full names or IDs, ignoring case and surrounding whitespace.
    Equal totals retain workshop input order. No remaining candidates returns [].
    """
    excluded = {value.strip().casefold() for value in (exclude or ())}
    results = []
    for eligibility in check_eligibility(batch, workshops):
        if not eligibility["eligible"]:
            continue
        workshop_id = eligibility["workshop_id"]
        if (
            workshop_id.strip().casefold() in excluded
            or eligibility["name"].strip().casefold() in excluded
        ):
            continue
        results.append({
            **eligibility,
            **estimate_eta(batch, workshop_id, workshops, queues, today),
            **estimate_cost(batch, workshop_id, workshops),
        })
    return sorted(results, key=lambda result: result["total_days"])


class ShockMonitor:
    """Detect unexplained queue growth using only past allocations and queues.

    expected_queue stores nominal queued days immediately after the last
    allocation to each workshop. Each prediction has a day anchor, so observe
    compares against max(0, predicted_queue - elapsed_days). Unvisited shops
    have no prediction and cannot be flagged. observe returns NEW detections;
    flags retains their original evidence until recovery or explicit clear().

    A jump strictly above threshold is suspicious, not proof of a closure:
    defect rework can also increase the queue. Merely observing an anomalous
    queue never rebases the prediction or forgets a flag. When sending more work
    to a suspect, record_allocation preserves its unexplained excess rather
    than treating that excess as expected work. Days must be nondecreasing.
    """

    def __init__(self, threshold: float = 3.0):
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("threshold must be finite and nonnegative")
        self.threshold = float(threshold)
        self.expected_queue: dict[str, float] = {}
        self.flags: dict[str, dict[str, Any]] = {}
        self.cleared_flags: list[dict[str, Any]] = []
        self._expected_on_day: dict[str, int] = {}
        self._last_day: int | None = None
        self._excess: dict[str, float] = {}

    def _check_day(self, day: int) -> None:
        if self._last_day is not None and day < self._last_day:
            raise ValueError("ShockMonitor days must be nondecreasing")

    def observe(self, queues: Mapping[str, float], day: int) -> list[dict[str, Any]]:
        """Flag jumps > threshold; clear flags when the excess is <= threshold.

        Clearing uses the decayed expectation, not an elapsed-time blacklist.
        Missing workshop observations leave their flags untouched. Multiple
        observations on the same day do not consume the expected queue twice.
        """
        self._check_day(day)
        self.cleared_flags = []
        detections = []
        for workshop_id, observed in queues.items():
            if workshop_id not in self.expected_queue:
                continue
            anchor = self._expected_on_day.setdefault(workshop_id, day)
            expected = max(0.0, self.expected_queue[workshop_id] - (day - anchor))
            jump = observed - expected
            self._excess[workshop_id] = max(0.0, jump)
            if jump > self.threshold:
                if not self.is_flagged(workshop_id):
                    evidence = {
                        "workshop_id": workshop_id,
                        "expected": expected,
                        "observed": observed,
                        "jump": jump,
                        "flagged_on_day": day,
                    }
                    self.flags[workshop_id] = evidence
                    detections.append(dict(evidence))
            elif self.is_flagged(workshop_id):
                self.cleared_flags.append({
                    **self.flags[workshop_id],
                    "cleared_on_day": day,
                    "expected_on_clear": expected,
                    "observed_on_clear": observed,
                })
                self.clear(workshop_id)
        self._last_day = day
        return detections

    def record_allocation(self, workshop_id: str, queue_after: float, day: int) -> None:
        """Store overload_probe's queue_after and its allocation day.

        For a suspect, subtract the excess measured by observe on this same day
        so another dispatch cannot erase the unresolved anomaly. Otherwise use
        the observed queue plus nominal processing, as returned by the probe.
        """
        self._check_day(day)
        excess = self._excess.get(workshop_id, 0.0) if self.is_flagged(workshop_id) else 0.0
        self.expected_queue[workshop_id] = max(0.0, queue_after - excess)
        self._expected_on_day[workshop_id] = day
        self._last_day = day

    def is_flagged(self, workshop_id: str) -> bool:
        return workshop_id in self.flags

    def clear(self, workshop_id: str) -> None:
        """Remove a suspect flag without erasing allocation history."""
        self.flags.pop(workshop_id, None)
