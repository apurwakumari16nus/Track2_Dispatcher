# Team handbook: understand and run Track 2 Dispatch

This is the short starting guide for someone cloning or pulling the repository.
Use the [README](../README.md) for deployment and detailed troubleshooting.

## 1. What the project does

A dispatcher needs to send a garment order to an outside workshop. The system
checks which workshops can accept it, estimates return dates and costs, and
recommends a workshop according to a chosen priority, such as speed or quality.

There are two ways to use the project:

- **Simulator:** replays structured orders and compares allocation policies. It
  needs no AI model or API key.
- **Dispatch app:** reads a written request, shows a checked recommendation, and
  lets a person confirm a local audit record. Live text intake needs an API key.

```text
Written request -> LLM extracts fields -> Python checks the facts
                -> tools calculate -> allocator chooses -> app shows evidence
                -> person confirms -> local decision log

CSV orders -> simulator -> allocation policy -> measured results and charts
```

The LLM interprets language. Python performs the calculations and chooses the
workshop. Explanations use templates populated with recorded facts.

## 2. First setup

Install Git, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/).
Run these commands in a terminal.

**Mac**

```bash
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
uv sync
cp .env.example .env
```

**Windows PowerShell**

```powershell
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
uv sync
Copy-Item .env.example .env
```

A virtual environment (`.venv`) keeps this project's Python packages separate
from other projects. `uv sync` creates or updates it from the committed lockfile.
For an existing clone, enter its folder instead of cloning again. Your local
folder may be called `Track2_dispatch`; a new clone uses `Track2_Dispatcher`.

**Run all commands below from the repository root**, where `pyproject.toml` and
`uv.lock` live. Use `uv run` on every platform; activation is unnecessary.

For live intake only, edit `.env` and fill in `LLM_PROVIDER` plus that provider's
key and model (`ANTHROPIC_API_KEY` and `ANTHROPIC_INTAKE_MODEL` by default).
The README provides a model configuration example.
Never commit your key. You can run tests and the simulator without these values.

## 3. Which command should I run?

Start with tests, then the simulator evaluation. Open the app after configuring
live intake, or use the mock inbox command to check the text-processing pipeline
without API calls.

| Purpose | Command | What to expect |
| --- | --- | --- |
| Check the code | `uv run python -m pytest -q` | Automated tests; no API calls by default. Human-label comparison skips while labels are incomplete. |
| Compare all policies | `uv run python eval/run_simulator.py` | 200 runs across ten paired seeds; 20 averaged rows, `eval/results.csv`, three charts in `eval/charts/`, and `eval/baseline_wins.md`. |
| Run supplied baselines | `uv run python harness/simulate.py` | Printed metrics for random, biggest-workshop and cheapest policies. |
| Run baselines with a closure | `uv run python harness/simulate.py --shock --seeds 10` | Same baselines with the simulated disruption. |
| Inspect shock detection | `uv run python eval/shock_trace.py` | Per-day CSV printed to the terminal for random versus the robustness allocator. |
| Check inbox using prepared extractions | `uv run python eval/run_inbox.py --mock --output-dir Apurwa/validation/mock_inbox` | Synthetic results saved separately; no live model calls or model-accuracy claim. |
| Evaluate live intake | `uv run python eval/run_inbox.py` | Processes 30 requests; creates `eval/inbox_results.csv`, `eval/failure_cases.md`, and `eval/inbox_audit.json`. Cache misses call the API. |
| Open the dispatcher screen | `uv run python -m streamlit run src/app.py` | Local app at `http://localhost:8501`. Keep the terminal open; Ctrl+C stops it. |

`Apurwa/` is an ignored local folder. The mock runner creates its output folder;
you do not need anyone's personal files to run it. `--offline` means reuse an
existing matching cache without new API calls; it does **not** create mock replies.
Do not set `TRACK2_INTAKE_REAL_LLM=1` for ordinary offline tests.

The app opens on the Simulation dashboard for one-seed exploration. Its exports
are diagnostics; the CLI comparison above supplies the required ten-seed means.
Both use the same eight official metrics.

## 4. How to use the app

1. Select **Dispatch** in the sidebar. Keep **Today = 2026-04-01** for the supplied inbox scenario. Choose an objective;
   its weights are shown alongside it.
