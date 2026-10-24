# Threadline V9, phase 1: visual foundation

> Superseded in part by V10 (`docs/threadline_v10_production.md`): the canvas now covers the
> whole window with transparent thread layers, and every length scales from one root size.

Phase 1 replaces generated textures with the three approved Threadline background
assets and moves the material system onto them. Business logic, evidence files,
the simulator and the audit data model are unchanged. Edge lighting, stitch
animation and routing animation are left for later phases.

## Assets

The three files in `src/static/threadline/backgrounds/` are the approved images,
installed unmodified:

- `midnight-wave-wide.webp`
- `midnight-wave-vertical.webp`
- `pearl-wave-canvas.webp`

Each is referenced through a token in `src/ui/threadline.css`: `--img-wide`,
`--img-tall` and `--img-pearl`.

## How the system works

- **Canvas.** The pearl canvas is fixed behind the workspace. It starts at the
  sidebar's edge, so its threads frame the content rather than hide under the
  navigation. It is cropped with `cover` (never stretched), so the threads stay
  at the perimeter. A broad, soft white wash calms the centre.
- **Light surfaces.** Ordinary cards are cool white glass at about 85 to 90
  percent opacity with a 10px frost. Near the page edges the canvas threads show
  through softly, so cards belong to the canvas instead of floating as flat
  white rectangles. Selected light surfaces each carry their own crop of the
  pearl canvas, weighted toward their quiet side:
  - the workshop map
  - the Dispatch empty state
  - the request composer
  - the Audit empty state
  - the four evidence claims, which each show one corner of one shared canvas
- **Dark surfaces.** One veil family (`--veil-text`, `--veil-top`) sits over the
  midnight assets. It is strong behind text and open where the surface is quiet.
  Short, wide surfaces use the wide asset, each with its own crop
  (`--mw-pos`): the Dispatch recommendation and confirmation, the Lab result,
  and the demo bar. Tall surfaces use the vertical asset: the sidebar, the
  recommended workshop panel and both inspectors.
- **Sidebar.** The vertical asset sits under a navy veil that holds the logo and
  navigation, opens in the quiet middle, and closes again behind the status card.
  The lower controls sit on dark glass, so no thread runs behind small type.
- **Palette.** The locked anchors are applied as tokens: midnight #071D37, deep
  navy #0B223C, cobalt #3278E9, ice #68CAFA, pearl #F4F8FD, teal #22B6A5, ink
  #10263C and champagne #C8A36F. Every warm ivory and beige tone from V7 and V8
  is now cool pearl, and champagne is confined to small accents on dark
  surfaces.
- **Removed.** The generated fold SVGs, the texture inliner in `components.py`,
  the dot grid on analytical cards and the concentric rings behind the map.

## Checked

1920x1080 and 1440x900 were checked on these screens:

- Dispatch: empty, recommendation, confirmed.
- Network: recommended and alternative workshop.
- Lab: all four workspaces.
- Audit: the empty live log, the rehearsal ledger and the record panel.

No page has horizontal overflow. `uv run pytest -q`: 297 passed, 1 skipped.

## V9.1: composition and balance

**What went wrong in V9.**

- **Viewport-tied canvas.** The canvas was a fixed layer sized with `cover` to
  the viewport. In a tall window or a full-page capture, `cover` blew the
  artwork up, which produced the vertical stripes. Because it was fixed and
  `stMain` is the element that scrolls, a stitched full-page capture repeated it
  in every viewport.
- **Reused artwork.** The same pearl artwork was laid again inside the map, the
  request composer, the empty states and the evidence claims, so the texture
  seemed to restart inside cards.
- **Wave behind text.** The saturated wide wave ran behind the decision text.

**Fix.**

- **Canvas.** Drawn once, on the scrolling content, as two accents at fixed
  pixel sizes: the artwork at the top right and the same artwork turned at the
  bottom left. Each fades into a calm centre. It never uses `cover`, never tiles
  and never restarts.
- **Material family.** Five materials, each used only where it is listed:

| Material | Where | Imagery |
| --- | --- | --- |
| Pearl standard | Inbox, composer, options, ledger, empty states, claims | None. Surface gradient, hairline seam, soft lift |
| Pearl atmospheric | Page canvas; workshop map (washed, lower left) | Pearl wave |
| Analytical | Charts, tables, matrices, capacity | None |
| Midnight standard | Decision and audit inspectors, demo bar | Satin, or none |
| Midnight textile | Recommendation, Lab result, recommended workshop | Calm wave at a fixed width in the lower right, behind a solid navy text zone |

- **Specificity bug.** The midnight rule grouped the dialog selector inside
  `:is()`, which raised every surface in the group to (0,3,1) and silently
  overrode the per-card textile. The dialog now has its own rule.
