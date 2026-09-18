# Agent responses, faithfulness, and records

`agent.handle(message, today, orders_df, workshops, queues, config)` handles one
chat request using fresh allocator history. For repeated decisions in the same
run, create `Agent(config)` once and call its `handle` method. Do not share that
instance between unrelated runs. The caller supplies current queues; the agent
does not advance or mutate them.

## Behaviour

| Intake result | Agent action |
| --- | --- |
| `clarify` | Ask concrete questions. Ambiguous-order choices include verified order IDs, customers, products, and pieces. No allocator call. |
| `decline` | Identify the missing source: an authoritative order row, historical workshop dispatch records, customer sales quotes, or worker assignments. No guessing or allocation. |
| `refuse` | Recheck the suggested workshop with `check_eligibility` and quote its reason. Preview the best remaining alternative, respecting exclusions/preferences. No allocation is committed. If the date or other required facts are unresolved, request them before estimating an alternative. |
| `allocate` | Run the allocator with exclusions and objective overrides. Report the chosen candidate through a fixed template. If permitted, evaluate a split as an additional preview. |

`fastest` selects the lateness preset; `lowest_defect` selects the defect preset.
`cheapest` selects cost weight alone and enforces `must_make_date=True`. An
explicit date constraint also survives other preferences. Overrides apply to
one request without replacing the session's base objective or clearing history.

When no whole-batch candidate meets the date, the existing allocator supplies a
least-late fallback and options. The agent displays `none_makes_date` prominently
and requires acceptance of lateness or review of splitting; it does not count the
fallback as an allocation. `no_eligible` similarly requires human review. These
flags describe whole-batch choices, even if a split preview provides an option.
`already_late` is displayed prominently regardless of the intake behaviour.

The allocator's `decide()` normally commits history, so the agent runs it on a
copy. After the explanation passes faithfulness, an ordinary `allocate` result
with no late/awkward flag commits that copy to the session. Refusals and awkward
alternatives remain previews. `allocation_committed` describes local allocator
history, not an external workshop dispatch. No split is automatically committed.

Split estimates use two positive integer parts at distinct legal, unexcluded
workshops. Each has its own lead time, but concurrent completion is the later
ETA. The explanation reports quantities, part ETAs, combined cost, and whether
the split is faster than the chosen whole-batch option. The record also compares
against the fastest whole-batch option, so an expensive or slow objective choice
cannot disguise that benchmark. See [tool_spec.md](tool_spec.md).

## Response and audit

`AgentResponse` contains:

- `parsed_request`, including raw LLM extraction, Python checks, notes, and
  original constraint wording and attribution;
- `decision_record`, a JSON-ready dictionary, plus `decision_record_json` for
  callers needing a JSON string;
- `explanation_text`, `already_late`, `awkward_case`, `faithfulness`, and
  `allocation_committed`.

`response.to_dict()` serializes the entire response, including ISO dates. Even
clarifications and declines have a record with no chosen workshop. Numerical
evidence for order choices, eligibility, queue probes and split estimates is
stored under `DecisionRecord.tool_outputs`. Allocator candidates already carry
their ETA/cost/queue values and scores. Constraints retain the sender, requested
exclusions/preferences, and statements with `imposed_by` and `relayed_by`.

Explanations use templates only. No extra LLM call for tone is made. Intake remains
the sole LLM boundary. A template with unsupported numbers raises an error before
history is committed. API/intake/data errors also propagate to the caller; the UI
should display an operational error without implying an allocation succeeded.

## What numerical faithfulness proves

`faithfulness.check(text, record)` returns `passed`, `numbers_in_text`, and
`unmatched`. It accepts a record dataclass, dictionary, or JSON string. Evidence
comes only from `candidates`, `ineligible`, and `tool_outputs`; raw model output,
constraints, timestamps and prose do not authorize numerical claims.

Integers, decimals, signed/scientific notation, formatted money, percentages,
full ISO/English dates and digit-bearing IDs are recognized. Money formatting
does not change the amount; a percentage maps to its fraction. Dates and IDs
remain whole tokens: a workshop ID does not justify a number of days. Ambiguous
numeric dates and dates without a year fail closed. Templates retain the tool's
exact numeric values; no rounding tolerance is used. This can produce long
decimal strings when the underlying tool has them.

This is numerical membership, not semantic or decision correctness. It cannot
prove that a supported number describes the correct workshop, unit, or quantity;
nor does it verify number words, number-free claims, or omissions. A swapped cost
and duration can pass. A response without numerals passes vacuously. Keep the
template tests and assess decision correctness separately; do not present this
check as a complete hallucination detector. `tool_outputs` must only receive
actual tool results, never arbitrary LLM prose added to make the check pass.

## Logging and UI reads

Logging is explicit, not an automatic side effect of `handle`:

```python
from agent import Agent
from objectives import PRESETS
import records

session = Agent(PRESETS["hybrid_lateness_fairness"])
response = session.handle(message, today, orders_df, workshops, queues)
saved = records.append(response)
history = records.load()
```

The default path is project-relative `records/decisions.jsonl`, independent of
the working directory. Each row contains the complete response, a UTC logging
timestamp, sender, and constraints with their attribution. The decision's
timestamp retains the supplied business date separately. `append` rechecks
faithfulness and JSON validity before writing. It appends rather than overwrites.
`load` returns an empty list before the file exists and raises a line-numbered
error for corrupt records. A UI should append once per handled request, not on
every rerender; automatic deduplication is not performed.

Local cooperating writers/readers use POSIX advisory file locks (macOS/Linux).
For Windows or a multi-host service, replace this storage adapter. Logs are
ignored by Git and contain the chat text and audit evidence; they are not sent
to the LLM by the logging module.

## Validation

```bash
python -m pytest tests/test_agent.py tests/test_faithfulness.py tests/test_split.py tests/test_records.py -q
```

The inbox integration uses synthetic extraction fixtures for all thirty requests;
it does not measure live model accuracy or replace human labels. Split tests
include hand calculations, a slower split, caps that require splitting, and an
exhaustive small-batch reference search. Agent tests cover no-allocation paths,
objective/date constraints, exclusions, session history, split previews, flags,
and unsupported-number failure before commitment. Persistence tests use temporary
files rather than writing fabricated decisions to the project's log.
