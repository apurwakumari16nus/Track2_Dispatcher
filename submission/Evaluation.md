# Evaluation report

Threadline, Group 01, Track 2. This report covers how we tested the dispatcher, what the numbers show, and where it does not work.

## Summary

Five results matter most:

- On the course simulator, our lateness preset leaves 1.7% of batches late. The best supplied baseline leaves 34.2% late.
- A simple rule, "give it to whichever workshop finishes first", ties our allocator on every metric. Our allocator adds nothing over that rule.
- On 16 requests we had not tested on before, keyword rules written without seeing the requests got 8 right. Our LLM reader got 15 right.
- On 34 further new requests (Round 2), run once on Sonnet, our LLM reader got 33 right on behaviour and 32 right on decision. The same blind keyword rules got 16 right.
- In 9 of 9 replies where a constraint was applied, the reply text did not mention it.

Our allocation rule works well, but a five-line rule does just as well. Where the system does help is in reading requests: on requests its authors had not seen, the LLM reader got 15 of 16 right and the blind keyword rules got 8. These results have problems too. The fixes we tested on the first held-out set were made after looking at it, an AI assistant drafted Round 2, and no real dispatcher or workshop has used the system. Section 2 explains which results are clean and which are not.

## 1. What we measured and why

| Question | Measure | Why this measure |
|---|---|---|
| Are allocations good? | Course simulator: % batches late, late days, busiest workshop's share of pieces, % defective pieces, cost | Every team uses the same simulator. Lateness is our primary objective because a late batch loses the margin |
| Does it handle a chat request? | Behaviour (extract, clarify, refuse, decline to answer) compared with human labels | Choosing the wrong behaviour is the costly error, for example guessing when the system should have asked a question |
| Is the decision right? | Same workshop as an independent earliest-finish reference, under the labelled constraints | Scored separately from behaviour, as the brief asks |
| Is the explanation faithful? | Two checks: every number traces to a tool output, and a separate review of what the reply says | A right decision with a made-up reason still counts as a failure. The number check alone cannot catch a misleading sentence |
| What does the LLM add? | The same requests run through three readers that use no LLM | Without this, "the LLM helps" is only an assumption |
| Is it usable at a desk? | Seconds and estimated cost per request | A dispatcher answers within the hour, often within minutes |

In the code the first behaviour is called *allocate*. It is the same as the brief's *extract*: the system reads the facts and produces a recommendation. Nothing is sent until a person approves it.

## 2. How the evaluation sets were built, and why they are not rigged

### Simulator

We used the course harness without changes (`harness/simulate.py`, identical to the supplied file) with 120 orders. A seed is the number that fixes the random draws, so two policies run on the same seed see exactly the same orders. We used 10 seeds (5105 to 5114) and ran each one twice: once normally and once with `--shock`, the option that closes a workshop during the run. Every policy sees the same orders and the same closures. The weights for the hybrid preset were chosen on a different set of seeds (6105 to 6114), using a selection rule we fixed before running. On 2 November 2026 we re-ran the whole evaluation on the final code, and `results.csv` came back byte for byte the same.

### The 30 supplied requests

This is our development set, and we tuned the system on it. Two reviewers, Vanshika Dhamija and Apurwa Kumari, labelled the requests independently and then reconciled their labels. Before discussion they agreed on 27 of 30 behaviours. Some things about this set favour us:

- The labelling happened after the intake was built.
- Some of one reviewer's columns were drafted by an AI assistant and then reviewed.
- Three labels (R20, R28, R30) were changed after we saw the system's answers. The change is logged in `eval/labeling/reconciliation.md`.

So the 30 of 30 score should be read as a development score.

### The held-out set

Held-out means requests we kept aside and did not use while building. There are 16 new requests (R31 to R47, with R39 removed before any run). The team wrote 13 and an AI assistant drafted 3 (R44 to R46). An AI drafted the labels from the rubric and the data, without running the system, and the team then reviewed them. We saved fingerprints of the files before the first run.

