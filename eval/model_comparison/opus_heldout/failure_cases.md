# Inbox evaluation failures

Mode: **live/cached**. Today: **2026-04-01**. Objective: **lateness**.
Human behaviour labels: **16/16**. Operational errors: **0**.

Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.
Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.
Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.
Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.

| expected behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 9 | 100.0% (9 scored) | 100.0% (9 scored) | 100.0% (9 scored) |
| clarify | 2 | 100.0% (2 scored) | 100.0% (2 scored) | 100.0% (2 scored) |
| refuse | 3 | 100.0% (3 scored) | 66.7% (3 scored) | 100.0% (3 scored) |
| decline | 2 | 50.0% (2 scored) | 50.0% (2 scored) | 100.0% (2 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 9 | 100.0% (9 scored) | 100.0% (9 scored) | 100.0% (9 scored) |
| clarify | 3 | 66.7% (3 scored) | 66.7% (3 scored) | 100.0% (3 scored) |
| refuse | 3 | 100.0% (3 scored) | 66.7% (3 scored) | 100.0% (3 scored) |
| decline | 1 | 100.0% (1 scored) | 100.0% (1 scored) | 100.0% (1 scored) |

Rows with at least one False check: **3**.

## R34

Failed checks: behaviour_correct, decision_correct

Raw message:

> R34 [10:45] Boss: is ORD-069 delivered to client?

What the system did:

> Do you want an order-status answer, or are you asking to allocate this order? No allocation has been made.

What it should have done:

Human behaviour: decline. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-04-09. Human notes: Asks if it was delivered. File shows it completed Mar 30 but has no delivery record. Say what we know, not that it was delivered.

Layer hypothesis: post-check: final classification disagrees with the human label; review extraction and rule precedence.

## R38

Failed checks: decision_correct, constraint_honoured

Raw message:

> R38 [11:25] Boss: Can we send ORD-095 to Little Loom? They offer good quality

What the system did:

> Little Loom (W4) cannot take this batch: cannot make TOPS. Best alternative under the selected objective: SteadyHands (W2). Lowest score among permitted candidates; score 0.03. Estimated completion 2026-04-10, due 2026-04-26; total 9.205882352941178 days, including queue 2.5 days, processing 4.705882352941177 days and lead 2 days. Days to spare: 16. Estimated total cost: 1040.0; cost per piece: 1.3. Expected batch defect probability: 0.03. This alternative is an offer only; no allocation has been made.

What it should have done:

Human behaviour: refuse. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-04-26. Human notes: Little Loom only makes accessories; a hoodie is a top. Refuse and offer another workshop.

Layer hypothesis: allocator: selected workshop or clarification options differ from the reference; inspect filtering, objective and template.

## R44

Failed checks: constraint_honoured

Raw message:

> R44 [11:55] Ravi: Maple & Co are chasing ORD-083, it's already late. Can we get the hoodies out today?

What the system did:

> ALREADY LATE: the requested deadline is today or in the past.
> AWKWARD CASE: none_makes_date. No eligible whole-batch option meets the deadline. Accept lateness explicitly or review splitting before proceeding.
> Recommended workshop: QuickStitch (W1). Least-late whole-batch fallback; score 0.36387604070305274. Estimated completion 2026-04-09, due 2026-03-23; total 8.333333333333334 days, including queue 4.0 days, processing 3.3333333333333335 days and lead 1 days. Days to spare: -17. Estimated total cost: 1500.0; cost per piece: 1.5. Expected batch defect probability: 0.12.

What it should have done:

Human behaviour: allocate. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-23. Human notes: Due Mar 23 has already passed (earliest return Apr 9). No date in the message, so the file date is used. Say so and give options.

Layer hypothesis: allocator: no eligible shop can meet the required date; the disclosed fallback still cannot satisfy it.

## Unscored checks

Requests with at least one missing reference/check: R37, R42.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
