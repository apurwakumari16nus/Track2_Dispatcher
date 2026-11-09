# Dispatch workspace redesign

> Superseded by [Product UI v2](product_ui_v2.md), which implements items 2, 3 and
> 5 below (visual candidate comparison, labelled rehearsal mode with isolated
> audit storage and reset, and prominent late/split/escalation options).

Based on Track 2 in Capstone_Project_Tracks_v4.pdf, pages 4–7.

The brief calls for a dispatcher who can compare eligibility, estimates and the
recommendation at a glance, then leave an auditable decision. The interface now
organizes that job into a searchable inbox, a request composer, a decision preview,
and explicit confirmation. Existing behavioural branches and persistence checks
remain in the backend.

## Implemented

- A consistent teal, ink and light-neutral theme, stronger type hierarchy,
  readable request cards and a visible selected state.
- Search over the 30 supplied messages by sender, request, order or message text.
- A wide decision area with parsed order facts, recommendation, return date,
  margin to deadline, cost and defect exposure.
- A compact candidate comparison, with queue/processing/transport details in a
  separate disclosure and original raw tool outputs still available.
- A workshop register page: change category, quantity and required return date;
  actual eligibility and ETA tools recompute the eight workshop profiles.
  This is a read-only exploration and does not call the model or allocate work.
- Existing confirmation, stale-preview checks, numerical faithfulness checks,
  refusal/clarification states and the filterable decision log.

## Try it

Run `uv run streamlit run src/app.py`. Start with the workshop register without
an API key. Try 1,500 TOPS, then 100 TOPS, and inspect FreshStart's batch cap.
Switch to ACCESSORIES and inspect capability exclusions and OldMill's suspension.

For Dispatch, configure the existing API settings and keep 2026-04-01 as the
scenario date. Search R09 for an allocation, R01 for clarification, R08 for a
refused workshop with an alternative, and R02 for an unanswerable request.
Dispatch produces a preview; confirmation saves a local audit entry.

## Further improvements

1. Implemented subsequently: an evaluation workspace showing baseline comparisons,
   primary/alternate/hybrid objectives and the shock scenario, with run provenance.
   See [the simulation workspace guide](simulation_workspace.md).
2. A visual candidate delivery timeline and objective comparison before confirmation.
3. A clearly labelled sandbox mode with synthetic extraction for API-free demos,
   isolated audit storage, and a reset control.
4. A structured clarification workflow retaining context across follow-up answers.
5. Prominent split/late/escalation alternatives with their assumptions. Existing
   split calculations are previews, not executable split allocations.

These remain future work; this redesign does not claim to implement them.
Human labels still need independent completion for measured intake accuracy.
