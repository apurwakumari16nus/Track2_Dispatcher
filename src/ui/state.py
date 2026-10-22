"""Persistent page state, kept apart from Streamlit widget state.

Why: Streamlit deletes a widget's session-state entry at the end of any run in
which that widget is not drawn, which is every run spent on another page. A
segmented control or pills drawn again without a default then reads the
missing frontend value as None. That is how the Network category and the Audit
log selection became None (V10 crash reports A and B).

Rule: a value the app relies on (the batch category, the audit log being
viewed, the objective, the request text) lives under its own session key, for
example "net_category". It is never a widget key, so Streamlit never removes it.
The widget is drawn with a mirror key, "_w_net_category", refreshed from the
domain value before every render. A user's change is copied back only if it is
a valid value; anything else (None, a stale option) leaves the domain value as
it was. Code reads and writes the domain key only.

Lifecycle, per run:
  1. bind() validates the domain value. Missing or invalid becomes the
     documented fallback (which may be None where "not chosen" is a real state).
  2. The mirror key is set to the domain value, then the widget is drawn.
  3. On a user change, sync() runs before the script: it copies a valid widget
     value to the domain key, then calls the page's own on_change.
"""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

WIDGET_PREFIX = "_w_"


def mirror(key: str) -> str:
    return WIDGET_PREFIX + key


def bind(widget: Callable, label: str, options=None, *, key: str, fallback: Any = None,
         accept: Callable[[Any], bool] | None = None, allow_none: bool = False,
         on_change: Callable | None = None, on_change_args: tuple = (), slot: str = "", **kwargs):
    """Draw widget(label[, options], ...) bound to the domain value state[key]; return that value.

    accept(value) decides what is valid; by default a value must be one of options.
    allow_none lets the domain value be None (a real "nothing chosen yet" state),
    but a widget can never write None back.
    slot gives a second widget for the same domain value its own widget key, so two
    differently configured widgets (a composer and an edit popover) never share frontend state.
    """
    state = st.session_state
    valid = accept or (lambda value: value in options)

    def ok(value):
        try:
            return bool(valid(value))
        except Exception:
            return False

    if not ((allow_none and state.get(key) is None and key in state) or ok(state.get(key))):
        state[key] = fallback
    widget_key = mirror(key) + (f"__{slot}" if slot else "")
    state[widget_key] = state[key]

    def sync():
        value = state.get(widget_key)
        if value is not None and ok(value):
            state[key] = value
        if on_change:
            on_change(*on_change_args)

    args = (label,) if options is None else (label, options)
    widget(*args, key=widget_key, on_change=sync, **kwargs)
    return state[key]


def one_of(options) -> Callable[[Any], bool]:
    allowed = list(options)
    return lambda value: value in allowed


def subset_of(options) -> Callable[[Any], bool]:
    allowed = set(options)
    return lambda value: isinstance(value, list) and set(value) <= allowed


def text(value) -> bool:
    return isinstance(value, str)
