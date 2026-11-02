"""Guardrail check: the Sprint 3 guards, before against after, on the same model reply.

Every comparison feeds one model reply through the post-checks twice: with the
guards off (exactly the Sprint 2 code; tests/test_guardrails.py proves it on all
62 recorded replies) and with them on. So a difference on this page is caused by
the guards alone, never by the model answering differently.

Recorded sets replay saved replies and cost nothing. A message typed here is
read once by the live model, unless it matches a recorded message.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

import agent
import guardrails
import intake
import rehearsal
from desk import TODAY
from objectives import PRESETS
from ui.components import banner, esc, html, metric_tile, status_pill, table

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "eval") not in sys.path:
    sys.path.insert(0, str(ROOT / "eval"))

# Recorded sets: requests, labels, and the audit whose model replies are replayed.
SETS = {
    "redteam": ("Red-team, 16", "data/redteam_requests.txt", "eval/redteam/labels.csv", "eval/redteam/before/inbox_audit.json"),
    "dev": ("Supplied inbox, 30", "data/dispatch_requests.txt", "eval/labels_v2.csv", "eval/guardrails_v2/sonnet_dev_before/inbox_audit.json"),
    "heldout": ("Held-out, 16", "data/heldout_requests.txt", "eval/labels_heldout_v2.csv", "eval/guardrails_v2/sonnet_heldout_before/inbox_audit.json"),
}
GUARD_TEXT = {
    "message_length": "Too long to read safely, so the model was not called",
    "order_reference": "No order, customer or product in the message",
    "several_orders": "More than one order in one message",
    "order_id_format": "Order ID written another way, read in its standard form",
    "order_id_exists": "Unknown order ID one typing slip from an open order",
    "workshop_name": "Misspelt workshop name with one clear match",
    "grounding": "A value the model returned is not in the message, so it was dropped",
    "units": "Dozens converted to pieces by Python",
}
BEHAVIOURS = ["allocate", "clarify", "refuse", "decline"]
EXAMPLES = ["asdf ok?? lol", "ord 041, 600pcs beanies for HK, rtn by 21/4", "Send ORD-0455 out today please, due Apr 12",
            "ORD-041 and ORD-045 both need to go out today", "ORD-073 hoodies due Apr 20, give it to Nimbel Needle",
            "ORD-008 50 dz polos for Loom & Leaf, ex-fty Apr 9"]
CSS = """<style>
.gc-case{display:grid;grid-template-columns:1fr 1fr;gap:0.9333rem;margin:0.5333rem 0 0.2rem}
@media (max-width:900px){.gc-case{grid-template-columns:1fr}}
.gc-side{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:0.9333rem 1.0667rem;box-shadow:var(--shadow-sm);min-width:0}
.gc-side.after{border-color:rgba(42,119,232,.45)}
.gc-side h4{margin:0 0 0.5333rem;font-size:0.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--text-muted);display:flex;gap:0.5333rem;align-items:center;flex-wrap:wrap}
.gc-reply{font-size:0.9667rem;line-height:1.55;color:var(--text);white-space:pre-wrap;overflow-wrap:anywhere}
.gc-msg{font-family:var(--mono);font-size:0.9rem;background:var(--sunken);border-radius:var(--radius-sm);padding:0.6667rem 0.8rem;overflow-wrap:anywhere;color:var(--text)}
.gc-exp{font-size:0.9333rem;color:var(--text-muted);margin:0.4rem 0 0}
.gc-exp b{color:var(--text)}
.gc-guards{margin:0.6667rem 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:0.3333rem}
.gc-guards li{font-size:0.8667rem;color:var(--cobalt-ink);background:rgba(42,119,232,.07);border-radius:var(--radius-sm);padding:0.3333rem 0.6rem}
.gc-guards li.none{color:var(--text-faint);background:var(--sunken)}
.gc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:0.8rem;margin:0.8rem 0}
.gc-yes{color:var(--green-ink);font-weight:600}.gc-no{color:var(--coral-ink);font-weight:600}.gc-na{color:var(--text-faint)}
.gc-read{display:flex;flex-wrap:wrap;gap:0.4rem;margin-top:0.5333rem}
</style>"""


# Running -----------------------------------------------------------------------------

def _handle(message, reply, guards_on, orders, workshops, answers=None):
    queues = {w: s.queue0 for w, s in workshops.items()}
    with intake.guards(guards_on), intake.extraction_source(lambda prompt, text: reply), intake.dispatcher_answers(answers):
        return agent.handle(message, TODAY, orders.copy(), deepcopy(workshops), queues, PRESETS["lateness"])


def compare(message, reply, orders, workshops):
    """(before, after) AgentResponses for one model reply. A message the guards stop early needs no reply."""
    return _handle(message, reply, False, orders, workshops), _handle(message, reply, True, orders, workshops)


def fired(response) -> list[str]:
    return [GUARD_TEXT[c["rule"]] for c in response.parsed_request.post_checks
            if c["rule"] in GUARD_TEXT and not (c["rule"] == "order_id_exists" and c["result"] != "close_match")]


class Replay:
    """Recorded model replies in the shape run_inbox.run_evaluation expects of its cache."""
    fixture, last_key = None, None

    def __init__(self, replies):
        self.replies = replies

    def __call__(self, prompt, message):
        return self.replies[message]


@st.cache_data(show_spinner=False)
def run_set(key: str, code_stamp: float) -> dict:
    """Replay a recorded set with guards off and on, scored by the inbox evaluator. code_stamp busts the cache on edits."""
    import run_inbox
    import run_redteam
    from simulate import load_workshops

    _, requests, labels_path, audit_path = SETS[key]
    messages = run_inbox.inbox_messages(ROOT / requests)
    labels = run_inbox.read_labels(ROOT / labels_path, messages)
    replies = {d["raw_message"]: intake.LLMReply(d["response"]["parsed_request"]["raw_llm_response"],
                                                 d["response"]["parsed_request"]["llm_metadata"])
               for d in json.loads((ROOT / audit_path).read_text())["requests"]}
    orders, workshops = pd.read_csv(ROOT / "data/orders.csv"), load_workshops()
    out = {}
    for name, on in (("before", False), ("after", True)):
        with intake.guards(on):
            frame, details = run_inbox.run_evaluation(messages, labels, orders, workshops, Replay(replies))
        out[name] = {"frame": frame.to_dict("records"), "replies": {d["request_id"]: d["response"]["explanation_text"] for d in details},
                     "guards": {d["request_id"]: [GUARD_TEXT[c["rule"]] for c in d["response"]["parsed_request"]["post_checks"]
                                                  if c["rule"] in GUARD_TEXT and not (c["rule"] == "order_id_exists" and c["result"] != "close_match")]
                                for d in details}}
        if key == "redteam":
            checks = pd.read_csv(ROOT / "eval/redteam/checks.csv", dtype=str).to_dict("records")
            by_id = {d["request_id"]: d["response"] for d in details}
            out[name]["checks"] = [{**c, "passed": run_redteam.check(c["check"], c["value"], by_id[c["request_id"]])[0]} for c in checks]
    out["messages"], out["labels"] = messages, labels
    return out


def code_stamp() -> float:
    return max(p.stat().st_mtime for p in [ROOT / "src/guardrails.py", ROOT / "src/intake.py", ROOT / "src/agent.py"])


# Drawing -----------------------------------------------------------------------------

def mark(value) -> str:
    if value in (True, "True"):
        return '<span class="gc-yes">Yes</span>'
    if value in (False, "False"):
        return '<span class="gc-no">No</span>'
    return '<span class="gc-na">n/a</span>'


def side(title, behaviour, reply, guards, expected=None, after=False, checks=None) -> str:
    verdict = ""
    if expected:
        verdict = status_pill("Right behaviour", "ok") if behaviour == expected else status_pill("Wrong behaviour", "risk")
    if checks:
        passed = sum(checks)
        verdict += " " + status_pill(f"Extra checks {passed}/{len(checks)}", "ok" if passed == len(checks) else "risk")
    items = "".join(f"<li>{esc(g)}</li>" for g in guards) or '<li class="none">No Sprint 3 guard changed this request</li>'
    return (f'<div class="gc-side{" after" if after else ""}"><h4>{esc(title)} {status_pill(behaviour, "info")} {verdict}</h4>'
            f'<div class="gc-reply">{esc(reply)}</div>' + (f'<ul class="gc-guards">{items}</ul>' if after else "") + "</div>")


def count(rows, column) -> str:
    scored = [r[column] for r in rows if r[column] in (True, False)]
    return f"{sum(scored)}/{len(scored)}"


def scoreboard(results):
    tiles = []
    red, dev, held = results["redteam"], results["dev"], results["heldout"]
    tiles.append(metric_tile("Red-team: right behaviour", f'{count(red["before"]["frame"], "behaviour_correct")} → {count(red["after"]["frame"], "behaviour_correct")}',
                             "Hard messages. Built against, so not a clean test."))
    tiles.append(metric_tile("Red-team: extra checks", f'{sum(c["passed"] for c in red["before"]["checks"])}/{len(red["before"]["checks"])} → '
                             f'{sum(c["passed"] for c in red["after"]["checks"])}/{len(red["after"]["checks"])}', "No order dump, both orders named, quantity kept"))
    for label, res in (("Supplied 30: right decision", dev), ("Held-out 16: right decision", held)):
        changed = [b["request_id"] for b, a in zip(res["before"]["frame"], res["after"]["frame"]) if res["before"]["replies"][b["request_id"]] != res["after"]["replies"][a["request_id"]]]
        tiles.append(metric_tile(label, f'{count(res["before"]["frame"], "decision_correct")} → {count(res["after"]["frame"], "decision_correct")}',
                                 f'Replies changed: {", ".join(changed) if changed else "none"}'))
    html(f'<div class="gc-kpis">{"".join(tiles)}</div>')


def case_browser(res, key, note):
    labels, messages = res["labels"], res["messages"]
    before = {r["request_id"]: r for r in res["before"]["frame"]}
    after = {r["request_id"]: r for r in res["after"]["frame"]}
    ids = list(messages)
    changed = [i for i in ids if res["before"]["replies"][i] != res["after"]["replies"][i]]
    show = st.radio("Show", ["Changed by the guards", "All"], horizontal=True, key=f"gc_show_{key}") if key != "redteam" else "All"
    ids = changed if show == "Changed by the guards" else ids
    if not ids:
        html(banner("No reply changed.", " With the guards on, every reply in this set is word for word the same as before.", "info"))
        return
    rows = []
    for i in ids:
        text = messages[i].split(": ", 1)[-1]
        rows.append([f"<b>{esc(i)}</b>", esc(labels[i].get("issue") or ""), esc(text[:48] + ("..." if len(text) > 48 else "")),
                     esc(labels[i]["expected_behaviour"]), esc(before[i]["actual_behaviour"]), mark(before[i]["behaviour_correct"]),
                     esc(after[i]["actual_behaviour"]), mark(after[i]["behaviour_correct"]), mark(after[i]["decision_correct"])])
    html(table(["ID", "Issue", "Message", "Expected", "Before", "Right", "After", "Right", "Right decision"], rows, max_height=420))
    pick = st.selectbox("Open a request", ids, key=f"gc_pick_{key}",
                        format_func=lambda i: f"{i} · {labels[i].get('issue') or ''} · {messages[i].split(': ', 1)[-1][:60]}")
    label = labels[pick]
    extra, before_checks, after_checks = "", None, None
    if key == "redteam":
        mine = [c for c in res["after"]["checks"] if c["request_id"] == pick]
        old = {(c["check"], c["value"]): c["passed"] for c in res["before"]["checks"] if c["request_id"] == pick}
        before_checks, after_checks = [old[(c["check"], c["value"])] for c in mine], [c["passed"] for c in mine]
        if mine:
            extra = "<br>Extra checks: " + "; ".join(f'{esc(c["check"].replace("_", " "))} {esc(c["value"])}: before {mark(old[(c["check"], c["value"])])}, after {mark(c["passed"])}' for c in mine)
    html(f'<div class="gc-msg">{esc(messages[pick])}</div>'
         f'<p class="gc-exp">Expected: <b>{esc(label["expected_behaviour"])}</b>'
         + (f' · order <b>{esc(label["expected_order_id"])}</b>' if label["expected_order_id"] else "")
         + (f' · {esc(label["expected_pieces"])} pieces' if label["expected_pieces"] else "")
         + (f' · due {esc(label["expected_due"])}' if label["expected_due"] else "")
         + f'. {esc(label["notes"])}{extra}</p>'
         f'<div class="gc-case">{side("Before", before[pick]["actual_behaviour"], res["before"]["replies"][pick], [], label["expected_behaviour"], checks=before_checks)}'
         f'{side("After", after[pick]["actual_behaviour"], res["after"]["replies"][pick], res["after"]["guards"][pick], label["expected_behaviour"], after=True, checks=after_checks)}</div>')
    if note:
        html(f'<div class="meta" style="margin-top:0.4rem">{esc(note)}</div>')


def readings(text) -> str:
    """What the guards read from the text by themselves, with no model involved."""
    refs = guardrails.order_refs(text)
    date = intake._calendar_date(text, TODAY)
    facts = [("Characters", f"{len(text):,} of {guardrails.MAX_MESSAGE_CHARS:,}"),
             ("Order references", ", ".join(refs) or "none"), ("Dozens", f"{guardrails.dozen_pieces(text):,} pieces" if guardrails.dozen_pieces(text) else "none"),
             ("Single date", date.isoformat() if date else "none or more than one")]
    return '<div class="gc-read">' + "".join(f'<span class="fact">{esc(k)} <b>{esc(v)}</b></span>' for k, v in facts) + "</div>"


def try_message(orders, workshops, recorded):
    state = st.session_state
    st.caption("Examples")
    cols = st.columns(3)
    for n, example in enumerate(EXAMPLES):
        if cols[n % 3].button(example[:38] + ("..." if len(example) > 38 else ""), key=f"gc_ex_{n}", width="stretch"):
            state["gc_text"] = example
    text = st.text_area("Message, as it would arrive in the chat", key="gc_text", height=90,
                        placeholder="For example: ORD45 vests for Cotton Club, due Apr 9")
    left, right = st.columns([2, 1])
    expected = left.radio("Expected behaviour (optional)", ["Not set", *BEHAVIOURS], horizontal=True, key="gc_expected")
    live = rehearsal.live_status()
    go = right.button("Check before and after", type="primary", width="stretch", disabled=not text.strip())
    if text.strip():
        html(readings(text))
    if not go:
        return
    line = text.strip() if text.strip().startswith("R") and "[" in text[:8] else f"R999 [12:00] Tester: {text.strip()}"
    reply = recorded.get(line) or recorded.get(next((m for m in recorded if m.split(": ", 1)[-1] == text.strip()), ""), None)
    source = "a recorded reply (no API call)"
    if reply is None and len(line) <= guardrails.MAX_MESSAGE_CHARS:
        if not live["ready"]:
            html(banner("The live model is not configured.", " Typed messages need one model call. Recorded requests above still work.", "warn"))
            return
        cache = state.setdefault("gc_replies", {})
        if line not in cache:
            with st.spinner("Reading the message once with the live model"):
                prompt = intake.build_system_prompt(TODAY, orders, workshops)
                cache[line] = intake._call_llm(prompt, line)
        reply, source = cache[line], f"one live call to {live['model']}"
    elif reply is None:
        reply, source = intake.LLMReply("{}", {}), "no model call"   # The length guard answers before any reply is read.
    try:
        before, after = compare(line, reply, orders, workshops)
    except intake.IntakeError as error:
        html(banner("The model reply could not be read.", " " + str(error), "risk"))
        return
    goal = None if expected == "Not set" else expected
    html(f'<div class="meta">Read with {esc(source)}. The same reply went through the checks twice.</div>'
         f'<div class="gc-case">{side("Before", before.parsed_request.behaviour, before.explanation_text, [], goal)}'
         f'{side("After", after.parsed_request.behaviour, after.explanation_text, fired(after), goal, after=True)}</div>')


def render(workshops, embedded=False):
    if not embedded:
        html(CSS)
    sub = ('<div class="home-sub">Each request goes through the checks twice with the same model reply: once as in Sprint 2, once with the new '
           'guards. Any difference is the guards, not the model. Recorded sets replay saved replies and cost nothing.</div>')
    if embedded:
        html('<div class="title">Guardrails</div>' + sub)
    else:
        html('<div class="kicker"><span>Guardrail check</span></div>'
             '<div class="home-title" style="margin-top:0.8rem">What the Sprint 3 guards changed</div>' + sub)
    orders = pd.read_csv(ROOT / "data/orders.csv")
    if st.button("Re-run all checks", icon=":material/refresh:"):
        run_set.clear()
    with st.spinner("Replaying 62 recorded requests twice"):
        results = {key: run_set(key, code_stamp()) for key in SETS}
    scoreboard(results)
    tabs = st.tabs(["Red-team, 16", "Supplied inbox, 30", "Held-out, 16", "Try a message"])
    with tabs[0]:
        case_browser(results["redteam"], "redteam", "Development set: the guards were built against these 16 failures. "
                     "The clean test is the Round 2 held-out set, written by a teammate and run once.")
    with tabs[1]:
        case_browser(results["dev"], "dev", "R19 is an intended change: it names no order, so it now asks for the order ID instead of "
                     "listing all 34 open orders. The evaluator's frozen rule expects the list, so we report it as a miss.")
    with tabs[2]:
        case_browser(results["heldout"], "heldout", "")
    with tabs[3]:
        recorded = {}
        for _, (_, _, _, audit) in SETS.items():
            for d in json.loads((ROOT / audit).read_text())["requests"]:
                p = d["response"]["parsed_request"]
                recorded[d["raw_message"]] = intake.LLMReply(p["raw_llm_response"], p["llm_metadata"])
        try_message(orders, workshops, recorded)
