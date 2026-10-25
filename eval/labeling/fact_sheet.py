"""Fact lookup for the human labellers. It states facts; it never labels.

Reads only data/orders.csv and data/workshops.csv. It deliberately imports NOTHING from
src/ (no intake, agent, allocator or tools), so using it does not make the labels depend
on the system under test. It applies the formulas written in data/data_dictionary.md:

    total days  = queue + pieces / capacity + pickup lead days
    return date = today + round(total days)        (Python rounds .5 to the even number)

It does not choose a behaviour, an issue, or a workshop. You read the message, decide
what it asks for, and type the facts you read in. Today is 2026-04-01 for all 30
requests, with the 1 April queue snapshot in workshops.csv.

Examples (run from the repository root):
  uv run python eval/labeling/fact_sheet.py --order ORD-045 --due 2026-04-09
  uv run python eval/labeling/fact_sheet.py --customer TrendCart
  uv run python eval/labeling/fact_sheet.py --customer "Cotton Club" --product Vest
  uv run python eval/labeling/fact_sheet.py --order ORD-045 --pieces 400 --due 2026-04-05
  uv run python eval/labeling/fact_sheet.py --order ORD-045 --category ACCESSORIES

Options: --pieces / --category override the order file when the MESSAGE gives a different
value (then record both in your notes). --due is the deadline you read in the message;
omit it to use the order's own due date.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(name: str) -> list[dict]:
    with (ROOT / "data" / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def show_order(o: dict) -> str:
    return (f"{o['order_id']}  {o['customer']} | {o['product']} ({o['category']}) | {o['pieces']} pcs | "
            f"due {o['due_date']} | {o['status']} / stage {o['current_stage']}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--order", help="order ID named in the message, e.g. ORD-045")
    p.add_argument("--customer", help="customer named in the message (matches in-progress orders)")
    p.add_argument("--product", help="product named in the message (narrows the customer match)")
    p.add_argument("--pieces", type=int, help="quantity stated in the message, if it differs from the file")
    p.add_argument("--category", choices=["TOPS", "ACCESSORIES"], help="override the file's category")
    p.add_argument("--due", help="deadline in the message as YYYY-MM-DD (default: the order's own due date)")
    p.add_argument("--today", default="2026-04-01")
    a = p.parse_args()

    today = date.fromisoformat(a.today)
    orders = read("orders.csv")
    by_id = {o["order_id"].casefold(): o for o in orders}
    order = None

    print(f"TODAY {today}   (queues = workshops.csv snapshot)\n")
    if a.order:
        order = by_id.get(a.order.casefold())
        print("ORDER LOOKUP")
        print("  " + (show_order(order) if order else f"{a.order} is NOT in orders.csv"))
    else:
        matches = [o for o in orders if o["status"] == "IN_PROGRESS"
                   and (not a.customer or o["customer"].casefold() == a.customer.casefold())
                   and (not a.product or o["product"].casefold() == a.product.casefold())]
        print(f"IN-PROGRESS ORDERS MATCHING customer={a.customer!r} product={a.product!r}: {len(matches)}")
        for o in sorted(matches, key=lambda o: o["order_id"]):
            print("  " + show_order(o))
        if len(matches) == 1:
            order = matches[0]
    if a.order and order is None:
        return
    if not order:
        print("\nNo single order identified, so no workshop table. State what you decide in your notes.")
        return

    pieces = a.pieces if a.pieces is not None else int(order["pieces"])
    category = a.category or order["category"]
    due = date.fromisoformat(a.due) if a.due else date.fromisoformat(order["due_date"])
    print("\nFACTS FOR THIS ORDER")
    print(f"  stage now: {order['current_stage']}" + ("   <-- already in PACKING" if order["current_stage"] == "PACKING" else ""))
    print(f"  status: {order['status']}")
    if a.pieces is not None and a.pieces != int(order["pieces"]):
        print(f"  quantity: message says {a.pieces}, file says {order['pieces']}")
    if a.category and a.category != order["category"]:
        print(f"  category: message-side value {a.category}, file says {order['category']}")
    print(f"  due date used: {due}   ({(due - today).days} days from today)"
          + ("   <-- on or before today" if due <= today else ""))

    rows, out = [], []
    for w in read("workshops.csv"):
        wid, name = w["workshop_id"], w["name"]
        cap = w["max_batch_pieces"].strip()
        if w["status"] != "ACTIVE":
            out.append((wid, name, w["status"].lower())); continue
        if category not in w["makes"].split("+"):
            out.append((wid, name, f"cannot make {category}")); continue
        if cap and pieces > int(cap):
            out.append((wid, name, f"batch of {pieces} exceeds {cap}-piece cap")); continue
        total = float(w["current_queue_days"]) + pieces / float(w["capacity_pieces_per_day"]) + float(w["pickup_lead_days"])
        back = today + timedelta(days=round(total))
        rows.append((back, wid, name, float(w["current_queue_days"]), pieces / float(w["capacity_pieces_per_day"]),
                     float(w["pickup_lead_days"]), total, (due - back).days, pieces * float(w["cost_per_piece"]),
                     float(w["defect_rate"])))

    print(f"\nWORKSHOPS THAT CAN TAKE {pieces} {category}  (sorted by return date)")
    print(f"  {'id':<3} {'name':<14} {'queue':>5} {'make':>5} {'lead':>4} {'total':>6}  {'back on':<10} {'spare':>5} {'cost':>7} {'defect':>6}")
    for r in sorted(rows):
        print(f"  {r[1]:<3} {r[2]:<14} {r[3]:>5.1f} {r[4]:>5.2f} {r[5]:>4.0f} {r[6]:>6.2f}  {r[0]!s:<10} {r[7]:>5} {r[8]:>7.0f} {r[9]:>6.2f}")
    print("\nNOT ELIGIBLE")
    for wid, name, why in out:
        print(f"  {wid:<3} {name:<14} {why}")
    if rows:
        on_time = [r for r in rows if r[7] >= 0]
        print(f"\nFACT: {len(rows)} eligible; {len(on_time)} return on or before {due}; "
              f"earliest return {min(r[0] for r in rows)}.")
    else:
        print("\nFACT: no workshop is eligible for this order.")
    print("Check by hand if any total ends in exactly .5 (rounding goes to the even day).")


if __name__ == "__main__":
    main()
