"""Compare the two independent label files. Reads only; never writes a label.

    uv run python eval/labeling/compare_reviews.py

Reports how many of the 30 rows each reviewer has completed, schema problems,
and, for rows both have completed, agreement on behaviour and primary issue and
every field that differs. Use the output to fill reconciliation.md; the agreed
answers go into ../labels.csv by hand, after discussion.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ["expected_behaviour", "expected_order_id", "expected_pieces", "expected_category", "expected_due", "issue", "constraint"]
BEHAVIOURS = {"allocate", "clarify", "refuse", "decline"}
ISSUES = {"none", "no_order_id", "multiple_matches", "order_not_found", "due_date_passed", "due_date_today_or_impossible",
          "already_in_packing", "ineligible_suggested_workshop", "no_such_data", "date_not_confirmed", "none_makes_date"}
IDS = [f"R{i:02d}" for i in range(1, 31)]


def load(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return {row["request_id"]: {k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(stream)}


def problems(name, rows):
    out = [f"{name}: missing {rid}" for rid in IDS if rid not in rows]
    for rid, row in rows.items():
        if not row["expected_behaviour"]:
            continue
        if row["expected_behaviour"] not in BEHAVIOURS:
            out.append(f"{name} {rid}: behaviour {row['expected_behaviour']!r} is not one of {sorted(BEHAVIOURS)}")
        if row["issue"] not in ISSUES:
            out.append(f"{name} {rid}: issue {row['issue']!r} is not an allowed value")
        if row["expected_pieces"] and not row["expected_pieces"].isdigit():
            out.append(f"{name} {rid}: pieces {row['expected_pieces']!r} is not an integer")
        if row["expected_category"] not in {"", "TOPS", "ACCESSORIES"}:
            out.append(f"{name} {rid}: category {row['expected_category']!r}")
    return out


def main():
    one, two = load(HERE / "reviewer_1.csv"), load(HERE / "reviewer_2.csv")
    final = load(HERE.parent / "labels.csv")
    done = {name: [rid for rid in IDS if rows.get(rid, {}).get("expected_behaviour")] for name, rows in
            (("reviewer_1", one), ("reviewer_2", two), ("labels.csv", final))}
    for name, rows in done.items():
        print(f"{name}: {len(rows)} of 30 rows completed")
    for line in problems("reviewer_1", one) + problems("reviewer_2", two):
        print("  schema:", line)
    both = [rid for rid in IDS if rid in done["reviewer_1"] and rid in done["reviewer_2"]]
    if not both:
        print("\nNo request has been labelled by both reviewers yet. Nothing to compare.")
        return
    behaviour = sum(one[r]["expected_behaviour"] == two[r]["expected_behaviour"] for r in both)
    issue = sum(one[r]["issue"] == two[r]["issue"] for r in both)
    print(f"\nCompared {len(both)} requests labelled by both.")
    print(f"Behaviour agreement before discussion: {behaviour}/{len(both)}")
    print(f"Primary-issue agreement before discussion: {issue}/{len(both)}")
    differing = 0
    for rid in both:
        diffs = [f for f in FIELDS if one[rid][f] != two[rid][f]]
        if diffs:
            differing += 1
            print(f"\n{rid}: " + "; ".join(f"{f}: {one[rid][f] or '(blank)'} vs {two[rid][f] or '(blank)'}" for f in diffs))
    print(f"\nRequests with any field disagreement: {differing}/{len(both)}")


if __name__ == "__main__":
    main()
