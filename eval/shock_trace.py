"""Print a daily CSV comparing random dispatch with our allocator under shock.

From the project root:
    python eval/shock_trace.py > eval/shock_trace.csv
    python eval/shock_trace.py --output eval/shock_trace.csv --events eval/shock_events.json

The simulator always runs with shock=True. Diagnostics go to stderr, keeping
stdout suitable for CSV redirection. The evaluator reproduces the simulator's
separate seed+6 draw ONLY to label the target, never to inform either policy.
Defaults: seed 5105 and the existing robustness preset, without tuned weights.

shock_window labels calendar days 30 <= day < 44 (reopening on day 44). The
v3 harness delays work starting inside the window and pauses work crossing its
start. It immediately includes that future delay in the queue: a flag can occur
before day 30. This is queue-anomaly evidence, not realistic advance detection. Same-day dispatches can precede and
follow detection: ours_pieces_while_suspect counts only those chosen after the
monitor has flagged the target. A suspect may later recover and receive work.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
import sys
from datetime import timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "harness")]

from allocator import Allocator
from objectives import PRESETS
from simulate import Simulator, random_choice


COLUMNS = [
    "day", "date", "shock_window", "shocked_workshop_id", "random_pieces",
    "ours_pieces", "ours_pieces_while_suspect", "new_suspect_flags",
    "cleared_flags", "suspect_at_day_end",
]


def run_trace(seed: int = 5105, objective: str = "robustness") -> dict:
    """Run independent policy replays, returning daily rows and detection evidence."""
    sim = Simulator(shock=True, seed=seed)
    day0 = sim.batches[0]["sent_date"]
    target = random.Random(seed + 6).choice([
        w.workshop_id for w in sim.workshops.values() if w.status == "ACTIVE"
    ])
    allocator = Allocator(PRESETS[objective])
    decisions = []

    def tracked_allocator(batch, workshops, queues):
        # Only the three ordinary allocator inputs cross this boundary.
        chosen = allocator(batch, workshops, queues)
        decisions.append(allocator.last_decision.to_dict())
        return chosen

    baseline = sim.run(random_choice, name="random")
    ours = sim.run(tracked_allocator, name=objective)
    final_day = (sim.batches[-1]["sent_date"] - day0).days
    rows = [{
        "day": day,
        "date": (day0 + timedelta(days=day)).isoformat(),
        "shock_window": int(30 <= day < 44),
        "shocked_workshop_id": target,
        "random_pieces": 0,
        "ours_pieces": 0,
        "ours_pieces_while_suspect": 0,
        "new_suspect_flags": 0,
        "cleared_flags": 0,
        "suspect_at_day_end": 0,
    } for day in range(final_day + 1)]
    events = []
    observed_state = {}
    for batch, base, own, record in zip(sim.batches, baseline, ours, decisions, strict=True):
        day = (batch["sent_date"] - day0).days
        row = rows[day]
        if base["workshop"] == target:
            row["random_pieces"] += batch["pieces"]
        flagged = any(flag["workshop_id"] == target for flag in record["shock_flags"])
        if own["workshop"] == target:
            row["ours_pieces"] += batch["pieces"]
            if flagged:
                row["ours_pieces_while_suspect"] += batch["pieces"]
        observed_state[day] = int(flagged)
        for event in record["shock_events"]:
            events.append({**event, "order_id": batch["order_id"], "date": row["date"]})
            if event["workshop_id"] == target:
                counter = "new_suspect_flags" if event["status"] == "suspect" else "cleared_flags"
                row[counter] += 1

    # Days without dispatches have no observations; carry the last known flag.
    flagged = 0
    for row in rows:
        flagged = observed_state.get(row["day"], flagged)
        row["suspect_at_day_end"] = flagged

    return {
        "seed": seed,
        "objective": objective,
        "shocked_workshop_id": target,
        "shocked_workshop_name": sim.workshops[target].name,
        "rows": rows,
        "events": events,
        "caveat": "Queues can include future closure delay before day 30; flags are not proof of an observed closure.",
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=5105)
    parser.add_argument("--objective", choices=PRESETS, default="robustness")
    parser.add_argument("--output", type=Path, help="Write CSV here instead of stdout")
    parser.add_argument("--events", type=Path, help="Also save flag/recovery evidence as JSON")
    args = parser.parse_args(argv)
    result = run_trace(args.seed, args.objective)

    def write_csv(stream):
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(result["rows"])

    if args.output:
        with args.output.open("w", encoding="utf-8", newline="") as stream:
            write_csv(stream)
    else:
        write_csv(sys.stdout)
    if args.events:
        args.events.write_text(json.dumps(
            {key: value for key, value in result.items() if key != "rows"},
            indent=2, allow_nan=False,
        ) + "\n", encoding="utf-8")

    print(
        f"Seed {args.seed}; target {result['shocked_workshop_id']} "
        f"{result['shocked_workshop_name']}; objective {args.objective}.", file=sys.stderr,
    )
    for event in result["events"]:
        if event["status"] == "suspect":
            print(
                f"{event['workshop_id']} flagged on day {event['flagged_on_day']}: "
                f"queue jumped from {event['expected']:.2f} to {event['observed']:.2f} "
                f"(excess {event['jump']:.2f}; order {event['order_id']}).", file=sys.stderr,
            )
        else:
            print(
                f"{event['workshop_id']} cleared on day {event['cleared_on_day']}: "
                f"expected {event['expected_on_clear']:.2f}, observed "
                f"{event['observed_on_clear']:.2f}.", file=sys.stderr,
            )
    total = sum(row["ours_pieces_while_suspect"] for row in result["rows"])
    print(f"Pieces sent by ours to the target while suspect: {total}.", file=sys.stderr)


if __name__ == "__main__":
    main()
