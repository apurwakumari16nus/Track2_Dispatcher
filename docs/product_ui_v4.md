# Product UI v4

The third productization pass. Same deterministic backend, an art-directed
product. v3 made the desk usable; v4 gives it a recognisable visual language.
It replaces [product_ui_v3.md](product_ui_v3.md) as the current guide.

## Design system

Tokens live at the top of `src/ui/theme.css`; Streamlit's base theme is in
`.streamlit/config.toml`.

| Token | Value | Use |
| --- | --- | --- |
| `--navy` | #071524 | Sidebar shell |
| `--surface-dark` | #0B1F32 | Recommendation hero, inspector, map |
| `--bg` | #F4F7FA | Canvas, with two faint ambient radials |
| `--glass` | rgba(255,255,255,.72) | Command bars, stat chips |
| `--cyan`, `--teal` | #48D9E6, #28C8AC | The decision beam |
| `--cobalt` | #5F78F5 | Our policy in charts |
| `--green`, `--amber`, `--coral` | #45D18A, #F3B84B, #F56F67 | Confirm, late, refused/suspended |
| `--text`, `--text-muted` | #122233, #617182 | Ink |

Type scale: page title 34px, section 18 to 20px, hero metrics 34 to 54px, body
14 to 16px, eyebrows and meta 11 to 12px uppercase with wide tracking.

**Signature: the decision beam.** A 1px cyan to teal luminous edge, drawn with a
masked gradient border. It appears only on the active, selected, recommended or
confirmed object: the selected nav item, the selected inbox request, completed
process nodes, the recommendation hero, the inspector's "why" card, on-time
network lines and node cards, the selected objective in the Lab, our marker on
the policy scale, and the primary button underline. Nothing else glows, so the
eye always lands on the decision.

**Controlled glass.** Glass is a material for command bars (Dispatch, Network,
Lab, Audit), stat chips, the inspector and audit slide-overs, and the demo
controller. Content cards stay solid white.

**Components** (`src/ui/components.py`): `status_pill`, `verdict_badge`,
`banner`, `page_head`, `section`, `metric_tile`, `glass_panel`, `fact`,
`decision_stage`, `candidate_row`, `weight_bars`, `score_bars`, `table`,
`json_block`, `chart` (shared Vega-Lite theme: transparent, dashed grid, no
ticks, legend on top). Surfaces that hold widgets are keyed containers styled in
CSS (`st-key-rec`, `st-key-request`, `st-key-cmdbar`, `st-key-ledger`, ...).

## Pages

**Shell.** Navy sidebar with a wordmark, icon navigation (selected item: soft
glass plus a cyan left edge), then Guided demo and System details at the foot.

**Dispatch.** Title, then a glass command bar: scenario date, objective, and a
"System ready" control that opens details on demand. Inbox on the left. On the
right, the request reads as an operations message (avatar, sender, time, the
text in 19px) with the order looked up deterministically from `orders.csv`
("On file": order, customer, product, pieces, due, stage). **Evaluate request**
runs the decision. A five-step strip (UNDERSTAND, VALIDATE, EVALUATE, DECIDE,
VERIFY) shows completed nodes as beam-filled checks, the active one as a pulsing
ring and pending ones as outlines. Below it:

- The **recommendation hero**: navy, beam edge, 46px workshop name, four metric
  tiles, one sentence on why it won, the objective, a green **Confirm
  allocation** button with a check icon, and **Why this decision?**. Confirmed
  state switches the eyebrow and edge to green: "Audit record saved. Queue
  updated. No message has been sent to Nimble Needle."
- **Alternatives**, lighter: the next three permitted workshops (the winner is
  not repeated) and "View all candidates (8)".
- Awkward cases stay conversational: "I need one detail before I can continue.",
  "This information is not available in the supplied data.", and for impossible
  deadlines the least-late hero (amber edge), three human options and the split
  preview.

