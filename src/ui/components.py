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
# Chart palette, validated for colour-blind separation and 3:1 contrast on the light surface.
OURS, BENCH, SHOCK, SLATE, SLATE_LIGHT, BEAM = "#5F78F5", "#149E8B", "#E8692F", "#A8B5C3", "#D6DEE7", "#48D9E6"
TERM_CLASS = {"lateness": "t-lateness", "defect": "t-defect", "fairness": "t-fairness", "robustness": "t-robustness", "cost": "t-cost"}
STAGE_ICONS = {"done": "✓", "blocked": "!", "active": "", "idle": "", "skipped": ""}
PRESENTATION_CSS = """
[class*="st-key-dev_"] { display: none !important; }
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarHeader"] button { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 1.8rem; }
"""


def esc(value) -> str:
    return escape("" if value is None else str(value))


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_css(presentation: bool = False) -> None:
    html("<style>" + CSS_PATH.read_text(encoding="utf-8") + (PRESENTATION_CSS if presentation else "") + "</style>")


# Atoms ----------------------------------------------------------------------

def status_pill(text: str, tone: str = "muted") -> str:
    """tone: ok, info, warn, risk, muted, beam-pill, dark, dark-green, dark-amber, dark-muted, dark-risk."""
    return f'<span class="pill {tone}">{esc(text)}</span>'


def verdict_badge(text: str, kind: str = "tie") -> str:
    """kind: tie, win, loss. Large, uppercase, used once per comparison."""
    return f'<span class="verdict {kind}">{esc(text)}</span>'


def banner(title: str, text: str = "", tone: str = "info") -> str:
    return f'<div class="banner {tone}" role="status"><div><b>{esc(title)}</b>{esc(text)}</div></div>'


def page_head(eyebrow: str, title: str, lede: str = "") -> None:
    html(f'<div class="eyebrow">{esc(eyebrow)}</div><div class="display">{esc(title)}</div>'
         + (f'<div class="lede">{esc(lede)}</div>' if lede else ""))


def section(title: str, note: str = "") -> None:
    html(f'<div class="title">{esc(title)}</div>' + (f'<div class="meta" style="font-size:13px;margin-top:2px">{esc(note)}</div>' if note else ""))


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

FONT = "Inter, -apple-system, Segoe UI, Arial, sans-serif"
AXIS = {"labelFontSize": 12.5, "titleFontSize": 12, "titleFontWeight": 600, "labelColor": "#617182", "titleColor": "#8695A6",
        "gridColor": "#E9EEF4", "gridDash": [2, 3], "domain": False, "ticks": False, "labelPadding": 8, "titlePadding": 12,
        "labelFont": FONT, "titleFont": FONT}


def chart(data, spec: dict, *, height: int = 300) -> None:
    """Shared chart theme: transparent, quiet axes, product palette; exact values in tooltips."""
    st.vega_lite_chart(data, {
        "height": height, "background": "transparent", "padding": {"left": 4, "right": 16, "top": 10, "bottom": 4},
        "config": {"view": {"stroke": None}, "axis": AXIS,
                   "legend": {"labelFontSize": 12.5, "labelColor": "#617182", "title": None, "orient": "top", "symbolSize": 80,
                              "labelFont": FONT, "symbolStrokeWidth": 0},
                   "text": {"color": "#122233", "fontSize": 12.5, "font": FONT}},
        **spec,
    }, width="stretch", theme=None)
