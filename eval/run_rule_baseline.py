"""What the LLM adds: the same requests through three no-LLM readers and the same allocator.

    uv run python eval/run_rule_baseline.py

No model call and no API key. Each reader is about the size of a shipped baseline and feeds the
same earliest-finish reference used to score the real system.

  id_only        order ID regex, then earliest finish on the order file; no ID means clarify
  keywords_seen  keyword lists written by an AI assistant straight after reading all 46 messages.
                 The phrases come from the test set, so this is an upper bound, not a fair test.
  keywords_blind keyword lists written once by a separate AI agent that was barred from every
                 request, label and evaluation file (eval/rule_baseline/keywords_blind.py).
                 This is the fair comparison. It was not edited after its first run.

Scoring favours the rules: a clarify or decline counts as a correct decision on behaviour alone,
without the checks the real system must pass (right candidate list, the constraint recorded).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "src"), str(ROOT / "harness")]

from run_inbox import TODAY, benchmark, eligible_workshops, inbox_messages, read_labels, reference
from simulate import load_workshops

sys.path.insert(0, str(ROOT / "eval/rule_baseline"))
import keywords_blind

SETS = {"dev": ("data/dispatch_requests.txt", "eval/labels_v2.csv", "eval/guardrails_v2/sonnet_dev/inbox_results.csv"),
        "heldout": ("data/heldout_requests.txt", "eval/labels_heldout_v2.csv", "eval/guardrails_v2/sonnet_heldout/inbox_results.csv"),
        "redteam": ("data/redteam_requests.txt", "eval/redteam/labels.csv", "eval/redteam/after/inbox_results.csv")}
QUESTIONS = r"\b(what price|which workshop did|any movement|who handled|delivered to)\b"
EXCLUDE = r"(?:keep (?:it )?away from|nothing new to|avoid|not to)\s+"
DATE = r"\b(Jan|Feb|Mar|Apr|May|Jun)[a-z]*\s+(\d{1,2})\b|\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun)[a-z]*\b"


def order_row(text, orders):
    found = re.findall(r"\bORD-\d+\b", text, re.I)
    if not found:
        return None, False
    rows = orders[orders.order_id == found[0].upper()]
    return (rows.iloc[0] if len(rows) else None), True


def plan(row, workshops, queues, *, exclude=(), preference=None, due=None):
    ref = {"order_id": row.order_id, "pieces": int(row.pieces), "category": row.category,
           "due_date": due or datetime.fromisoformat(str(row.due_date)).date(), "exclude": list(exclude),
           "preference": preference, "must_make_date": preference == "cheapest"}
    return (benchmark(ref, workshops, queues) or {}).get("chosen_workshop")


def id_only(text, orders, workshops, queues):
    row, has_id = order_row(text, orders)
    if row is None:
        return "clarify", None
    return "allocate", plan(row, workshops, queues)


def blind(text, orders, workshops, queues):
    try:
        got = keywords_blind.read(text, orders, workshops)
    except ValueError:  # an impossible date such as 31/2 crashes the rule; asking is the kindest reading
        return "clarify", None
    if got["behaviour"] in {"clarify", "decline"}:
        return got["behaviour"], None
    rows = orders[orders.order_id == got["order_id"]]
    if not len(rows):
        return "decline", None
    row = rows.iloc[0]
    named, exclude = got.get("named") or [], got.get("exclude") or []
    legal = {w.workshop_id for w in eligible_workshops({"category": row.category, "pieces": int(row.pieces)}, workshops)}
    if named and named[0] not in legal:
        return "refuse", plan(row, workshops, queues, exclude=exclude + named[:1], preference=got.get("preference"), due=got.get("due_date"))
    return "allocate", plan(row, workshops, queues, exclude=exclude, preference=got.get("preference"), due=got.get("due_date"))


def seen(text, orders, workshops, queues):
    low = text.casefold()
    row, has_id = order_row(text, orders)
    if re.search(QUESTIONS, low) or (has_id and row is None):
        return "decline", None
    if row is None or "confirm" in low:
        return "clarify", None
    exclude = [wid for wid, shop in workshops.items() if re.search(EXCLUDE + re.escape(shop.name.casefold()), low)]
    named = [wid for wid, shop in workshops.items() if shop.name.casefold() in low and wid not in exclude]
    preference = ("cheapest" if re.search(r"cheapest|costs? least", low) else
                  "lowest_defect" if re.search(r"lowest defect|quality", low) else None)
    due = None
    if (match := re.search(DATE, text)):
        month, day = (match[1], match[2]) if match[1] else (match[4], match[3])
        try:
            due = datetime.strptime(f"{month} {day} {TODAY.year}", "%b %d %Y").date()
        except ValueError:
            return "clarify", None
    if named:
        batch = {"category": row.category, "pieces": int(row.pieces)}
        if named[0] not in {w.workshop_id for w in eligible_workshops(batch, workshops)}:
            return "refuse", plan(row, workshops, queues, exclude=exclude + named[:1], preference=preference, due=due)
    return "allocate", plan(row, workshops, queues, exclude=exclude, preference=preference, due=due)


def score(name, reader, requests, labels_path, orders, workshops):
    queues = {wid: w.queue0 for wid, w in workshops.items()}
    messages = inbox_messages(ROOT / requests)
    labels = read_labels(ROOT / labels_path, list(messages))
    rows = []
    for rid, message in messages.items():
        label = labels[rid]
        text = message.split(":", 1)[-1] if "]" in message else message
        behaviour, chosen = reader(text, orders, workshops, queues)
        ref = reference(message, label, orders, workshops)
        target = benchmark(ref, workshops, queues)
        right = behaviour == label["expected_behaviour"]
        decision = right and (label["expected_behaviour"] not in {"allocate", "refuse"}
                              or (target is not None and chosen == target["chosen_workshop"]))
        rows.append({"reader": name, "request_id": rid, "expected": label["expected_behaviour"], "actual": behaviour,
                     "chosen": chosen, "reference": target["chosen_workshop"] if target else None,
                     "behaviour_correct": right, "decision_correct": decision})
    return rows


def main():
    orders = pd.read_csv(ROOT / "data/orders.csv")
    workshops = load_workshops()
    out = ROOT / "eval/rule_baseline"
    out.mkdir(exist_ok=True)
    lines = ["# Rule-only readers against the LLM reader", "", "Same labels, same reference allocator. keywords_seen is an upper bound: its author had read the messages.", "",
             "| Set | Reader | Behaviour | Decision |", "|---|---|---:|---:|"]
    for set_name, (requests, labels_path, recorded) in SETS.items():
        rows = []
        for name, reader in (("id_only", id_only), ("keywords_seen", seen), ("keywords_blind", blind)):
            part = score(name, reader, requests, labels_path, orders, workshops)
            rows += part
            n = len(part)
            lines.append(f"| {set_name} | {name} | {sum(r['behaviour_correct'] for r in part)}/{n} | {sum(r['decision_correct'] for r in part)}/{n} |")
        system = pd.read_csv(ROOT / recorded)
        lines.append(f"| {set_name} | Sonnet 5.5 with guards | {int(system.behaviour_correct.sum())}/{len(system)} | {int(system.decision_correct.sum())}/{len(system)} |")
        frame = pd.DataFrame(rows)
        frame.to_csv(out / f"{set_name}.csv", index=False)
        lines += [""] if set_name == "heldout" else []
        by = frame.groupby(["reader", "expected"])[["behaviour_correct", "decision_correct"]].sum().join(
            frame.groupby(["reader", "expected"]).size().rename("n"))
        by.to_csv(out / f"{set_name}_by_type.csv")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
