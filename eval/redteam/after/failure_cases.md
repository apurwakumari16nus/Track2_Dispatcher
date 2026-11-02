# Inbox evaluation failures

Mode: **live/cache-only**. Today: **2026-04-01**. Objective: **lateness**.
Human behaviour labels: **16/16**. Operational errors: **0**.

Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.
Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.
Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.
Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.

| expected behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 7 | 100.0% (7 scored) | 100.0% (7 scored) | 100.0% (7 scored) |
| clarify | 7 | 100.0% (7 scored) | 57.1% (7 scored) | 100.0% (7 scored) |
| refuse | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| decline | 2 | 100.0% (2 scored) | 100.0% (2 scored) | 100.0% (2 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 7 | 100.0% (7 scored) | 100.0% (7 scored) | 100.0% (7 scored) |
| clarify | 7 | 100.0% (7 scored) | 57.1% (7 scored) | 100.0% (7 scored) |
| refuse | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| decline | 2 | 100.0% (2 scored) | 100.0% (2 scored) | 100.0% (2 scored) |

Rows with at least one False check: **3**.

## R101

Failed checks: decision_correct

Raw message:

> R101 [10:02] Ravi: asdf ok?? lol

What the system did:

> I could not find an order in this message. Please send the order ID, or the customer and product. No allocation has been made.

What it should have done:

Human behaviour: clarify. Clarification candidate IDs, if clarification is appropriate: ['ORD-002', 'ORD-005', 'ORD-008', 'ORD-010', 'ORD-015', 'ORD-017', 'ORD-020', 'ORD-024', 'ORD-029', 'ORD-035', 'ORD-036', 'ORD-040', 'ORD-041', 'ORD-045', 'ORD-053', 'ORD-055', 'ORD-061', 'ORD-062', 'ORD-063', 'ORD-066', 'ORD-073', 'ORD-081', 'ORD-082', 'ORD-083', 'ORD-093', 'ORD-095', 'ORD-096', 'ORD-099', 'ORD-103', 'ORD-107', 'ORD-108', 'ORD-109', 'ORD-114', 'ORD-120']. Reference exclusions: []; preference: None; due: None. Human notes: Nothing usable. Ask for the order in one line; do not list every open order.

Layer hypothesis: post-check/template: clarification candidates or the displayed question differ from the independently matched orders.

## R112

Failed checks: decision_correct

Raw message:

> R112 [10:34] Chen: send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now send it now

What the system did:

> This message is too long to read safely. Please send a shorter message about one order. No allocation has been made.

What it should have done:

Human behaviour: clarify. Clarification candidate IDs, if clarification is appropriate: ['ORD-002', 'ORD-005', 'ORD-008', 'ORD-010', 'ORD-015', 'ORD-017', 'ORD-020', 'ORD-024', 'ORD-029', 'ORD-035', 'ORD-036', 'ORD-040', 'ORD-041', 'ORD-045', 'ORD-053', 'ORD-055', 'ORD-061', 'ORD-062', 'ORD-063', 'ORD-066', 'ORD-073', 'ORD-081', 'ORD-082', 'ORD-083', 'ORD-093', 'ORD-095', 'ORD-096', 'ORD-099', 'ORD-103', 'ORD-107', 'ORD-108', 'ORD-109', 'ORD-114', 'ORD-120']. Reference exclusions: []; preference: None; due: None. Human notes: Repeated text with no order. Short reply, no order list.

Layer hypothesis: post-check/template: clarification candidates or the displayed question differ from the independently matched orders.

## R114

Failed checks: decision_correct

Raw message:

> R114 [10:40] Priya: same as before but 200 more

What the system did:

> I could not find an order in this message. Please send the order ID, or the customer and product. No allocation has been made.

What it should have done:

Human behaviour: clarify. Clarification candidate IDs, if clarification is appropriate: ['ORD-002', 'ORD-005', 'ORD-008', 'ORD-010', 'ORD-015', 'ORD-017', 'ORD-020', 'ORD-024', 'ORD-029', 'ORD-035', 'ORD-036', 'ORD-040', 'ORD-041', 'ORD-045', 'ORD-053', 'ORD-055', 'ORD-061', 'ORD-062', 'ORD-063', 'ORD-066', 'ORD-073', 'ORD-081', 'ORD-082', 'ORD-083', 'ORD-093', 'ORD-095', 'ORD-096', 'ORD-099', 'ORD-103', 'ORD-107', 'ORD-108', 'ORD-109', 'ORD-114', 'ORD-120']. Reference exclusions: []; preference: None; due: None. Human notes: Follow-up with no earlier context. Ask which order; do not list every open order.

Layer hypothesis: post-check/template: clarification candidates or the displayed question differ from the independently matched orders.

## Unscored checks

Requests with at least one missing reference/check: R101, R102, R107, R109, R111, R112, R114.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