<div class="note" markdown="1">
On this set, only one result was never used for development: the first held-out run, Haiku 5.5, with 15/16 on behaviour and 13/16 on decision. We then ran Sonnet and Opus on the same set to choose a model, so Sonnet's first result (15/16, 14/16) is already a selection. Our final figure, Sonnet with 15/16 and 15/16, came after two fixes that we chose by looking at those held-out failures, so it is a development result. We planned a second held-out round, written by a teammate who had not built the guards. Round 2, below, is a different kind of test from that plan, and the two fixes made after it have no clean test either.
</div>

### Round 2 held-out set

This is a second set of 34 new requests (R48 to R81). It covers the supplied kinds of request plus some messy chat. An AI assistant drafted the requests after reading the guard documents and past failures, and the team then rephrased them. The orders started from a seeded draw, were limited by request type and were swapped by hand to avoid near-copies of earlier requests. The AI drafted the labels from the rubric and the data without running the system, and a script checked them against the data. The team had not reviewed the labels before the run. We saved fingerprints first (`eval/heldout_round2/freeze_manifest.txt`), and Sonnet 5.5 then ran once on 7 November 2026, at commit `95a0815`. This is not the round we planned, which was to be written and labelled by a teammate who did not build the guards, so we report it as a first run on new requests, with those limits.


### Red-team set

These are 16 messages we wrote to try to break the system: gibberish, prompt injection, typos and several orders in one message. We then built guards, which are checks written in Python, against the failures we found. A score of 16 of 16 therefore shows only that the guards do what they were built to do.

### The rule readers

We wrote readers based on keyword rules for this report, so that we could measure what the LLM adds. The first attempt was contaminated. Its author, an AI assistant, had just read all 46 messages, and that reader scored 29 of 30 and 16 of 16. We kept it as an upper bound. We then asked a separate agent to write rules from the data dictionary alone; it was blocked from every request file and from all of our label and evaluation files. Its file was not edited after its first run. The scoring favours all of the rule readers, as section 3.4 explains.

## 3. Results

### 3.1 Simulator: objectives against the baselines

{{SIMULATOR}}

<p class="fig">Mean of 10 paired seeds. SD is across seeds, for normal runs. Sources: eval/results.csv, eval/results_per_seed.csv.</p>

![Share of batches late by policy, normal and with a workshop closed.](figures/late_by_policy.png)

Each preset has a guardrail, a minimum condition it must meet before we would offer it.

- Lateness, our primary objective, beats all three baselines on % late and on late days, both in normal runs and with a workshop closed. The closure moves it only from 1.7% to 1.9%, which is about one extra late batch in 120 in the worst case.
- Fairness, our second objective, brings the busiest workshop's share down to 17.5%. Its % late is 24.4, which stays inside its guardrail of being no worse than random.
- The hybrid uses 90% lateness and 10% fairness. It gives 5.1% late with the busiest share at 19.7%, so it gives up 3.4 points of lateness to get most of the fairness gain. With a workshop closed it rises to 8.5% late. Spreading work out leaves the desk more exposed to a closure.
- Lowest defect fails its guardrail. It reaches 2.9% defective pieces, but 95.1% of batches are late. We report it and do not offer it as a default.

### 3.2 Where a baseline wins

We compared every baseline and the simple rule with each of our presets, one pair at a time. In 83 of these comparisons in the normal run, and 80 with a workshop closed, the baseline or simple rule did strictly better on some metric. All of them are listed in `eval/baseline_wins.md`. These are the ones that matter:

