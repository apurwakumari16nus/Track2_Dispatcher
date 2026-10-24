# Demo storyboard (draft, UI v4)

Draft scenes for the Sprint 2 video, built on the finished v4 screens. This is not
the final narration. Spec v5 asks for Objective (about 1 min), Tech (about 2 min)
and Demo (about 2 min). Flow A fills the demo slot. Flow B is a full walkthrough
to cut down.

Before each take: follow `demo_readiness.md` (reset, 1920 × 1080, presentation mode,
pre-warm, Rehearsal: recorded model replies or Live model).

## Flow A: about 2 minutes, product demo

| # | Screen | User action | What appears | What it proves | Time |
| --- | --- | --- | --- | --- | --- |
| A1 | Dispatch, empty | Start on the landing page | Inbox of 30 chat lines, "Select a request to begin.", System ready in the command bar | The group chat is the input; the next action is obvious | 0:08 |
| A2 | Dispatch | **Guided demo** (step 1, R09); press **Evaluate request** | UNDERSTAND to VERIFY light up; the navy hero: Nimble Needle, 4 Apr, 5 days spare, cost 180, Evidence verified | Recommendation in seconds, numbers from tools | 0:20 |
| A3 | Decision inspector → Why this won | Press **Why this decision?** | Slide-over: Nimble Needle against FreshStart, 3.2 against 3.5 days, 0.3 days sooner | The choice is explained from recorded data, not prose | 0:15 |
| A4 | Why not another | Click **OldMill**, then **FreshStart** | "Not eligible: Suspended"; FreshStart "Eligible", 0.3 days later, lower cost, Result: not selected because the lateness objective prioritises an earlier return | Every rejection has a deterministic reason | 0:12 |
| A5 | Dispatch | Close the panel; press **Confirm allocation** | Hero edge turns green: CONFIRMED, "Audit record saved. Queue updated. No message has been sent to Nimble Needle." | Human in the loop; nothing is sent automatically | 0:10 |
| A6 | Dispatch | Demo controller **Next** twice (R08); Evaluate request | "FreshStart cannot accept this batch." Reason with the numbers; best permitted alternative | Refuses with reason and alternative | 0:15 |
| A7 | Dispatch | **Next** twice (R30); Evaluate request; Preview a two-workshop split | "No eligible workshop can meet 5 Apr", earliest 11 Apr, options, split preview | Impossible cases are explicit, with options | 0:20 |
| A8 | Dispatch | **Previous** to step 2 (R01); Evaluate request | "I need one detail before I can continue." with two matching orders | Asks instead of guessing | 0:10 |
| A9 | Audit Trail | Step 6 of the tour; press **Open** on the R09 row | Ledger row, then the slide-over: original request, why, parsed fields, constraints, candidates, confirmation | Auditable six weeks later | 0:10 |

## Flow B: about 5 minutes, full walkthrough

| # | Screen | User action | What appears | What it proves | Time |
| --- | --- | --- | --- | --- | --- |
| B1 | Dispatch | Pan across the inbox and command bar | Calm workspace, one System ready control | Built for a dispatcher under time pressure | 0:15 |
| B2 | Dispatch | Load R09; Evaluate request; pause on the strip | UNDERSTAND, VALIDATE, EVALUATE, DECIDE, VERIFY | Observable stages; confirmation is separate | 0:20 |
| B3 | Dispatch | Point at the hero, then Alternatives | Recommendation first; three alternatives; View all candidates (8) on demand | Eligibility, timing and cost at a glance | 0:20 |
| B4 | Why this won, Score breakdown | Open both tabs | Runner-up comparison; weights with inactive terms muted; contribution bars | Objective is configuration; scores are inspectable | 0:30 |
| B5 | Evidence trace | Open "Request parsed", then "Recommendation selected" | Extraction source named; scores and reason | The model only extracts; Python decides | 0:25 |
| B6 | Dispatch | Confirm; press View audit record | Green confirmed state, then the new ledger row | Explicit confirmation and audit | 0:20 |
| B7 | Dispatch | Run R08, then R02 | Refusal with alternative; "not available in the supplied data" | Refuse and decline behaviours | 0:25 |
| B8 | Dispatch | Run R30, preview the split | Least-late option, three human options, split preview | Track 2 awkward cases | 0:25 |
| B9 | Workshop Network | 1,500 tops by 15 Apr | Network map with lit on-time lines; "5 of 8 can take 1,500 tops. 4 return by 15 Apr."; node cards with reasons | Queryable register using the same tools | 0:20 |
| B10 | Simulation Lab, Overview | Lateness, Normal | Duel 1.67% against 1.67%, TIE; every baseline on one scale; four KPI tiles with Tie pills | Honest comparison with the strongest simple rule | 0:25 |
| B11 | Tradeoffs | Switch the objective to Quality only, then Fairness | Heatmap shifts: Quality only puts 70% at SteadyHands | Objectives change decisions | 0:20 |
| B12 | Disruption | Objective Robustness, then Lateness | Phase timeline; first flag day 26 vs 22; 0 pieces vs 1,500 routed while suspect | Shock handling, with the honest note on early flags | 0:30 |
| B13 | Course Evidence | Scroll the scorecard | Duel TIE; scale Random 34.17%, Biggest 84.25%, Cheapest 91.83%; verdict blocks: Fairness qualifies, Robustness qualifies, Quality guardrail fails | Ten-seed evidence, limits shown | 0:30 |
| B14 | Audit Trail | Filter by workshop; Open a row; Evidence → View raw record | Ledger, slide-over, raw JSON on demand | Auditable structured output | 0:15 |

Total: about 5:20. Trim B4 or B14 to land at 5:00.

## Notes for the narration pass

- Say "tie" for lateness against earliest finish, never "as good as".
- If the take uses recorded replies, say once that they were recorded from the live model.
- Do not use Rehearsal: test fixtures in the final video unless the narration says so.
- The disruption numbers above are seed 5105; re-check them on screen if you change the seed.
