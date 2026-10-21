# Threadline V5 design system

Built from one benchmark component (the Workshop Network detail card) and then
extended to every page. Tokens live in the "Threadline V5 design system" block at
the end of `src/ui/theme.css`; the shared builder is `state_line()` in
`src/ui/components.py`.

## Motifs

| Motif | What it is | Where |
| --- | --- | --- |
| Woven canvas | Pearl to ice gradient, a fine 6px warp and weft, stronger at the outer edges, lit by cyan (top right), champagne (top left) and cobalt (bottom left) | Every page background |
| Precision edge | A 1.5px edge light that enters at the top-left corner and fades along the border, plus a 3px state rail | Only selected request, recommended workshop, routing preview, principal simulation result, selected objective, confirmation, warnings and blocks |
| Stitch | 6px dashes with 4px gaps; cobalt when complete, slate when pending; vertical variant for timelines | Dispatch steps, route tracker, network candidate routes, disruption timeline, audit chronology, empty-state steps |
| Weave micro-pattern | A crosshatch that fades out from a card corner | Recommended workshop card, Audit empty state |
| Selvedge | A stitched champagne edge on featured navy surfaces (from V4) | Dispatch recommendation, Lab hero |

## States

One family of five states, each with a colour, an icon and words. A suggestion
and a commitment never look the same.

| State | Colour | Icon | Example wording |
| --- | --- | --- | --- |
| Recommended | Teal #0F9F8A | verified | "Recommended. Suggested by the engine. Not yet confirmed." |
| Selected | Cobalt #2A77E8 | my_location | "Routing preview. Chosen by you." |
| Confirmed | Green #1E9E5C | task_alt | "Confirmed by you at 15:45 UTC. Audit record saved." |
| Warning | Amber #D7901E | warning | "Least-late option. No permitted workshop meets the due date." |
| Blocked | Coral #E25A52 | block | "Suspended. It may not take new work." |

On the network map the engine's recommendation route and ring are teal; a
manual routing preview is cobalt.

The old filled pills are now quiet inline markers (a small diamond plus a word),
so status no longer competes with content.

## Buttons

Primary: cobalt gradient with an inner highlight, lifts 1px on hover, presses on
click. Secondary: white with a slate border that turns cobalt on hover. Tertiary:
cobalt text that underlines on hover. Transitions name their properties; nothing
uses `transition: all`.

## Layout

The main column now uses up to 1880px on wide screens (it was capped at 1680px).
Headings use balanced wrapping.

## Not changed

Allocation, tools, evidence files, simulator and audit data model. The
recommendation, rank and every figure on a card come from the engine and the
register.
