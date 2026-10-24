# Threadline V10: production design recovery

V10 repairs the regressions that V9.1 left in the running app and sets the
visual foundation for the stitched workflow animation that comes next. Only the
presentation changed. The allocator, tools, simulator, data, evaluation files and
audit data model are untouched, and `uv run pytest -q` still passes (297 passed,
1 skipped).

## What was broken

Verified in a real browser (Playwright, Chrome) by measuring the DOM:

- **Canvas confined to a rectangle.** The pearl canvas was drawn on
  `stMainBlockContainer`, which is capped at `min(1880px, 100%)`. On a
  3440 x 1316 window that column is 1880px wide and sits at x = 914, so the
  artwork stopped at x = 914 and x = 2794. The rest of the window was plain. On
  short pages the column was also shorter than the window (1109px of 1316px),
  which left a plain band below it.
- **A second hard edge inside the map.** The workshop map laid a rectangular
  crop of the pearl artwork into its lower left (`820px auto`), and the crop's
  top and right edges showed.
- **Nothing scaled with the screen.** Every length in `theme.css` and
  `threadline.css` was a fixed pixel value set for a 15px root (317 font sizes in
  `theme.css` alone), so a 34 inch ultrawide or a projector got a laptop-sized UI.
  Body copy computed to 12.5px.
- **Dark factory emblem.** The Threadline mark's stem is navy. Drawn on a navy
  disc, it vanished. The sidebar logo had the same problem.
- **Faint edges.** The perimeter ring on light cards was mostly white and ice
  on white, so it read as no edge at normal zoom.
- **Competing definitions.** `theme.css` still carried V3 to V6 backgrounds,
  borders and shadows for surfaces that `threadline.css` overrode with
  `!important`, plus 187 rules for components no page renders.

Suspected at first and ruled out: background repetition, stacking-context bugs
and `cover` scaling (all fixed in V9.1); browser zoom (screenshots were at 1x).

## What changed

**One scale.** All layout lengths are rem (1rem = 15px at the design base). The
root size follows the window from 1600 x 860 up, `clamp(15px, min(1.4815vh,
.8333vw), 21px)`: 15px on laptops, 16px at 1920 x 1080, about 19.5px on a
3440 x 1316 ultrawide, and 14px below 1366px. Presentation mode multiplies it by
1.12 for projectors. The type scale was raised one step: body 15px, metadata
13.5px, labels 12px at the base.

**One canvas.** The canvas is painted on `.stApp`, which never scrolls, so it
covers the whole window and stays still while the page scrolls inside it. It
uses two transparent thread layers cut from the approved pearl artwork:
colour-to-alpha against the artwork's own white, compression haze removed, and
faded to zero before every edge. No image boundary can appear at any size. The
threads sit at the top right and rise from the bottom edge beside the sidebar,
and the centre stays calm. The map has no imagery: fine twill and a soft light
over the factory, with nothing that could pass for a route.

**Edge light.** One `::before` ring for every material, in four intensities:

- **Ambient:** 1px, an ice glint at the top-left corner and a cobalt reflection
  in the far corner, over a visible blue-grey line.
- **Focus:** 1.5px cobalt, with a soft halo.
- **Featured:** 1.5px, with cyan and champagne corner reflections, inner light
  and outer illumination.
- **State:** teal (engine recommendation), green (human confirmation), amber
  and coral.

Corner reflections are radial gradients anchored to the corners, so they land
on the corners whatever the card's shape.

**Materials:**

- **Pearl:** white under a key light, cooling toward the base.
- **Command glass:** blurred translucent bars.
- **Analytical:** neutral white glass with one faint reflection; charts sit on
  a ruled line.
- **Dossier:** paper.
- **Midnight:** a base gradient, a cobalt key light and an ice bounce. It carries
  threads cut from the calm horizontal wave: at the top right of the
  recommendation, and beside the Lab figure passing behind the comparison glass,
  masked away from every paragraph.
- **Satin:** inspectors and the recommended workshop.

**Controls and states:**

- The commit button is a pearl key on midnight with a champagne thread.
- The rehearsal ribbon and banners are pearl with an amber stitched rail, not
  beige slabs.
- Green appears only on a human confirmation.

**Brand:**

- The factory is the unaltered mark on a pearl disc with a navy band and a
  champagne rim.
- The sidebar mark sits on a pearl tile.

**Architecture:**

- `theme.css` is structure only: 187 dead rules and 123 overridden material
  declarations were removed, along with the old canvas, sidebar fabric and the
  old main column width.
- `threadline.css` owns tokens, scale, canvas, light, materials, controls and
  pages, in that order.

**Responsive fixes:**

- The recommended workshop's metrics fold to two by two in a narrow panel.
- The map's SVG labels grow when the map card is narrow.
- On laptops the Audit timeline moves under the ledger, so ledger rows stay on
  one line.

## Checked

QA used Playwright with real clicks, at 1920 x 1080, 1440 x 900 and
3440 x 1316. It covered all 14 states:

- Dispatch: empty, recommended, inspector and confirmed.
- Network: recommended, alternative and suspended.
- Lab: the four workspaces.
- Audit: the live empty state, the rehearsal records and the record panel.

The checks found:

- **Overflow:** none at those sizes, nor at 1280 x 800, 1366 x 768 or in
  presentation mode at 1920.
- **Edge rings:** every material renders its ring, read from the computed
  `::before`.
- **Reduced motion:** no animation runs.
- **Confirmed edge:** green.
- **Recordings:** QA confirmations went to the git-ignored rehearsal log; the
  live log was not written.

## Not done

- Vega charts take a fixed pixel height from Python. They scale in width but not
  height, and their labels are 13.5px at every size.
- The supplied `threadline-mark.png` is 268 x 240 with jagged alpha edges, which
  shows at 2x. An SVG master would fix it.
- `src/static/brand/fabric-dark-*.webp` are no longer referenced (they are
  committed files, so they were left in place).
