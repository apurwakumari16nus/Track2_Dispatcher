# Track 2 Dispatch

A subcontractor dispatch desk: turn a request into checked order facts, compare
eligible workshops, and show a recommendation with its supporting calculations.
The LLM extracts language; Python checks eligibility, estimates delivery and cost,
and chooses the workshop. A dispatcher explicitly confirms the local audit entry.

**New to the repository?** Read the concise [team handbook](docs/team_handbook.md)
for the project overview, setup, run commands, app walkthrough, and code map.

## Prerequisites

- **Python 3.11+**, 64-bit; check the version before creating the environment.
- **uv** package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/)).
- **Git**, a terminal, and internet access to install packages.
- An **Anthropic API key** (default provider) or an OpenAI key, available API credit,
  and access to the configured model for live requests. No key is needed for the simulator or ordinary tests.

The quick start targets **under 10 minutes once these prerequisites are ready**;
download speed and API availability affect timing. Evaluating all 30 live inbox
requests is a separate step. No Java, database, Node.js, or GPU is required.

## Setup and first run

The app opens on **Dispatch** and has four areas: **Dispatch**, **Workshop
Network**, **Simulation Lab** and **Audit Trail**. See
[Product UI v2](docs/product_ui_v2.md) for the page structure and what changed,
[demo readiness](docs/demo_readiness.md) for recording, and the
[storyboard draft](docs/demo_storyboard_draft.md). The Simulation Lab needs no
API key; its **Course evidence** tab reads the committed ten-seed results.
Dispatch reads requests with the live model, or with a clearly labelled
rehearsal source (recorded model replies, or the synthetic test fixtures).

### Mac — Terminal (or Linux)

```bash
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
python3 --version
uv sync
cp .env.example .env
open -e .env
```

`uv sync` creates (or updates) `.venv` from `pyproject.toml` and the committed
`uv.lock`. Use `uv run` below; no activation is necessary.

### Windows — PowerShell

```powershell
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
py -3 --version
uv sync
Copy-Item .env.example .env
notepad .env
```

These Windows commands do not require activation or an execution-policy change.
`uv run` works the same way on Mac, Linux, and Windows.

### Configure the API and open the app

