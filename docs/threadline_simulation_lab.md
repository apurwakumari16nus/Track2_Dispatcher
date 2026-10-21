# Threadline Simulation Lab

The page answers "how does our policy perform, and what can we honestly
claim?" Official numbers come first; single-seed diagnostics sit behind tabs.

## Structure, top to bottom

1. **Header and command bar**: objective, scenario (normal or shock), seed, Run.
   The seed and Run only affect the seed diagnostics.
2. **Hero** (navy): the selected objective's ten-seed result, its verdict against
   earliest finish, a one-paragraph interpretation, and every comparison policy on
   one shared bar scale with its outcome chip.
3. **Policy comparison**: five cards (our policy, Random, Biggest workshop,
   Cheapest, Earliest finish) with the objective's own metric, late batches,
   late days, cost and largest workshop share, and the course pass-rule status.
4. **Every objective**: one card per objective (lateness, fairness, robustness,
   quality, two hybrids) with its verdict. Clicking a card moves it into the hero.
5. **Analysis tabs**
   - *Trade-offs*: ten-seed lateness against cost (policies on the same point get
     one "(tie)" label), the seed's workload heatmap, objectives as weight
     settings, and the custom sandbox.
   - *Robustness*: normal against shock for every policy (dumbbell), the change
     under shock (bars), then the seed's closure timeline.
   - *Seed variability*: all ten official seeds per policy with the mean tick.
   - *Seed run*: the selected seed's tiles against earliest finish and a
     completion-time histogram (ours, earliest finish, random).
   - *Order audit*: any automatic decision from the seed replay.
6. **Course Evidence**: four claim boxes (beats or qualifies, ties, fails, do not
   claim), the full outcome matrix, shock deltas, and the language-evaluation card.

## Honesty rules in the code

`src/ui/lab_evidence.py` maps each committed check outcome to a fixed word:
qualifying is "Beats", an equal required metric is "Tie", a lost lateness
guardrail is "Guardrail fails", and hybrids are "No course rule". The hero
says "TIE with earliest finish" for lateness and spells out that a tie is not a
win. Quality only shows "Guardrail fails" in red. Tests in
`tests/test_lab_evidence.py` pin these verdicts to the committed files.

## Chart palette

Threadline royal (#2A77E8) for the selected objective, light blue for our other
objectives, deep slate for earliest finish, light slate for the supplied
baselines, amber for shock. Green, amber and red appear only in status chips.
