# Inbox evaluation failures

Mode: **live/cached**. Today: **2026-04-01**. Objective: **lateness**.
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

Rows with at least one False check: **0**.

## Unscored checks

Requests with at least one missing reference/check: R01, R02, R03, R05, R10, R15, R18, R19, R29.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
