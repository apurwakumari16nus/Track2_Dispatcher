# Re-score after the two Round 2 fixes

**This is a development result.** The fixes were chosen after seeing Round 2, so the clean Round 2 score stays 33/34 behaviour and 32/34 decision (`eval/heldout_round2/`).

All sets were re-scored with Claude Sonnet 5.5 from saved model replies, so the model output is identical before and after. The prompt did not change and no new API calls were made.

## Fixes (`src/intake.py`, on with guards only)

1. **Deadline wording around "today":** "due today", "by today" and "deadline today" now read as today. "out today" does not.
2. **Who gave a constraint:** when an exclusion, preference or split was applied and the model named nobody, the sender and the message wording are recorded and marked `attribution: assumed_sender`.

## Scores

| Set | Behaviour | Decision | Numbers verified | Constraint honoured | Late flag |
| --- | ---: | ---: | ---: | ---: | ---: |
| Supplied 30, before | 30/30 | 29/30 | 30/30 | 28/30 | 21/21 |
| **Supplied 30, after** | **30/30** | **29/30** | **30/30** | **29/30** | **21/21** |
| Held-out 50, before | 48/50 | 47/50 | 50/50 | 47/49 | 38/39 |
| **Held-out 50, after** | **49/50** | **48/50** | **50/50** | **48/49** | **39/39** |
| of which earlier 16, after | 15/16 | 15/16 | 16/16 | 16/16 | 14/14 |
| of which Round 2 34, after | 34/34 | 33/34 | 34/34 | 32/33 | 25/25 |

## What changed

Of 80 rows, 3 changed score:

- **R63:** clarify became allocate, with an ALREADY LATE warning and SteadyHands recommended (earliest Apr 14).
- **R52, R25:** constraint check now passes. Workshop and reply text are unchanged.

Workshop choice and reply text are unchanged on the other 79 rows. 16 rows gained an assumed-sender audit entry, including R52 and R25. Red-team results and extra checks are identical. 592 tests pass.

## Still failing

| ID | Check | Cause |
| --- | --- | --- |
| R19 | Decision | Intended: one short question instead of a list of all open orders, against the evaluator's frozen rule |
| R23 | Constraint | The evaluator expects "fastest" from "faster", and the model set no preference. Workshop choice matches the benchmark |
| R34 | Behaviour, decision | Open from before: delivery question gets a clarify, not a decline |
| R50 | Decision | Evaluator: does not recognise "Northwind" or "polos". The reply named the right orders |
| R65 | Constraint | Evaluator: looks for "boss says", the message says "Boss said". The attribution is right |

## Limits

- **Assumed sender can be wrong:** R15 was relayed from Boss but now records Mei, marked as assumed.
- **Check coverage:** the evaluator tests who gave a constraint on exclusions only.
- **Not fixed, by choice:** R61 still ignores a named eligible workshop, and information questions still open with ALREADY LATE.
- **No clean test:** these fixes need new unseen requests for that.

The simulator was not re-run. It does not load `intake`, `agent` or `guardrails`, so its results cannot change.