- Earliest finish ties our lateness preset on every metric, in both scenarios. With its default weights, our allocator reduces to "whoever finishes first". That rule is about the size of one of the supplied baselines and uses no LLM. For allocation alone, our system adds nothing.
- Cheapest always costs least: 85,960 against 115,566, a gap of 26%. But it is late 92% of the time.
- Random and greedy biggest are both cheaper than our lateness preset. Being fast costs about 3 to 7%.
- Random beats our lateness preset on defects (5.6% of pieces against 7.2%), because the fast workshops are not the careful ones.
- Earliest finish beats every other preset of ours on lateness, including the hybrid.

#### What the system adds over a simple rule-based allocator

The gain is in the work around the rule. A simple allocator takes a clean order and returns a workshop. It cannot read a chat message, refuse a suspended workshop by name, ask when the date is unconfirmed, decline a question the data cannot answer, or keep a record of who approved what. Sections 3.3 and 3.4 measure the first of these, reading the message.

### 3.3 The 30 supplied requests, by behaviour (development set)

{{DEV}}

<p class="fig">Sonnet 5.5, final code. Model replies recorded earlier and re-scored offline on 2 November 2026; the guards changed one result (R19, failure 5). A second re-score on 7 November 2026, after the Round 2 fixes, left this table unchanged. "Explanation fully clear" is the new review in section 3.5. Every request is listed in the appendix.</p>

The only decision miss is R19, and it comes from a change we made on purpose. The first live run of the original system, on Haiku, scored 28/30 on both behaviour and decision.

### 3.4 What the LLM adds: rule readers on the same requests

{{READERS}}

![Behaviour correct by reader on each set.](figures/readers.png)

<p class="fig">Numbers on bars are requests right. Source: eval/rule_baseline/, run with eval/run_rule_baseline.py. No model call.</p>

Every reader feeds the same reference allocator. The scoring favours the rules. For them, a clarify or decline counts as a right decision if the behaviour is right, while our reader must also pass the checks on the candidate list. On the red-team set our decision score is 13 of 16, because the scorer still expects the old list of 34 orders, which the guards removed on purpose (failure 13).

We think this is the most useful comparison in the report. On held-out requests, rules from a blind author got 8 of 16 and our reader got 15 of 16. Rules written by someone who had seen the messages got 16 of 16. That is uncomfortable for us: these 46 messages are short, in English and regular enough that a person who has read them can cover them with keywords. Those rules break on new phrasing, though. On the red-team set, which their author had not read, they fall to 9 of 16. What the LLM offers is the ability to cope with messages nobody planned for. Round 2 points the same way. On its 34 new requests, which none of the rule readers had seen, the blind keyword rules got 16 right on behaviour and 14 on decision, and our reader got 33 and 32 in its one run. Even the rules written after reading the first 46 messages got only 25 of 34. Our evidence for the LLM's lead is now 50 unseen requests and the partner replies below, so it is promising but not proven.

### 3.5 Explanation review: is the reply true, and does it say why?

The number check only proves that a number came from a tool. So we also reviewed all 46 replies, partly by script and partly by reading each one (`eval/run_explanation_review.py`, `eval/explanation_review.csv`). The reading was done by an AI assistant and has not yet had a second human reader.

| Check | Result | What it means |
|---|---:|---|
| Every number traces to a tool output | 46/46 | No invented numbers |
| Days, return date and cost, recomputed from `workshops.csv` | 32/32 | The arithmetic is right in every reply that names a workshop |
| An applied exclusion or preference is named in the reply text | 0/9 | True, but not explained. See failure 10 |
| ALREADY LATE shown only when placement was requested | 2/4 | Shown on two information questions. See failure 9 |
| A clarification asks only for what is missing | 0/6 | Asks for a due date the order file already holds. See failure 11 |

No reply says anything false about an order. Seventeen of the 46 could be clearer, and we count those as explanation weaknesses, separate from the decision score. The 34 Round 2 replies have not had this review.

### 3.6 Held-out result, model choice, red team, partners and speed

{{HELDOUT}}

