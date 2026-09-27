# What Track 2 is building

The project brief (Capstone_Project_Tracks_v4.pdf) asks for a
quick-response subcontracting system with two demonstrable paths:

1. Natural-language requests: extract facts, ask when ambiguous, refuse
   ineligible suggestions, honor attributed constraints, automatically choose a
   workshop, and produce a faithful structured decision.
2. Evaluation: replay the 120 supplied orders through the shared simulator,
   compare all three baselines plus a strong simple heuristic, test another
   objective and a hybrid, and investigate the hidden closure scenario.

The goal is to build and evaluate the dispatch system, not merely run a simulator.
The LLM handles language; Python tools perform arithmetic. The brief allows
different allocation mechanisms and explicitly values tools and outcomes over
multi-agent complexity. It does not require an LLM to calculate or select a
workshop directly.

The simulator automatically allocates every order. No manual selection or
confirmation is involved. The Dispatch page's confirmation is a prototype
workflow choice for accepting an operational audit entry; it is not a Track 2
requirement and is not part of simulation.

## Run the app

From the repository root:

```bash
uv sync
uv run streamlit run src/app.py
```

Open http://localhost:8501. Simulation is the landing page. On first visit it
computes the complete single-seed diagnostic at seed 5105. Course reporting
uses the separate ten-seed CLI evaluator; dashboard exports are not ten-seed averages. Enter a seed and press **Run
simulation** to run a new experiment. It needs no API key.

Every experiment runs the four comparison policies and six objective presets in
both scenarios, with independent allocation state. It stores results in this
browser session and does not overwrite saved evaluation files or operational logs.

- **Performance:** inspect objectives and scenarios, eight selectable ranking
  metrics, a delivery/cost comparison, allocation by workshop, and turnaround
  over dispatch dates. KPI deltas compare with earliest finish.
- **Disruption analysis:** compare routing to the affected workshop with random,
  inspect anomaly events, and compare normal/shock lateness for every policy.
  This tab always describes the shock experiment, regardless of the Performance
  scenario selector.
- **Order audit:** inspect automatic workshop choices and their actual decision
  records. Candidate estimates are distinct from realized simulator outcomes.
- **How it works:** definitions, evaluation limitations, input/code fingerprints
  and reproduction commands.
- Download full metric CSV, per-batch outcomes and a report of baseline wins/ties.

The charts use exact simulator results and the same arithmetic as the CLI.
Horizontal bars begin at zero; the selected objective uses teal. Trade-off ties
share a point with combined tooltip labels, without moving observations.
Temporal lines show daily means, not individual-order durations. No confidence
intervals are claimed for a single-seed experiment.

## A useful project demonstration

1. Open Performance with Lateness and Normal. Compare Random, Biggest workshop,
   Cheapest and Earliest finish. Explain ties and losses rather than only wins.
2. Switch to Quality, Fairness and the hybrid settings. Show costs and allocation
   concentration changing with the objective.
3. Open Disruption analysis. Inspect the actual observed anomaly and whether the
   selected allocator keeps sending work while the workshop is flagged.
4. Open Order audit. Show eligible candidates, estimates and why the chosen
   workshop won.
5. Go to Dispatch for R09 (allocation), R01 (clarification), R08 (refusal with an
   alternative) and R02 (unanswerable). Live language intake requires API settings.
6. Export results, complete independent human labels, and present the separate
   language evaluation alongside the simulation evidence.

## Command-line alternatives

```bash
# Full comparison, including our allocator and both scenarios:
uv run python eval/run_simulator.py --seed 5105 --seeds 10

# Only the three supplied baselines:
uv run python harness/simulate.py
uv run python harness/simulate.py --shock --seeds 10

# Synthetic language-pipeline check, not real LLM accuracy:
uv run python eval/run_inbox.py --mock --output-dir Apurwa/validation/mock_inbox

# Live language evaluation (API calls on cache misses):
uv run python eval/run_inbox.py
```

## Limitations and future improvements

Single-seed results do not establish statistical superiority. In the v3 harness,
normal and shock scenarios have corresponding defect draws; different workshop
choices can still produce different defect outcomes. Queues can include future
closure delay before day 30, so early flags are simulated queue anomalies rather
than demonstrated real-world early warnings. The supplied orders and default
seed have been used during development; they are not a held-out benchmark.
Human labels are incomplete, so actual language accuracy is not established.

Useful next additions are multi-seed uncertainty analysis, a full inbox evaluation
page with human labels, and a structured clarification flow. There is no need
to add a manual workshop picker: the allocator already makes that decision.

The eight measures include mean late days over all batches and piece-weighted
defect exposure. The baseline report also applies Track v4 objective guardrails.
The simulator uses the CSV queue as a January 1 start; Dispatch independently uses
it as the April 1 snapshot. Default whole-job mode remains active.
