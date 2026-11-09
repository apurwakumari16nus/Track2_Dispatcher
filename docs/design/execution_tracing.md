# Execution tracing

How Threadline measures where an evaluation spends its time. Code: `src/tracing.py`.

## What is measured

Every press of **Evaluate request** runs inside one trace (`src/ui/dispatch.py`, `evaluate`).
A trace is a tree of spans timed with `time.perf_counter_ns` (monotonic, not wall
clock). Spans in execution order:

| Span | Where | Stage group |
|---|---|---|
| `evaluation` (root) | dispatch.evaluate | Other processing (its own time only) |
| `prepare` | desk.make_preview | Other processing |
| `llm.prepare` | intake.parse_request | Parsing and validation |
| `llm.call` | intake.parse_request, attribute `source` | Language model request |
| `llm.parse`, `llm.validate` | intake.parse_request | Parsing and validation |
| `validation` | intake._post_checks (order lookup, dates, exclusions) | Parsing and validation |
| `order_lookup`, `allocation`, `eligibility`, `evidence` | agent.py | Python decision engine |
| `verification` | desk.make_preview (replay and inventory) | Python decision engine |
| `explanation_check` | agent.py and desk.make_preview | Evidence check |

A stage that does not run (allocation after a clarification) is recorded as
`skipped` with a reason, not left out.

## No double counting

Each span's **own time** is its duration minus its direct children's durations.
The stage bar and the Performance chart add up own times, so the stages sum to the
root total. Span durations in the span table include their children, as labelled.

## Provider timing

For a live call, `llm.call` covers SDK client creation, the HTTP request, any SDK
retries and response parsing. Inside it, `provider_ms` in the metadata is the time
from just before the request to the parsed response, and every HTTP attempt is timed
through httpx event hooks (`attempts`, with the retry number from the
`x-stainless-retry-count` header). Model-internal inference time cannot be observed
from the client; the provider time always includes the network.

Measured once on 22 October 2026 (R09, Sonnet 5.5, one attempt): total 3.96 s,
of which the provider call was 3.26 s; parsing, validation, the engine and the
evidence check together took under 10 ms. This is one call, not a benchmark.

## Errors

The root span always closes. On an exception the trace is marked `error` with a
category (`timeout`, `auth`, `rate_limit`, `provider_unavailable`, `invalid_output`,
`refusal`, `incomplete`, `rehearsal_miss`, or the exception class name); the
message itself is not stored.

## What is stored, and what is not

`records/traces.jsonl` (git-ignored), newest 500 traces, file-locked appends.
Stored: trace ID, UTC start, status, error category, span names and timings,
source (live, cached, fixture), request ID, a 12-character SHA-256 digest of the
message, objective, scenario date, provider, requested and served model, token
counts, HTTP attempt timings, tool-call count, chosen workshop, guided-demo flag.

Not stored: the message text, the model's raw reply, API keys, request or response
headers.

A confirmed decision record stores its `trace_id`, so the Audit record and the
Performance view link to each other. Traces are diagnostics: they never change a
recommendation and are not decision records.

## Where to see it

* **Dispatch:** a one-line timing bar under the request after each evaluation;
  "View execution trace" opens the span table in the inspector.
* **Audit Trail, Performance diagnostics:** every trace with filters (request or
  trace ID, source, status, date), time by stage for the newest 15, the span table
  for any trace, a link to its decision record, and JSONL export.