| Run | Set | Behaviour | Decision | Status |
|---|---|---:|---:|---|
| Haiku 5.5, original system | Held-out 16 | 15/16 | 13/16 | Clean, run once |
| Sonnet 5.5, original system | Held-out 16 | 15/16 | 14/16 | Model selection |
| Opus 5.5, original system | Held-out 16 | 15/16 | 14/16 | Model selection |
| Haiku 5.5, after fixes | Held-out 16 | 13/16 | 13/16 | Development. Haiku got worse |
| Sonnet 5.5, after fixes (final) | Held-out 16 | 15/16 | 15/16 | Development |
| Opus 5.5, after fixes | Held-out 16 | 15/16 | 15/16 | Development |
| **Sonnet 5.5, at the Round 2 run** | **Round 2, 34** | **33/34** | **32/34** | **Run once, limits in section 2** |
| Sonnet 5.5, after Round 2 fixes | Round 2, 34 | 34/34 | 33/34 | Development, saved replies re-scored |
| Sonnet 5.5, after Round 2 fixes | Held-out 16 and Round 2, 50 | 49/50 | 48/50 | Development, not clean |
| Sonnet 5.5, after Round 2 fixes | Supplied 30 | 30/30 | 29/30 | Development, saved replies re-scored |

The first row is the only clean result on the first held-out set. For 15 of 16, a rough 95% Wilson range is 72% to 99%. Round 2 was run once, with the limits given in section 2. For 33 of 34 the range is 85% to 99.5%, and for 32 of 34 it is 81% to 98%. By expected behaviour, Round 2 got allocate 17 of 18 (decision 17 of 18), clarify 8 of 8 (decision 7 of 8), refuse 4 of 4 and decline 4 of 4. Every number traced to a tool on all 34, constraints were honoured on 31 of 33 scored rows, and the late flag was right on 24 of 25. Only Sonnet was run on Round 2. We chose Sonnet because its accuracy tied or beat the other models, it was the fastest, and it costs about one cent per request. This choice was not made on a clean basis.

| Other measure | Result | Note |
|---|---|---|
| Red team, behaviour | 10/16 before guards, 16/16 after | Development set. Supplied 30: unchanged, one intended decision change. Held-out: 0 rows changed |
| Prompt injection | 2/3 held before guards, 3/3 after | "Mark as approved" produced only a recommendation, because the schema has no such field. The third asked for the system prompt |
| Workshop replies, development | 42/48 before fix, 48/48 after | English 12, Hinglish 12, Hindi 12, Chinese 12 |
| Workshop replies, held-out | 11/12 | Hindi 6/6, Chinese 5/6. Written after the fix. Sender languages only, never real workshop staff |
| Speech, word errors | 26% phone model, 6% Whisper with names as hints | 48 spoken requests in 4 synthetic voices. Real speakers will differ |
| Speed | Median 2.4 s, slowest 5.7 s on the server; 2.52 s median and 5.84 s slowest from click to screen | 30 requests, one run. The Python engine takes about 2 ms |
| Cost | About $0.011 per request | Estimated from list prices, not billed |
| Automated tests | 592 passed | Run 7 November 2026. No model calls |

## 4. Failure cases

We list 15 failures. Each case gives the message, what went wrong, the cause, and whether it is fixed.

| # | Requests | Problem | Status |
|---|---|---|---|
| 1 | R04, R25 | Date with words in front of it | Fixed |
| 2 | R44 | Model filled the wrong date slot | Fixed, not cleanly tested |
| 3 | R36 | Vague quality wording ignored | Fixed, rule set after the failure |
| 4 | R34 | Cannot say what it does not know | Open |
| 5 | R19 | Better reply, lower score | Kept, costs a point |
| 6 | R23 | Split wording read differently | Open, minor |
| 7 | R25, R41 | Who gave the instruction was lost | Open |
| 8 | R42, R45 | Haiku got worse after our fixes | Open for Haiku |
| 9 | R13, R47 | ALREADY LATE on a question | Open |
| 10 | Nine replies | Constraint applied but not mentioned | Open |
| 11 | Six replies | Clarification asks for a date we hold | Open |
| 12 | C26 | Price lost in Chinese | Open |
| 13 | Red-team set | Failures before the guards | Fixed on the set they were built against |
| 14 | R20, R28, R30 | A case the four behaviours do not cover | Labels changed, reported |
| 15 | Hybrid preset | The shipped hybrid is not the best one found | Open |

