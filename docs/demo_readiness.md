# Demo readiness

A checklist for rehearsing and recording the Sprint 2 video with the real app (UI v3).

## Prerequisites

- `uv sync` completed; `uv run pytest -q` passes (one skip for human labels is expected).
- Start the app from the repository root: `uv run streamlit run src/app.py`.
- Chrome or Safari, 1920 × 1080 window, browser zoom 100%, bookmarks bar hidden.
  Full-screen the browser so the 1080 px height is mostly app. 1440 × 900 also works.
- macOS: turn on Do Not Disturb and hide the Dock.
- Sidebar → **System settings** → turn on **Presentation mode**. It hides developer
  detail and Streamlit chrome. Calculations do not change.

## API requirements

Live reading needs `LLM_PROVIDER`, the provider key and the intake model in `.env`
(for example `ANTHROPIC_API_KEY` and `ANTHROPIC_INTAKE_MODEL`). System settings shows
the model name when ready and "Not configured" when not. Never show `.env` on screen.
If you run a decision without a model, Dispatch shows "Language intake unavailable"
with a button to switch to rehearsal.

Simulation Lab, Workshop Network, Audit Trail and both rehearsal sources need no key.

## Record real replies before the video

**Rehearsal: recorded model replies** only replays genuine model replies for the exact
request and scenario date. Create them once with the key configured, either by
running each demo request in **Live model** mode (replies are saved to
`records/rehearsal_cache/`), or with `uv run python eval/run_inbox.py` (`eval/cache/`).
System settings then shows "N of 30 inbox requests" recorded, and the banner reads
"REHEARSAL MODE Uses verified cached extraction. Allocation logic remains live."

**Rehearsal: test fixtures** uses hand-written test extractions. Fine for practice,
but they are not model output. The banner and every trace step say so. Do not use
them for any claim about language understanding.

## Reset procedure

1. System settings → **Reset demo session**. Restores 1 April queues and fresh
   allocator history, clears decisions in this session, empties the rehearsal
   audit log. The live audit log is never touched.
2. Check the scenario date is 01/04/2026 and the objective is Minimise lateness.
3. Open Simulation Lab once so the default seed is computed and cached, then
   return to Dispatch.

## Requests to use (Guided demo)

| Scenario | Request | What you should see |
| --- | --- | --- |
| Normal allocation | R09 | Nimble Needle, back 4 Apr, 5 days spare, cost 180; finishes 0.3 days before FreshStart |
| Clarification | R01 | "Which Harbor Knits order do you mean?" with ORD-061 and ORD-108 as options |
| Refused workshop | R08 | "FreshStart cannot accept this batch." Trial batch cap: 400 pieces against 300; Nimble Needle offered |
| Unanswerable request | R02 | "This information is not available in the supplied data." Missing source: historical dispatch records |
| Impossible deadline | R30 | "No eligible workshop can meet 5 Apr." Earliest achievable 11 Apr at QuickStitch, 6 days late; split preview |
| Already late | R28 | Already-late banner plus the least-late option |
| Constraint attribution (inbox) | R25 | Why not another → BudgetWorks: "Excluded by the requester", imposed by Mei |

Values come from the fixture extraction at 1 April with fresh queues. A live model
may extract differently; the deterministic result follows whatever it extracts.
Confirming changes session queues, so record in your planned order or reset first.

## Pre-warm

- Open Simulation Lab once after starting the server, and click each Lab tab once.
- In rehearsal, run each demo request once, then reset.

## What not to claim

- No language accuracy: labels are 0 of 30 and no live inbox evaluation exists here.
- Lateness **ties** earliest finish on all eight measures over ten seeds. Not a win.
- The early anomaly flag reacts to simulated queue data. It is not real advance warning.
- Test fixtures are not model output.
- Confirming does not contact a workshop. Splits are previews only.
- Single-seed Lab tabs are diagnostics. Quote ten-seed figures from Course Evidence.

## Known risks during recording

- Live API latency or rate limits: record in Rehearsal: recorded model replies.
- Edited text or another scenario date has no recorded reply; the app says so.
- Confirmations change queues and later recommendations. Reset between takes.
- After a server restart, the first Lab open takes about a second.
- Streamlit briefly dims the page after a click. Pause a beat before narrating.
