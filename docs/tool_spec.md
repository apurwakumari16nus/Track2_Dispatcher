# Allocation tool specification

`src/tools.py` provides eight pure functions: no LLM calls, file or network access,
randomness, or mutation of the batch, workshop profiles, or queues. Each function
returns a plain dictionary or a list of plain dictionaries. Returned dates use
ISO `YYYY-MM-DD` strings so results can be logged as JSON.

It also provides the stateful `ShockMonitor` described below. The monitor updates
its own predictions and flags, while leaving supplied queues unchanged.

`batch` is the simulator's dictionary with `order_id`, `category`, integer
`pieces`, `sent_date`, and `due_date`. `workshops` maps workshop IDs to the
`Workshop` dataclasses from `harness/simulate.py`. `queues` maps workshop IDs to
current queued days, as supplied to the allocator. `today` and `batch.due_date`
accept a Python `date` or an ISO `YYYY-MM-DD` string. Use the batch's `sent_date`
as `today` when evaluating a simulator dispatch.

The inbox uses `workshops.csv` as the **1 April 2026 snapshot**. The default
simulator independently uses it as the **1 January 2026 starting queue**. Neither
is reconstructed from the other. This tool contract supports the default
whole-job mode; a nonempty `batch.from_stage` raises `NotImplementedError` in
eligibility before a stage-incompatible choice can be made. Optional stages
mode in the official harness is not an implemented agent feature.

| name | input | output | purpose | non-goals | failure mode |
| --- | --- | --- | --- | --- | --- |
| `check_eligibility` | `batch`, `workshops` | List of `{workshop_id, name, eligible, reason}`, in workshop iteration order. Reasons are exactly `ok`, `suspended`, `cannot make <category>`, or `batch of N exceeds M-piece cap`. | Reproduce `simulate.eligible_workshops()`: reject any status other than `ACTIVE`, then unsupported category, then pieces above a non-null cap. Report the first failing rule for each workshop. | Does not rank workshops, inspect queues, enforce exclusions, split a batch, or detect closures absent from the profile. | Missing required batch keys raise `KeyError` when accessed. An unrecorded suspension or closure cannot be detected; stale profiles can report a workshop as eligible. |
| `queue_check` | `workshop_id`, `workshops`, `queues` | `{workshop_id, queue_days, capacity_per_day, lead_days}` | Expose `queues[workshop_id]`, `Workshop.capacity`, and `Workshop.lead_days` for the current dispatch. | Does not substitute the initial `queue0`, recalculate queue age, update the queue, or check eligibility. | An unknown workshop ID or missing queue entry raises `KeyError`. A stale queue figure is returned unchanged and can mislead subsequent decisions. |
| `estimate_eta` | `batch`, `workshop_id`, `workshops`, `queues`, `today` | `{workshop_id, queue_days, processing_days, lead_days, total_days, eta_date, due_date, days_to_spare, expected_defect_rate}` | Compute processing as `pieces / capacity`, total as `queue + processing + lead`, ETA as `today + timedelta(days=round(total))`, and spare days as `(due_date - eta_date).days` (negative means late). Return the workshop's unmodified defect probability. | Does not enforce eligibility, draw a defect outcome, add expected rework, predict hidden shocks, or promise an arrival date. | Missing batch keys, workshop IDs, or queue entries raise `KeyError`; zero capacity raises `ZeroDivisionError`; malformed ISO dates raise `ValueError`. The estimate assumes the queue is current; if the workshop is silently closed, the estimate is wrong. A defective batch takes longer than this base estimate. |
| `estimate_cost` | `batch`, `workshop_id`, `workshops` | `{workshop_id, cost_per_piece, total_cost}` | Return `Workshop.cost` and `pieces * Workshop.cost`, matching the simulator's charge. | Does not enforce eligibility, optimize spending, round currency, or add transport, tax, penalties, or rework surcharges absent from the simulator. | Missing pieces or an unknown workshop ID raises `KeyError`. An outdated per-piece rate gives the wrong charge; costs outside the simulator's model are omitted. |
| `overload_probe` | `batch`, `workshop_id`, `workshops`, `queues` | `{workshop_id, queue_before, queue_after, delay_added_to_next_batch_days}` | Compute processing as `pieces / capacity`; report `queue_after = queue_before + processing` and added delay equal to processing. Lead time does not occupy the workshop queue. | Does not mutate queues, check eligibility, simulate elapsed time before another dispatch, add defect rework, or model a hidden closure. | Missing pieces, workshop IDs, or queue entries raise `KeyError`; zero capacity raises `ZeroDivisionError`. A stale queue or extra rework changes the actual queue. Added delay describes another batch sent immediately to this workshop; a later batch may arrive after some work has cleared. |
| `candidates` | `batch`, `workshops`, `queues`, `today`, optional `exclude=None` (list of full workshop names or IDs) | List of merged eligibility, ETA, and cost dictionaries for eligible, unexcluded workshops; every row has `eligible=True` and `reason="ok"`. Stable ascending sort by `total_days`; `[]` when none remain. | Assemble comparable options using the other tools. Match exclusions by stripped, case-insensitive full name or ID; ignore unknown exclusions. Equal totals preserve workshop iteration order. | Does not choose or dispatch a workshop, enforce a due-date cutoff, balance cost or concentration, split batches, or interpret partial names and natural-language constraints. | Propagates the estimation errors for a retained candidate, including `KeyError`, `ZeroDivisionError`, and `ValueError`. Misspelled or partial exclusions match nothing. Stale queues, hidden shocks, and stochastic defects can change the observed ranking. |