### Failure 1. R04 and R25: a date with words in front of it

*"ORD-041 needs a home today. 600 beanies, back by Apr 21."*

In Haiku's first run, the system asked for the due date instead of allocating. The model had read the date correctly, but the Python date reader could not parse a date with words in front of it, so it threw the reading away. This gave the wrong behaviour on 2 of 30 requests. The bug was in our own parsing code, not the model, and we fixed it in the date reader.

### Failure 2. R44: the model filled the wrong date slot

*"Maple & Co are chasing ORD-083, it's already late. Can we get the hoodies out today?"*

All three models read "out today" as the deadline and reported the order as 8 days late instead of 17. The template had only one date slot, and the model never sees the due date in the file, so the date in the message overrode it. The number check still passed, because 8 was a real tool output computed from a wrong input. We fixed this with a separate send-date field and a check that flags a conflict with the order file. The fix has not been cleanly tested.

### Failure 3. R36: vague quality wording ignored

*"ORD-082, 600 Beinie for TrendCart, due May 1. Ensure quality."*

Haiku ignored "Ensure quality" and chose a workshop with 5% defects over one with 2%. Vague wording like this was not mapped to any preference. Rule version 2 fixes it: quality words now mean lowest defect, as long as the date is still met. We wrote that rule after seeing this failure, and we changed the label to match.

### Failure 4. R34: it cannot say what it does not know

*"is ORD-069 delivered to client?"*

The expected behaviour was to decline, because delivery is not recorded in our data. Instead, every model asked whether the sender wanted a status answer. Our rules send every status question to clarify, and they cannot tell data we hold (the production stage) from data we do not (delivery). No harm is done, but the question leads nowhere. This is still open, and it is the one miss on the first 16 held-out requests in our final score.

### Failure 5. R19: the reply got better and the score got worse

*"That big reorder from last week, send it to whoever is quickest."*

The old reply listed all 34 open orders, which is what the frozen evaluator expects. With the guards, the system now asks for the order ID in one line. We think the new reply is better, but it loses a point. We did not change the evaluator, so we report 29/30.

### Failure 6. R23: split wording read differently

*"Split it across two shops if that gets it back faster."*

The workshop and the split preview were both right. Sonnet did not record "fastest" as a preference, but the label does. "Faster" here is a condition for splitting, and readers disagree on whether it counts as a preference. This is a minor open issue. It is the one constraint miss left: the score was 28/30, and it is 29/30 after the fix in failure 7.

### Failure 7. R25, R41 and R52: who gave the instruction was lost

*"...keep it away from BudgetWorks..."*

The exclusion was applied and the workshop was right, but the audit record left out who asked for the exclusion. We saw this with Sonnet on R25 and R52, and with Haiku on R41. The field is optional for the model. Across the Sonnet runs on the supplied 30, the first 16 and Round 2, it named who gave only 3 of 20 labelled constraints, all of them exclusions. The score hid this, because the evaluator checks who gave the instruction on exclusions only, and it still does. This is now fixed in Python, but not cleanly tested: when a constraint is applied and the model names nobody, the record takes the sender and marks it as assumed. That assumption can be wrong. R15 came from Boss through Mei, and it now records Mei.

### Failure 8. R42 and R45: Haiku got worse after our fixes

*"ORD-040, assign something, due date to be confirmed."*

On R42, Haiku allocated using the date in the file. On R45, the phrase *"as long as it arrives on time"* made it ask for a date. Its held-out behaviour score fell from 15 to 13, which suggests it had been right on these partly by accident. Sonnet gets both right. This stays open for Haiku, which still does background reading of the whole inbox.

