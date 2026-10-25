# Inbox evaluation failures

Mode: **live/cache-only**. Today: **2026-04-01**. Objective: **lateness**.
Human behaviour labels: **30/30**. Operational errors: **0**.

Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.
Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.
Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.
Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.

| expected behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 16 | 100.0% (16 scored) | 100.0% (16 scored) | 100.0% (16 scored) |
| clarify | 7 | 100.0% (7 scored) | 100.0% (7 scored) | 100.0% (7 scored) |
| refuse | 4 | 100.0% (4 scored) | 100.0% (4 scored) | 100.0% (4 scored) |
| decline | 3 | 100.0% (3 scored) | 100.0% (3 scored) | 100.0% (3 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 16 | 100.0% (16 scored) | 100.0% (16 scored) | 100.0% (16 scored) |
| clarify | 7 | 100.0% (7 scored) | 100.0% (7 scored) | 100.0% (7 scored) |
| refuse | 4 | 100.0% (4 scored) | 100.0% (4 scored) | 100.0% (4 scored) |
| decline | 3 | 100.0% (3 scored) | 100.0% (3 scored) | 100.0% (3 scored) |

Rows with at least one False check: **3**.

## R10

Failed checks: constraint_honoured

Raw message:

> R10 [08:38] Mei: New rush coming in from Loom & Leaf — details to follow, but book capacity somewhere good.

What the system did:

> Which order do you mean: ORD-073 (Loom & Leaf, Hoodie, 400 pieces); ORD-008 (Loom & Leaf, Polo shirt, 600 pieces); ORD-024 (Loom & Leaf, Vest, 300 pieces); ORD-035 (Loom & Leaf, Beanie, 300 pieces); ORD-040 (Loom & Leaf, Hoodie, 1200 pieces); ORD-063 (Loom & Leaf, Cardigan, 100 pieces)? What is the confirmed due date, including the year? No allocation has been made.

What it should have done:

Human behaviour: clarify. Clarification candidate IDs, if clarification is appropriate: ['ORD-008', 'ORD-024', 'ORD-035', 'ORD-040', 'ORD-063', 'ORD-073']. Reference exclusions: []; preference: None; due: None. Human notes: New Loom & Leaf order, details to follow. No order or quantity yet. Ask for details.

Layer hypothesis: LLM extraction: a requested constraint may have been lost or misattributed; check post-check and allocator propagation.

## R15

Failed checks: constraint_honoured

Raw message:

> R15 [09:03] Mei: Boss wants the Loom & Leaf stuff outside asap.

What the system did:

> Which order do you mean: ORD-073 (Loom & Leaf, Hoodie, 400 pieces); ORD-008 (Loom & Leaf, Polo shirt, 600 pieces); ORD-024 (Loom & Leaf, Vest, 300 pieces); ORD-035 (Loom & Leaf, Beanie, 300 pieces); ORD-040 (Loom & Leaf, Hoodie, 1200 pieces); ORD-063 (Loom & Leaf, Cardigan, 100 pieces)? What is the confirmed due date, including the year? No allocation has been made.

What it should have done:

Human behaviour: clarify. Clarification candidate IDs, if clarification is appropriate: ['ORD-008', 'ORD-024', 'ORD-035', 'ORD-040', 'ORD-063', 'ORD-073']. Reference exclusions: []; preference: None; due: None. Human notes: Loom & Leaf has 6 open orders. Ask which one.

Layer hypothesis: LLM extraction: a requested constraint may have been lost or misattributed; check post-check and allocator propagation.

## R25

Failed checks: constraint_honoured

Raw message:

> R25 [09:53] Mei: ORD-109 — 500 vests for Harbor Knits, due Apr 13. …and keep it away from BudgetWorks, the last batch came back rough.

What the system did:

> Recommended workshop: Nimble Needle (W6). Lowest score among permitted candidates; score 0.0016309012875536481. Estimated completion 2026-04-07, due 2026-04-13; total 5.846153846153847 days, including queue 1.0 days, processing 3.8461538461538463 days and lead 1 days. Days to spare: 6. Estimated total cost: 600.0; cost per piece: 1.2. Expected batch defect probability: 0.05.

What it should have done:

Human behaviour: allocate. Constraint-aware heuristic choice: W6. Reference exclusions: ['W3']; preference: None; due: 2026-04-13. Human notes: Message matches the order. Keep it away from BudgetWorks.

Layer hypothesis: LLM extraction: a requested constraint may have been lost or misattributed; check post-check and allocator propagation.

## Unscored checks

Requests with at least one missing reference/check: R01, R02, R03, R05, R10, R15, R18, R19, R29.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
