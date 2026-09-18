# Track 2 Dispatch

A subcontractor dispatch desk: turn a request into checked order facts, compare
eligible workshops, and show a recommendation with its supporting calculations.
The LLM extracts language; Python checks eligibility, estimates delivery and cost,
and chooses the workshop. A dispatcher explicitly confirms the local audit entry.

## Prerequisites

- **Python 3.11+**, 64-bit; check the version before creating the environment.
- **Git**, a terminal, and internet access to install packages.
- An **OpenAI API key**, available API credit, and access to the configured model
  for live requests. No key is needed for the simulator or ordinary tests.

The quick start targets **under 10 minutes once these prerequisites are ready**;
download speed and API availability affect timing. Evaluating all 30 live inbox
requests is a separate step. No Java, database, Node.js, or GPU is required.

## Setup and first run

### Mac — Terminal

```bash
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
open -e .env
```

Wait for environment creation and installation to finish. If environment creation
was interrupted, rerun `python3 -m venv .venv` before activating it.

### Windows — PowerShell

```powershell
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

These Windows commands do not require activation or an execution-policy change.
For the remaining commands, **replace `python` with
`.\.venv\Scripts\python.exe` on Windows**. If `py` is unavailable but `python`
is your Python 3.11+ installation, use `python -m venv .venv` instead.

### Configure the API and open the app

In the `.env` file opened above, save these settings, replacing the key placeholder:

```dotenv
OPENAI_API_KEY=your-api-key-here
OPENAI_INTAKE_MODEL=gpt-4.1-mini-2025-04-14
```

The example uses a versioned GPT-4.1 mini model with structured-output support.
See the [official OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
An alternative model must support Chat Completions, strict JSON Schema, and
`temperature=0`. The app loads `.env` automatically; existing environment values
take precedence. Never commit `.env` or your real API key.

Mac, in the activated environment:

```bash
python -m streamlit run src/app.py
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/app.py
```

This is equivalent to `streamlit run src/app.py` when the environment is activated.
Open **http://localhost:8501** if the browser does not open automatically. Keep the
terminal running; use **Ctrl+C** to stop it.

For a first check, keep **2026-04-01** and the **lateness** objective, select an inbox
request, and click **Dispatch**. Review the verdict, recommendation, candidates,
tool outputs, and faithfulness result. **Confirm allocation** writes one local
entry to `records/decisions.jsonl`; Dispatch alone writes none. The Decision log
page shows saved entries. Confirmation does not send a message to a workshop.

Always run commands from the repository root. Keep `data/` beside `harness/`:
the unchanged simulator reads its inputs from `harness/../data/`.

## Run evaluations and tests

On Mac, activate `.venv` in each new terminal. On Windows, use the full interpreter
path shown below. Run evaluation commands after stopping the app, or in a second
terminal at the repository root.

| Task | Mac (activated environment) | Windows PowerShell |
| --- | --- | --- |
| Simulator evaluation | `python eval/run_simulator.py` | `.\.venv\Scripts\python.exe eval/run_simulator.py` |
| Live inbox evaluation | `python eval/run_inbox.py` | `.\.venv\Scripts\python.exe eval/run_inbox.py` |
| Tests, no API calls by default | `python -m pytest -q` | `.\.venv\Scripts\python.exe -m pytest -q` |
| Original simulator | `python harness/simulate.py` | `.\.venv\Scripts\python.exe harness/simulate.py` |
| Original simulator with closure | `python harness/simulate.py --shock` | `.\.venv\Scripts\python.exe harness/simulate.py --shock` |

**Simulator evaluation** runs random choice, greedy biggest, cheapest, earliest
finish, and all six allocator presets with and without the shock (20 runs; seed
5105). It prints a Markdown table and creates `eval/results.csv`,
`eval/baseline_wins.md`, and these charts:

- `eval/charts/lateness_by_policy.png`
- `eval/charts/tradeoff_lateness_vs_cost.png`
- `eval/charts/tradeoff_lateness_vs_fairness.png`

Metrics use the simulator's report arithmetic. Percentages are on a 0–100 scale;
fairness in the chart is `100 - max_share`. The baseline report includes cases
where our allocator loses. Use `--seed 42 --output-dir eval/seed_42` to keep an
additional run separate from the default outputs.

**Inbox evaluation** runs all 30 requests at the reference date 2026-04-01 with
the lateness preset. It creates `eval/inbox_results.csv`, `eval/failure_cases.md`,
and `eval/inbox_audit.json`, and prints a summary by behaviour class. Live cache
misses make paid API calls. Matching raw replies are reused from `eval/cache/`;
`--offline` forbids new calls and reports missing cache entries. Temperature 0
reduces variation; cached replies make repeated extraction reproducible.

The team must independently complete and reconcile **`eval/labels.csv`** before
claiming behaviour accuracy. At documentation time, human answers are blank:
missing labels remain unscored, and the human-label comparison test skips. Do not
present those blanks as passes. Previously saved evaluation files are not proof
of a successful live run; inspect the execution notes and regenerate them.

For a free synthetic smoke test (not an evaluation of the real LLM):

```bash
python eval/run_inbox.py --mock --output-dir eval/mock_inbox
```

Windows equivalent:

```powershell
.\.venv\Scripts\python.exe eval/run_inbox.py --mock --output-dir eval/mock_inbox
```

For the intake confusion matrix, run `python -m pytest tests/test_intake.py -q -s`.
Set `TRACK2_REQUIRE_LABELS=1` to fail rather than skip incomplete human labels.
`TRACK2_INTAKE_REAL_LLM=1` optionally enables live intake tests and API charges.
In PowerShell, set a flag with `$env:TRACK2_REQUIRE_LABELS = "1"`; on Mac use
`export TRACK2_REQUIRE_LABELS=1`. Clear flags after use (`Remove-Item Env:NAME`
on Windows or `unset NAME` on Mac).
See [inbox evaluation details](docs/inbox_evaluation.md).

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

**[src/app.py](src/app.py)** implements the Streamlit dispatch desk and filterable
decision log. It exposes the date and objective, the inbox, recommendation,
candidates, exclusions, raw outputs, faithfulness, and workshop register.
Dispatch creates a preview; confirmation validates that preview and saves it
before updating session history and queues. Queue state belongs to the browser
session and is not a live workshop feed.

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
[requirements.txt](requirements.txt); transitive dependencies are resolved by pip,
so this is not a complete platform-specific lockfile. The simulator uses an
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
   the same minor version tested locally. The current local checks used 3.14.
5. In **Secrets**, paste the following TOML with your real key:

   ```toml
   OPENAI_API_KEY = "your-api-key-here"
   OPENAI_INTAKE_MODEL = "gpt-4.1-mini-2025-04-14"
   ```

6. Save the advanced settings and click **Deploy**. Cloud installs the root
   `requirements.txt`. Once the app opens, try an inbox request and inspect its
   tools and faithfulness. Confirm a sample only if you want a saved demo entry.

These steps follow the official [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
Use root-level secret keys exactly as shown: Streamlit exposes them as environment
variables, which intake already reads. Do not put them inside an `[openai]` table.
To rotate a key, update the app's Secrets in its settings. See the official
[Cloud secrets guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
and [environment-variable behaviour](https://docs.streamlit.io/develop/concepts/connections/secrets-management).

Treat the hosted JSONL file as demo storage, not a durable shared audit database.
The app currently keeps allocation state per session; a production multi-user
service needs shared queue state and durable external record storage.

## Troubleshooting

- **Wrong Python / missing package:** use the `.venv` interpreter, and rerun
  `python -m pip install -r requirements.txt` with that interpreter.
- **Missing API/model setting:** save both `.env` fields, or both root-level Cloud
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