### Failure 9. R13 and R47: ALREADY LATE on a question

*"Finance asks: what price did we quote TrendCart on ORD-120?"*

The reply correctly declines, then adds "ALREADY LATE: the requested deadline is today or in the past." Nobody asked about a deadline. The flag is based on the order's date in the file and runs for every behaviour. On R47 the order is due today, so "late" is not even true yet. Every automated check passed, and we found this only by reading the replies. Round 2 shows the same on R49, R55 and R69. It is still open, though the fix is one line.

### Failure 10. Nine replies apply a constraint and do not say so

The affected requests are R09, R12, R21, R25, R27, R32, R36, R41 and R45. R21 asks for the cheapest shop that can make the date. The reply says "Lowest score among permitted candidates" and says nothing about BudgetWorks being cheaper but three days late. R25 asks to keep away from BudgetWorks, and the reply never mentions it. Each decision is right and each sentence is true, but the template only states the winner's numbers, not the reason it won. The "Why this decision" panel on the web desk does show the reason, but the evaluator scores the text reply. This is open, and it is the biggest gap in our explanations, because the product promises that a person can see why a choice was made.

### Failure 11. Six clarifications ask for a date we already hold

*"Which order do you mean: ORD-061; ORD-108? What is the confirmed due date, including the year?"*

This happens on R01, R03, R10, R15, R29 and R37. Once the order is picked, the date comes from the file. The system asks anyway because the message did not give one. That adds an extra round of chat and looks careless. R10 has a second problem: "New rush... details to follow" is a new order, but the reply lists existing ones. Round 2 shows the same extra question on R50, R62 and R74. This is open.

### Failure 12. C26: a price lost in Chinese

每件涨到2块 ("up to 2 per piece")

The model understood that the price had changed but lost the number. Because the number was missing, the desk asked the workshop again and changed nothing. The failure was safe, but it is real. It is the one held-out miss in partner replies, and the film shows it. The English "up to 1.8 per piece" works, so colloquial Chinese numbers need more testing. This is open. We found it before the Sprint 3 film, and it is one of the film's stated limits.

### Failure 13. The red-team set before the guards

*"asdf ok?? lol"*

Before the guards, 6 of 16 behaviours were wrong and 9 of 15 extra checks failed. Gibberish like the message above, off-topic questions and a request for the system prompt all got a list of the 34 open orders. *"ord 041"* and *"ORD45"* were declined as unknown orders. When a message held two orders, one was lost. All of these came from one code path: anything without a clean order became a clarify with every open order attached. We fixed this with Python guards, but only on the set they were built against. Messages with several orders still get a question back instead of being split into separate cards. The guards have not been run with Haiku.

### Failure 14. R20, R28, R30: a case the four behaviours do not cover

These requests have a deadline that cannot be met. The reviewers split between refuse and decline, and the system allocated with a warning. None of the four behaviours fits a request that is complete but impossible. We moved the labels to allocate after seeing the system's answer. That helps our score, so we report it: without the change, the first-run score would be three lower. A person should decide how to handle this category before testing.

### Failure 15. The hybrid we ship is not the best one we found

Our selection rule picked a fairness weight of 0.1 on a grid with steps of 0.1, and that is what we ship. On a finer grid, the same rule picks 0.05. That gives 4.0% late, a busiest share of 19.2% and 5.5% late with a workshop closed, against 5.1%, 19.7% and 8.5% for 0.1. So 0.05 is better on all three. This is open. We kept 0.1 for this report rather than change it after seeing the course seeds. The preset should change, with new tuning seeds kept apart from the test seeds.

</div>
<div class="failure">

### Failure 16. R63: "due today" was not read

*"ORD-029, 1500 beanies for Northwind, due today. Any shop that can take it?"*

