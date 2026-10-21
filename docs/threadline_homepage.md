# Threadline homepage (Dispatch)

The product is now **Threadline by Sweater Co**. This pass rebuilt the homepage
(Dispatch) and the shared shell to match the supplied target design. Other pages
inherit the new shell and palette but were not redesigned.

## Layout

| Target element | Implementation |
| --- | --- |
| Sidebar with logo | Threadline mark (from the supplied logo) beside a live wordmark, on a navy slab over the dark fabric texture |
| Navigation | Dispatch, Workshop Network (Operations); Simulation Lab, Audit Trail (Evidence) |
| System status card | Real checks only: request reading, workshops active, allocation engine, queue date, confirmations this session |
| User card | "Dispatcher, you approve every decision". No invented person |
| Top bar | Dispatch kicker (plus a REHEARSAL MODE pill when rehearsing), search (filters the inbox), alerts bell (requests waiting on the sender), date, objective, System ready |
| Title | "Turn requests into confident workshop decisions" with an honest subtitle on who does what |
| Inbox | Avatar rows, All / Pending / Reviewed filters from this session's outcomes, selected row highlighted |
| Request card | Sender, request ID, order headline and chips from `orders.csv`, Edit request, New request, Evaluate request, garment rail photo |
| Recommendation card | Navy over the dark fabric: "Assign to {workshop}", the engine's reason, "Why this workshop?" points, a white workshop panel with back-by date, spare days, total cost and defect risk, then Assign and View other options |
| Process strip | Understand, Validate, Evaluate, Decide, Confirm, driven by the recorded trace. Verification folds into Decide; Confirm is the human step |

## Honesty rules kept

- The recommendation is the deterministic engine's choice (R09 recommends Nimble
  Needle, not the mock's SteadyHands). Every figure on the card is read from the
  decision record.
- The mock's capacity match, star rating, location and attachments are not in the
  data, so they are not shown. Urgency is not recorded, so the inbox filters are
  All / Pending / Reviewed.
- "Assign" records the decision only. The card says nothing is sent to the workshop.

## Assets (`src/static/brand/`)

| File | Source | Used in |
| --- | --- | --- |
| `threadline-mark.png` | Supplied logo, mark cut out with a transparent background | Sidebar, browser tab icon |
| `threadline-logo.png` | Supplied logo, full lockup | Kept for light surfaces (not used yet) |
| `hangers.webp` | Supplied garment rail photo | Request card |
| `fabric-dark-tall.webp` | Supplied dark fabric (portrait) | Sidebar texture under a navy veil |
| `fabric-dark-wide.webp` | Supplied dark fabric (wide) | Recommendation card backdrop |
| `fabric-light.webp` | Supplied light silk | Canvas edges, masked to low contrast |
| `atelier.webp` | **Not supplied yet** | Drop a workshop photo here and the recommendation panel shows it automatically |

All images are resized and compressed (about 400 KB in total) and served with
Streamlit static serving, so they work offline.

## Tokens

Navy `#0A1E3A`, deep blue `#123A66`, royal `#2A77E8`, cyan `#5ED8FF`, pearl
`#F7F9FC`, ivory `#FAF6EF`, champagne `#D9B37A`, text `#102238`, muted `#5E6D82`,
border `#DDE4EC`, success `#2FC77A`. Defined at the top of `src/ui/theme.css`
and in `.streamlit/config.toml`. Primary actions are royal blue; the signature
beam now runs cyan to royal with a champagne tail.

## Run

```bash
uv run streamlit run src/app.py
```

Open Dispatch (the default page). Without an API key, press Evaluate request and
choose "Switch to rehearsal mode" to see the recommendation card.
