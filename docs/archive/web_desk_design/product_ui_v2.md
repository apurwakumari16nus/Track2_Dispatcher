# Product UI v2

> Superseded by [Product UI v3](product_ui_v3.md): light canvas, simpler Dispatch,
> decision inspector, Guided demo. Backend notes below still apply.

The app is now a four-area operations product built on the same backend.
The visual language comes from `Presentation_Group01_Sprint1.pptx`: midnight
navy, cyan, teal and cobalt, green for human confirmation, amber and coral for
warnings, Inter type, and one signature element, the edge-lit decision card.

## What changed and why

| Before | Now | Why |
| --- | --- | --- |
| Landing page was Simulation | Landing page is **Dispatch** | A dispatcher should be able to act immediately |
| Four loosely related pages | **Dispatch, Workshop Network, Simulation Lab, Audit Trail** | One clear job per area |
| Light teal theme | Dark theme derived from the Sprint 1 deck | The product should look like it belongs to the presentation |
| Recommendation plus raw JSON | Hero recommendation, "why this won", candidate panel, decision explorer | Understand the result in about five seconds, inspect detail on demand |
| `st.status` spinner | Seven-stage stepper driven by real stage transitions and the recorded tool trace | Shows what ran, never model reasoning |
| Live model only | Explicit, labelled extraction sources: live, recorded replies, synthetic fixtures | Demos and recordings without API latency, without passing fixtures off as model output |
| Decision log | Searchable, filterable **Audit Trail** with a record view and exports | Governance, not a list of JSON blobs |
| Single-seed dashboard only | Lab adds **Course evidence** from the committed ten-seed files | Course reporting needs ten paired seeds |

## Page structure

**Dispatch** (default). The inbox is on the left and the workspace on the right.
The workspace shows the current request, scenario shortcuts, the stepper, then
the result. For an allocation, the edge-lit card shows the workshop, return
date, spare days, cost, defect risk, one-sentence "why this won", the
evidence-check badge and the confirm button. The candidate panel beside it
lists all eight workshops in decision order, with exclusions still visible.
Below sits the decision explorer:

- **Summary**: what the request says (with constraint attribution) and the decision status.
- **Candidates**: delivery timeline bars (queue, processing, transport against the due date) and the full table.
- **Why this won**: chosen vs runner-up, objective weights (inactive terms greyed), score decomposition, and **Why not this workshop?** for any other workshop.
- **Evidence**: the numerical evidence check with every checked value, plus structured extraction and the decision record.
- **Execution trace**: each recorded step, who performed it (model, Python, human) and its tool evidence.

Awkward cases have their own states. Clarification shows the missing facts,
matching orders and a reply field. A refused workshop gets a reason banner and
the best permitted alternative. An impossible date shows the earliest
achievable return, a least-late option, a split preview and escalation.
Unanswerable requests name the missing source. An overdue request gets a
prominent already-late banner.

**Workshop Network.** Category, batch size and required date filters, a
one-line answer ("5 of 8 workshops can take 1,500 tops..."), and eight
workshop cards or a compact matrix. Each card shows status, capabilities,
capacity, queue load bar, transport, cap, cost, defect risk and estimated
return. Excluded workshops stay visible with their reason.

**Simulation Lab.** Objective, scenario and seed controls, then five tabs:
Overview (five hero metrics against earliest finish, with explicit ties),
Objective trade-offs (weights, two trade-off plots, a workshop-share heatmap
and a clearly labelled custom what-if sandbox), Disruption (closure window,
first anomaly flag, clearance and routing on one timeline, plus normal vs
shock), Order audit (any simulated order's candidates, scores, decomposition
and realised outcome) and Course evidence (the committed ten-seed results,
criteria and guardrails, seed spread, and language-evaluation status).

**Audit Trail.** Live and rehearsal logs kept separate. Search, sender,
workshop, decision type and date filters. A selectable table and a record
view with Request, Decision, Evidence, Confirmation and Raw JSON tabs.
Per-record JSON download and JSONL export.

## How to navigate

