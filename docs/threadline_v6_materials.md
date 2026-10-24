# Threadline V6 materials

V6 gives every surface a material and every material the same edge. All of it
lives in `src/ui/materials.css`, loaded after `theme.css` by `inject_css()` in
`src/ui/components.py`. Allocation, tools, evidence files, the simulator and the
audit data model are unchanged.

## One edge, four materials

Every material surface carries a full-perimeter rim: a `::before` ring drawn from
one variable, `--rim`, with light entering at the top left and running all the
way round. Materials change only the fill, the rim gradient and the lift.

| Material | Used for | Treatment |
| --- | --- | --- |
| Pearl glass | Inbox, request, ledger, policy and option cards, process strip | Near-opaque white fill, ice-to-slate rim, soft lift |
| Functional glass | Command bars on Network, Lab and Audit | The only real blur (`backdrop-filter`), so controls float over content |
| Frosted analytical glass | Charts, the network map, capacity, evidence, empty states | Ice gradient with a top-left sheen and a stronger cyan rim |
| Illuminated midnight glass | The one decision on a screen: Dispatch recommendation, recommended workshop on the Network, Lab hero, record and decision inspectors | Navy fill lit cyan top left and champagne bottom right, 1.5px rim from ice through cobalt to champagne |
| Operational state glass | Selected, warning, blocked and confirmed states | Tinted fill plus a rim in the state colour |

Nested content inside a midnight or state card takes no rim of its own, so a
card never shows two edges.

## Green is earned

Green appears only where a person confirmed something: the confirmed Dispatch
hero, the inbox "Confirmed" marker, audit records and the "Confirmed by
dispatcher" marker. Anything the engine or the evidence established on its own
is teal (the engine's colour) or neutral:

| Was green | Now |
| --- | --- |
| "Every number checked against the tools", "Verified", "Matches current code" | Teal |
| Lab verdicts that beat or qualify, and their claim cards | Teal |
| "On time" on Dispatch alternatives, "On plan" on the route | Teal |
| Strong fit ring on the map | Slate ring (eligible, nothing more) |
| Simulated "Back at factory" in playback | Cobalt, completing the route colour |
| Spare capacity | Pale outlined segment, like unbooked cloth |
| System ready and sidebar health checks | Teal |

## New motifs

**Pinked swatch edge.** Fabric swatch books cut samples with pinking shears.
Cards that are options laid side by side for comparison (Dispatch "Against the
next options", Lab policy cards) carry a pinked lower edge, so "one option among
several" reads at a glance. Single-answer cards never have it.

**Live thread.** While a request is actually being evaluated, the stitch leading
into the active step runs like thread through a machine. It stops when the
evaluation ends; a step waiting for a person never moves. Reduced motion turns it
off.

**Twill at the edges.** The canvas keeps the plain weave and adds a 45 degree
twill only at the outer edges, plus a faint champagne reflection near the page
heading. It is masked away from the reading area.

## Type

Mona Sans carries two voices: proper nouns and figures (workshop names, the
inspector title, hero numbers, policy numbers) use the wide cut at 112 percent;
the Dispatch headline uses 104 percent so a full sentence stays on one line.
Geist Mono marks identifiers such as order and workshop codes.

## Checked

1920x1080 and 1440x900: Dispatch before, after recommendation and after
confirmation; Network with the recommended workshop, another candidate and a
suspended workshop; all four Lab workspaces; Audit with the empty live log, the
rehearsal ledger and an open record. No horizontal overflow on any page at either
size. `uv run pytest -q`: 297 passed, 1 skipped.