## Arithmetic and simulator limits

The agent also uses these evidence-producing tools:

| name | input | output | purpose | non-goals | failure mode |
| --- | --- | --- | --- | --- | --- |
| `order_options` | `orders_df`, list of order IDs | Existing order rows reduced to ID, customer, product, pieces, current stage | Supply concrete CSV-backed clarification choices and their numerical evidence | Does not infer or invent a missing order, classify chat text, or read files | Unknown IDs yield no row; malformed/missing columns or non-integer quantities raise errors. Stale CSV data produces stale clarification choices. |
| `estimate_split` | Batch, workshops, queues, today, optional exclusions and whole-batch comparison workshop ID | Availability/reason or two part estimates, combined duration/ETA/cost, spare days, whole-batch comparison, fastest-single comparison, speed-up and earlier-calendar-ETA flags | Find the fastest legal positive-integer two-workshop split, using existing ETA/cost/eligibility/queue tools for each part | Does not commit allocations, optimize defects/fairness/cost, infer a transport charge, or model consolidation and rework | Returns unavailable when fewer than two suitable shops or caps cannot fit both parts; malformed pieces or an invalid supplied comparison shop raise `ValueError`. Stale queues and hidden closures can invalidate the estimate. |

Split parts run concurrently: the combined duration is the **maximum** of the
part durations, and the combined ETA is the later part ETA. Each part's own lead
time is included in its estimate. Lead time is not summed across parallel parts
to calculate elapsed time. Consequently a split can be faster; this model does
not justify a blanket claim that splits usually lose. Costs are summed using the
existing per-piece model, without inventing a pickup fee.

For each eligible pair, the split tool checks the integer quantities around the
intersection of the two completion-time lines and the feasible cap boundaries.
The maximum of those lines is convex, so this finds the minimum nominal duration
without enumerating every piece count. Ties among evaluated plans use cost, shop
IDs, and quantity for deterministic output. A lower duration can round to the
same calendar ETA. Split results are previews, not simulator dispatches.

The base processing, queue, lead-time, eligibility, and cost rules use the
simulator's profile fields without rounding intermediate values. The tools
assume valid simulator inputs; they do not validate or repair negative pieces,
negative queues, or other malformed numeric data. Direct queue, ETA, cost, and
overload calls can inspect an ineligible workshop; call `check_eligibility` or
`candidates` before making an allocation.

`expected_defect_rate` is the probability that a **batch** is defective, not an
estimate of the fraction of individual pieces that are defective. The simulator
randomly increases processing by 50% when a batch is defective. These tools
report the base processing duration and that probability separately. The shock
scenario can delay a workshop without changing its eligibility profile, so the
inputs available to the tools do not reveal all future delays.

