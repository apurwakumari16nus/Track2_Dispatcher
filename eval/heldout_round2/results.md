# Round 2 held-out results

34 new requests (R48 to R81), run once on 2026-11-07 with Claude Sonnet 5.5 at commit `95a0815`.
Scenario date 2026-04-01, lateness objective. Fingerprints were saved before the run in `freeze_manifest.txt`.

## Score as frozen

| Check | Round 2 (34) | Earlier held-out (16, development) | All 50 (not clean) |
| --- | ---: | ---: | ---: |
| Behaviour correct | 33/34 | 15/16 | 48/50 |
| Decision correct | 32/34 | 15/16 | 47/50 |
| Explanation numbers verified | 34/34 | 16/16 | 50/50 |
| Constraint honoured (scored rows) | 31/33 | 16/16 | 47/49 |
| Already-late flag (scored rows) | 24/25 | not recalculated | not recalculated |

Quote the Round 2 column as the main result. The earlier 16 were used for model choice and fixes.

## Failed checks

| ID | Failed | Cause | Type |
| --- | --- | --- | --- |
| R63 | Behaviour, decision, late flag | The model copied "due today", but the date reader accepts only the bare word "today". The system asked for a date it had been given. | System |
| R52 | Constraint | SteadyHands was excluded and not chosen, but the constraint list is empty, so who imposed it was not recorded. | System, minor |
| R50 | Decision | The reply named the right two orders. The evaluator did not match "Northwind" or "polos", so it expected all 34 open orders. | Evaluator |
| R65 | Constraint | The system recorded Boss, relayed by Ravi, which is right. The evaluator looks for "boss says", and the message says "Boss said". | Evaluator |

## Passed the checks, but found in manual review

- **R61:** "Please assign ORD-036 to SteadyHands" was answered with Nimble Needle, and the reply never mentions SteadyHands. Both return Apr 11. The label did not state an expected workshop and the constraint was unscored, so it passed. The label was weak, and the system's handling is a gap.
- **R49, R55, R69:** information questions open with "ALREADY LATE", which does not help the person asking. On R55 the question is about last December, but it was matched to ORD-114.
- **Clarifications (R50, R62, R72, R74):** "Which order?" is followed by a request for a due date, even though the date comes with the order.

## Limits

- Requests were drafted by Claude after reading the guardrail docs, then rephrased by the team. Orders began from a seeded draw but were limited by request type and adjusted by hand. This differs from the plan in `submission/Evaluation.md`.
- Labels were drafted by Claude and had not been reviewed by the team at the time of the run. R58 and R66 are judgement calls; both passed as labelled.
- Rephrasing removed the day/month date from R57, so that guard is not tested here.
- One model, one run. Any fix made from these results needs new unseen requests to count as clean.

No code, evaluator or label was changed after the run.
