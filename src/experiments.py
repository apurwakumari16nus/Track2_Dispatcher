"""Read-only simulation experiments using the unchanged shared harness.

No LLM calls, workshop messages, or writes to the operational decision log.
Summary arithmetic is shared with the existing command-line evaluator.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "harness")]

from allocator import Allocator
from objectives import PRESETS
from run_simulator import BASELINES, COLUMNS, summarize_outcomes
from simulate import Simulator


def fingerprints():
    paths = ["data/orders.csv", "data/workshops.csv", "harness/simulate.py",
             "src/allocator.py", "src/tools.py", "src/objectives.py",
             "src/heuristic.py", "eval/run_simulator.py", "eval/shock_trace.py",
             "src/experiments.py"]
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def run_experiment(seed=5105):
    """Run the complete matrix, retaining batch outcomes for visual inspection."""
    summaries, batches = [], []
    for shock in (False, True):
        sim = Simulator(shock=shock, seed=seed)
        policies = [(name, "none", policy) for name, policy in BASELINES.items()]
        policies += [("allocator", name, Allocator(config)) for name, config in PRESETS.items()]
        for policy, objective, allocator in policies:
            outcomes = sim.run(allocator, name=f"{policy}:{objective}")
            summaries.append(dict(policy=policy, objective=objective, shock=shock,
                                  **summarize_outcomes(outcomes)))
            for batch, outcome in zip(sim.batches, outcomes, strict=True):
                batches.append({**batch, **outcome, "policy": policy,
                                "objective": objective, "shock": shock,
                                "sent_date": batch["sent_date"].isoformat(),
                                "due_date": batch["due_date"].isoformat()})
    summary = pd.DataFrame(summaries, columns=COLUMNS)
    summary.attrs.update(seed=seed, batch_count=len(sim.batches),
                         total_pieces=sum(b["pieces"] for b in sim.batches))
    return {"summary": summary, "outcomes": pd.DataFrame(batches),
            "seed": seed, "batch_count": len(sim.batches),
            "total_pieces": sum(b["pieces"] for b in sim.batches),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "fingerprints": fingerprints()}


def decision_replay(seed, objective, shock):
    """Recover genuine per-order decision records from a fresh identical replay."""
    allocator = Allocator(PRESETS[objective])
    decisions = {}

    def tracked(batch, workshops, queues):
        chosen = allocator(batch, workshops, queues)
        decisions[batch["order_id"]] = allocator.last_decision.to_dict()
        return chosen

    Simulator(shock=shock, seed=seed).run(tracked, name=objective)
    return decisions
