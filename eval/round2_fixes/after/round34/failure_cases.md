# Inbox evaluation failures

Mode: **live/cache-only**. Today: **2026-04-01**. Objective: **lateness**.
Human behaviour labels: **34/34**. Operational errors: **0**.

Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.
Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.
Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.
Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.

| expected behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 18 | 100.0% (18 scored) | 100.0% (18 scored) | 100.0% (18 scored) |
| clarify | 8 | 100.0% (8 scored) | 87.5% (8 scored) | 100.0% (8 scored) |
| refuse | 4 | 100.0% (4 scored) | 100.0% (4 scored) | 100.0% (4 scored) |
| decline | 4 | 100.0% (4 scored) | 100.0% (4 scored) | 100.0% (4 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 18 | 100.0% (18 scored) | 100.0% (18 scored) | 100.0% (18 scored) |
| clarify | 8 | 100.0% (8 scored) | 87.5% (8 scored) | 100.0% (8 scored) |
| refuse | 4 | 100.0% (4 scored) | 100.0% (4 scored) | 100.0% (4 scored) |
| decline | 4 | 100.0% (4 scored) | 100.0% (4 scored) | 100.0% (4 scored) |

Rows with at least one False check: **2**.

## R50

Failed checks: decision_correct

Raw message:

> R50 [12:27] Chen: Northwind’s polos need to go out. Can you find a workshop?

What the system did:

> Which order do you mean: ORD-099 (Northwind Apparel, Polo shirt, 1500 pieces); ORD-066 (Northwind Apparel, Polo shirt, 1000 pieces)? What is the confirmed due date, including the year? No allocation has been made.

What it should have done:

Human behaviour: clarify. Clarification candidate IDs, if clarification is appropriate: ['ORD-002', 'ORD-005', 'ORD-008', 'ORD-010', 'ORD-015', 'ORD-017', 'ORD-020', 'ORD-024', 'ORD-029', 'ORD-035', 'ORD-036', 'ORD-040', 'ORD-041', 'ORD-045', 'ORD-053', 'ORD-055', 'ORD-061', 'ORD-062', 'ORD-063', 'ORD-066', 'ORD-073', 'ORD-081', 'ORD-082', 'ORD-083', 'ORD-093', 'ORD-095', 'ORD-096', 'ORD-099', 'ORD-103', 'ORD-107', 'ORD-108', 'ORD-109', 'ORD-114', 'ORD-120']. Reference exclusions: []; preference: None; due: None. Human notes: Two open Northwind polo orders: ORD-066, ORD-099. KEEP: customer and product, no ID.

Layer hypothesis: post-check/template: clarification candidates or the displayed question differ from the independently matched orders.

## R65

Failed checks: constraint_honoured

Raw message:

> R65 [13:23] Ravi: ORD-008, 600 polos for Loom & Leaf, due Apr 9. Boss said don’t assign anything new to Nimble Needle, they’re short-staffed.

What the system did:

> Recommended workshop: QuickStitch (W1). Lowest score among permitted candidates; score 0.001891891891891892. Estimated completion 2026-04-08, due 2026-04-09; total 7.0 days, including queue 4.0 days, processing 2.0 days and lead 1 days. Days to spare: 1. Estimated total cost: 900.0; cost per piece: 1.5. Expected batch defect probability: 0.12.

What it should have done:

Human behaviour: allocate. Constraint-aware heuristic choice: W1. Reference exclusions: ['W6']; preference: None; due: 2026-04-09. Human notes: QuickStitch, SteadyHands and GiantWeave still make Apr 9. KEEP: exclusion is from Boss, sent by Ravi.

Layer hypothesis: LLM extraction: a requested constraint may have been lost or misattributed; check post-check and allocator propagation.

## Unscored checks

Requests with at least one missing reference/check: R50, R55, R58, R60, R61, R62, R64, R66, R72, R74.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
