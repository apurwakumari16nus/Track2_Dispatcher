# Threadline V11: stabilization, simpler operations, guided demo

Status on 22 October 2026: built and tested locally on `product-ui-v2`. Not committed.

## Crashes fixed (P0)

**Root cause.** Streamlit's required segmented control, pills and radio send `None`
when the selected option is clicked again, or when a widget is recreated after
navigation. The pages used that value directly: Audit looked up `LOGS[None]`
(`KeyError: None`) and Network called `.lower()` on a `None` category.

**Fix.** `src/ui/state.py` separates the domain value (`state["audit_log"]`) from
the widget (`state["_w_audit_log"]`). `bind()` validates the domain value before
drawing, copies it to the widget, and copies a widget change back only when it is a
valid, non-`None` value. Every selection widget on Dispatch, Network, Lab and Audit
uses it. A second widget for the same value (the "Edit the text" popover) gets its
own widget key (`slot`), which also fixed an "Evaluate request" click that could wipe
the selected message.

An unknown category handed from Dispatch to Network is kept as "not chosen" with a
notice. It is never swapped for another category.

## Five outcomes (P1)

| Outcome | What the dispatcher sees |
|---|---|
| Allocation | Recommendation card, confirm button, the reasons |
| Clarification | "I need one more detail", candidate orders, a reply box |
| Unanswerable | The missing data source, nothing allocated |
| Invalid or infeasible | Refused workshop with the permitted alternative, or least-late option with split and escalate |
| Model or system error | A named category (timeout, auth, rate limit, provider unavailable, refusal, incomplete, invalid output, engine, system), what to do, Try again where it helps, Use rehearsal mode for configuration errors |

Errors never allocate and never write to an audit log.

## Confirm exactly once (P2)

`confirm()` returns early when the preview is already confirmed; the button is
replaced by "View audit record" after the first click. The queue is adopted once.
"View audit record" opens the right log (rehearsal for rehearsal and guided-demo
confirmations) and opens that record directly.

## Simpler pages (P3)

* Dispatch: request, facts from `orders.csv`, one Evaluate button; recommendation
  with its actions on one full-width row; "What the model read", "What Python
  checked" and "Workshops compared" as closed sections.
* Workshop Network inspector: state, return date, cost, the reason and the two
  actions first; capacity, queue, rework and risk in one closed section. "Route here"
  is labelled as a preview: only Dispatch confirms.

## Guided demo (P4)

Eight steps on request R09, each waiting for the real action: receive, understand,
validate, evaluate, recommendation, confirm, verify, complete. Continue appears only
on reading steps; you cannot step back past a confirmation. Work in progress is set
aside and restored on exit. The demo reads R09 with the live model only if asked,
otherwise a recorded reply, otherwise the labelled test fixture, and says which.
Confirmations go to the rehearsal log and are marked `guided_demo`. A small library
(R01 ambiguous, R08 refusal, R02 unanswerable, R30 impossible deadline) loads one
case each without evaluating it.

## Tracing and performance (section 17)

See `docs/execution_tracing.md`. Audit Trail has a separate **Performance
diagnostics** view; the decision audit is unchanged.

## Model comparison

`benchmarks/` holds a controlled Sonnet 5.5 against Haiku 5.5 benchmark with a dry
run by default and a decision rule fixed in advance. **Not yet measured**: no paid
run has been made. See `benchmarks/README.md`.

## OpenUI

Reviewed and not adopted. Threadline is a Streamlit app with a finished design
system; a second component framework would add a build step and a second styling
system without fixing any V11 problem.

## Not changed

The allocation policy, simulator data, evaluation files, baselines, metrics and
faithfulness checks. `src/tools.py` was briefly instrumented and then restored,
because it is part of the evaluation fingerprint.

## Review fixes (23 October 2026)

* Clarification: amber card, never red. Candidate orders are rows under one header
  (order, product, pieces, due date from `orders.csv`, stage), so values line up.
  Choosing an order, or adding a typed reply, evaluates the request again at once.
* The thread dot under the request is centred on its stitched line.
* Workshop Network: the five summary cards became one line of facts; the legend has
  four entries; the step list shows only while a routing run plays; the route tracker
  and what-if outcomes sit in one closed section.
* Simulation Lab, Tradeoffs: the six small objective cards and the side list became one
  table (objective, verdict, late batches, cost, largest share, defect exposure, each
  cell shaded within its column, the best outlined) and a radar of the selected
  objective over the other five. Click a table row to select an objective.
