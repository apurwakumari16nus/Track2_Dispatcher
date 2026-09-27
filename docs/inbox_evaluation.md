# Inbox evaluation

From the project root with the virtual environment active:

```bash
python eval/run_inbox.py
```

Live mode requires `OPENAI_API_KEY` and `OPENAI_INTAKE_MODEL` in `.env` or the
environment. `--model MODEL` overrides the configured model. The provider request
uses intake's existing strict schema and temperature zero. Human behaviour
accuracy requires completed `eval/labels.csv`; the runner never fills those labels.

## Outputs

- `eval/inbox_results.csv`: exactly one row per request, with the requested fields.
  Boolean cells are `True`, `False`, or blank when a reference is unavailable.
- Printed class summaries: the primary summary groups by **human expected
  behaviour**, including misclassified and errored requests in their true class.
  A second diagnostic summary groups by actual behaviour and includes unlabeled
  requests. Each rate displays its scored denominator; `N/A` is not a zero score.
- `eval/failure_cases.md`: every request with any False check, including its raw
  text, actual explanation or error, human expectation (when available), independent
  reference facts/choice, failed checks, and a layer hypothesis. Unscored requests
  are listed separately. An infeasible deadline is reported honestly.
- `eval/inbox_audit.json`: complete responses, independent references, benchmark
  choices, cache keys, mode/model, queue policy, and input file hashes. Use this
  to investigate failures; the CSV is deliberately compact.

Use `--output-dir PATH` to keep experiments separate. The output directory does
not affect the shared cache location; override that with `--cache-dir PATH`.

## Replay and cost

Provider replies are cached under `eval/cache/`, which Git ignores. A key covers
the entire system prompt (including schema, date, workshop directory and customer/
product catalog), raw message, model, temperature, cache version, and provider
mode. Only matching entries are reused. Provider content and metadata are preserved;
post-checks, allocator decisions, and evaluation always rerun against current code
and data. Changing labels or allocation queues does not need a new extraction.
Changing the extraction prompt, model, or message does.

```bash
python eval/run_inbox.py --offline
```

Offline mode reads matching cache entries without an API key. Keep the model
configured, or pass the original model with `--model`, to identify those entries.
Cache misses become visible execution errors and make no network request. Reuse
is free and deterministic for unchanged code/data and the stored responses;
temperature zero alone does not guarantee identical fresh model generations.
Corrupt cache entries fail visibly instead of silently triggering paid calls.
Provider refusals with response evidence are cached; setup and transport errors
are retriable and are not saved as permanent model responses.

For a clearly marked synthetic dry run:

```bash
python eval/run_inbox.py --mock --output-dir Apurwa/validation/mock_inbox
python eval/run_inbox.py --mock --offline --output-dir Apurwa/validation/mock_inbox
```

`Apurwa/` is a Git-ignored local folder for personal materials and validation
outputs, excluded from the submission. These synthetic outputs are kept separate
from the final live evaluation evidence in `eval/`.

Mock mode uses the existing CI extraction fixtures, a separate cache namespace,
and a fixture-content hash. It never becomes live mode automatically and does
not measure model accuracy. Changing the inbox invalidates these fixtures until
they are reviewed. No human labels or expected behaviours are taken from fixtures.

## Evaluation rules

Every request calls the standalone `agent.handle()` with **2026-04-01** and
`PRESETS['lateness']`. Each gets fresh history and the same `Workshop.queue0`
snapshot, read directly from `workshops.csv` as **1 April 2026**. The January
simulator replay is separate and is not used to derive this snapshot. This evaluates independent inbox requests, not a sequential dispatch
simulation. The agent still applies its per-request objective overrides.

The reference checks do not reuse the agent's parsed fields or candidate list
as their own truth. Human expected order, pieces, category, and due date take
precedence. Missing factual labels fall back to literal IDs, named customers,
product names/plurals, explicit quantities, dates, and the supplied order CSV.
An explicitly unconfirmed new date never falls back to the old CSV date.

This is a small, inspectable reference grammar for the supplied inbox, not a
general language interpreter and not a replacement for human labels. Exclusions
recognize `avoid`, `not`, `exclude`, `nothing new to`, and `keep it away from`
followed by a known name/ID. Preferences recognize cheapest, lowest defect,
fastest/quickest, and cost-does-not-matter wording. Explicit make-date requirements
and split instructions are recorded. Human constraint text is also considered;
constraints outside this grammar need manual review and may be unscored. New
wordings should be reviewed before extending the evaluation set.

| Check | Definition |
| --- | --- |
| `behaviour_correct` | Exact agreement with the human `expected_behaviour`; blank if unlabeled. |
| `decision_correct` for allocate/refuse | Correct branch and factual batch, with the chosen/alternative shop equal to the independent constrained heuristic. Eligibility comes from `simulate.eligible_workshops`; ranking uses `earliest_finish`. Cheapest restricts to minimum-cost on-time shops; lowest defect restricts to minimum-defect shops. Earliest finish breaks ties in input order. If all eligible shops are late, the public allocator contract uses a least-late/earliest-finish fallback regardless of preference. |
| `decision_correct` for clarify | No allocation and the exact independent candidate set, with order ID/product/pieces displayed. Already-identified packing or unconfirmed-date requests instead need the corresponding clarification. |
| `decision_correct` for decline | It declines and makes no allocation. Correctness of declining rather than another behaviour remains the separate human-label check. |
| `faithfulness_passed` | Recompute `faithfulness.check` against the response's recorded tool evidence. This verifies numerical support, not semantic correctness. Number-free replies pass vacuously. |
| `constraint_honoured` | Check independent exclusions, preference, split permission/preview, deadline requirement, chosen-shop eligibility, and exclusion attribution. Explicit hard date requirements fail if the chosen fallback is late, even when the agent correctly discloses that impossibility. No-choice clarifications can respect a constraint without allocating. |
| `already_late_flagged_when_needed` | When the independently determined due date is on/before today, require both the response flag and prominent `ALREADY LATE` text. True when no overdue warning is needed; blank if the due date is unresolved. |

When behaviour is unlabeled, the decision diagnostic uses the **actual** branch
and is explicitly conditional. A perfect conditional score does not establish
that the branch was appropriate. Once a human label exists, it determines which
decision check is appropriate. Unknown facts remain unscored instead of being
silently replaced by whatever the agent extracted.

Operational exceptions generate `actual_behaviour=error`, failed decision and
faithfulness delivery checks, and a failure entry. They never masquerade as a
business decline. The runner continues through the other requests and exits
with status 2 if any execution failed. These delivery failures are distinguishable
from incorrect numerical claims in the notes/audit. Errors in the evaluator itself must
raise rather than blame the agent. Layer hypotheses are review aids, not proven
causes or evidence that an infeasible deadline could have been met.

## Validation

```bash
python -m pytest tests/test_run_inbox.py -q
```

Tests cover all thirty inbox lines, byte-identical cached CSV replay, model/prompt/
message invalidation, cached refusals, corrupt entries, independent decision and
constraint checks, missing labels, operational errors, and complete failure reports.


## Data v3 revision

Nine requests changed: R04, R06, R07, R16, R17, R22, R23, R26 and R27. Their
synthetic extraction fields and input fingerprint were reviewed together.
Messages, prompts and fixture contents are cache-key inputs; old extractions
cannot be silently reused for changed messages. R20, R28 and R30 remain
intentionally impossible; inspect their numerical warnings and alternatives.
All human label files remain human work: re-review the updated source, record
the data version, and do not copy synthetic fixture expectations into labels.
