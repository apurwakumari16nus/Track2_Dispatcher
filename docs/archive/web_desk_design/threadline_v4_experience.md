# Threadline product experience V4

A refinement of the existing product. The backend, the official evidence in
`eval/`, the data and the simulator are unchanged.

## Material system

Three surfaces, used by meaning (tokens at the end of `src/ui/theme.css`):

| Surface | Where | Treatment |
| --- | --- | --- |
| Standard | Inbox, request card, controls, ledger, detail and route panels | Pearl white, soft border, ambient shadow |
| Analytical | Charts, capacity, comparisons, the network map, evidence | Ice-tinted gradient, firmer border, deeper shadow, title plus question plus source |
| Featured | Recommended workshop, confirmed allocation, principal simulation result | Navy and cobalt over the dark fabric, cyan edge light |

**Signature: the selvedge.** Featured surfaces carry a stitched champagne edge
along the top, like the finished edge of a woven bolt. It turns green on a
confirmed allocation and amber on a least-late decision, and appears nowhere
else, so its presence means a decision lives there. It replaced a looping sheen
animation that implied activity when nothing was running.

**Canvas weave.** The outer canvas carries a vector warp and weft pattern held to
the edges by a mask. It is crisp at any zoom (the earlier raster silk looked
grainy on white) and never sits behind text, forms or charts.

## Pages

**Dispatch.** After evaluation the featured recommendation is followed by an
analytical "Against the next options" panel: the next three permitted workshops
with return date, time and cost differences from the recommendation, defect
risk, and the engine's one-line reason. Workshop photos are labelled
"Illustrative photo".

**Workshop Network.** The four-week capacity chart is now an analytical card:
one row per week with booked (hatched slate), this batch (cobalt) and spare
(green) segments, pieces written on each segment, spare pieces per week, totals
in the key, and the note that it is an estimate from the session queue, not a
booking. Photos carry an "Illustrative photo" label. Map labels have a halo so
route lines never cut through them.

**Simulation Lab.** Four workspaces, each answering one question:

| Workspace | Question | Content |
| --- | --- | --- |
| Performance | How does our policy perform? | Featured hero (ten-seed result, verdict against earliest finish, every comparison policy), policy cards, normal against shock dumbbell |
| Tradeoffs | What do we gain or give up? | Objective verdict cards, the selected objective's weights, lateness against cost, fairness or quality, and every preset's trade table; single-seed workload and sandbox behind an expander |
| Disruption | What happens when a workshop closes? | Seed replay controls, a five-step event timeline (normal operation, simulator closure marked as hidden ground truth, anomaly observed with the leakage caveat, routing response, measured outcome), daily pieces chart, official change under shock for every policy |
| Evidence | Can we defend it? | Official ten-seed view (claims, qualification matrix, seed variability, collapsed full tables, sources and hashes, language status) and a separate single-seed explorer (seed run, order audit) |

**Audit Trail.** A governance header stating that only human confirmations are
logged, a rehearsal-log warning when that log is selected, an activity summary,
a "Decisions by day" chart counted from the records, the ledger, and a decision
timeline that labels every entry as a human-confirmed allocation.

## Review path

1. Dispatch: select R09, press Evaluate request (choose rehearsal if prompted),
   read the featured recommendation and scroll to "Against the next options".
2. Press Trace on the network: watch the routing replay, click GiantWeave, read
   the capacity card.
3. Simulation Lab: Performance, then Tradeoffs (switch Cost, Fairness, Quality),
   then Disruption, then Evidence (switch to Single-seed explorer).
4. Audit Trail: activity, chart, ledger, timeline; open a record.
