# Demo readiness

A checklist for rehearsing and recording the Sprint 2 video with the real app.

## Prerequisites

- `uv sync` completed; `uv run pytest -q` passes (one skip for human labels is expected).
- Start the app from the repository root: `uv run streamlit run src/app.py`.
- Chrome or Safari, 1920 × 1080 window, browser zoom 100%, bookmarks bar hidden.
  Full-screen the browser (Ctrl+Cmd+F on Mac) so the 1080 px height is mostly app.
- macOS: turn on Do Not Disturb and hide the Dock.

## API requirements

Live dispatch needs `LLM_PROVIDER`, the provider key and the intake model in
`.env` (for example `ANTHROPIC_API_KEY` and `ANTHROPIC_INTAKE_MODEL`). The
sidebar's System status shows "Model …" when it is ready and "Live model not
configured" when it is not. Never show `.env` on screen.

Simulation Lab, Workshop Network, Audit Trail and both rehearsal sources need
no key.

## Record real replies before the video

Rehearsal · recorded only replays genuine model replies for the exact request
and scenario date. Create them once with the key configured, by either:

1. Dispatching each demo request once in **Live model** mode (each reply is
   saved to `records/rehearsal_cache/`), or
2. Running `uv run python eval/run_inbox.py` (replies cached in `eval/cache/`).

The sidebar then shows "N of 30 replies recorded". In **Rehearsal · recorded**
the banner reads *REHEARSAL MODE · Verified cached extraction* and the
execution trace names the recorded model.

**Rehearsal · fixtures** uses hand-written test extractions. They are fine for
practice but are not model output. Do not use them for any claim about
language understanding.

## Reset procedure

1. Sidebar → **Reset demo session**. This restores 1 April queues and fresh
   allocator history, clears previews and confirmations, and empties the
   rehearsal audit log. The live audit log is never touched.
2. Check the scenario date is 01/04/2026 and the objective is Minimise lateness.
3. Open Simulation Lab once, so the default seed is computed and cached, then
   return to Dispatch.

## Requests to use

| Shortcut | Behaviour shown | Expected result |
| --- | --- | --- |
| R09 | Normal allocation, preference "fastest" | Nimble Needle, back 4 Apr, 5 days spare, cost 180 |
| R01 | Clarification | Two Harbor Knits scarf orders (ORD-061, ORD-108); asks which, and the due date |
| R08 | Suggested workshop refused | FreshStart refused (400 exceeds its 300-piece cap); Nimble Needle offered |
| R02 | Unanswerable | Needs historical dispatch records; nothing invented |
| R30 | Complete but impossible | No workshop meets 5 Apr; QuickStitch least late (11 Apr, 6 days late); split preview available |
| R28 | Already overdue | Already-late banner plus the least-late option |
| R25 | Constraint with attribution | BudgetWorks excluded, imposed by Mei (open Why not → BudgetWorks) |

These values come from the fixture extraction at 1 April with fresh queues. A
live model can extract differently; the deterministic result follows whatever
it extracts. Confirming changes the session queues, so dispatch requests in
the order you plan to record them, or reset first.

## Pre-warm

- Open Simulation Lab once after starting the server. The default seed is then
  cached for every session.
- Click each Lab tab once (Disruption and Order audit compute small replays).
- In rehearsal, dispatch each demo request once, then reset.

## What not to claim

- No language accuracy: labels are 0 of 30 and no live inbox evaluation exists in this checkout.
- Lateness **ties** earliest finish on all eight metrics over ten seeds. It is not a win.
- The early anomaly flag reacts to simulated queue data. It is not real advance warning.
- Synthetic fixtures are not model output.
- Confirming does not contact a workshop.
- Splits are previews and cannot be confirmed.
- Single-seed Lab views are diagnostics. Quote ten-seed figures from Course evidence.

## Known risks during recording

- Live API latency or rate limits: use Rehearsal · recorded for the take.
- A changed scenario date or edited text has no recorded reply: the app says so instead of guessing.
- Confirmations change queues and later recommendations. Reset between takes.
- First Lab open after a server restart takes about a second.
- Streamlit reruns briefly dim the page after clicks. Pause a beat before narrating.
