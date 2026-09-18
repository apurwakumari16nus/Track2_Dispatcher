# Dispatch intake

`parse_request(message, today, orders_df, workshops)` returns a `ParsedRequest`.
This module is the application's free-text interpretation boundary. It uses an
LLM for extraction and Python for business checks. It does not call the allocator,
estimate completion times, calculate costs, or decide whether splitting works.

## Use

Install `requirements.txt`. Set `OPENAI_API_KEY` and `OPENAI_INTAKE_MODEL` in the
project's `.env` or shell environment. The chosen model must support strict JSON
Schema and temperature zero. There is no implicit model selection or fallback
to unstructured text. The request uses OpenAI's
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
through Chat Completions, with `temperature=0` and `store=False`.

From the project root, with the virtual environment active:

```bash
PYTHONPATH=src:harness python - <<'PY'
from datetime import date
import json
import pandas as pd
from intake import parse_request
from simulate import load_workshops

record = parse_request(
    "R30 [10:18] Mei: Please allocate ORD-099: 1500 polo shirts, "
    "Northwind Apparel. Deadline Apr 05.",
    date(2026, 4, 1),
    pd.read_csv("data/orders.csv"),
    load_workshops(),
)
print(json.dumps(record.to_dict(), indent=2))
PY
```

The live call receives the message, today's date, workshop names/IDs, valid
customer/product names, and the extraction schema. It does not receive human
labels or order rows. It copies a deadline phrase into `due_date_text`; Python
parses it. An inbox header provides the request ID and sender when present;
ordinary messages without a header may leave these fields null.

## Checks and precedence

| Order | Python check | Result |
|---|---|---|
| 1 | Explicit order ID does not exist | Terminal `decline`, `order not found`. No guessing a replacement. |
| 2 | No order ID | Filter `IN_PROGRESS` orders by the customer and/or product provided. Resolve exactly one match; otherwise `clarify`, with candidate IDs in the reason. |
| 3 | Information-only question | `decline` for unavailable workshop allocation history, customer selling quotes/prices, or worker identities. Other information-only questions remain `clarify`; they must not silently allocate. |
| 4 | Deadline | Parse the message's explicit date, or use the CSV date when no date was stated. Missing/unparseable dates require clarification. A changed, unconfirmed deadline must not fall back to the old CSV date. |
| 5 | Deadline on/before today | Set `already_late=True` and add a note requiring the agent to mention it. This check does not change the behaviour. |
| 6 | Current stage is `PACKING` | `clarify`, `order is already in packing`. |
| 7 | Suggested workshop | Resolve names/IDs case-insensitively. Call `tools.check_eligibility` with the category and pieces; `refuse` with its exact reason when ineligible. |
| 8 | Message quantity differs from CSV | Keep the message quantity and note both values; the mismatch alone does not fail intake. |

Unavailable-data declines remain declines through subsequent checks. Otherwise,
later packing/eligibility checks can override earlier clarifications in the
specified order. The audit retains those intermediate decisions. An unknown
order returns immediately after check 1.

A resolved order supplies canonical customer, product, and category and fills a
missing quantity. Conflicts in those descriptive fields are noted; the original
extraction remains available. Required-field checks finally prevent an allocation
with no order, category, pieces, or deadline. Unknown workshop references cause
clarification for an otherwise-ready allocation and remain in the record.

Dates without a year use the supplied `today.year`; past dates are never rolled
into next year. ISO dates, English month/day dates, and the literal `today` are
supported. Other relative expressions, such as `next Friday`, remain unresolved
for clarification or a future date tool. Intake performs no relative-date,
duration, ETA, or cost arithmetic.

`allocate` means ready for downstream allocation checks. It does not guarantee
that a workshop can make the date. The later agent must mention `already_late`,
apply exclusions and preferences, enforce `must_make_date`, and handle splitting
and `none_makes_date`. Those operations are not performed by intake.

## Record and failures

The dataclass contains the requested extracted fields and final behaviour/reason.
It also retains:

- `raw_llm_json`, the exact `raw_llm_response`, and provider metadata;
- `post_checks`, with each Python rule, evidence, and behaviour/reason before and
  after the rule;
- `already_late`, `notes`, `due_date_text`, and `date_not_confirmed`;
- `candidate_order_ids` and `unresolved_workshops`;
- `must_make_date` and constraints with wording, imposing person, and relaying
  person, so instructions such as "Boss says..." retain their origin.

The model's proposed behaviour, reason, and missing fields remain in raw JSON.
Python derives the final values independently. `record.to_dict()` converts the
date to an ISO string and can be passed directly to `json.dumps`. Intake returns
the evidence; it does not write a log file or mutate the input tables/workshops.

Malformed JSON, schema violations, provider refusal, truncated output, and missing
API/model configuration raise `IntakeError`, not a business `decline`. The error
retains raw response/JSON and metadata when available. Invalid input data raises
`ValueError`. Provider transport/authentication errors propagate from the SDK.
Callers must handle these failures without dispatching a batch. Structured output
validates shape, not truth: extracted facts can still be wrong.

## Tests and evaluation status

`python -m pytest tests/test_intake.py -q -s` processes every inbox line with a
synthetic extraction fixture. Further cases check rule precedence, dates, missing
data, workshop restrictions, constraints, quantity mismatches, JSON serialization,
and the provider request configuration. No live API is used by default.

The comparison reads `eval/labels.csv` only in tests and prints a four-by-four
behaviour confusion matrix. Rows are human expectations; columns are predictions.
Missing labels are excluded and coverage is printed. Disagreements on completed
rows fail the test. Incomplete labeling skips the complete-set comparison unless
`TRACK2_REQUIRE_LABELS=1`, which makes it fail. With no labels, a zero-filled
matrix means **no scored examples**, not perfect results.

Set `TRACK2_INTAKE_REAL_LLM=1` to replace the 30 fixture extractions with real calls.
The remaining unit cases still mock the provider. Temperature zero does not
guarantee identical model outputs across calls. Mock-mode comparisons evaluate
Python post-checks given synthetic extractions, not real LLM accuracy.

At implementation time all 30 human labels were blank. The fixtures contain
synthetic extraction facts, not human gold labels. Intake was therefore built
before the agreed human labeling was complete: disclose this timing in the
evaluation, rather than claiming the set was frozen before development. Preserve
the independent human reviews and reconciliation process, and reserve additional
unseen requests for held-out evaluation. Do not copy intake outputs into labels.