In the `.env` file opened above, save these settings, replacing the key placeholder:

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_INTAKE_MODEL=claude-sonnet-5-5
```

The default provider is Anthropic. Intake calls the Claude Messages API with a
JSON-schema structured output, so the reply is always the extraction form; see the
[Claude structured outputs guide](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
Current Claude models reject a non-default temperature, so none is sent; the
evaluator's reply cache is what makes repeated runs reproducible. To use OpenAI
instead, set `LLM_PROVIDER=openai`, `OPENAI_API_KEY` and `OPENAI_INTAKE_MODEL`
(a model with Chat Completions, strict JSON Schema and `temperature=0`, for
example `gpt-4.1-mini-2025-04-14`). The app loads `.env` automatically; existing
environment values take precedence. Never commit `.env` or your real API key.

From the repository root:

```bash
uv run streamlit run src/app.py
```

Open **http://localhost:8501** if the browser does not open automatically. Keep the
terminal running; use **Ctrl+C** to stop it.

For an inbox check, stay on **Dispatch** with **01/04/2026** and the **Minimise
lateness** objective, select an inbox request (or a scenario shortcut such as
R09) and click **Dispatch**. Review the recommendation, the candidate panel and
the decision explorer (Summary, Candidates, Why this won, Evidence, Execution
trace). **Confirm** writes one local entry to `records/decisions.jsonl`; Dispatch
alone writes none. Rehearsal sources write to `records/rehearsal_decisions.jsonl`
instead. The **Audit Trail** shows saved entries. Confirmation does not send a
message to a workshop. Without an API key, choose **Rehearsal · fixtures** in the
sidebar to try every page; those extractions are test fixtures, not model output.

Always run commands from the repository root. Keep `data/` beside `harness/`:
the unchanged simulator reads its inputs from `harness/../data/`.

## Run evaluations and tests

Run evaluation commands after stopping the app, or in a second terminal at the
repository root. `uv run` uses the locked project environment on every platform.

| Task | Command |
| --- | --- |
| Simulator evaluation | `uv run python eval/run_simulator.py` |
| Live inbox evaluation | `uv run python eval/run_inbox.py` |
| Tests, no API calls by default | `uv run pytest -q` |
| Original simulator | `uv run python harness/simulate.py` |
| Original simulator with closure | `uv run python harness/simulate.py --shock --seeds 10` |

**Simulator evaluation** runs random choice, greedy biggest, cheapest, earliest
finish, and all six allocator presets with and without the shock over ten paired
seeds, 5105–5114 (200 runs, 20 averaged rows; stages mode off). It prints a
Markdown table and creates `eval/results.csv`,
`eval/baseline_wins.md`, and these charts:

- `eval/charts/lateness_by_policy.png`
- `eval/charts/tradeoff_lateness_vs_cost.png`
- `eval/charts/tradeoff_lateness_vs_fairness.png`

Metrics use the official v3 `Simulator.metrics()` arithmetic, including
`late_days` (mean lateness over all batches) and `pct_defect_pieces` (pieces in
defective batches). `results_per_seed.csv` keeps all 200 runs;
`shock_changes_per_seed.csv` and `shock_changes.csv` keep paired shock-minus-normal
differences; `objective_checks.csv` checks Track v4 criteria and guardrails.
`simulator_metadata.json` records seeds, mode, aggregation, and source hashes.
Every run starts with a fresh allocator and shock monitor. Percentages are on a 0–100 scale;
fairness in the chart is `100 - max_share`. The baseline report includes cases
where our allocator loses. Use `--seed 42 --seeds 10 --output-dir eval/seed_42` to keep an
additional experiment separate from the default outputs. `--seeds 1` is a quick
diagnostic only; report ten-seed shock averages for the course.

**Inbox evaluation** runs all 30 requests at the reference date 2026-04-01 with
the lateness preset. It creates `eval/inbox_results.csv`, `eval/failure_cases.md`,
and `eval/inbox_audit.json`, and prints a summary by behaviour class. Live cache
misses make paid API calls. Matching raw replies are reused from `eval/cache/`;
`--offline` forbids new calls and reports missing cache entries. Temperature 0
reduces variation; cached replies make repeated extraction reproducible.

The team must independently complete and reconcile **`eval/labels.csv`** before
claiming behaviour accuracy. At documentation time, human answers are blank:
missing labels remain unscored, and the human-label comparison test skips. Do not
present those blanks as passes. Intake is already implemented, so labels cannot
now be described as frozen before development. Record the actual review timing,
prior exposure to system output, and reconciliation; freeze labels before final
scoring and reserve additional unseen requests where possible. Previously saved
evaluation files are not proof of a successful live run; inspect the execution
notes and regenerate them.

For a free synthetic smoke test (not an evaluation of the real LLM):

```bash
uv run python eval/run_inbox.py --mock --output-dir Apurwa/validation/mock_inbox
```

`Apurwa/` is a Git-ignored local folder for personal study materials and validation
outputs. It is excluded from the submission and is not needed to run the app.
The evaluator creates the requested output directory when needed; mock results
there must not be presented as live inbox evaluation evidence.

For the intake confusion matrix, run `uv run pytest tests/test_intake.py -q -s`.
Set `TRACK2_REQUIRE_LABELS=1` to fail rather than skip incomplete human labels.
`TRACK2_INTAKE_REAL_LLM=1` optionally enables live intake tests and API charges.
In PowerShell, set a flag with `$env:TRACK2_REQUIRE_LABELS = "1"`; on Mac use
`export TRACK2_REQUIRE_LABELS=1`. Clear flags after use (`Remove-Item Env:NAME`
on Windows or `unset NAME` on Mac).
See [inbox evaluation details](docs/inbox_evaluation.md).

## Course data version and interpretation

The active `data/` and `harness/` use the supplied Data v3 release, interpreted
against Spec v5 and Tracks v4. Old `_old` folders, if present locally, are backups
and are not used. The official harness is preserved as supplied.

For inbox decisions, `workshops.csv` is the **1 April 2026 queue snapshot**.
The simulator independently reuses those numbers on **1 January 2026**, replaying
all 120 orders as whole jobs, one workshop per batch. Do not derive one snapshot
from the other. Queues and processing/lead numbers appear in the UI candidates.

Nine inbox requests were revised; R20, R28 and R30 are deliberately infeasible.
The response must show the late ETA and options, requiring explicit confirmation.
Optional `--stages` works in the supplied harness, but our tools/app/evaluator
support the default whole-job mode only and reject stage dispatch explicitly.

Current ten-seed results: the lateness preset ties earliest-finish; pure defect
reduces piece-weighted defect exposure but fails the random-policy lateness
guardrail. See `eval/baseline_wins.md` for all comparisons. The simulator can
expose future closure delay through its queues (W2 flagged on day 26 with the
default robustness trace, before closure on day 30). This is simulated queue
anomaly detection, not proof of realistic advance outage detection.

See [migration and validation notes](docs/data_v3_migration.md).

## Architecture

The main path is **app → intake → agent → allocator/tools → template →
faithfulness → explicit confirmation → records**. The simulator uses the
allocator directly without language extraction.

**[src/intake.py](src/intake.py)** is the only LLM boundary for free-text requests.
It requests schema-constrained JSON at temperature 0, then applies Python checks
against orders and workshops. It resolves orders, handles missing information,
flags overdue dates, checks packing and suggested-workshop eligibility, and keeps
raw extraction plus post-check evidence. It does not choose a workshop or estimate
its delivery time or cost.

**[src/tools.py](src/tools.py)** provides eligibility, queue, ETA, cost, overload,
candidate, order-option, and two-workshop split calculations. Its `ShockMonitor`
compares observed queues with predictions to flag unexplained delays after work
has been sent. Tool tracing captures outputs for inspection. The arithmetic
follows the simulator; the monitor cannot see the hidden closure schedule. See
[the tool specification](docs/tool_spec.md) for inputs, outputs, non-goals, and
specific failure modes.

**[src/objectives.py](src/objectives.py)** defines validated objective weights,
six named presets, JSON/YAML loading, and auditable scoring terms. It balances
lateness, defects, allocation share, queue anomaly risk, and cost; smaller scores
are better. Its scoring docstring explains each normalization and weight.

**[src/allocator.py](src/allocator.py)** keeps allocation history and the shock
monitor, filters candidates using constraints, and deterministically selects a
workshop. Its `DecisionRecord` contains candidates, scores, exclusions, reasons,
flags, and alternatives for awkward cases. No eligible workshop produces an
escalation; if every candidate is late, it explicitly recommends the least-late
option. Its callable interface plugs into the unchanged simulator.

**[src/heuristic.py](src/heuristic.py)** is the earliest-finish baseline. It chooses
the eligible workshop with the smallest queue plus processing plus lead time.
It provides a simple comparison that our more elaborate system must earn the
right to beat; it uses no LLM or weighted objectives.

**[src/agent.py](src/agent.py)** connects parsed requests to clarification,
declining unavailable questions, refusal with an alternative, and allocation.
It maps preferences to objectives, applies exclusions, and optionally calculates
a split preview. It constructs explanations from templates and checks them.
`Agent` retains history across calls; standalone `handle()` starts fresh history.
It returns structured evidence without automatically writing an audit file.

**[src/faithfulness.py](src/faithfulness.py)** extracts numeric tokens, dates,
identifiers, money, and percentages from an explanation and checks them against
allowed evidence in the decision record. It returns pass/fail and unmatched
values. This catches unsupported numbers separately from whether the allocation
itself was correct; it does not prove the meaning of every sentence.

**[src/records.py](src/records.py)** explicitly appends JSONL audit entries with
logging time, sender, attributed constraints, and a freshly checked faithfulness
result. It loads them for the log page and reports malformed records instead of
dropping them. Cross-platform file locks coordinate cooperating local readers
and writers on Windows, Mac, and Linux.

**[src/app.py](src/app.py)** is the Streamlit entry point: theme, sidebar,
extraction-source choice and routing to the four areas in **[src/ui/](src/ui)**.
**[src/desk.py](src/desk.py)** holds the session logic: Dispatch creates a
preview, an independent replay verifies it, and confirmation validates and saves it
before updating session history and queues. **[src/rehearsal.py](src/rehearsal.py)**
supplies labelled extraction sources; `intake.extraction_source()` routes the raw
reply without changing any post-check. `src/ui/explain.py` derives "why this won",
"why not", score decomposition and the execution trace from the recorded decision
without re-deciding it. Queue state belongs to the browser session and is not a live
workshop feed.

Supporting folders: `data/` holds inputs, `harness/` the supplied simulator,
`eval/` the two evaluation runners and evidence, `tests/` the automated checks,
`config/` a custom objective example, and `docs/` the detailed specifications.

## Design decisions

**Deterministic allocation; narrow LLM role.** Eligibility, calculations,
constraints, and ranking are ordinary Python so they can be audited and tested
against the simulator. Given the same inputs, configuration, and state, the
allocator makes the same choice. The LLM handles intake only in this version.
The design permits future tone-only rephrasing if the faithfulness check still
passes; that optional rephrasing is not implemented. Current explanations are
fixed templates filled with recorded facts.

**Objectives as inspectable configuration.** Weights describe a dispatcher's
priorities, so changing priorities should not require rewriting the scoring
algorithm. `load_config()` accepts JSON or YAML, validates it, and records its
name. [config/objective.example.yaml](config/objective.example.yaml) provides a
complete example. The six built-in UI/evaluation presets currently live in
`PRESETS` in Python; the app does not yet offer a custom-config upload. Code can
load a file with `load_config("config/objective.example.yaml")` and pass the
result to `Allocator(config)`.

**Faithfulness is a separate check.** A plausible explanation can invent a date
or price even when the chosen workshop is sensible. Numeric evidence matching
makes that failure visible and blocks an unfaithful audit entry. Decision
correctness is evaluated separately: a real number attached to the wrong claim
can still pass numeric membership checking.

**Reproducible evidence.** Direct dependencies are pinned to exact versions in
[pyproject.toml](pyproject.toml), with complete resolved versions in the committed
[uv.lock](uv.lock). `requirements.txt` is a compatibility export for Streamlit
Community Cloud; after changing dependencies, refresh it with
`uv export --no-dev --no-hashes -o requirements.txt`. The simulator uses an
explicit seed, and inbox extraction uses a versioned model and cached replies.
Human labels must be written independently rather than copied from system output.

## Deploy to Streamlit Community Cloud

1. Make sure the desired version is committed and pushed to
   `apurwakumari16nus/Track2_Dispatcher`, including `src/`, `harness/`, `data/`,
   `requirements.txt`, and `.streamlit/config.toml`. Keep `.env` and
   `.streamlit/secrets.toml` out of Git; both are ignored.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) with the
   GitHub account that can access the repository. Choose **Create app**, then
   **Yup, I have an app**.
3. Select repository **apurwakumari16nus/Track2_Dispatcher**, branch **main**
   (or your actual deployment branch), and main file path **src/app.py**.
4. Open **Advanced settings** and select **Python 3.11 or newer**, preferably
   the same minor version tested locally. The current local checks used 3.13.
5. In **Secrets**, paste the following TOML with your real key:

   ```toml
   LLM_PROVIDER = "anthropic"
   ANTHROPIC_API_KEY = "your-api-key-here"
   ANTHROPIC_INTAKE_MODEL = "claude-sonnet-5-5"
   ```

6. Save the advanced settings and click **Deploy**. Cloud installs the root
   `requirements.txt`. Once the app opens, try an inbox request and inspect its
   tools and faithfulness. Confirm a sample only if you want a saved demo entry.

These steps follow the official [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
Use root-level secret keys exactly as shown: Streamlit exposes them as environment
variables, which intake already reads. Do not put them inside a nested table.
To rotate a key, update the app's Secrets in its settings. See the official
[Cloud secrets guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
and [environment-variable behaviour](https://docs.streamlit.io/develop/concepts/connections/secrets-management).

Treat the hosted JSONL file as demo storage, not a durable shared audit database.
The app currently keeps allocation state per session; a production multi-user
service needs shared queue state and durable external record storage.

## Troubleshooting

- **Wrong Python / missing package:** run `uv sync`; `uv run ...` then selects
  the project interpreter automatically. Use `uv python install 3.13` if no
  compatible Python is available locally.
- **Missing API/model setting:** save the provider's key and model in `.env`, or as root-level Cloud
  secrets. Model access, invalid keys, quota, and connection errors are reported
  separately from a business decision to decline a request.
- **Inbox accuracy is blank / one test skips:** finish the human labels; mock
  extractions are not a substitute for the team's independent evaluation set.
- **Port 8501 is occupied:** add `--server.port 8502` to the app command and open
  `http://localhost:8502`.

## Known limitations

Team: fill in the evidence and impact before the final submission. The unfinished
human labels, numerical-only faithfulness check, session-local queues, and demo
storage limitations are described above.

- [ ] **Data coverage and missing information:** _team to fill in._
- [ ] **Observed intake/decision failures and affected requests:** _team to fill in._
- [ ] **Shock detection delay and false alarms:** _team to fill in._
- [ ] **Where baselines outperform our allocator:** _team to fill in from evaluation._
- [ ] **Split assumptions and differences from real workshop operations:** _team to fill in._
- [ ] **Deployment, latency, and operating-cost observations:** _team to fill in._
