"""Small HTML builders and the shared chart grammar. Presentation only.

Builders return escaped HTML strings so pages can compose them; html() renders.
Every dynamic value passes through esc(). Keep markup on one line: Markdown
treats indented lines as code blocks.
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

import streamlit as st

CSS_PATH = Path(__file__).with_name("theme.css")
TERM_COLORS = {"lateness": "#4ED9E6", "defect": "#A391FF", "fairness": "#23C9A7", "robustness": "#F4BB55", "cost": "#6488FF"}
OURS, HEURISTIC, BASE, MUTED = "#4ED9E6", "#7F9CFF", "#5E6F84", "#8D9DB0"


def esc(value) -> str:
    return escape("" if value is None else str(value))


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_css() -> None:
    html("<style>" + CSS_PATH.read_text(encoding="utf-8") + "</style>")


def pill(text: str, tone: str = "info", *, soft: bool = False) -> str:
    return f'<span class="pill {tone}{" soft" if soft else ""}">{esc(text)}</span>'


def chip(label: str, value: str | None = None, dot: str | None = None) -> str:
    lead = f'<span class="dot {dot}"></span>' if dot else ""
    body = f"<b>{esc(value)}</b> {esc(label)}" if value is not None else esc(label)
    return f'<span class="chip">{lead}{body}</span>'


def page_head(eyebrow: str, title: str, lede: str = "", right: str = "") -> None:
    html(f'<div class="page-head"><div><div class="eyebrow">{esc(eyebrow)}</div><div class="page-title">{esc(title)}</div>'
         + (f'<div class="page-lede">{esc(lede)}</div>' if lede else "") + f'</div>{right}</div>')


def section(title: str, note: str = "") -> None:
    html(f'<div class="section-title">{esc(title)}</div>' + (f'<div class="section-note">{esc(note)}</div>' if note else ""))


def banner(title: str, text: str, tone: str = "info") -> str:
    return f'<div class="banner {tone}" role="status"><div><strong>{esc(title)}</strong>{esc(text)}</div></div>'


def kpi(label: str, value: str, comparison: str = "", badge: str = "") -> str:
    return (f'<div class="kpi"><small>{esc(label)}</small><strong>{esc(value)}</strong>'
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


def json_block(value, *, height: int | None = None) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False)
    st.code(text, language="json", wrap_lines=True, height=height)


# Charts ---------------------------------------------------------------------

AXIS = {"labelFontSize": 13, "titleFontSize": 13, "titleFontWeight": 500, "labelColor": "#B4C0CD",
        "titleColor": "#8D9DB0", "gridColor": "rgba(127,156,255,0.10)", "domain": False, "tickColor": "rgba(127,156,255,0.18)",
        "labelFont": "Inter, -apple-system, Segoe UI, sans-serif", "titleFont": "Inter, -apple-system, Segoe UI, sans-serif"}


def chart(data, spec: dict, *, height: int = 300) -> None:
    """Dark, transparent Vega-Lite chart; values stay exact in tooltips."""
    st.vega_lite_chart(data, {
        "height": height, "background": "transparent", "padding": {"left": 4, "right": 12, "top": 8, "bottom": 4},
        "config": {"view": {"stroke": None}, "axis": AXIS,
                   "legend": {"labelFontSize": 13, "labelColor": "#B4C0CD", "title": None, "orient": "bottom", "symbolSize": 90},
                   "text": {"color": "#B4C0CD", "fontSize": 12.5, "font": "Inter, -apple-system, Segoe UI, sans-serif"},
                   "title": {"color": "#F4F7FB"}},
        **spec,
    }, width="stretch", theme=None)


def score_bars(breakdown: list[dict], chosen_id: str | None, terms, labels, note: str = "") -> str:
    """Stacked weighted-term bars; widths are relative to the largest score shown."""
    top = max((item["score"] for item in breakdown), default=0) or 1
    rows = []
    for item in breakdown:
        segs = "".join(f'<span class="term-{p["term"]}" style="width:{p["contribution"] / top * 100:.2f}%" '
                       f'title="{esc(p["label"])}: {p["contribution"]:.6f}"></span>' for p in item["parts"] if p["contribution"] > 0)
        cls = " chosen" if item["workshop_id"] == chosen_id else ""
        rows.append(f'<div class="sb-row{cls}"><span class="nm">{esc(item["name"])}</span><div class="sb-track">{segs}</div>'
                    f'<span class="val">{item["score"]:.5f}</span></div>')
    active = {p["term"] for item in breakdown for p in item["parts"] if p["active"]}
    legend = "".join(f'<span><i class="term-{t}"></i>{esc(labels[t])}</span>' for t in terms if t in active)
    return (f'<div class="card"><div class="sb">{"".join(rows)}</div><div class="legend" style="margin-top:12px">{legend}</div>'
            + (f'<div class="section-note" style="margin-top:8px">{esc(note)}</div>' if note else "") + "</div>")
