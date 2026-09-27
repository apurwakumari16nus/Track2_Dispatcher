# Data v3 migration and validation - 25 September 2026

## Scope

Active inputs are `data/` and `harness/`, supplied by the user. The official
`harness/simulate.py` is preserved; our changes are to integration, evaluation,
tests, UI snapshot wording and documentation. `data_old/`, `harness_old/` and
other user backups were not changed or deleted. Optional stages mode remains
off; tools reject a nonempty `from_stage` explicitly. No weights were tuned.

The current order/workshop CSVs are unchanged from the previous release.
Nine inbox requests changed (R04, R06, R07, R16, R17, R22, R23, R26, R27).
All nine extraction fixtures, including orders, pieces, products, dates and
constraint text, now match the active messages. The file fingerprint remains
an enforced stale-fixture check. No human labels were filled by software.

## Changes

- Official eight-metric arithmetic via `Simulator.metrics()`, with `late_days`
  over all batches and `pct_defect_pieces` weighted by batch size.
- Ten paired seeds by default, 5105-5114; a fresh allocator for each seed and
  condition. The official averaging helper cannot reset stateful callables.
- Twenty averaged rows in `eval/results.csv`; 200 rows in
  `eval/results_per_seed.csv`; individual and averaged shock-minus-normal changes
  in `eval/shock_changes_per_seed.csv` and `eval/shock_changes.csv`.
- Track v4 objective checks in `eval/objective_checks.csv`, including lateness
  guardrails relative to random and explicit ties/losses in `baseline_wins.md`.
- Updated charts, shock trace and evidence. The trace labels targets using the
  harness's separate seed+6 generator, without passing target information to policies.
- Explicit April 1 queue snapshot in the app, inbox audit, and documentation.
- Revised team instructions and personal handbook. Personal files remain ignored.

## Commands and evidence

```bash
python -m pytest -q
python -m pip check
python harness/simulate.py
python harness/simulate.py --shock --seeds 10
python eval/run_simulator.py --seed 5105 --seeds 10
python eval/shock_trace.py --output eval/shock_trace.csv --events eval/shock_events.json
python eval/run_inbox.py --mock --output-dir Apurwa/validation/mock_inbox --cache-dir Apurwa/validation/mock_inbox/cache
python eval/run_inbox.py --mock --offline --output-dir Apurwa/validation/mock_inbox --cache-dir Apurwa/validation/mock_inbox/cache
```

| Check | Result |
| --- | --- |
| Full offline tests | 242 passed, 1 skipped for incomplete human labels |
| Dependency consistency | No broken requirements |
| Simulator matrix | 200 successful runs; 20 mean rows; all eight metrics |
| Shock integration | Target labels independently checked across ten seeds; mid-job closure and paired defect draws tested |
| Revised inbox facts | Nine new fact sets verified; three impossible deadlines warn with numerical alternatives |
| Mock inbox | 30 completed; zero operational errors or False conditional checks; all faithfulness checks passed |
| Cached mock replay | 30 hits, zero misses, no API calls |
| Streamlit AppTest | All 30 request previews pass; no automatic audit writes |
| Confirmation/log tests | Single append, repeated-click protection, refusal alternative, queue updates and log filters pass |
| Native browser | Revised R07: W6, April 4, 25 spare days. R28: W1, April 9, -11 spare days with both warnings |

Mock branch counts are 16 allocate, 7 clarify, 4 refuse and 3 decline. They
are implementation diagnostics, not human labels or LLM accuracy. The human
label comparison is unscored (0/30). All checks used the offline/mock boundary.

## Findings to report honestly

Lateness ties earliest-finish on all eight metrics in both conditions for every
seed. Pure defect has 2.91% piece-weighted defect exposure but 95.08% late batches
versus random's 34.17% in normal runs, so it fails the lateness guardrail.

The v3 harness immediately includes a future closure in an affected queue.
In the default robustness trace W2 is flagged on day 26, expected 9.44 days versus
observed 23.44, before the closure starts on day 30. It clears on day 47 and
receives zero pieces while flagged. This is simulated queue-anomaly detection,
not verified real-world advance warning. Rework can also trigger flags.

The inbox uses workshops.csv as the **1 April 2026** snapshot, while the simulator
independently reuses the same queue values at **1 January 2026**. It replays all
120 orders as whole jobs, one workshop per batch. Split previews do not change
this contract. Normal/shock metric differences use paired seeds, and per-run
p90s are averaged rather than calculated from pooled outcomes.

## Remaining work

Human reviewers must complete and reconcile labels, followed by measured live
intake evaluation with configured credentials. Complete individual failure
analysis and the final course reports. Do not claim labels were frozen before
implementation. The defect preset needs an improved strategy if selected as the
primary objective. This run does not establish Windows/cloud behaviour, real
workshop integration, split execution, or the 90-second usability target.
The personal video is preserved but still describes the older benchmark; its
entry-point README identifies it as historical. No commit or push was made.

## Recheck after merging ui-sim - 27 September 2026

The Data v3 migration was saved in local commit `4215478` and merged with the
teammate's `ui-sim` branch in `9cf1161`. The active inputs remain `data/` and
`harness/`; neither the official inputs nor the `_old` backups were modified
in this recheck. Optional stages mode remains off.

The app now opens on **Simulation**, with separate **Dispatch**, **Workshop
register**, and **Decision log** pages. The dashboard runs one seed for diagnostic
inspection. Its eight metrics agree with the CLI at the same seed; use the
CLI's ten paired seeds for course reporting. The merge fixed the new metric
labels and the test's single-seed versus ten-seed comparison. The allocation
formula and objective weights were not changed.

Validation repeated using the frozen uv environment (Python 3.13.7):

- **248 passed, 1 skipped** in pytest; the skip still requires human labels.
- All **200 simulator trials / 20 averaged rows** reproduced the saved outputs;
  normal and ten-seed shock baseline commands also completed.
- All **30 mock inbox requests** completed with passed numerical faithfulness,
  no operational errors and no False conditional checks. Cached replay had
  **30 hits, zero misses** and reproduced the same rows.
- All **30 Streamlit previews** passed with synthetic extraction, no live API
  calls and no automatic audit writes. The suite separately checks confirmation,
  log filtering, navigation and dashboard metric selection.
- R20, R28 and R30 retained `none_makes_date`, numerical late ETAs and options.
- The actual local Streamlit server loaded the Simulation page in Chrome,
  showing 120 orders, 20 runs and the single-seed reporting notice.

The personal handbook now explains the merged UI, uv/lockfile setup and new
modules. It remains under Git-ignored `Apurwa/`; the previous edition is archived.
Detailed rerun logs are in `Apurwa/validation/merged_v3/`. No live intake accuracy,
Windows/cloud deployment or dispatcher timing claim follows from these checks.
The human labels remain 0/30 complete. This section records the offline
recheck before the subsequent repository sync.
