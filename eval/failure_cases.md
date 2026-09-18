# Inbox evaluation failures

Mode: **live/cached**. Today: **2026-04-01**. Objective: **lateness**.
Human behaviour labels: **0/30**. Operational errors: **30**.

Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.
Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.
Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.
Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.

| expected behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| clarify | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| refuse | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| decline | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |

Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):

| actual behaviour | n | behaviour accuracy | decision accuracy | faithfulness pass rate |
| --- | ---: | --- | --- | --- |
| allocate | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| clarify | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| refuse | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |
| decline | 0 | N/A (0 scored) | N/A (0 scored) | N/A (0 scored) |

Rows with at least one False check: **30**.

## R01

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R01 [07:53] Chen: Need scarves for Harbor Knits sent out today, usual quantities.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-061', 'ORD-108']. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R02

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R02 [07:59] Ravi: Which workshop did we use for the Harbor Knits batch last October?

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-041', 'ORD-061', 'ORD-081', 'ORD-108', 'ORD-109']. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R03

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R03 [08:03] Priya: Can we get the TrendCart order moving? They are chasing.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-005', 'ORD-017', 'ORD-020', 'ORD-082', 'ORD-096', 'ORD-120']. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R04

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R04 [08:08] Boss: ORD-029 needs a home today. 1500 beanies, back by Apr 01.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W2. Reference exclusions: []; preference: None; due: 2026-04-01.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R05

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R05 [08:14] Mei: ORD-066 due date just moved up — will confirm the new date after the call, but line something up.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R06

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R06 [08:18] Chen: Farm out ORD-061 please — 800 scarves for Harbor Knits, ship date Apr 05.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-04-05.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R07

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R07 [08:23] Ravi: ORD-020 — 1200 vests. No special requirements, just make Mar 31.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-31.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R08

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R08 [08:29] Priya: Send ORD-073 (400 hoodies) to FreshStart, their quote was good.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-04-20.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R09

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R09 [08:33] Boss: ORD-045 — 150 vests for Cotton Club, due Apr 09. It's urgent. Cost doesn't matter, just the fastest turnaround.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: fastest; due: 2026-04-09.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R10

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R10 [08:38] Mei: New rush coming in from Loom & Leaf — details to follow, but book capacity somewhere good.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-008', 'ORD-024', 'ORD-035', 'ORD-040', 'ORD-063', 'ORD-073']. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R11

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R11 [08:44] Chen: OldMill is free right now — give them ORD-008.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-04-09.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R12

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R12 [08:48] Ravi: ORD-053 — 800 polo shirts for UrbanThread, due Apr 10. Boss says nothing new to QuickStitch this week, they're swamped.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: ['W1']; preference: None; due: 2026-04-10.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R13

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R13 [08:53] Priya: Finance asks: what price did we quote TrendCart on ORD-120?

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-17.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R14

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R14 [08:59] Boss: QuickStitch for the scarves on ORD-103?

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W2. Reference exclusions: []; preference: None; due: 2026-04-04.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R15

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R15 [09:03] Mei: Boss wants the Loom & Leaf stuff outside asap.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-008', 'ORD-024', 'ORD-035', 'ORD-040', 'ORD-063', 'ORD-073']. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R16

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R16 [09:08] Chen: Northwind Apparel confirmed the reorder: ORD-114, 2000 hoodies. Needs to ship Mar 23, so it has to go out today.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-23.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R17

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R17 [09:14] Ravi: ORD-120 — 1500 vests for TrendCart. Factory is full, this one goes outside. Back by Mar 17 please.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-17.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R18

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R18 [09:18] Priya: Any movement on ORD-999? Customer is chasing.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R19

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R19 [09:23] Boss: That big reorder from last week — send it to whoever is quickest.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-002', 'ORD-005', 'ORD-008', 'ORD-010', 'ORD-015', 'ORD-017', 'ORD-020', 'ORD-024', 'ORD-029', 'ORD-035', 'ORD-036', 'ORD-040', 'ORD-041', 'ORD-045', 'ORD-053', 'ORD-055', 'ORD-061', 'ORD-062', 'ORD-063', 'ORD-066', 'ORD-073', 'ORD-081', 'ORD-082', 'ORD-083', 'ORD-093', 'ORD-095', 'ORD-096', 'ORD-099', 'ORD-103', 'ORD-107', 'ORD-108', 'ORD-109', 'ORD-114', 'ORD-120']. Reference exclusions: []; preference: fastest; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R20

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R20 [09:29] Mei: New one for the network: ORD-103, 2000 scarves for Bright Basics, due Apr 04.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W2. Reference exclusions: []; preference: None; due: 2026-04-04.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R21

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R21 [09:33] Chen: ORD-081 — 1500 crewneck sweaters for Harbor Knits, due Apr 13. Margin is thin on this one — cheapest shop that can still make Apr 13.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W5. Reference exclusions: []; preference: cheapest; due: 2026-04-13.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R22

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R22 [09:38] Ravi: ORD-083 ready to dispatch. 1000 hoodies for Maple & Co, back by Mar 23.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-23.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R23

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R23 [09:44] Priya: ORD-093 — 100 beanies for Maple & Co, due Mar 29. Split it across two shops if that gets it back faster.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-03-29.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R24

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R24 [09:48] Boss: Little Loom does lovely work — ORD-015 to them?

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: []; preference: None; due: 2026-04-16.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R25

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R25 [09:53] Mei: ORD-109 — 500 vests for Harbor Knits, due Apr 13. …and keep it away from BudgetWorks, the last batch came back rough.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W6. Reference exclusions: ['W3']; preference: None; due: 2026-04-13.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R26

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R26 [09:59] Chen: Can someone place ORD-107? 2000 cardigans, Northwind Apparel, due Mar 16.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-16.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R27

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R27 [10:03] Ravi: ORD-055 — 800 crewneck sweaters for Cotton Club, due Mar 31. Cotton Club rejected a batch last month, so lowest defect rate you can get.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: lowest_defect; due: 2026-03-31.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R28

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R28 [10:08] Priya: Sending ORD-002 outside — 1000 crewneck sweaters. Who has room this week? Due Mar 29.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-03-29.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R29

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R29 [10:14] Boss: The vests need to go out this week — who takes them?

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Clarification candidate IDs, if clarification is appropriate: ['ORD-015', 'ORD-020', 'ORD-024', 'ORD-045', 'ORD-109', 'ORD-120']. Reference exclusions: []; preference: None; due: None.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## R30

Failed checks: decision_correct, faithfulness_passed

Raw message:

> R30 [10:18] Mei: Please allocate ORD-099: 1500 polo shirts, Northwind Apparel. Deadline Apr 05.

What the system did:

> No response. OPENAI_INTAKE_MODEL is not configured; no live evaluation was performed

What it should have done:

Human behaviour: Unlabeled: human expected behaviour is still pending. Constraint-aware heuristic choice: W1. Reference exclusions: []; preference: None; due: 2026-04-05.

Layer hypothesis: LLM extraction: execution failed; inspect the captured operational error.

## Unscored checks

Requests with at least one missing reference/check: R01, R02, R03, R04, R05, R06, R07, R08, R09, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24, R25, R26, R27, R28, R29, R30.
See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator.
