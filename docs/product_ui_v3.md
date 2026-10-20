# Product UI v3

> Superseded by [product_ui_v4.md](product_ui_v4.md). Kept for the design history.

The second productization pass. Same deterministic backend, a calmer product.
v2 proved the features; v3 makes them usable by a dispatcher under time
pressure. It replaces [product_ui_v2.md](product_ui_v2.md) as the current guide.

## What changed and why

| v2 problem | v3 change |
| --- | --- |
| Almost everything was dark | Light operational canvas (`#F6F8FB`), white cards, a narrow navy navigation shell |
| Many status chips competed for attention | One "System health" control; details open on demand |
| Developer state in the sidebar | Sidebar holds only the four destinations, Guided demo and System settings |
| Weak "QR" logo tile | Typography-first wordmark: Quick Response Desk, Subcontracting Operations |
| Dispatch showed everything at once | Request, five stages, then the result in four parts: summary, recommendation, alternatives, confirm |
| Cramped seven-step stepper | Five computational stages; confirmation sits on the recommendation, not in the progress bar |
| Raw candidate table up front | Top four alternatives; "View all workshops" and "Excluded workshops" on demand |
| Explorer tabs always visible | A collapsed "Decision details" inspector with four tabs |
| Awkward cases looked like errors | Conversational cards: "I need one detail before I can continue." |
| Lab felt like an analytics console | Overview answers "How does our policy perform?" with four metrics against earliest finish |
| Course evidence was text-heavy | Executive scorecard: five lateness tiles, then one verdict per objective |
| Scenario shortcuts cluttered Dispatch | A Guided demo launcher in the sidebar |

## Navigation

- **Dispatch** (default): inbox on the left (28%), decision workspace on the right.
- **Workshop Network**: who can take a batch, and when it would be back.
- **Simulation Lab**: Overview, Tradeoffs, Disruption, Order Audit, Course Evidence.
- **Audit Trail**: every confirmed decision, searchable, with its evidence.
- **Guided demo** (sidebar): loads one of six supplied requests into Dispatch.
- **System settings** (sidebar): request reading source, model and cache status,
  presentation mode, demo reset.

## Dispatch flow

1. Pick a request in the inbox, or press **New request** and type one.
2. Press **Run decision**. Five stages complete: Understand (structured extraction),
   Validate (order and request type), Evaluate workshops (eligibility and estimates),
   Decide (scoring and ranking), Verify (evidence check). The stages reflect real
   transitions: the first waits for the extraction reply, the rest come from the
   recorded tool trace. No model reasoning is shown.
3. Read the request summary, then the **recommendation card**: workshop, back-by date,
   spare days, cost, defect risk, objective, one sentence on why it won, and
   "Evidence verified".
4. Press **Confirm allocation** (or "Accept alternative", "Accept late return").
   The card turns green: decision confirmed, audit record created, queue updated.
   **View in Audit Trail** opens the record.

## Decision inspector

"Decision details" opens four tabs, all read from the recorded decision:

- **Why this won**: winner against the runner-up, showing only the measures the
  selection rule used (for lateness: total time and return date).
- **Why not another**: pick any workshop. Suspended, cannot produce, trial batch cap
  exceeded (with the numbers), excluded by the requester (with who said it),
  misses the required date, or a higher configured score with the deciding measure.
- **Score breakdown**: weights for the objective (inactive terms muted) and stacked
  contribution bars per candidate from the recorded score terms.
- **Evidence trace**: a timeline of recorded events (request extracted, order
  verified, eligibility checked, candidates remaining, return dates, costs, scores,
  winner selected, decision reproduced, explanation verified, human confirmation).
  Each step opens to its data.

## Awkward requests

Clarification asks one question and offers the matching orders as buttons.
A refused workshop gets "FreshStart cannot accept this batch" with the reason and
the best permitted alternative. Unanswerable requests name the missing source.
Impossible deadlines say "No eligible workshop can meet 5 Apr", give the earliest
achievable date, and offer accept, split preview or escalate. Overdue requests
get an already-late banner.

## Guided demo and presentation mode

The Guided demo lists Normal allocation (R09), Clarification (R01), Refused
workshop (R08), Unanswerable request (R02), Impossible deadline (R30) and Already
late (R28). Choosing one loads the request; you still press Run decision, so the
real pipeline runs. A five-step walkthrough ticks as you go.

Request reading sources: Live model, Rehearsal: recorded model replies, and
Rehearsal: test fixtures. In rehearsal, one banner says so, for example
"REHEARSAL MODE Uses verified cached extraction. Allocation logic remains live."
Test fixtures are labelled as not model output everywhere they appear.

Presentation mode (System settings) hides developer detail and Streamlit chrome
and adds breathing room. Calculations do not change.

## Design system

| Token | Value | Use |
| --- | --- | --- |
| Shell | `#091A2D` | Navigation |
| Canvas | `#F6F8FB`, `#EEF3F7` | Page, quiet panels |
| Card | `#FFFFFF` | Information surfaces |
| Text | `#142334`, `#5D6C7B`, `#677686` | Primary, secondary (5.4:1), small labels (4.7:1) |
| Border | `#DDE5EC` | Hairlines |
| Cobalt | `#5677F3` (`#3E5FD9` for text and buttons, 5.5:1) | Primary action, selection |
| Cyan, teal | `#3ACED8`, `#20BFA9` | Accents and the hero gradient only, never body text |
| Green | `#2FC77A` | Human confirmation |
| Amber, coral | `#E8A53A`, `#EA665E` | Warnings and blocks, always with text |

The one signature surface is the recommendation card: navy with a cobalt, cyan and
teal edge (amber edge when late, green once confirmed). Charts use a palette
validated for colour-blind separation on the light surface: cobalt for our
policy, teal for earliest finish, orange for shock, grey for context. Type is
Inter with system fallbacks. Visible copy avoids em and en dashes.

## Backend behaviour preserved, and what was strengthened

The runtime sequence is unchanged and now has executable checks in
`tests/test_architecture.py`:

request → LLM structured extraction (`intake`) → Python validation and behaviour
(`intake.parse_request` post-checks) → deterministic tools (`tools`) →
deterministic allocator (`allocator`, `objectives`) → template explanation
(`agent`) → numerical faithfulness (`faithfulness`) → human confirmation
(`desk.confirm_preview`) → audit record (`records`) and session state.

New checks:

- the deterministic modules import no language-model client;
- the extraction schema has no fields for a workshop, date, cost or score;
- a model reply that proposes a different behaviour or workshop cannot change the
  decision; an ineligible suggested workshop is never chosen;
- every tool, scoring and ranking call is repeatable and does not mutate inputs;
- audit writes happen only after explicit confirmation.

`desk.confirm_state()` is new: one rule now decides whether a preview may be
confirmed (ready, stale, blocked or confirmed), used by both the button and the
write. `explain.py` gained deterministic helpers for the deciding measures,
plain-language eligibility reasons and the clarification question.
`evidence.objective_scorecard()` computes each objective's verdict from the
committed files. No new dependency or framework was added.

## Still incomplete

- Human labels: 0 of 30. No language accuracy is shown.
- No live inbox evaluation in this checkout, and no model configured here, so
  live reading was not exercised; there are no recorded replies yet.
- A clarification reply is appended to the request text; the live model must
  re-read it. There is no conversation memory.
- Splits are previews; they cannot be confirmed.
- Queues and history are per browser session; the audit log is local JSONL.
