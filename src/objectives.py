"""Inspectable objective weights and deterministic, normalised scoring.

Use PRESETS["lateness"] or load_config("objective.yaml"). File contents are a
flat mapping, for example (JSON; YAML uses the same keys)::

    {"name": "my_hybrid", "w_lateness": 0.7, "w_fairness": 0.3}

Omitted weights default to zero. Weights are not automatically rescaled.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ObjectiveConfig:
    """Nonnegative, finite weights; name labels the objective in decision logs."""

    w_lateness: float = 0.0
    w_defect: float = 0.0
    w_fairness: float = 0.0
    w_robustness: float = 0.0
    w_cost: float = 0.0
    name: str = "custom"

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Objective name must be a nonempty string")
        for field in fields(self):
            if field.name == "name":
                continue
            value = getattr(self, field.name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{field.name} must be a finite, nonnegative number")
            object.__setattr__(self, field.name, float(value))


PRESETS = {
    "lateness": ObjectiveConfig(w_lateness=1.0, name="lateness"),
    "defect": ObjectiveConfig(w_defect=1.0, name="defect"),
    "fairness": ObjectiveConfig(w_fairness=1.0, name="fairness"),
    "robustness": ObjectiveConfig(w_robustness=1.0, name="robustness"),
    "hybrid_lateness_fairness": ObjectiveConfig(
        w_lateness=0.9, w_fairness=0.1, name="hybrid_lateness_fairness"
    ),
    "hybrid_lateness_defect": ObjectiveConfig(
        w_lateness=0.6, w_defect=0.4, name="hybrid_lateness_defect"
    ),
}


def load_config(path: str | Path) -> ObjectiveConfig:
    """Load a flat weight mapping from .json, .yaml or .yml (safe YAML).

    Unknown keys, invalid weights and non-mappings raise ValueError. Malformed
    JSON/YAML raises its parser's error; inaccessible files raise OSError.
    An omitted name uses the file stem. Only this loader performs file I/O.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ValueError("Objective config must be a .json, .yaml or .yml file")
    content = path.read_text(encoding="utf-8")
    if suffix == ".json":
        values = json.loads(content)
    else:
        import yaml

        values = yaml.safe_load(content)
    if not isinstance(values, dict):
        raise ValueError("Objective config must contain a mapping of weights")
    unknown = values.keys() - {field.name for field in fields(ObjectiveConfig)}
    if unknown:
        raise ValueError(f"Unknown objective config keys: {sorted(map(str, unknown))}")
    return ObjectiveConfig(**{"name": path.stem, **values})


def score_terms(cand: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, float]:
    """Return the unweighted terms documented in score_candidate for auditing."""
    pieces = state.get("pieces_by_workshop", {})
    total_pieces = sum(pieces.values())
    share = pieces.get(cand["workshop_id"], 0) / total_pieces if total_pieces else 0.0
    monitor = state.get("shock_monitor")
    flagged = float(monitor.is_flagged(cand["workshop_id"])) if monitor is not None else 0.0
    max_cost = max((workshop.cost for workshop in state["workshops"].values()), default=0.0)
    late = max(0, -cand["days_to_spare"])
    duration = cand["total_days"]
    return {
        "lateness": late / (late + 30.0) + 0.01 * duration / (duration + 30.0),
        "defect": float(cand["expected_defect_rate"]),
        "fairness": share,
        "robustness": (flagged + 0.25 * share) / 1.25,
        "cost": cand["cost_per_piece"] / max_cost if max_cost else 0.0,
    }


def score_candidate(
    cand: Mapping[str, Any], config: ObjectiveConfig, state: Mapping[str, Any]
) -> float:
    """Return a weighted penalty; lower is better, with no mutation or randomness.

    Let late = max(0, -days_to_spare), t = total_days, p = pieces previously
    allocated to this workshop, P = pieces previously allocated to all shops,
    flag = 1 if shock_monitor.is_flagged(workshop_id) else 0, and max_cost be the
    maximum Workshop.cost across ALL state['workshops'] (including ineligible
    shops, to keep the price reference independent of filtering).

      L = late / (late + 30) + 0.01 * t / (t + 30)
      D = expected_defect_rate
      F = p / P, or 0 when P == 0
      R = (flag + 0.25 * F) / 1.25
      C = cost_per_piece / max_cost, or 0 when max_cost == 0
      score = w_lateness*L + w_defect*D + w_fairness*F
              + w_robustness*R + w_cost*C

    Thirty days is the fixed half-saturation scale for lateness and duration.
    The speed term is at most 0.01 and breaks equal-lateness ties. Terms lie in
    [0, 1], except L which is below 1.01, for valid simulator inputs. Robustness
    adds a quarter-share concentration penalty to a binary flag, then divides
    by its maximum 1.25. Scores are not divided by the sum of weights.

    state contains 'workshops', 'pieces_by_workshop' (ID -> nonnegative pieces),
    and 'shock_monitor' (a ShockMonitor). Missing history/monitor means no
    previous allocations/no flags.
    Shares describe history BEFORE this batch; no queues, transport, or rework
    are added to piece counts. At run start all shares are zero. The monitor
    flags observed queue anomalies; these are evidence, not proof of a closure.
    """
    terms = score_terms(cand, state)
    return float(sum(getattr(config, f"w_{name}") * value for name, value in terms.items()))