ETA follows the requested `today + round(total_days)` formula. Python's `round`
uses ties to even: `round(2.5) == 2` and `round(3.5) == 4`. There is a small
difference from the harness's date calculation: `simulate.py` rounds the
absolute completion day measured from the run's first dispatch (`day0`), rather
than rounding the duration from `today`. With an odd number of elapsed days
since `day0` and a duration ending in exactly half a day, these two date
calculations can differ by one day. For example, if `day0` is `2026-04-01`,
`today` is `2026-04-02`, and total duration is `2.5` days, the requested formula
returns `2026-04-04`, while the harness returns `2026-04-05`. The tool keeps the
requested formula; it has no `day0` input, and the harness is unchanged.

## ShockMonitor

`ShockMonitor(threshold=3.0)` tracks `expected_queue`, the nominal queue immediately
after the last allocation to each workshop, with a separate allocation-day anchor.
Only workshops that have received an allocation have a prediction. Before every
decision, `observe(queues, day)` compares each observed queue with
`max(0, expected_queue[id] - (day - prediction_day[id]))`. Day zero is the first
decision's date; multiple batches on the same day do not advance the clock.

An excess **strictly greater** than the threshold creates a suspect flag.
`observe` returns new detections as dictionaries with `workshop_id`, `expected`,
`observed`, `jump`, and `flagged_on_day`. `is_flagged(id)` reports whether a flag
is active. Observations within the threshold automatically call `clear(id)`;
explicit clearing is also available. Missing observations leave flags intact.
Negative/nonfinite thresholds and days going backwards raise `ValueError`.

After allocation, the allocator calls `overload_probe` and passes `queue_after`
to `record_allocation(id, queue_after, day)`. For an active suspect, the monitor
subtracts the unexplained excess measured in that day's observation before
storing the new prediction. This preserves the anomaly if the policy must send
another batch there; it does not make the inflated queue its new normal.

Every `DecisionRecord` contains `shock_flags` (copies of all active detections)
and `shock_events` (new detections and recoveries at that decision). Detection
events have `status="suspect"`; recovery events have `status="cleared"`,
`cleared_on_day`, `expected_on_clear`, and `observed_on_clear`. Candidate rows
include `shock_flagged`, and the robustness score reads `is_flagged()`.

The monitor never receives the target, shock dates, or seed. It detects a queue
anomaly only after work has been sent and a later observation reveals the jump.
Defect rework can also trigger a flag, small jumps may be missed, and idle shops
cannot be diagnosed without observations. A flag is not proof of a closure.
Avoidance is a weighted preference, not a hard eligibility rule: other objectives,
an all-late fallback, or a sole eligible shop may still select a suspect.

## Daily shock trace

From the project root, run:

```bash
python eval/shock_trace.py --output eval/shock_trace.csv --events eval/shock_events.json
```

Without `--output`, the CSV goes to stdout and diagnostic messages go to stderr.
The script uses the existing robustness preset and seed 5105 by default, and
compares separate simulator replays of `random_choice` and `Allocator`. Target
identity is derived by the evaluator only, using the separate `random.Random(seed + 6)` draw used by
the v3 harness; it is never passed to the allocator. `--seed` and `--objective`
allow other runs without assuming that W2 is always the target.

The daily CSV includes zero-dispatch days, target pieces by policy, new and
cleared flag counts, and end-of-day suspect state. `ours_pieces_while_suspect`
distinguishes dispatches before and after detection on the same day.
`shock_window` labels days 30 through 43; the workshop reopens on day 44. The
v3 harness delays work starting inside the closure and pauses work crossing
its start. Its queue already includes that future delay: at seed 5105, the
robustness monitor flags W2 on day 26 (expected 9.44, observed 23.44), before
day 30, and clears on day 47. This is queue-anomaly detection, not demonstrated
realistic early warning. Defect rework can cause anomalies too. A new allocator
must be constructed for every seed/scenario so monitor history is not reused.
