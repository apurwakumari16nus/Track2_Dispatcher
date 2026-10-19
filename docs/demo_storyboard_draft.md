# Demo storyboard (draft)

Draft scenes for the Sprint 2 video. This is not the final narration. Spec v5
asks for Objective (about 1 min), Tech (about 2 min) and Demo (about 2 min).
Flow A fills the demo slot. Flow B is a full walkthrough you can cut down.

Before each take: follow `demo_readiness.md` (reset, 1920 × 1080, pre-warm,
Rehearsal · recorded with real replies, or Live model).

## Flow A: about 2 minutes, product demo

| # | Screen | Action | What is visible | What it proves | Time |
| --- | --- | --- | --- | --- | --- |
| A1 | Dispatch, empty | Start on the landing page | Inbox of 30 chat lines, system status, the three-lane "model reads, Python decides, you confirm" | The group chat is the input; roles are separated | 0:10 |
| A2 | Dispatch | Click scenario **R09 Normal allocation** | Stepper runs Interpret to Verify; hero card: Nimble Needle, 4 Apr, 5 days spare, cost 180, Evidence check passed | Recommendation in five seconds, with numbers from tools | 0:20 |
| A3 | Dispatch → Why this won | Open the tab; click **SteadyHands** under Why not | Runner-up comparison, score decomposition with inactive terms greyed, reason card | The choice is explainable from score terms, not prose | 0:20 |
| A4 | Dispatch | Click **Confirm allocation** | Card edge turns green: "Confirmed · Audit record created · Session queue updated", "No message has been sent" | Human in the loop; nothing is auto-confirmed or sent | 0:10 |
| A5 | Dispatch | Scenario **R08 Refused workshop** | Coral banner: FreshStart cannot take 400 (300-piece cap); best permitted alternative | Refuses with the reason and an alternative | 0:15 |
| A6 | Dispatch | Scenario **R30 Impossible deadline**; click **Estimate a two-workshop split** | Amber "No eligible workshop meets the requested date", least-late 11 Apr, three human options, split preview | Impossible cases are explicit, with options | 0:20 |
| A7 | Dispatch | Scenario **R01 Clarification** | Missing facts, two matching orders, question to send, reply field | Asks instead of guessing | 0:10 |
| A8 | Audit Trail | Open the page; select the R09 record | Filters, record tabs, constraints, candidates, confirmation metadata | The decision is auditable six weeks later | 0:15 |

## Flow B: about 5 minutes, full walkthrough

| # | Screen | Action | What is visible | What it proves | Time |
| --- | --- | --- | --- | --- | --- |
| B1 | Dispatch, empty | Pan from the inbox to the three lanes | Inbox, status chips, extraction source | Problem: allocation decided in a group chat | 0:20 |
| B2 | Dispatch | **R09**; pause on the stepper | Stages complete in order; Confirm waits in green | Observable stages, not hidden reasoning | 0:20 |
| B3 | Dispatch | Point at the hero and the candidate panel | All eight workshops, ineligible ones still visible with reasons | Eligibility, capacity and permission at a glance | 0:20 |
| B4 | Execution trace tab | Expand step 1, then step 6 | Extraction source and model named; candidates and scores | LLM extracts only; Python ranks; every step has evidence | 0:30 |
| B5 | Evidence tab | Show the checked values | Every number in the explanation matched to tool outputs | Faithfulness is checked, and its limits are stated | 0:15 |
| B6 | Dispatch | Confirm R09 | Green confirmed state | Explicit confirmation and audit | 0:10 |
| B7 | Dispatch | **R25** → Why this won → Why not **BudgetWorks** | "Excluded by request · imposed by Mei" | Constraints honoured and attributed | 0:20 |
| B8 | Dispatch | **R08**, then **R02** | Refusal with alternative; "This needs data the desk does not hold" | Refuse and decline behaviours | 0:25 |
| B9 | Dispatch | **R30** → split preview; **R28** | Least-late option, options, split; already-late banner | Track 2 awkward cases | 0:30 |
| B10 | Workshop Network | 1,500 tops by 15 Apr; toggle Matrix | One-line answer, eight cards, load bars, statuses; a confirmed batch raised a queue | Queryable register using the same tools | 0:20 |
| B11 | Simulation Lab → Overview | Lateness, Normal | Five metrics with TIE badges; tie banner | Honest comparison with the strongest simple rule | 0:25 |
| B12 | Objective trade-offs | Switch objective to Fairness, then Quality | Heatmap shifts where work goes; Quality concentrates 70% at SteadyHands | Objective is configuration and changes decisions | 0:25 |
| B13 | Disruption | Shock; objective Robustness, then Lateness | Closure window, first flag, clearance, pieces sent while flagged (compare the two objectives) | Shock handling, with the honest caveat on early flags | 0:30 |
| B14 | Order audit | Pick a late order | Candidates at the moment of choice vs realised outcome | Every automatic decision is inspectable | 0:15 |
| B15 | Course evidence | Scroll findings, criteria matrix, language status | Ten-seed tie, defect guardrail failure, fairness and robustness qualify, accuracy not reported | Academic honesty: limits shown, not hidden | 0:30 |
| B16 | Audit Trail | Filter by workshop; open a record; export | Governance view | Auditable structured output | 0:20 |

Total: about 5:30. Trim B5, B10 or B14 to land at 5:00.

## Notes for the narration pass

- Say "tie", never "match" or "as good as", for lateness vs earliest finish.
- If the take uses Rehearsal · recorded, say once that replies were recorded from the live model.
- Do not use Rehearsal · fixtures in the final video unless the narration says they are test fixtures.
- Point at the coloured actor tags in the trace: violet for the model, cyan for Python, green for the human.
