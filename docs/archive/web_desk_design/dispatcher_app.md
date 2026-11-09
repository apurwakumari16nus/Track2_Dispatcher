# Dispatcher app

> Updated by [Product UI v2](product_ui_v2.md): the app now opens on Dispatch,
> the register is the Workshop Network, and the log is the Audit Trail. The
> preview, confirmation and persistence rules below are unchanged.

From the repository root, run:

```bash
uv run streamlit run src/app.py
```

The first screen needs only the supplied CSV files. Dispatch uses live intake,
so configure `LLM_PROVIDER` and its key and model in `.env` first
(`ANTHROPIC_API_KEY` and `ANTHROPIC_INTAKE_MODEL` by default). The UI
never substitutes synthetic replies when configuration is missing. It displays
an actionable error and leaves the audit log unchanged.

## Dispatcher workflow

1. Set today's date (initially **2026-04-01**) and choose an objective preset.
   The adjacent numbers show its read-only weights. A request preference can
   override this objective; the result identifies that override.
2. Select a message from the scrollable inbox or type a new one. **New** clears
   the editor. Selecting, editing, and changing settings do not call the model.
3. Click **Dispatch**. The main panel shows the behaviour banner, any overdue or
   awkward-case warning, and the workshop, return date, spare days, total cost,
   defect probability, and one-sentence reason. This is a preview.
4. Review the score-sorted candidate table or expand the evidence. Profile-eligible
   workshops excluded by the request remain visible, with a restriction. The
   chosen row uses bold text and a grey background. The Ineligible expander keeps
   exact profile-rejection reasons and separately identifies request/date exclusions.
5. **Confirm allocation** saves the audit row and adopts its projected queue and
   allocation history in this session. A confirmation of a refusal accepts its
   alternative; confirmation of an all-late fallback explicitly accepts the late
   ETA. Those choices are recorded. No external workshop is contacted.

Clarifications, declines, missing choices, unresolved packing-stage requests, and
failed numerical evidence checks cannot be confirmed. An input change requires
a new Dispatch. Rerendering, opening an expander, or switching pages does not
append an audit row. After a successful save, the same confirmation button is
disabled. A new Dispatch creates a new preview, so intentionally repeating a
request is a separate action; this is not global order deduplication.

## Layout and evidence

The sidebar opens on Simulation and also offers Dispatch, Workshop register,
and Decision log. Simulation automatically allocates all orders and is described
in [the simulation workspace guide](simulation_workspace.md).
The date and preset survive page navigation. The searchable inbox sits beside
the request composer and decision area. A teal accent identifies actions and
selection; green, amber, red and grey banners distinguish outcomes.
Candidate numbers are right-aligned. Displayed numbers are rounded for
readability; full-precision values remain in the raw evidence.

The Workshop register offers category, batch-size and return-date controls.
Eligibility and delivery estimates use the same tools as dispatch, without a
model call or an allocation. The Dispatch page retains a collapsible queue
snapshot. See [redesign notes and next steps](ui_redesign.md).

The Faithfulness badge checks the complete template explanation. It does not
claim that rounding on the presentation card is itself a separate faithfulness
test, nor that numerical support proves a decision is correct.

`tools.trace_calls()` captures every decorated tool invocation within this
Dispatch, including nested ETA, cost, eligibility and queue calls and shock-monitor
observations. The raw outputs are copied into `DecisionRecord.tool_outputs.call_trace`.
Context-local storage prevents one Streamlit session from seeing another session's
trace. No trace is written until confirmation. The Tool outputs expander also
contains the parsed request and complete decision record, including the raw LLM
JSON and deterministic post-check evidence.

The app prepares an independent copy of the allocator's prospective accepted
state and checks that it reproduces the displayed decision. It never commits the
agent's initial preview to the live session. File persistence must succeed before
the app adopts the accepted state. The saved response includes an explicit
confirmation marker and preserves the original preview explanation as such.

## Queue and persistence scope

Register queues start from the workshop CSV's snapshot on 2026-04-01. Confirmed
batches add only processing work via `overload_probe`; lead time does not occupy
the production queue. Moving the date forward projects normal queue clearance,
clamped at zero. Dates before the last confirmed snapshot are disabled. Register
figures are local-session projections, not a live workshop feed; therefore the
app does not discover a closure without an observed queue anomaly. Existing
shock-monitor flags are shown as monochrome SUSPECT labels.

Allocator history, queues, and pending confirmations belong to the browser session.
They reset with a new session and are not reconstructed from the audit log. The
JSONL log persists and is shared on this local installation; this prototype is
not a synchronized multi-dispatcher queue service.

Decision log reads `records/decisions.jsonl`, shows newest append first, and
filters by the chosen/alternative workshop and sender. Each entry expands to the
full stored audit. Corrupt log rows show a visible error instead of disappearing.
The app never creates an empty log just by viewing this page.

## Verification

```bash
uv run pytest tests/test_app.py -q
```

Tests use synthetic extraction and temporary audit files. They cover all UI
branches, inbox loading, state restoration across pages, stale previews, refusal
alternatives, late acceptance, score inventory, isolated traces, save failures,
one append per confirmation, and combined log filters. The actual Streamlit
widget flow is exercised with `streamlit.testing.v1.AppTest`. Browser layout was
also checked using an isolated synthetic-response harness; no production audit
entry or live LLM call was needed for visual verification.
