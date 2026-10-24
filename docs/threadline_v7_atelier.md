# Threadline V7: Luminous Atelier

> Superseded in part by V8 (`docs/threadline_v8_experience.md`): the knitted
> textures described below were replaced by fabric-fold line art.

V7 replaces the V4, V5 and V6 override layers with one design system,
`src/ui/threadline.css`, loaded after `src/ui/theme.css`. theme.css now keeps
layout and component structure only. Allocation, tools, evidence, the
simulator and the audit data model are unchanged.

## Why V6 looked almost the same as V5

The V6 materials only changed fills and borders on the same rectangles. Pearl
was near-white, the analytical glass a pale blue wash, and the edge light a 1px
ring that disappeared at normal zoom. The background weave was a faint grid.
Controls (buttons, pills, segmented capsules) were untouched, so most of each
screen looked as it did before.

## Direction

Three directions were considered: Luminous Atelier (warm pearl, champagne,
ice glass), Precision Loom (midnight, sapphire light, engineered weave) and
Silk and Signal (light glass, smooth transitions). Precision Loom was dropped
because the product works on a light operations canvas. Silk and Signal was too
close to V6. Luminous Atelier was chosen: it stays legible and calm, and gives
the knitwear subject a recognisable material.

## Materials

| Material | Where | Character |
| --- | --- | --- |
| Pearl | Inbox, request, ledger, cards | Warm pearl, a pearlescent band, a knitted ground, outer hairline and soft lift |
| Command glass | Network, Lab and Audit command bars | The only real blur |
| Instrument | Charts, the map, capacity, matrices | Neutral optical glass with a dot scale and a cobalt-lit bezel |
| Dossier | Evidence claims, the empty ledger and the Dispatch empty state | Ivory paper with a stitched binding in the verdict colour |
| Midnight | Recommendation, recommended workshop, Lab result, inspectors | Navy with cobalt and champagne light inside, a knitted dark ground, a full seam |
| State glass | Selected, recommended, confirmed, warning, blocked | Seam colour, inner light and, for blocked, a hatched header and a desaturated photo |

**Seam light.** Every material draws its edge from one `::before` ring. A conic
gradient puts a reflection on each corner, so the edge reads as a lit seam.
Brightness follows importance: pearl cards are quiet, selections are cobalt
and brighter, and midnight cards are the brightest.

**Canvas.** The page ground is a warm pearl to ice gradient with four light
fields, a knitted stockinette texture that is strongest at the edges, and
drape contours in ice and champagne at two corners. The textures are SVG files
in `src/static/brand/texture`, inlined as data URIs by `inject_css()`.

## Components

- **Stitched progress rail.** Steps are knots on one thread. Finished stretches
  are sewn in cobalt, the rest is tacked, and the thread runs only during a real
  evaluation. It is used for Dispatch steps, the route tracker, the network
  route sequence, and the Lab and Audit chronologies.
- **Woven capacity meter.** Booked capacity is a dense twill, this batch is lit
  thread, and spare capacity is open weave. The widths come from the engine.
- **Decision thread.** A stitch under the request card says what follows: the
  engine recommendation waiting for you, or your confirmation, which is green.
- **Swatch cards.** The Dispatch alternatives and the Lab policy cards carry a
  woven header band. Our policy's band is lit.
- **Tab rail.** Every segmented choice sits on a stitched track, and the
  choice is a sewn thread. The Lab workspaces get a raised pearl tab. The
  evidence source is a choice between two archive drawers.
- **Mode ribbon.** Rehearsal mode is a strip anchored to the top of every page,
  tacked on with basting stitches.
- **Empty states.** On Dispatch, a three-step explanation sits beside a loom
  illustration (requests, the factory knot, eight workshops). On Audit, the
  explanation sits beside an empty ledger page that is ruled and waiting.

## Controls

Signal (primary) is cobalt with an internal light. Pearl (secondary) uses the
card material. Thread (tertiary) underlines with a running stitch. Basting
(disabled) is a dashed outline. Confirming an allocation is a human decision,
so that button is ivory and champagne on midnight and looks unlike any other.
Status words use a diamond marker, not a capsule. Eyebrows lead in with a short
thread and a knot.

## Checked

1920x1080 and 1440x900 were checked on these screens:

- Dispatch: empty, recommended, inspector, confirmed.
- Network: recommended, alternative, suspended.
- Lab: all four workspaces.
- Audit: the empty live log, the rehearsal ledger and the record panel.

No page has horizontal overflow. `uv run pytest -q`: 297 passed, 1 skipped.
