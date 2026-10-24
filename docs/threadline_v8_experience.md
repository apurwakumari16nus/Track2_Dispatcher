# Threadline V8: product experience

> Superseded in part by V9 (`docs/threadline_v9_materials.md`): the generated fold line
> art was replaced by the three approved background assets.

V8 builds on V7's design system (`src/ui/threadline.css` over the structural
`src/ui/theme.css`). It follows the reference concept's art direction and keeps
the application's own text, numbers and workflows. Allocation, tools, evidence
files, the simulator and the audit data model are unchanged.

## Direction

The factory runs quick-response apparel production: knitwear and tops for mall
brands, in four stages (knitting, assembly, washing, packing), with batches
farmed out to eight workshops. V7's knitted stockinette texture said "sweaters"
too literally and repeated across the page like wallpaper. V8 replaces it with
cloth itself: one large drape study drawn in fine vector line. It sits in ice
and champagne on midnight surfaces and in navy at low contrast on the ivory
canvas, it never repeats, and it stays crisp at any zoom.

## Changes from the reference

| Reference | Threadline V8 |
| --- | --- |
| Raster fabric photo inside the hero | Vector fold lines: sharp at every size and weightless |
| White workshop card on the dark hero | One midnight surface. The workshop panel is dark glass with a ruled metric row. |
| Invented values and labels | Every figure comes from the recorded decision. The batch line ("ORD-045, 150 vests for Cotton Club") is read from the parsed request. |
| Fabric swatches as option images | The workshops' illustrative photos, labelled as illustrative |
| A gold button wherever an action appears | Champagne is kept for the one human commitment (Assign or Accept). Routing previews stay cobalt. |

## New in V8

- **Fold line art.** `src/static/brand/texture/folds-light.svg` and
  `folds-dark.svg` are generated vector drawings, inlined by
  `components.textures()`. They appear on the canvas corners, every midnight
  surface, the sidebar and the workshop map.
- **Unified hero.** The batch line sits above the headline. The workshop panel
  is dark glass, and the four metrics are divided by hairlines. The commit
  button is champagne with an arrow.
- **Commit transition.** On confirmation the seam turns green, a short glow
  blooms and one champagne light passes across the headline. It plays once and
  is switched off when the system asks for reduced motion.
- **Option cards.** Each card carries a small illustrative photo, pinned like a
  swatch to a spec sheet.
- **Inspection on the map.** The workshop you inspect wears a dashed ring. The
  routed workshop keeps its solid seam, so inspecting never looks like
  choosing.

## Review path

1. Dispatch: look at the empty state (loom illustration, three steps). Select
   R09, evaluate it (choose rehearsal if prompted), then read the hero: the
   batch line, the workshop panel and the champagne Assign button.
2. Press Assign: watch the seam turn green and the light pass once. The
   decision thread under the request now reads "Confirmed by you".
3. Press Trace on the network: the recommended workshop is a midnight card.
   Click GiantWeave (dashed inspection ring, pearl card), then OldMill (hatched,
   desaturated, coral seam).
4. Simulation Lab: Performance (midnight result with fold lines), Tradeoffs,
   Disruption (stitched event timeline), Evidence (archive-drawer source
   selector, bound claim sheets, matrix).
5. Audit Trail: the Live log shows the designed empty ledger. Switch to the
   Rehearsal log, then open a record.
