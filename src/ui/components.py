"""Small HTML builders and the shared chart grammar. Presentation only.

Builders return escaped HTML strings so pages can compose them; html() renders.
Every dynamic value passes through esc(). Keep markup on one line: Markdown
treats indented lines as code blocks. Status is always text plus colour.
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

import streamlit as st

CSS_PATH = Path(__file__).with_name("theme.css")
# Chart palette validated for the light surface (dataviz validate_palette.js, all pairs).
OURS, BENCH, SHOCK, CONTEXT, CONTEXT_2 = "#4F6FE8", "#12998A", "#E8692F", "#B7C2CE", "#D5DDE6"
TERM_CLASS = {"lateness": "t-lateness", "defect": "t-defect", "fairness": "t-fairness", "robustness": "t-robustness", "cost": "t-cost"}
PRESENTATION_CSS = """
[class*="st-key-dev_"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1600px; padding-top: 1.8rem; }
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarHeader"] button { display: none !important; }
[data-testid="stVerticalBlock"] { gap: 1.15rem; }
"""


def esc(value) -> str:
    return escape("" if value is None else str(value))


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_css(presentation: bool = False) -> None:
    css = CSS_PATH.read_text(encoding="utf-8") + (PRESENTATION_CSS if presentation else "")
    html("<style>" + css + "</style>")


def tag(text: str, tone: str = "muted", *, dot: bool = True) -> str:
    return f'<span class="tag {tone}{"" if dot else " plain"}">{esc(text)}</span>'


def banner(title: str, text: str = "", tone: str = "info") -> str:
    return f'<div class="banner {tone}" role="status"><div><b>{esc(title)}</b>{esc(text)}</div></div>'


def page_head(eyebrow: str, title: str, sub: str = "") -> None:
    html(f'<div class="eyebrow">{esc(eyebrow)}</div><div class="page-title">{esc(title)}</div>'
         + (f'<div class="page-sub">{esc(sub)}</div>' if sub else ""))


def h3(title: str, note: str = "") -> None:
    html(f'<div class="h3">{esc(title)}</div>' + (f'<div class="note">{esc(note)}</div>' if note else ""))


def tile(label: str, value: str, comparison: str = "", badge: str = "", kind: str = "") -> str:
    return (f'<div class="tile {kind}"><small>{esc(label)}</small><strong>{esc(value)}</strong>'
            f'<div class="cmp">{comparison}</div>{badge}</div>')


def table(headers, rows, *, right=(), classes=None, max_height: int | None = None) -> str:
    """rows hold pre-escaped cell HTML; use esc() for plain values."""
    head = "".join(f'<th class="{"r" if i in right else ""}">{esc(h)}</th>' for i, h in enumerate(headers))
    body = "".join(
        f'<tr class="{classes[n] if classes else ""}">' + "".join(
            f'<td class="{"r" if i in right else ""}">{cell}</td>' for i, cell in enumerate(cells)) + "</tr>"
        for n, cells in enumerate(rows))
    style = f' style="max-height:{max_height}px"' if max_height else ""
    return f'<div class="dt-wrap"{style}><table class="dt"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def load_bar(days: float, top: float) -> str:
    share = max(min(days / top, 1), .02) if top else .02
    return (f'<div class="load"><div class="load-bar"><span class="{"high" if days >= 4 else ""}" style="width:{share:.0%}"></span></div>'
            f'<b>{days:.1f} d</b></div>')


def json_block(value, *, height: int | None = None) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False)
    st.code(text, language="json", wrap_lines=True, height=height)


def score_bars(breakdown: list[dict], chosen_id: str | None, terms, labels) -> str:
    """Stacked weighted-term bars; widths relative to the largest score shown."""
    top = max((item["score"] for item in breakdown), default=0) or 1
    rows = []
    for item in breakdown:
        segs = "".join(f'<span class="{TERM_CLASS[p["term"]]}" style="width:{p["contribution"] / top * 100:.2f}%" '
                       f'title="{esc(p["label"])}: {p["contribution"]:.6f}"></span>' for p in item["parts"] if p["contribution"] > 0)
        cls = " chosen" if item["workshop_id"] == chosen_id else ""
        rows.append(f'<div class="bar-row{cls}"><span class="nm">{esc(item["name"])}</span><div class="bar-track">{segs}</div>'
                    f'<span class="val">{item["score"]:.5f}</span></div>')
    active = [t for t in terms if any(p["term"] == t and p["active"] for item in breakdown for p in item["parts"])]
    legend = "".join(f'<span><i class="{TERM_CLASS[t]}"></i>{esc(labels[t])}</span>' for t in active)
    return f'<div class="bars">{"".join(rows)}</div><div class="legend" style="margin-top:10px">{legend}</div>'


# Charts ---------------------------------------------------------------------

FONT = "Inter, -apple-system, Segoe UI, sans-serif"
AXIS = {"labelFontSize": 13, "titleFontSize": 13, "titleFontWeight": 500, "labelColor": "#5D6C7B", "titleColor": "#5D6C7B",
        "gridColor": "#EEF2F6", "domain": False, "tickColor": "#DDE5EC", "labelFont": FONT, "titleFont": FONT}


def chart(data, spec: dict, *, height: int = 300) -> None:
    """Light, transparent Vega-Lite chart; exact values stay in tooltips."""
    st.vega_lite_chart(data, {
        "height": height, "background": "transparent", "padding": {"left": 4, "right": 14, "top": 8, "bottom": 4},
        "config": {"view": {"stroke": None}, "axis": AXIS,
                   "legend": {"labelFontSize": 13, "labelColor": "#5D6C7B", "title": None, "orient": "top", "symbolSize": 90, "labelFont": FONT},
                   "text": {"color": "#142334", "fontSize": 12.5, "font": FONT}},
        **spec,
    }, width="stretch", theme=None)
