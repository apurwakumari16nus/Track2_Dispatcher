"""Quick Response Desk component library. Presentation only.

Builders return escaped HTML strings so pages can compose them; html() renders.
Every dynamic value passes through esc(). Keep markup on one line: Markdown
treats indented lines as code blocks. Status is always a word plus colour.
Widgets cannot live inside HTML, so surfaces that hold widgets are keyed
Streamlit containers styled in theme.css (st-key-rec, st-key-request, ...).
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

import streamlit as st

CSS_PATH = Path(__file__).with_name("theme.css")
SYSTEM_PATH = Path(__file__).with_name("threadline.css")  # V7 design system: materials, light, controls, states.
# Chart palette, validated for colour-blind separation and 3:1 contrast on the light surface.
OURS, BENCH, SHOCK, SLATE, SLATE_LIGHT, BEAM = "#5F78F5", "#149E8B", "#E8692F", "#A8B5C3", "#D6DEE7", "#48D9E6"
TERM_CLASS = {"lateness": "t-lateness", "defect": "t-defect", "fairness": "t-fairness", "robustness": "t-robustness", "cost": "t-cost"}
STAGE_ICONS = {"done": "✓", "blocked": "!", "active": "", "idle": "", "skipped": ""}
PRESENTATION_CSS = """
:root { --ui-zoom: 1.12; }
[class*="st-key-dev_"] { display: none !important; }
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarHeader"] button { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 1.8rem; }
"""


def esc(value) -> str:
    return escape("" if value is None else str(value))


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_css(presentation: bool = False) -> None:
    css = CSS_PATH.read_text(encoding="utf-8") + SYSTEM_PATH.read_text(encoding="utf-8")
    html("<style>" + css + (PRESENTATION_CSS if presentation else "") + "</style>")


# Atoms ----------------------------------------------------------------------

def status_pill(text: str, tone: str = "muted") -> str:
    """tone: conf (a person confirmed it, the only green), ok (a check passed), info, warn, risk, muted, beam-pill,
    dark, dark-conf, dark-amber, dark-muted, dark-risk."""
    return f'<span class="pill {tone}">{esc(text)}</span>'


def verdict_badge(text: str, kind: str = "tie") -> str:
    """kind: tie, win, loss. Large, uppercase, used once per comparison."""
    return f'<span class="verdict {kind}">{esc(text)}</span>'


def banner(title: str, text: str = "", tone: str = "info") -> str:
    return f'<div class="banner {tone}" role="status"><div><b>{esc(title)}</b>{esc(text)}</div></div>'


def mode_ribbon(title: str, text: str, note: str = "") -> str:
    """Operating-mode strip anchored to the top of the workspace (rehearsal, cached replies)."""
    tail = f"<em>{esc(note)}</em>" if note else ""
    return f'<div class="mode-ribbon" role="status">{icon("science")}<b>{esc(title)}</b><span>{esc(text)}</span>{tail}</div>'


def thread_link(label: str, confirmed: bool = False) -> str:
    """The stitch that ties the selected request to its recommendation and, later, to the confirmation."""
    return f'<div class="dthread{" conf" if confirmed else ""}" aria-hidden="true"><i></i><span>{esc(label)}</span></div>'


def loom_art() -> str:
    """Dispatch empty state: requests on the left, the factory knot, eight workshops on the right. Purely illustrative."""
    msgs = "".join(f'<g class="msg" transform="translate(8 {y})"><rect width="92" height="34" rx="9"/><line x1="12" y1="13" x2="70" y2="13"/>'
                   f'<line x1="12" y1="22" x2="50" y2="22"/></g>' for y in (36, 104, 172))
    ins = "".join(f'<path class="th in" d="M100 {y + 17} C170 {y + 17} 170 150 236 150"/>' for y in (36, 104, 172))
    ws = [(410, 34), (444, 78), (462, 128), (464, 178), (446, 228), (410, 268), (370, 24), (372, 276)]
    outs = "".join(f'<path class="th {"lit" if i == 2 else "out"}" d="M262 150 C320 150 {x - 60} {y} {x - 12} {y}"/>' for i, (x, y) in enumerate(ws))
    nodes = "".join(f'<g class="ws{" lit" if i == 2 else ""}"><circle cx="{x}" cy="{y}" r="11"/></g>' for i, (x, y) in enumerate(ws))
    return ('<svg class="loom" viewBox="0 0 500 300" role="img" aria-label="Requests are routed through the factory to one of eight workshops">'
            '<defs><linearGradient id="loomLit" x1="0" x2="1"><stop offset="0" stop-color="#3278E9"/><stop offset="1" stop-color="#9BE8FB"/></linearGradient></defs>'
            f'{ins}{outs}{msgs}<circle class="hubr" cx="249" cy="150" r="27"/><circle class="hubc" cx="249" cy="150" r="23"/>'
            f'<image href="app/static/brand/threadline-mark.png" x="236" y="138" width="26" height="23"/>{nodes}'
            '<text class="k" x="8" y="22">REQUESTS</text><text class="k" x="206" y="200">FACTORY</text><text class="k" x="392" y="300">WORKSHOPS</text></svg>')


def page_head(eyebrow: str, title: str, lede: str = "") -> None:
    html(f'<div class="eyebrow">{esc(eyebrow)}</div><div class="display">{esc(title)}</div>'
         + (f'<div class="lede">{esc(lede)}</div>' if lede else ""))


def section(title: str, note: str = "") -> None:
    html(f'<div class="title">{esc(title)}</div>' + (f'<div class="meta" style="font-size:0.9333rem;margin-top:2px">{esc(note)}</div>' if note else ""))


def metric_tile(label: str, value: str, note: str = "") -> str:
    return f'<div class="kpi"><small>{esc(label)}</small><strong>{esc(value)}</strong><span>{note}</span></div>'


def glass_panel(inner: str, *, beam: bool = False, style: str = "") -> str:
    return f'<div class="glass{" beam" if beam else ""}" style="{style}">{inner}</div>'


def fact(label: str, value, *, mono: bool = False) -> str:
    """A labelled value chip; mono=True sets identifiers in Geist Mono."""
    cls = ' class="id"' if mono else ""
    return f'<span class="fact">{esc(label)} <b{cls}>{esc(value)}</b></span>'


# Composites -----------------------------------------------------------------

def decision_stage(stages) -> str:
    """Five-step process strip. stages: (key, label, detail, status)."""
    cells = []
    for i, (_, label, detail, status) in enumerate(stages):
        line = '<span class="line"></span>' if i < len(stages) - 1 else ""
        cells.append(f'<div class="stage {status}" title="{esc(detail)}"><span class="node">{STAGE_ICONS.get(status, "")}</span>'
                     f'<span class="lbl">{esc(label)}</span>{line}</div>')
    return f'<div class="strip" role="list" aria-label="Decision stages">{"".join(cells)}</div>'


STATE_ICONS = {"rec": "verified", "sel": "my_location", "conf": "task_alt", "warn": "warning", "block": "block", "info": "info"}


def state_line(variant: str, title: str, sub: str = "", glyph: str | None = None) -> str:
    """The integrated status line that heads a card: icon, a short state, one line of context.
    variant: rec (recommended), sel (selected), conf (confirmed), warn (warning), block (blocked), info."""
    return (f'<div class="tl-state is-{variant}">{icon(glyph or STATE_ICONS.get(variant, "info"))}<div><b>{esc(title)}</b>'
            + (f"<span>{esc(sub)}</span>" if sub else "") + "</div></div>")


def icon(name: str, cls: str = "") -> str:
    """A Material Symbols glyph (the icon font Streamlit already loads), hidden from screen readers."""
    return f'<span class="msym {cls}" aria-hidden="true">{esc(name)}</span>'


def process_strip(steps, live: bool = False) -> str:
    """Homepage five-step strip. steps: (key, label, sublabel, status); status done, active, idle, skipped or blocked.
    live=True only while a request is really being evaluated: the thread into the active step then runs."""
    cells = []
    for n, (_, label, sub, status) in enumerate(steps, 1):
        mark = "✓" if status == "done" else "!" if status == "blocked" else str(n)
        cells.append(f'<div class="pstep {status}"><span class="pnum">{mark}</span><span class="ptxt"><b>{esc(label)}</b>'
                     f'<small>{esc(sub)}</small></span></div>')
    def line(i):
        cls = " done" if steps[i][3] == "done" else ""
        if steps[i][3] == "done" and steps[i + 1][3] == "active":
            cls += " run"
        return f'<span class="pline{cls}" aria-hidden="true"></span>'
    lines = [line(i) for i in range(len(cells) - 1)]
    joined = "".join(cell + (lines[i] if i < len(lines) else "") for i, cell in enumerate(cells))
    return f'<div class="pstrip{" live" if live else ""}" role="list" aria-label="Decision steps">{joined}</div>'


def candidate_row(name: str, sub: str, eta: str, spare: int | None, cost: str, tone: str) -> str:
    spare_text = "n/a" if spare is None else f"{spare:+d}"
    cls = "neg" if spare is not None and spare < 0 else ""
    return (f'<div class="alt"><span class="nm"><span class="dot {tone}"></span><span style="min-width:0"><b>{esc(name)}</b>'
            f'<div class="meta">{esc(sub)}</div></span></span><span class="r">{esc(eta)}</span>'
            f'<span class="r {cls}">{spare_text}</span><span class="r">{esc(cost)}</span></div>')


def weight_bars(config, terms, labels) -> str:
    """Objective weights as luminous bars; zero weights are drawn muted."""
    rows = []
    for t in terms:
        w = getattr(config, "w_" + t)
        rows.append(f'<div class="wbar{"" if w else " off"}"><span>{esc(labels[t])}</span><div class="trk"><span style="width:{w * 100:.0f}%"></span></div>'
                    f'<span class="v">{w:.2f}</span></div>')
    return f'<div class="wbars">{"".join(rows)}</div>'


def score_bars(breakdown: list[dict], chosen_id: str | None, terms, labels) -> str:
    """Stacked weighted-term bars per candidate on dark; widths relative to the largest score."""
    top = max((item["score"] for item in breakdown), default=0) or 1
    rows = []
    for item in breakdown:
        segs = "".join(f'<span class="{TERM_CLASS[p["term"]]}" style="width:{p["contribution"] / top * 100:.2f}%" '
                       f'title="{esc(p["label"])}: {p["contribution"]:.6f}"></span>' for p in item["parts"] if p["contribution"] > 0)
        cls = " win" if item["workshop_id"] == chosen_id else ""
        rows.append(f'<div class="sbar{cls}"><span>{esc(item["name"])}</span><div class="trk">{segs}</div><span class="v">{item["score"]:.5f}</span></div>')
    active = [t for t in terms if any(p["term"] == t and p["active"] for item in breakdown for p in item["parts"])]
    legend = "".join(f'<span><i class="{TERM_CLASS[t]}"></i>{esc(labels[t])}</span>' for t in active)
    return f'<div class="sbars">{"".join(rows)}</div><div class="dk-legend">{legend}</div>'


def table(headers, rows, *, right=(), classes=None, max_height: int | None = None) -> str:
    """rows hold pre-escaped cell HTML; use esc() for plain values."""
    head = "".join(f'<th class="{"r" if i in right else ""}">{esc(h)}</th>' for i, h in enumerate(headers))
    body = "".join(
        f'<tr class="{classes[n] if classes else ""}">' + "".join(
            f'<td class="{"r" if i in right else ""}">{cell}</td>' for i, cell in enumerate(cells)) + "</tr>"
        for n, cells in enumerate(rows))
    style = f' style="max-height:{max_height}px"' if max_height else ""
    return f'<div class="dt-wrap"{style}><table class="dt"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def json_block(value, *, height: int | None = None) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False)
    st.code(text, language="json", wrap_lines=True, height=height)


# Charts -----------------------------------------------------------------------

FONT = "Mona Sans, -apple-system, Segoe UI, Arial, sans-serif"
AXIS = {"labelFontSize": 13.5, "titleFontSize": 13.5, "titleFontWeight": 600, "labelColor": "#5A6B80", "titleColor": "#33465E",
        "gridColor": "rgba(38,119,216,0.13)", "gridDash": [2, 4], "domain": False, "ticks": False, "labelPadding": 8, "titlePadding": 12,
        "labelFont": FONT, "titleFont": FONT}


def chart(data, spec: dict, *, height: int = 300) -> None:
    """Shared chart theme: transparent, quiet axes, product palette; exact values in tooltips."""
    st.vega_lite_chart(data, {
        "height": height, "background": "transparent", "padding": {"left": 4, "right": 16, "top": 10, "bottom": 4},
        "config": {"view": {"stroke": None}, "axis": AXIS, "bar": {"cornerRadiusEnd": 3},
                   "legend": {"labelFontSize": 13.5, "labelColor": "#5A6B80", "title": None, "orient": "top", "symbolSize": 90,
                              "labelFont": FONT, "symbolStrokeWidth": 0},
                   "text": {"color": "#10263C", "fontSize": 13.5, "font": FONT}},
        **spec,
    }, width="stretch", theme=None)
