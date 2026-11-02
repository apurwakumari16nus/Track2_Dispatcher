"""How well the desk reads what workshops write, in four languages. Forty-eight hand-labelled messages, the same twelve
meanings in English, Hinglish, Hindi and Chinese, through the same reader and Python checks the desk uses.

    uv run python eval/run_partner_replies.py eval/partner_replies/after.csv
    uv run python eval/run_partner_replies.py eval/partner_replies/heldout_result.csv heldout.csv

Live model calls. A message passes only if its kind is right and every expected value survived the Python checks.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "harness")]

import intake  # noqa: E402
import partners  # noqa: E402

TODAY = date(2026, 4, 1)
ORDERS = ["ORD-041", "ORD-063"]
VALUES = ("date", "delay_days", "capacity_per_day", "price_per_piece")


def call(prompt, text):
    return intake._call_llm(prompt, text, schema=partners.SCHEMA)


def score(row) -> dict:
    reading = partners.read(row["message"], role="partner workshop", today=TODAY, order_ids=ORDERS, call=call)
    wrong = [name for name in VALUES if pd.notna(row[name]) and str(reading[name]) not in (str(row[name]), str(row[name]).removesuffix(".0"))]
    return {"id": row["id"], "language": row["language"], "message": row["message"], "expected": row["kind"], "kind": reading["kind"], "source": reading["source"],
            "kind_ok": reading["kind"] == row["kind"], "values_ok": not wrong, "passed": reading["kind"] == row["kind"] and not wrong, "lost": ", ".join(wrong)}


def main(out, source="messages.csv"):
    intake.llm_settings()
    rows = pd.read_csv(Path(__file__).parent / "partner_replies" / source, dtype=str).to_dict("records")
    with ThreadPoolExecutor(6) as pool:
        done = pd.DataFrame(pool.map(score, rows))
    done.to_csv(out, index=False)
    print(done.groupby("language", sort=False)[["kind_ok", "values_ok", "passed"]].sum().assign(of=done.groupby("language", sort=False).size()).to_string())
    print(done[~done["passed"]][["id", "expected", "kind", "lost"]].to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
