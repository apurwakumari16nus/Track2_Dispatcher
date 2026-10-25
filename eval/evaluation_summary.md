# Evaluation summary: results and failure cases

Draft for Evaluation.pdf. Every number comes from files in `eval/`; sources are named in each section.
Final system: **rule-based dispatcher + Claude Sonnet 5.5 intake**, with the two fixes described in §4.

## 1. What we measured and why

| Question | Measure | Why this measure |
|---|---|---|
| Are the allocation decisions good? | Course simulator: % late batches, late days, % defective pieces, cost, max share (busiest workshop's share of pieces) | Shared, reproducible yardstick for every team; lateness is our primary objective |
| Does it understand chat requests? | Behaviour (allocate / clarify / refuse / decline) and decision (right workshop, instructions honoured) against human labels | The brief asks for results by behaviour, with the decision judged separately |
| Are explanations honest? | Number check: every number in the explanation must come from a tool output | A right decision with an invented reason counts as a failure |
| Is it fast and affordable? | Seconds per request; estimated cost per request | A dispatcher works under time pressure |

## 2. How the evaluation sets were built, and why they are not rigged

- **Simulator:** the unchanged course harness, 120 orders, 10 paired seeds (5105–5114), normal and closure (`--shock`) runs. Hybrid weights were chosen on different seeds (6105–6114) with a selection rule fixed before running.
- **Development set:** the 30 course inbox requests. Two reviewers (Vanshika Dhamija, Apurwa Kumari) labelled them independently and then reconciled them; agreement before discussion was 27/30 on behaviour. Labelling happened after the intake was built, and some of Reviewer 1's columns were AI-drafted and then reviewed. All of this is disclosed in `eval/labeling/reconciliation.md`.
- **Held-out set:** 16 new requests (R31–R47; R39 removed before the run). The team wrote 13; an AI assistant drafted 3 (R44–R46). Labels were AI-drafted from the rubric and data without running the system, then reviewed by the team. File fingerprints were saved before the first run and the files were committed unchanged.
- **Honesty notes:** the system was developed on the 30-request set. Three dev labels (R20, R28, R30) were corrected after seeing the system's answers (logged). The version 2 preference rule and the fixes were decided after the held-out run, so all "after the fixes" numbers are **development results**. The only fully clean held-out result is the first Haiku run.

## 3. Results

### 3.1 Simulator (10 seeds; `eval/results.csv`)

| Policy | Normal: % late | Late days | Max share | % defective pieces | Cost | Closure: % late |
|---|---:|---:|---:|---:|---:|---:|
| Random (baseline) | 34.2 | 6.13 | 22.6 | 5.6 | 111,780 | 38.2 |
| Biggest workshop (baseline) | 84.3 | 26.53 | 70.2 | 5.3 | 108,430 | 84.9 |
| Cheapest (baseline) | 91.8 | 81.92 | 70.2 | 8.2 | 85,960 | 91.8 |
| Earliest finish (simple rule) | 1.7 | 0.18 | 26.3 | 7.2 | 115,567 | 1.9 |
| **Ours: lateness (primary)** | **1.7** | **0.18** | 26.3 | 7.2 | 115,567 | **1.9** |
| Ours: fairness (other objective) | 24.4 | 7.20 | **17.5** | 6.5 | 116,028 | 26.1 |
| Ours: hybrid 90% lateness + 10% fairness | 5.1 | 0.43 | 19.7 | 6.2 | 113,172 | 8.5 |

- Lateness beats all three baselines on % late and late days, in both scenarios. Fairness passes its guardrail (% late no worse than random) and has the lowest max share.
- **Where baselines win:** cheapest always has the lowest cost; random and biggest are cheaper than ours. **Earliest finish ties our lateness setting on every metric**, so our value lies in chat handling, refusals and the audit trail, not in the allocation rule itself (`eval/baseline_wins.md`).
- In the closure test our late rate moves only from 1.7% to 1.9%. A closure hurts most when one of the two all-round workshops (W2 or W6) closes: one extra late batch in 120.

### 3.2 Who gets the work (normal run, average share of pieces; `eval/allocation_shares.csv`)

| Workshop | Random | Lateness | Fairness | Hybrid 90/10 |
|---|---:|---:|---:|---:|
| W1 QuickStitch | 10.9% | 25.6% | 15.6% | 17.3% |
| W2 SteadyHands | 20.7% | 17.4% | 17.5% | 19.7% |
| W3 BudgetWorks | 22.6% | 11.9% | 15.1% | 16.8% |
| W4 Little Loom | 12.1% | 4.6% | 15.6% | 8.4% |
| W5 GiantWeave | 12.8% | 25.5% | 15.3% | 17.3% |
| W6 Nimble Needle | 19.4% | 13.4% | 15.7% | 15.4% |
| W7 OldMill (suspended) | 0% | 0% | 0% | 0% |
| W8 FreshStart (300-piece cap) | 1.5% | 1.8% | 5.1% | 5.1% |

Lateness concentrates work on the two big, fast workshops (W1, W5: about half the pieces). Fairness spreads work almost evenly across the six usable workshops. The hybrid sits between them, which is why it gains most of the fairness benefit for a small lateness cost.

### 3.3 Chat requests (`eval/model_comparison/`, `eval/model_comparison_v2/`)

| Run | Set | Behaviour | Decision | No invented numbers |
|---|---|---|---|---|
| Haiku 5.5, first live run | Dev (30) | 28/30 | 28/30 | 30/30 |
| Haiku 5.5, after date-reader fix | Dev (30) | 30/30 | 30/30 | 30/30 |
| **Haiku 5.5, original system (clean, run once)** | **Held-out (16)** | **15/16** | **13/16** | 16/16 |
| Sonnet 5.5, original system | Held-out (16) | 15/16 | 14/16 | 16/16 |
| Opus 5.5, original system | Held-out (16) | 15/16 | 14/16 | 16/16 |
| Haiku 5.5, after both fixes (development) | Held-out (16) | 13/16 | 13/16 | 16/16 |
| **Sonnet 5.5, after both fixes (development)** | **Held-out (16)** | **15/16** | **15/16** | 16/16 |
| Opus 5.5, after both fixes (development) | Held-out (16) | 15/16 | 15/16 | 16/16 |
| All three models, after both fixes | Dev (30) | 30/30 | 30/30 | 30/30 |

**Final system (Sonnet 5.5, after the fixes), by request type:** held-out: allocate 9/9, clarify 2/2, refuse 3/3, decline 1/2. Dev: all 30 correct.
With 16 requests, 15/16 corresponds to a rough 95% range of about 72–99%, so we report counts, not percentages per type.

### 3.4 Speed and cost (after the fixes; estimated from `benchmarks/pricing.json` list prices)

| Model | Median seconds per request | Slowest | Estimated cost per request |
|---|---:|---:|---:|
| Haiku 5.5 | 4.0–4.3 | 8.8 | ~$0.0008 |
| **Sonnet 5.5** | **2.4** | **5.4** | **~$0.011** |
| Opus 5.5 | 3.7–4.3 | 28.0 (one slow call) | ~$0.024 |

Almost all the time is the model call; the Python decision engine takes about 2 ms. **Why Sonnet:** accuracy was the same or better than the other models, it was the fastest, and it costs about 1 cent per request.

## 4. Failure cases

**Fix 1:** a separate "send date" field in the extraction template, plus a check that flags a message date that differs from the order file.
**Fix 2:** team rule version 2, under which speed words ("urgent", "asap", "faster") count as a "fastest" preference and quality words count as "lowest defect rate", with lowest defect still required to meet the date.

| # | Request | Run | What happened | Cause | Effect | Status |
|---|---|---|---|---|---|---|
| 1 | R04 "…back by Apr 21" | Haiku, dev, first run | Asked for the due date instead of allocating | Python date reader could not read a date with words in front ("back by") | Wrong behaviour | **Fixed** (date reader) |
| 2 | R25 "…due Apr 13…" | Haiku, dev, first run | Same as #1 | Same bug | Wrong behaviour | **Fixed** |
| 3 | R44 "already late… out today?" | All models, held-out | Read "out today" as the deadline; reported 8 days late instead of 17 (still flagged late, right fallback) | Template had one date slot; the model never sees the order's due date; the message date overrode the file | Wrong due date and days late; the number check cannot catch a wrong input | **Fixed** (Fix 1, all models) |
| 4 | R36 "Ensure quality" | Haiku, held-out | Ignored the instruction; picked a 5% defect workshop over a 2% one | Vague wording not mapped to a preference | Wrong workshop | **Fixed** (Fix 2) |
| 5 | R34 "is ORD-069 delivered?" | All models, held-out | Asked "do you want an order-status answer?" instead of saying there is no delivery record | Rules route every order-status question to clarify; they cannot tell recorded data (stage) from unrecorded data (delivery) | Wrong behaviour; nothing invented | **Open** (status answers: future work) |
| 6 | R38 "…They offer good quality" | Opus, held-out | Took praise for a workshop as a quality preference; proposed a different alternative | Larger model inferred intent; the version 1 labels counted only explicit instructions | Decision differed from the label | **Resolved by rule change** (Fix 2 counts it) |
| 7 | R32 "…Urgent." | Sonnet, held-out | Recorded "fastest" | Version 1 labels did not count urgency | Constraint check only; same workshop | **Resolved by rule change** |
| 8 | R15 "…outside asap" | Sonnet, Opus, dev | Recorded "fastest" | As #7 | Constraint check only | **Resolved by rule change** |
| 9 | R23 "Split… if that gets it back faster" | All models (v1); Sonnet (v2) | v1: recorded "fastest" when the label had none. v2: Sonnet did **not** record it when the new label expects it | "Faster" is a condition on splitting; readers disagree whether it is a preference | Constraint check only; same workshop | **Open** (minor) |
| 10 | R16 "Needs to ship Apr 15…" | Sonnet, dev (v1) | Did not mark the date as a hard requirement | The evaluator treats "needs to ship" as a hard date; our label did not | Constraint check only | Resolved after fixes |
| 11 | R42 "due date to be confirmed" | Haiku, held-out (after fixes) | Allocated using the file date instead of asking for the new date | Haiku left the deadline empty but did not flag it as unconfirmed (it was right before only by accident) | Wrong behaviour | **Open**, Haiku only (Sonnet correct) |
| 12 | R45 "…as long as it arrives on time" | Haiku, held-out (after fixes) | Treated "on time" as a deadline phrase and asked for a date | New wording made Haiku over-literal about dates | Wrong behaviour | **Open**, Haiku only (Sonnet correct) |
| 13 | R41, R25 (exclusions) | Haiku R41, Sonnet R25 (after fixes) | Exclusion applied, but who gave it was not recorded | Model omitted the attribution field; possibly the longer prompt, possibly run-to-run variation | Audit record incomplete; right workshop | **Open** (monitor in Round 2) |
| 14 | R20, R28, R30 (impossible deadlines) | Labelling | Reviewers split between `refuse` and `decline`; the system answered `allocate` with warnings | The four behaviours have no "complete but impossible" case | Labels corrected after seeing the system (logged) | **Resolved and disclosed** |

**Summary of causes:** real system errors (#1–#4, #11, #12), instruction-reading disagreements that did not change the chosen workshop (#7–#10, #13), and design or labelling limits (#5, #6, #14).

## 5. Limitations

- Small samples: 16 held-out requests, one run per model (Claude has no temperature control).
- The "after the fixes" numbers are development results; the fixes still need a clean test.
- Labels and three held-out requests were partly AI-drafted (disclosed).
- The number check verifies numbers come from tools, not that the inputs were right (#3).
- The allocation rule itself adds nothing over earliest finish on lateness.
- Order-status questions cannot be answered yet (#5).

## 6. What we would measure with more time

1. **Round 2 held-out:** 20+ new requests, orders chosen by seeded random sampling, written and labelled by the team, run once. This gives a clean test of both fixes.
2. **Repeat runs** of Sonnet (3 times) to measure run-to-run variation.
3. **Usability test** with 3 people acting as dispatchers: task time, errors, confidence.
4. **End-to-end time in the app** (including the screen), not only the server.
5. **Harder messages:** several orders in one message, typos, multi-turn follow-ups.
