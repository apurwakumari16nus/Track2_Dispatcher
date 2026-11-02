"""Explanation review on the 46 recorded requests: is what the reply says true, and does it say why?

    uv run python eval/run_explanation_review.py <dev_audit.json> <heldout_audit.json>

Goes past the number check in src/faithfulness.py, which only proves that a number came from a
tool. No model call.

  recomputed      total days, return date and cost worked out again from workshops.csv
  constraint_named  an exclusion or preference that was applied is named in the reply
  late_flag_fits  ALREADY LATE appears only on a request that asks for placement
  ask_needed      a clarification does not ask for a due date the order file already holds
"""

from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "harness")]

from simulate import load_workshops

TODAY = date(2026, 4, 1)
WORDS = {"cheapest": ("cheap", "lowest cost"), "lowest_defect": ("defect rate", "lowest defect", "quality"),
         "fastest": ("fastest", "quickest", "earliest")}


def review(item, workshops):
    response, record = item["response"], item["response"]["decision_record"]
    parsed, text = response["parsed_request"], response["explanation_text"]
    behaviour = parsed["behaviour"]
    row = {"request_id": item["request_id"], "behaviour": behaviour, "recomputed": None, "constraint_named": None,
           "late_flag_fits": None, "ask_needed": None}
    chosen = record.get("chosen_workshop")
    if chosen:
        shop = workshops[chosen]
        pick = next(c for c in record["candidates"] if c.get("workshop_id") == chosen or c["name"] == shop.name)
        pieces = pick["total_cost"] / pick["cost_per_piece"]
        total = shop.queue0 + pieces / shop.capacity + shop.lead_days
        eta = TODAY + timedelta(days=round(total))
        row["recomputed"] = (abs(total - pick["total_days"]) < 1e-6 and eta.isoformat() == pick["eta_date"]
                             and abs(pieces * shop.cost - pick["total_cost"]) < 1e-6)
    applied = record.get("constraints_applied", {})
    if chosen and behaviour == "allocate":
        wanted = [workshops[w].name for w in applied.get("exclude", [])]
        named = [text.count(name) > 0 for name in wanted]
        if applied.get("preference"):
            named.append(any(word in text.casefold() for word in WORDS[applied["preference"]]))
        row["constraint_named"] = all(named) if named else None
    if "ALREADY LATE" in text:
        row["late_flag_fits"] = behaviour in {"allocate", "refuse"}
    if behaviour == "clarify" and re.search(r"Which order do you mean", text):
        row["ask_needed"] = "confirmed due date" not in text
    return row


def main(dev_audit, heldout_audit):
    workshops = load_workshops()
    rows = [dict(set=name, **review(item, workshops))
            for name, path in (("dev", dev_audit), ("heldout", heldout_audit))
            for item in json.loads(Path(path).read_text())["requests"]]
    frame = pd.DataFrame(rows)
    frame.to_csv(ROOT / "eval/explanation_review.csv", index=False)
    for check in ("recomputed", "constraint_named", "late_flag_fits", "ask_needed"):
        scored = frame[frame[check].notna()]
        failed = scored[scored[check] == False].request_id.tolist()  # noqa: E712
        print(f"{check}: {int((scored[check] == True).sum())}/{len(scored)}  failed: {failed}")  # noqa: E712


if __name__ == "__main__":
    main(*sys.argv[1:])
