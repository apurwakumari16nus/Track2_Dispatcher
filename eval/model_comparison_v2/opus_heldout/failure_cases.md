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
| refuse | 3 | 100.0% (3 scored) | 100.0% (3 scored) | 100.0% (3 scored) |
| decline | 2 | 50.0% (2 scored) | 50.0% (2 scored) | 100.0% (2 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 9 | 100.0% (9 scored) | 100.0% (9 scored) | 100.0% (9 scored) |
| clarify | 3 | 66.7% (3 scored) | 66.7% (3 scored) | 100.0% (3 scored) |
| refuse | 3 | 100.0% (3 scored) | 100.0% (3 scored) | 100.0% (3 scored) |
| decline | 1 | 100.0% (1 scored) | 100.0% (1 scored) | 100.0% (1 scored) |

Rows with at least one False check: **1**.

## R34

Failed checks: behaviour_correct, decision_correct

Raw message:

> R34 [10:45] Boss: is ORD-069 delivered to client?

What the system did:

> Do you want an order-status answer, or are you asking to allocate this order? No allocation has been made.

What it should have done:

Human behaviour: decline. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-04-09. Human notes: Asks if it was delivered. File shows it completed Mar 30 but has no delivery record. Say what we know, not that it was delivered.

Layer hypothesis: post-check: final classification disagrees with the human label; review extraction and rule precedence.

## Unscored checks

Requests with at least one missing reference/check: R37, R42.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