2. Select an inbox request or enter new text, then click **Dispatch**.
3. Read the verdict and any warning before the recommendation. The four outcomes
   are allocate, needs clarification, refused, and cannot answer. A refusal can
   still offer a permitted alternative.
4. Review the workshop, ETA, days to spare, cost and defect probability. Compare
   the candidates; expand **Ineligible**, **Tool outputs**, and **Full explanation**
   when you need the supporting evidence.
5. Click **Confirm allocation** only to accept the recommendation. Dispatch alone
   writes nothing. Confirmation saves `records/decisions.jsonl` and updates the
   session's projected queues. It does not contact a workshop.
6. Open **Decision log** to inspect accepted records and filter by workshop or sender.

R09 is a useful first example with the lateness preset and fresh queues: W6
Nimble Needle, return 4 April, five days to spare, modeled cost 180. Later
confirmations change queues, so subsequent recommendations can differ.

## 5. Where the code lives

| File or folder | Responsibility |
| --- | --- |
| `data/` | Orders, eight workshop profiles, 30 written requests, and the data dictionary. |
| `harness/simulate.py` | Supplied simulation framework: replays orders, applies a hidden shock, and measures outcomes. Keep it unchanged; it reads `harness/../data/`. |
| `src/tools.py` | Eligibility, queues, ETA, cost, split estimates and queue-anomaly monitoring. |
| `src/objectives.py` | Six named priorities and their scoring formulas; also loads custom JSON/YAML weights. |
| `src/allocator.py` | Deterministic workshop selection, allocation history and decision records. |
| `src/heuristic.py` | Simple earliest-finish comparison policy. |
| `src/intake.py` | LLM extraction followed by Python checks against the data. |
| `src/agent.py` | Coordinates clarification, refusal, decline, allocation and explanation templates. |
| `src/faithfulness.py` | Checks whether numbers in the explanation are supported by the record. |
| `src/records.py` | Reads and explicitly appends the local JSONL audit file. |
| `src/app.py` | Streamlit interface. Streamlit turns Python code into the browser screen. |
| `eval/`, `tests/`, `config/`, `docs/` | Evaluation runners/evidence, automated tests, configuration example, and specifications. |

For an implementation change, read the relevant module and its matching tests.
For calculation contracts, start with [tool_spec.md](tool_spec.md). For intake
evaluation, read [inbox_evaluation.md](inbox_evaluation.md).

## 6. What is proven, and what remains unfinished?

The Data v3 migration was checked on 25 September 2026 with offline tests,
200 simulator runs across ten paired seeds, and all 30 updated inbox requests
through prepared extractions and the Streamlit test driver. See
[data_v3_migration.md](data_v3_migration.md) for current evidence and limitations.
The lateness allocator ties earliest-finish on all eight metrics; do not claim
it beats that heuristic. The pure-defect preset fails the lateness guardrail.
Prepared extractions do not measure live LLM accuracy.

The inbox uses `workshops.csv` as the **1 April 2026** queue snapshot. The
simulator independently reuses it on **1 January** for its replay of all orders.
R20, R28 and R30 intentionally cannot meet their deadlines: show numbers and
options. R07 is now a feasible request; old screenshots may show the old data.
Keep optional stages mode off for our allocator/app. The supplied harness's
future-adjusted queues can reveal a closure before it starts; describe monitor
flags as simulated queue anomalies rather than real-world early warning.

The evaluator saves eight metrics, individual seeded runs, paired changes,
objective guardrails, source fingerprints and updated charts. Ten-seed shock
averages are required; `--seeds 1` is only a quick diagnostic.

Two human reviewers still need to complete and reconcile the
[label templates](../eval/labeling/README.md) before final behaviour scoring.
Record the real labeling timeline: intake already exists. A past deadline cannot
be satisfied; warnings and an explicit least-late fallback are expected.

Other limits: queues are local session projections, not a factory feed; the log
is local storage; split estimates do not execute split allocations; and numerical
faithfulness does not prove every sentence's meaning or the decision's quality.

Before sharing changes, run the relevant tests and inspect `git diff` and
`git status`. Keep `.env`, `.venv`, audit logs, caches and `Apurwa/` out of commits.
Commit source, tests and useful shared documentation. Use the README's deployment
section if you need to host the app.
