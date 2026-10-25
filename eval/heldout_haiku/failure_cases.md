# Inbox evaluation failures

Mode: **live/cached**. Today: **2026-04-01**. Objective: **lateness**.
Human behaviour labels: **16/16**. Operational errors: **0**.

Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.
Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.
Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.
Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.

| expected behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 9 | 100.0% (9 scored) | 77.8% (9 scored) | 100.0% (9 scored) |
| clarify | 2 | 100.0% (2 scored) | 100.0% (2 scored) | 100.0% (2 scored) |
| refuse | 3 | 100.0% (3 scored) | 100.0% (3 scored) | 100.0% (3 scored) |
| decline | 2 | 50.0% (2 scored) | 50.0% (2 scored) | 100.0% (2 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 9 | 100.0% (9 scored) | 77.8% (9 scored) | 100.0% (9 scored) |
| clarify | 3 | 66.7% (3 scored) | 66.7% (3 scored) | 100.0% (3 scored) |
| refuse | 3 | 100.0% (3 scored) | 100.0% (3 scored) | 100.0% (3 scored) |
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

## R36

Failed checks: decision_correct, constraint_honoured

Raw message:

> R36 [11:07] Mei: ORD-082, 600 Beinie for TrendCart, due May 1. Ensure quality.

What the system did:

> Recommended workshop: Nimble Needle (W6). Lowest score among permitted candidates; score 0.00180672268907563. Estimated completion 2026-04-08, due 2026-05-01; total 6.615384615384615 days, including queue 1.0 days, processing 4.615384615384615 days and lead 1 days. Days to spare: 23. Estimated total cost: 720.0; cost per piece: 1.2. Expected batch defect probability: 0.05.

What it should have done:

Human behaviour: allocate. Constraint-aware heuristic choice: W4. Reference exclusions: []; preference: lowest_defect; due: 2026-05-01. Human notes: Matches the order (typo in product). 'Ensure quality' read as lowest defect rate.

Layer hypothesis: allocator: selected workshop or clarification options differ from the reference; inspect filtering, objective and template.

## R44

Failed checks: decision_correct

Raw message:

> R44 [11:55] Ravi: Maple & Co are chasing ORD-083, it's already late. Can we get the hoodies out today?

What the system did:

> ALREADY LATE: the requested deadline is today or in the past.
> AWKWARD CASE: none_makes_date. No eligible whole-batch option meets the deadline. Accept lateness explicitly or review splitting before proceeding.
> Recommended workshop: QuickStitch (W1). Least-late whole-batch fallback; score 0.21270022883295192. Estimated completion 2026-04-09, due 2026-04-01; total 8.333333333333334 days, including queue 4.0 days, processing 3.3333333333333335 days and lead 1 days. Days to spare: -8. Estimated total cost: 1500.0; cost per piece: 1.5. Expected batch defect probability: 0.12.

What it should have done:

Human behaviour: allocate. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-23. Human notes: Due Mar 23 has already passed (earliest return Apr 9). No date in the message, so the file date is used. Say so and give options.

Layer hypothesis: post-check: extracted or reconciled facts disagree with the independent reference.

## Unscored checks

Requests with at least one missing reference/check: R37, R42.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
