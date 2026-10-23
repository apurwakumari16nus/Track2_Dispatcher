# Final demo storyboard: Threadline in 120 seconds

One take, one request (R09), recorded at 1920 × 1080. Every control named below
exists in the app; every number shown is produced by the app at recording time.
The path was run end to end with Playwright on 23 October 2026 at 1920 × 1080 and
1440 × 900 (screenshots in `docs/final_demo_screens/`).

The eight-step **Guided demo** stays in the app for people exploring it. It is not
used for the recording: its coach panel covers part of the screen and its reading
steps are paced for a first-time user, not for 120 seconds.

## Required state before the take

| Item | Setting |
|---|---|
| App | `uv run streamlit run src/app.py`, browser at 1920 × 1080, zoom 100%, full screen |
| Request reading | **System details** → **Rehearsal: recorded model replies** (a genuine Sonnet 5.5 reply to R09, replayed, no API call). Alternative: **Live model**, about 4 s per evaluation |
| Reset | **System details** → **Reset demo session** (fresh 1 April queues, empty rehearsal log) |
| Presentation mode | **System details** → **Presentation mode** on |
| Page | **Dispatch**, scrolled to the top, no request selected |
| Objective | **Minimise lateness** |

## Timeline

| # | Time | Screen | Action (exact control) | What the viewer sees | Point made |
|---|---|---|---|---|---|
| 1 | 0:00–0:10 (10 s) | Dispatch, empty | None. Let the inbox be seen. | 30 chat messages in the inbox, the five-step strip, "Rehearsal mode" ribbon | The input is a messy group chat; the dispatcher must place each batch |
| 2 | 0:10–0:24 (14 s) | Dispatch | Click the **Boss, R09** inbox row. Click **Evaluate request**. | The request and its order facts from `orders.csv`; the strip fills Understand → Confirm pending; timing bar | An urgent request is read into structured fields |
| 3 | 0:24–0:38 (14 s) | Dispatch | Scroll down past the navy card to **What Python checked** and open it. | The checks: order number exists, order fields read from the order book, quantity matches, due date confirmed and still ahead, not in packing; the timing bar split into model, parsing, engine and evidence check | Python validates every field and evaluates all eight workshops |
| 4 | 0:38–0:54 (16 s) | Dispatch, recommendation | Scroll back up to the navy card. Click **Why this decision?**, read the first tab, press Esc. | "Assign to Nimble Needle": back 4 Apr, 5 days spare, cost 180, "Every number checked against the tools"; inspector: 3.2 against 3.5 days at FreshStart | The recommendation and the reason it won, from recorded numbers |
| 5 | 0:54–1:12 (18 s) | Workshop Network | Click **See it on the network**. Let the routing play (about 11 s). Click the **FreshStart** node. | The batch is checked against all eight workshops, three filtered out with reasons, route to Nimble Needle; FreshStart panel: back 5 Apr, cost 150, "0.3 days after Nimble Needle, costs 30 less" | The network view and one real alternative |
| 6 | 1:12–1:22 (10 s) | Dispatch | Click **Dispatch** in the sidebar. Scroll to the card. Click **Assign to Nimble Needle**. | Card turns to "Confirmed by you at …", "Audit record saved. Queue updated." | A human approves; nothing is sent to the workshop |
| 7 | 1:22–1:35 (13 s) | Audit Trail record | Click **View audit record**. | The saved record opens: original message, why this workshop, parsed request, constraints | The confirmed decision is auditable |
| 8 | 1:35–1:50 (15 s) | Simulation Lab | Press Esc. Click **Simulation Lab** in the sidebar. | Official ten-seed result: lateness objective 1.67% late batches; beats Random (34.17%), Biggest (84.25%), Cheapest (91.83%); ties earliest finish (1.67%) | The policy is evaluated in the course simulator, honestly, including the tie |
| 9 | 1:50–2:00 (10 s) | Simulation Lab (stay) | None. | Same screen | AI reads, Python decides, a person approves |

Total: 120 seconds.

## Notes for an accurate demo

* Say "recorded reply" if rehearsal mode is on. The ribbon says so on screen.
* The lateness policy **ties** earliest finish. Do not call it better than earliest finish.
* Do not claim language-model accuracy: the 30 human labels are not complete.
* Do not claim Haiku is faster or cheaper: the paid comparison has not been run.
* The confirmation goes to the session queue and the rehearsal log. It does not contact
  the workshop.