**Decision inspector.** A right slide-over (dark glass, 780px) opened by
**Why this decision?**. Tabs: Why this won (beam card plus comparison grid),
Why not another (verdict card: status pill, facts, "Result: not selected
because ..."), Score breakdown (luminous weight bars, final score against the
runner-up, contribution bars), Evidence trace (a vertical timeline of recorded
events with lit nodes; raw JSON behind "View raw evidence").

**Workshop Network.** A schematic map, not geography: the factory hub with eight
partners. Line style answers the query: beam for on time, amber for late, dashed
slate for cannot take it, dashed coral for suspended; an amber dot marks a
suspect queue and a pulsing ring marks the fastest. Beside it, the answer in one
line ("5 of 8 can take 1,500 tops. 4 return by 15 Apr."), stat chips and a
legend. Below, eight node cards with capacity, price, defect rate and a queue
gauge. A Map/Table toggle keeps the plain register.

**Simulation Lab.** A strategy lab. The Overview opens on a head-to-head duel
(our policy against earliest finish, with a TIE, BETTER or WORSE verdict), then
every baseline on one 0 to 100% lateness scale, then four KPI tiles with
verdict pills. Course Evidence uses the same duel for the ten-seed result
(1.67% against 1.67%, TIE), the scale (Random 34.17, Biggest 84.25, Cheapest
91.83), and three verdict blocks: Fairness qualifies (17.5% largest share),
Robustness qualifies (-0.25 points under shock, the smallest change of any
policy), Quality fails its guardrail (2.9% defect exposure, 95.1% late). Hybrids
are reported with no pass rule. Every figure is read from `eval/`; verdicts and
superlatives are computed.

**Audit Trail.** A governance ledger: glass filter bar, summary chips, then rows
of time, order, requester, workshop, objective, decision and evidence status.
**Open** shows the stored record in the same dark slide-over (Decision,
Candidates, Evidence), with the tool trace and raw record behind toggles.

## Guided demo

**Guided demo** in the sidebar starts a six-step tour: Normal allocation (R09),
Clarification (R01), Refused workshop (R08), Unanswerable request (R02),
Impossible deadline (R30), Audit trail. A floating controller shows "DEMO n OF 6",
the step name and a one-line hint, with Previous, Next and Exit. Each step only
loads the real request into Dispatch (or opens the Audit Trail). The presenter
still presses Evaluate request and Confirm; nothing is precomputed, evaluated or
confirmed by the tour.

## Motion

Cards rise 6px on entry (350ms), the active process node pulses, the hero has a
slow top-edge sheen, on-time map lines carry a dotted flow, and slide-overs
slide in from the right. `prefers-reduced-motion` turns all of it off.

## Design review checklist

- [x] The beam appears only on active, selected, recommended or confirmed objects.
- [x] The recommendation is the largest, darkest object on Dispatch.
- [x] Alternatives are visibly secondary and never repeat the winner.
- [x] Every status has a word, not only a colour.
- [x] No default-looking Streamlit controls: inputs, selects, tabs, pills,
      expanders, popovers, dialogs and scrollbars are restyled.
- [x] No em or en dashes in UI copy written by the app (inbox messages are data
      and are shown as supplied).
- [x] Honest copy: ties are ties, the guardrail failure is shown, accuracy is
      "not reported yet", fixtures are labelled, no workshop is contacted.
- [x] Checked at 1920 x 1080, and at 1440 x 900 in presentation mode.
- [ ] Not checked: Safari, Windows fonts, browser zoom other than 100%.

## Technical notes

- Backend untouched: `agent.py`, `tools.py`, `allocator.py`, `objectives.py`,
  `faithfulness.py`, `records.py`, `desk.py`, `intake.py`, `harness/`, `data/`,
  `eval/`. The UI only reads previews, records and committed evaluation files.
- The inspector and audit panels are `st.dialog`s restyled as slide-overs via
  `[data-testid="stDialog"]:has(.inspector)`.
- `[data-testid="stMarkdownContainer"]:has(> div)` removes Streamlit's -1rem
  prose margin from custom HTML blocks so the layout gap holds.
- The network map is inline SVG generated in `network.py`; positions are fixed
  by workshop ID so the map never reshuffles between queries.