The model copied "due today" correctly, but the Python date reader accepted only the bare word "today". So the system asked for a date it had already been given, and gave no late warning. This is the one behaviour miss in Round 2. We fixed the date reader, which still does not read "out today" as a deadline. The fix has not been cleanly tested, and other wording, such as "by end of today", still gets a question.

</div>
<div class="failure">

### Failure 17. R61: a named workshop was ignored

*"Please assign ORD-036 to SteadyHands. 1000 scarves for UrbanThread, due Apr 26."*

SteadyHands can take this order, but the reply recommends Nimble Needle and never mentions SteadyHands. Both would return it on Apr 11. Every scored check passed, because our label named no expected workshop and the evaluator did not check the named one. We found it by reading the reply. The dispatcher can still override the pick. This is open, and it is not counted in the Round 2 score.

</div>
<div class="failure">

### Failure 18. R50 and R65: the reply was right and the evaluator marked it wrong

*"Northwind's polos need to go out."*

The reply named the right two orders, but the evaluator did not recognise "Northwind" or "polos" and expected all 34 open orders. On R65, the system correctly recorded the instruction as Boss's, relayed by Ravi, but the evaluator looks for "boss says" and the message says "Boss said". We did not change the evaluator, so both still count as misses: R50 on decision and R65 on constraint.

### What the failures have in common

Most of the serious failures came from the Python code around the model rather than from the model itself. Examples are the date reader, the template with one date slot, the list of 34 orders and the misplaced flag. Our checks could not see these, because each one tests something narrow. Reading the replies by hand found failures 9, 10, 11 and 17 after every automated score was already green.

## 5. Limits of this evaluation

- No real users. No dispatcher or workshop has used the system, and we wrote all of the workshop replies ourselves.
- Small sets. There are 16 held-out requests, then 34 more in Round 2, and 12 held-out replies. We ran each model once and ran only Sonnet on Round 2. Claude's current models accept no temperature setting, so we have no measure of how much results vary between runs.
- Some of the material was drafted by AI: 3 of the first held-out requests, all 34 Round 2 drafts, the labels for both sets, some reviewer columns, the blind rule reader and the explanation reading.
- Gaps in Round 2. Rephrasing removed the day and month date from R57, so that guard is not tested there. R58 and R66 are judgement calls on the labels, and both passed as labelled.
- The simulator tests the allocation rule, not the app. It has no chat, no language and no person in the loop. The demo also differs from this report. In the film, orders start from eight earlier decisions, so the queues are different and ORD-045 goes to FreshStart. This evaluation resets the queues for each request, and ORD-045 goes to Nimble Needle.
- Workshop speed and defect rates are the supplied estimates, not measurements, and the desk assumes they hold.

## 6. What we would measure with more time

1. A clean held-out round. At least 20 new requests, with orders drawn by seeded sampling, written and labelled by a teammate who did not build the guards, then frozen and run once. Round 2 did not meet this, and the two fixes made after it have no clean test.
2. Repeat runs. Run Sonnet three times on all sets to see how much the score moves between runs.
3. A second human reader for the explanation review, followed by a rewrite of the reply template and a re-run.
4. A usability test with at least three people acting as dispatchers, measuring time per decision, errors and whether they trust the stated reason. This is the only way we can measure time saved.
5. Real Hindi and Mandarin speakers testing written replies and speech, on real phones in noisy places.
6. Costs from real invoices, and a week-long run on one Mac to see how the single point of failure behaves.

## Appendix: all 30 supplied requests

Decision and Numbers are the evaluator's checks. Explanation is the review in section 3.5. The workshops are W1 QuickStitch, W2 SteadyHands, W3 BudgetWorks, W4 Little Loom, W5 GiantWeave, W6 Nimble Needle, W7 OldMill (suspended) and W8 FreshStart (300-piece cap). Refuse rows show the alternative offered, with no allocation made.

<div class="small" markdown="1">

{{REQUESTS}}

</div>
