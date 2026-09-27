"""Pure allocation functions plus a stateful queue-anomaly monitor.

Estimates describe normal processing without a sampled defect or hidden closure.
Inputs follow the simulator's schema; missing keys raise KeyError. Dates in tool
results are ISO strings so results can be logged directly as JSON.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import date, timedelta
from functools import wraps
from itertools import combinations
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulate import Workshop


_CALL_TRACE: ContextVar[list | None] = ContextVar("tool_call_trace", default=None)


@contextmanager
def trace_calls():
    """Collect ordered raw outputs in this context only; never write to disk.

    ContextVar prevents concurrent Streamlit sessions from sharing evidence.
    Imported aliases still point at decorated functions, so nested tool calls
    and the intake/allocator's direct imports are captured too.
    """
    calls = []
    token = _CALL_TRACE.set(calls)
    try:
        yield calls
    finally:
        _CALL_TRACE.reset(token)


def _traced(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        calls = _CALL_TRACE.get()
        if calls is None:
            return function(*args, **kwargs)
        entry = {"tool": function.__qualname__}
        calls.append(entry)
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            entry["error"] = {"type": type(error).__name__, "message": str(error)}
            raise
        entry["output"] = deepcopy(result)
        return result
    return wrapped


def _as_date(value: date | str) -> date:
    """Accept a simulator date or its ISO representation."""
    return date.fromisoformat(value) if isinstance(value, str) else value


@_traced
def check_eligibility(
    batch: Mapping[str, Any], workshops: Mapping[str, Workshop]
) -> list[dict[str, Any]]:
    """Explain default whole-job eligibility; optional stage dispatch is unsupported."""
    if batch.get("from_stage"):
        raise NotImplementedError(
            "Optional stages mode is not supported by the allocation tools. "
            "Use the default orders.csv/workshops.csv whole-job mode."
        )
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


@_traced
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


@_traced
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


@_traced
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


@_traced
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


@_traced
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


@_traced
def order_options(orders_df, order_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Look up concrete clarification options; return only existing CSV rows."""
    requested = set(order_ids)
    return [{"order_id": str(row.order_id), "customer": str(row.customer),
             "product": str(row.product), "pieces": int(row.pieces),
             "current_stage": str(row.current_stage)}
            for row in orders_df.itertuples(index=False) if row.order_id in requested]


@_traced
def estimate_split(batch, workshops, queues, today, exclude=None, single_workshop_id=None) -> dict[str, Any]:
    """Fastest legal integer two-workshop split, as a preview with no mutations.

    For n pieces, minimise max(qA + x/cA + leadA,
    qB + (n-x)/cB + leadB), with positive integer parts and each shop's cap.
    For each pair the maximum of the increasing/decreasing lines is convex:
    only the integers around their intersection and the bounds need testing.
    Parts run concurrently. Each pays its own lead, but completion is the later
    ETA, NOT the sum of durations/leads. No extra transport charge is invented.
    Existing ETA/cost/queue tools calculate each part with the same input queues.

    Compare with the selected whole-batch shop when supplied, otherwise the
    fastest whole-batch candidate. Also return the fastest-single benchmark.
    A continuous-duration improvement may round to the same calendar ETA.
    This estimates nominal speed only; it does not allocate or model rework,
    hidden closures, consolidation, or a split-specific fixed charge.
    """
    n = batch["pieces"]
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("split pieces must be a positive integer")
    singles = candidates(batch, workshops, queues, today, exclude)
    single = next((row for row in singles if row["workshop_id"] == single_workshop_id), None) if single_workshop_id else (singles[0] if singles else None)
    if single_workshop_id and single is None:
        raise ValueError("single_workshop_id must be an eligible, unexcluded whole-batch candidate")
    base = {"available": False, "single": single, "fastest_single": singles[0] if singles else None}
    if n < 2:
        return {**base, "reason": "not enough pieces for two positive parts"}
    shops = candidates({**batch, "pieces": 1}, workshops, queues, today, exclude)
    best = None
    best_key = None
    for left, right in combinations(sorted(shops, key=lambda row: row["workshop_id"]), 2):
        a, b = workshops[left["workshop_id"]], workshops[right["workshop_id"]]
        lo = max(1, n - int(b.max_batch)) if b.max_batch is not None else 1
        hi = min(n - 1, int(a.max_batch)) if a.max_batch is not None else n - 1
        if lo > hi:
            continue
        crossing = ((queues[b.workshop_id] + b.lead_days + n / b.capacity)
                    - (queues[a.workshop_id] + a.lead_days)) / (1 / a.capacity + 1 / b.capacity)
        quantities = {lo, hi, max(lo, min(hi, math.floor(crossing))), max(lo, min(hi, math.ceil(crossing)))}
        for x in sorted(quantities):
            parts = []
            for shop, pieces in ((a, x), (b, n - x)):
                part = {**batch, "pieces": pieces}
                eligibility = check_eligibility(part, {shop.workshop_id: shop})[0]
                if not eligibility["eligible"]:
                    break
                parts.append({**eligibility, "pieces": pieces,
                              **estimate_eta(part, shop.workshop_id, workshops, queues, today),
                              **estimate_cost(part, shop.workshop_id, workshops),
                              "queue": overload_probe(part, shop.workshop_id, workshops, queues)})
            if len(parts) != 2:
                continue
            total_days = max(p["total_days"] for p in parts)
            total_cost = sum(p["total_cost"] for p in parts)
            key = (total_days, total_cost, a.workshop_id, b.workshop_id, x)
            if best_key is None or key < best_key:
                best_key = key
                best = {"available": True, "parts": parts, "total_days": total_days,
                        "eta_date": max(p["eta_date"] for p in parts),
                        "days_to_spare": min(p["days_to_spare"] for p in parts),
                        "total_cost": total_cost}
    if best is None:
        return {**base, "reason": "no legal two-workshop split after exclusions and caps"}
    return {**base, **best,
            "faster": best["total_days"] < single["total_days"] if single else None,
            "earlier_eta": best["eta_date"] < single["eta_date"] if single else None,
            "days_saved": single["total_days"] - best["total_days"] if single else None,
            "faster_than_fastest_single": best["total_days"] < singles[0]["total_days"] if singles else None}


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

    @_traced
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

    @_traced
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
