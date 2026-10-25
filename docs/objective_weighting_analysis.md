# Objectives and hybrid weights: what the simulator says

25 October 2026. The shared course simulator (120 orders) was used unchanged, with no
model calls. Weights were chosen on the **tuning seeds 6105 to 6114**, then reported on
the **course seeds 5105 to 5114**, the same split as `eval/run_hybrid_sweep.py`. Each
hybrid is `w_lateness = 1 - w` plus `w` on one other term (all terms are scaled 0 to 1
in `objectives.py`). Grid for w: 0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.

Honesty note, from the team's sweep: the separate seeds change only the defect draws and
which workshop closes. The 120 orders are the development orders, so this is not an
unseen-data test.

## Every objective on its own (course seeds, `eval/results.csv`)

| Objective | % late, normal | % late, shock | Change | Largest share | Defect % (pieces) | Cost |
|---|---|---|---|---|---|---|
| Lateness (primary) | 1.67 | 1.92 | +0.25 | 26.3 | 7.18 | 115,566 |
| Earliest finish (strong simple rule) | 1.67 | 1.92 | +0.25 | 26.3 | 7.18 | 115,566 |
| Robustness alone | 23.00 | 22.75 | -0.25 | 17.4 | 6.43 | 115,742 |
| Fairness alone | 24.42 | 26.08 | +1.67 | 17.5 | 6.51 | 116,028 |
| Defect alone | 95.08 | 95.08 | 0 | 70.2 | 2.91 | 129,920 |
| Random (baseline) | 34.17 | 38.17 | +4.00 | 22.6 | 5.60 | 111,780 |
| Hybrid lateness 0.9 / fairness 0.1 (current preset) | 5.08 | 8.50 | +3.42 | 19.7 | 6.22 | 113,172 |
| Hybrid lateness 0.6 / defect 0.4 (current preset) | 18.50 | 20.92 | +2.42 | 40.8 | 5.58 | 109,320 |

## Should robustness stay the secondary objective?

**As an evaluation check, yes. As something to optimise or weight, no.** The case for
moving fairness into the secondary role is stronger.

* The lateness policy is already robust: a two-week hidden closure adds only **0.25
  points** of late batches (random adds 4.0). Its return dates come from the live queues,
  so a closed workshop's growing queue steers new work away on its own.
* Weighting robustness makes things worse, not better. On the tuning seeds every
  robustness weight from 0.05 up raises both lateness and the shock penalty (w = 0.1:
  3.0% late, shock change +2.3 points). No weight passes the selection rule at any
  tolerance. Optimised alone, it reaches 23% late.
* Fairness is a genuine trade-off with a business meaning: dependence on one workshop.
  Lateness alone puts **26.3%** of all pieces at one workshop; a small fairness weight
  brings that to about **19%** for one or two extra late batches in 120.
* Be honest about the tension: spreading work makes the policy more exposed to a closure
  (shock change +1.5 points at w = 0.05, against +0.25 for lateness alone).

**Decision (25 October 2026):** primary objective, minimise lateness; secondary
objective, fairness (largest workshop share), pursued through the hybrid; robustness
reported as a stress test for every policy (normal against shock). The fairness
objective qualifies against all four comparators in both scenarios
(`eval/objective_checks.csv`). Re-running the simulator and both hybrid sweeps after
the change reproduced every committed file byte for byte: the roles changed, the
numbers did not.

## Lateness + fairness: which weight?

Tuning seeds, normal scenario (shock in the last two columns):

| w (fairness) | % late | Late days | Largest share | Defect % | Cost | % late, shock | Change |
|---|---|---|---|---|---|---|---|
| 0 | 1.75 | 0.15 | 26.75 | 6.61 | 115,705 | 2.17 | +0.42 |
| 0.02 | 2.92 | 0.18 | 19.79 | 5.75 | 113,761 | 5.00 | +2.08 |
| **0.05** | **3.33** | **0.27** | **19.20** | **4.91** | **113,301** | **6.08** | **+2.75** |
| 0.1 | 4.67 | 0.36 | 19.81 | 5.58 | 113,305 | 9.08 | +4.42 |
| 0.2 | 6.58 | 0.49 | 20.33 | 5.26 | 113,224 | 10.08 | +3.50 |
| 0.3 (70/30) | 7.25 | 0.55 | 20.90 | 4.93 | 113,179 | 10.92 | +3.67 |
| 0.5 | 8.00 | 0.49 | 20.08 | 5.30 | 113,155 | 11.08 | +3.08 |
| 1 | 24.50 | 7.22 | 17.49 | 5.14 | 116,045 | 27.25 | +2.75 |

The team's pre-declared rule (eligible: within 5 points of lateness-only and better than
random on lateness and largest share; pick the lowest largest share) chose **0.1 on the
0.1-step grid**. On the finer grid the same rule picks **0.05 at every tolerance from 2 to
8 points**.

Course seeds confirm it: 0.95 / 0.05 gives **4.00% late, 19.2% largest share, 5.50% late
under shock**. The current 0.9 / 0.1 gives 5.08%, 19.7% and 8.50%. So 0.05 is better on
lateness, on spread and under shock. 70 / 30 is dominated: more late batches (7.0%) and
more concentration (20.5%).

**Why such a small weight works:** for most batches several workshops are on time, so their
lateness terms are all near zero and a small fairness weight decides between them. Past
about 0.05 the fairness term starts overriding real lateness differences: late batches keep
rising while the spread no longer improves (the largest share bottoms out near 19%).

**Decision: keep 0.9 lateness / 0.1 fairness**, the weight the team's rule chose on the
0.1-step grid before any result was seen. The finer grid is reported as a sensitivity
check, not used to change the weight: picking 0.05 after seeing it perform slightly better
would be tuning to the results. The two settings behave alike: the largest share falls
from 26% to about 19 to 20% at a cost of about three extra late batches per hundred.

## Lateness + defect: which weight?

The current 0.6 / 0.4 preset gives 18.5% late and puts 40.8% of pieces on one workshop.
The rule picks **0.02** (3 to 8 point tolerance; none at 2). On the course seeds that gives
3.75% late and defect exposure 6.57% (from 7.18%), but the largest share rises to 34.7%.
Defects are a weak secondary here: the gain is small and work concentrates.

**Option:** if you keep a second hybrid, use 0.98 / 0.02 and report it as
"reported only". Otherwise drop it: the deck names one hybrid, lateness + fairness.

## Lateness + cost (for completeness)

w = 0.02 cuts cost from 115,566 to 100,732 (13%) for 2.25% late on the course seeds, but
the largest share jumps to 37.8%. It is worth one sentence as a sensitivity result, not a
headline.

## Not changed

`objectives.py` and the official evidence files are unchanged. The hybrid preset stays at
0.9 / 0.1, and the lateness and defect hybrid stays at 0.6 / 0.4 (reported only).
