# Extraction model benchmark: Sonnet 5.5 against Haiku 5.5

**Status: not yet measured.** The tooling is ready and has been checked offline with
a stubbed model. No paid run has been made, so there are no results in this folder.

## Question

Can Claude Haiku 5.5 replace Claude Sonnet 5.5 as the model that reads dispatch
requests, without losing accuracy, while being faster and cheaper?

## What is held constant

Both models get the same request text, system prompt, JSON schema, order and
workshop data, scenario date (1 April 2026), Python validation, allocation engine,
objective (lateness preset) and queue snapshot. Only the model ID changes.

Settings are the production ones in `src/intake.py`: structured JSON output,
`max_tokens` 4096, no temperature, each model's default effort (Sonnet 5.5 high,
Haiku 5.5 medium), a 60 second timeout and two SDK retries. Server-side fallback is
sent only for models that support it (Sonnet 5.5, not Haiku 5.5); any reply served by
a fallback model is counted and reported. `--effort` runs both models at one effort
level as a sensitivity check.

Production does not use prompt caching, so every call is cold for caching. Calls are
sequential, the model order is shuffled per trial with a fixed seed (5105), and each
call opens a new HTTP connection, as the app does.

## Cases

* **Official set:** the 30 inbox requests in `data/dispatch_requests.txt`.
* **Stress set:** 13 extra requests in `stress_cases.json` (missing order number,
  ambiguous date, changed deadline, urgency, exclusions, refusal, unanswerable and
  unsupported questions, infeasible deadline, unknown order).

Default plan: 43 cases, 2 models, 3 trials, 258 calls.

## What counts as accuracy, honestly

* `eval/labels.csv` and both reviewer files are blank. There is **no human ground
  truth** for the 30 inbox requests yet, so the summary reports *agreement with the
  hand-written test fixtures* for them, and labels it as agreement, not accuracy.
* The stress expectations were written by the author from the order data and have
  **not been reviewed by a person**. They support robustness and model-to-model
  comparison only.
* When `eval/labels.csv` is filled, the summary will say so; accuracy against it
  should then be added before any decision is final.

Fields are scored after Python validation, because that is what the engine receives.

## Measures

Per model: critical-field accuracy (behaviour, order, pieces, category, due date,
exclusions) with Wilson 95% intervals; clarification recall (asks instead of
guessing); schema validity; error, retry and fallback rates; decision agreement on the
official set; model-call latency and full-evaluation latency (mean, p50, p90, p95 from
20 calls up, min, max); mean input and output tokens; estimated cost per successful
request, per 100 and per 1,000 requests.

Cost uses `pricing.json` (official Claude API prices, fetched 22 October 2026). These
are estimates from recorded token counts, not bills.

## Pre-registered decision rule

Fixed before any result was seen. Haiku 5.5 becomes the default only if **all** hold:

1. Critical-field accuracy no more than 2 points below Sonnet's.
2. No unexplained critical extraction error.
3. Every case that needs a clarification gets one (recall 100%).
4. Schema-valid output in at least 99% of calls.
5. Median full evaluation at least 30% faster.
6. Mean cost per successful request at most half of Sonnet's.
7. The test suite still passes with Haiku configured.

Because the accuracy evidence is unreviewed, even a full pass only recommends Haiku
for a repeat run once the human labels exist. Sonnet stays the default until then.

## Commands

```bash
uv run python benchmarks/run_models.py
```

Dry run (the default): prints the plan and estimated spend, sends nothing.

```bash
uv run python benchmarks/run_models.py --execute
```

Paid run, about USD 1.41 for the default plan. Writes `results/<run id>/manifest.json`,
`calls.jsonl`, `calls.csv` and `summary.json`. It never writes to the audit logs,
the queues or `records/traces.jsonl`.

```bash
uv run python benchmarks/run_models.py --summarize benchmarks/results/<run id>
```

Recomputes the summary for an existing run. The Audit page's Performance view reads
the newest `summary.json` and shows "Not yet measured" while there is none.