Use the left sidebar. **Extraction source** sits under the four areas. Leave
it on **Live model** for real use. Use **Rehearsal · recorded** to replay
earlier real model replies, or **Rehearsal · fixtures** to use the
hand-written test extractions. Rehearsal modes show an amber banner on Dispatch
and write confirmations to a separate rehearsal log. **Reset demo session**
restores the 1 April queues and empties the rehearsal log. It never touches the
live log.

## Backend behaviour preserved

- `intake`, `agent`, `allocator`, `tools`, `objectives`, `faithfulness`, `records`,
  `experiments` and the official harness are unchanged in behaviour. The
  committed evaluation's source hashes still match, and Course evidence checks
  this on every load.
- `make_preview` and `confirm_preview` keep their logic: preview never
  persists, the app independently replays the decision on a fresh copy before
  allowing confirmation, a stale preview cannot be confirmed, and only a
  successful append updates the session queue. They moved from `app.py` to
  `src/desk.py`; `app.py` re-exports them.
- Selection stays deterministic. A test dispatches the same request twice with
  identical inputs and asserts identical decision records.

## Architectural changes (small, justified)

1. **`intake.extraction_source(call)`**, a context-local override of where the
   raw extraction reply comes from. It is needed for labelled rehearsal replay
   and for the stepper's "reply received" transition. A process-wide
   monkeypatch would leak between concurrent Streamlit sessions. With no
   override, behaviour is identical; schema validation and every Python
   post-check still run.
2. **`src/rehearsal.py`** replays recorded model replies, with exact prompt and
   message match plus a payload-hash integrity check. It also serves the
   existing synthetic fixtures, labelled as such, and records live replies to
   `records/rehearsal_cache/` (git-ignored). It reuses the cache format of
   `eval/run_inbox.py`, so a live inbox evaluation's cache can be replayed too.
   App recordings never feed the evaluation cache.
3. **`src/desk.py`** (session logic) and **`src/ui/`** (theme, components,
   pages, read-only explanation and evidence helpers). This is a presentation
   refactor; `src/simulation_dashboard.py` and `src/desk.css` were folded into
   `src/ui/`.

No new framework or runtime dependency was added.

## New features and the data they use

| Feature | Source |
| --- | --- |
| Why this won / runner-up / why not | Recorded candidate rows, score terms, eligibility results and constraints; selection order mirrors `Allocator.decide` |
| Score decomposition | Recorded `score_terms` times the objective's configured weights |
| Execution trace and stepper | `tools.trace_calls()` output, intake post-checks, faithfulness result, determinism replay |
| Evidence badge | `faithfulness.check` on the recorded explanation |
| Split preview for impossible dates | `tools.estimate_split`, called on demand |
| Workshop Network | `tools.check_eligibility`, `estimate_eta`, `estimate_cost`, session queues |
| Lab overview, trade-offs, disruption, order audit | `experiments.run_experiment`, `decision_replay`, `shock_trace.run_trace` (single seed) |
| Custom what-if | Extra single-seed replays with `ObjectiveConfig(user weights)`; presets untouched |
| Course evidence | `eval/results.csv`, `results_per_seed.csv`, `objective_checks.csv`, `shock_changes.csv`, `simulator_metadata.json` |
| Language evaluation status | `eval/labels.csv`, `eval/labeling/*`, `data/data_dictionary.md` |

UI sentences show rounded copies of recorded values. The numerical
faithfulness check applies to the recorded template explanation, not to UI
sentences.

## Still incomplete

- Human labels are 0 of 30 and reconciliation has not started, so no language
  accuracy is shown anywhere.
- No live inbox evaluation has been run in this checkout, and the live model
  is not configured here, so live dispatch was not exercised in this session.
- There are no recorded model replies yet, so rehearsal currently means synthetic
  fixtures. Record real replies before the video (see `demo_readiness.md`).
- Clarification replies are appended to the request text and need the live
  model to re-read them. There is no structured multi-turn memory.
- Splits are previews only and cannot be confirmed.
- Queues and history are per browser session. The audit log is local JSONL,
  not a shared service.
