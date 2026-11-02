"""QA checklist: each Sprint 3 change, how it was before, and how to verify it now.

Per feature: the screen before the change (a screenshot taken on 30 Oct 2026),
automated checks that run here on scratch files with test extractions (no API
call, no real log touched), and manual cases with the expected result. A manual
verdict (Pass or Fail) is appended to records/qa_checklist.jsonl with who and
when, so the team shares one checklist and nothing is overwritten.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile

import streamlit as st

from allocator import Allocator
import batches
import desk
import intake
from objectives import PRESETS
import records
from ui import explain, guardrail_check
from ui.components import esc, html, status_pill

ROOT = Path(__file__).resolve().parents[2]
QA_LOG = ROOT / "records" / "qa_checklist.jsonl"
BEFORE = "app/static/qa"

FEATURES = {
    "today": {
        "title": "Today board", "page": "Today", "before": "before_home.jpg",
        "was": "The app opened on Dispatch: an inbox and an empty request box. Nothing showed what was due back, overdue or late.",
        "now": "A Today page first in the sidebar: five counters and three lanes (needs a decision, due back today or overdue, back after the customer date).",
        "cases": [
            ("Open Today from the sidebar.", "Five counters (Overdue, Due back today, Back after the customer date, On track, Received) and three lanes."),
            ("In Needs a decision, click Open on a request.", "Dispatch opens with that request selected in the inbox."),
            ("Set Board date to a day after one batch's return date.", "That batch moves to Due back today or overdue with an Overdue pill; the Overdue counter goes up."),
            ("Click Mark received on that batch.", "It leaves the lane and the Received counter goes up by one."),
            ("Go back to Dispatch.", "The scenario date there is unchanged (01/04/2026): the board date only changes the Today view."),
        ]},
    "timeline": {
        "title": "Due-back timeline", "page": "Today", "before": "before_timeline.jpg",
        "was": "Workshop queues showed how many days of work each workshop has, and chips for confirmed batches, but no dates on a timeline and no way to record an arrival.",
        "now": "Under the Today board: one row per workshop, a bar per batch from sent to booked return, the customer date as a diamond, the board date as a dashed line, and Mark received.",
        "cases": [
            ("Scroll to Due-back timeline on Today.", "One row per workshop with work out; each bar starts on the day sent and ends on the booked return date."),
            ("Hover a bar.", "A tooltip with order, pieces, sent, back, customer date and status."),
            ("Move Board date past the end of a bar.", "The bar turns red (overdue) and the dashed line moves to the new date."),
            ("Choose that batch in Mark a batch received and click Mark received.", "The bar disappears; turn on Show received batches and it returns faded green."),
            ("Click Undo that arrival.", "The bar is back in its previous colour. The arrival log keeps both lines."),
        ]},
    "runner_up": {
        "title": "Pick against runner-up", "page": "Dispatch", "before": "before_runner_up.jpg",
        "was": "The recommendation named one workshop with one bullet comparing it to the next best. The other option's date, cost and defect rate were not visible next to it.",
        "now": "A card under the recommendation: the pick and the next best side by side (back by, spare, total time, cost per piece, total cost, defect risk), better values in green, the deciding rows marked.",
        "cases": [
            ("On Dispatch, open R09 and click Evaluate request.", "A Pick against runner-up card appears under the recommendation, with Recommended and Next best columns."),
            ("Read the sentence above the table.", "It names the same reason as the rows marked Decided here."),
            ("Compare each row.", "The better value in each row is green; Decided here rows are shaded."),
            ("Change Objective to Lowest defect and evaluate again.", "The Decided here mark moves to Defect risk when that is what separates the two."),
        ]},
    "override": {
        "title": "Override reasons", "page": "Dispatch", "before": "before_override.jpg",
        "was": "The dispatcher could accept the pick, take a split or escalate. There was no way to send the batch to a different workshop, and no reason was ever recorded.",
        "now": "Send to a different workshop: choose another permitted workshop (with its date, spare and cost), tap a reason, add a note if needed. The engine's pick and the reason go to the audit log.",
        "cases": [
            ("Evaluate R09 and click Send to a different workshop.", "A list of the other permitted workshops with back date, spare and cost, and five reason chips."),
            ("Leave the reason empty, then pick Other with no note.", "The send button stays disabled in both cases."),
            ("Pick a workshop, tap Quality concern, click Send to ... instead.", "The card says Sent to that workshop, your choice over the engine's pick, with the reason."),
            ("Open Workshop queues.", "The batch is booked under the workshop you chose, not the engine's pick."),
            ("Open Audit Trail and the newest record.", "Kind is Dispatcher override; the record shows the engine's pick, your choice and the reason."),
            ("Open Today.", "The batch is on the timeline under the workshop you chose."),
        ]},
}


# Shared verdicts --------------------------------------------------------------------

def verdicts() -> dict[str, dict]:
    try:
        lines = QA_LOG.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    latest = {}
    for line in lines:
        if line.strip():
            event = json.loads(line)
            latest[event["case"]] = event
    return latest


def save_verdict(case: str, widget_key: str):
    value = st.session_state.get(widget_key)
    QA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with QA_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"case": case, "verdict": value, "by": st.session_state.get("qa_tester") or "Team",
                                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")


# Automated checks (scratch files, test extractions) ---------------------------------

def _preview(rid):
    data = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    orders, shops, messages = desk.load_inputs()
    message = next(m for m in messages if m.startswith(rid))
    reply = intake.LLMReply(json.dumps({**data["defaults"], **data["requests"][rid]}), {"model": "test"})
    queues = {wid: w.queue0 for wid, w in shops.items()}
    with intake.extraction_source(lambda prompt, text: reply):
        preview = desk.make_preview(message, desk.TODAY, PRESETS["lateness"], orders, shops, queues, Allocator(PRESETS["lateness"]))
    return preview, shops, queues


@st.cache_data(show_spinner=False)
def automated(stamp: float) -> dict[str, list[tuple[str, bool, str]]]:
    out = {k: [] for k in FEATURES}
    data = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    fixture_ok = data["dispatch_requests_sha256"] == hashlib.sha256((ROOT / "data/dispatch_requests.txt").read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        log, arrivals = Path(tmp) / "decisions.jsonl", Path(tmp) / "received.jsonl"
        append = lambda response: records.append(response, log)   # noqa: E731

        # Pick against runner-up: every allocation with two or more permitted workshops gets a comparison.
        compared = total = consistent = 0
        for rid in sorted(data["requests"]):
            record = _preview(rid)[0].response.decision_record
            chosen = explain.chosen_row(record)
            if chosen is None or len(explain.selection_order(record)) < 2:
                continue
            total += 1
            other = explain.runner_up(record)
            rows = explain.deciding_metrics(record, chosen, other) if other else []
            compared += bool(other and other["workshop_id"] != chosen["workshop_id"] and rows)
            consistent += any(r["better"] is True for r in rows)
        out["runner_up"] += [(f"Every allocation with two or more permitted workshops has a runner-up and a deciding row", compared == total, f"{compared} of {total}"),
                             ("At least one deciding row favours the pick", consistent == total, f"{consistent} of {total}")]

        # Override.
        preview, shops, queues = _preview("R09")
        engine = preview.response.decision_record["chosen_workshop"]
        target = next(c for c in preview.response.decision_record["candidates"] if c["workshop_id"] != engine)
        try:
            desk.confirm_override(preview, preview.signature, {}, target["workshop_id"], "", "", shops, queues, Allocator(PRESETS["lateness"]), append=append)
            blocked = False
        except ValueError:
            blocked = True
        row, nq, _ = desk.confirm_override(preview, preview.signature, {}, target["workshop_id"], "Quality concern", "", shops, queues,
                                           Allocator(PRESETS["lateness"]), append=append)
        ov = row["decision_record"]["constraints_applied"]["override"]
        replayed, _, _ = desk.queues_from_log(shops, log)
        out["override"] += [("An override without a reason is refused", blocked, "ValueError raised" if blocked else "accepted"),
                            ("The record keeps the engine's pick, the chosen workshop and the reason",
                             ov["engine_pick"] == engine and ov["chosen"] == target["workshop_id"] and ov["reason"] == "Quality concern",
                             f"{engine} to {target['workshop_id']}"),
                            ("The explanation still passes the number check", row["faithfulness"]["passed"], ""),
                            ("Replaying the log books the chosen workshop, not the engine's pick",
                             abs(replayed[target["workshop_id"]] - nq[target["workshop_id"]]) < 1e-9 and replayed[engine] == queues[engine], "")]

        # Tracking and the Today board (reads the same scratch log).
        [b] = batches.out_batches(log, arrivals)
        before, on, after = b["back"] - timedelta(days=1), b["back"], b["back"] + timedelta(days=1)
        statuses = [batches.status(b, d) for d in (before, on, after)]
        batches.record_arrival(b["key"], by="QA", scenario_date=after, path=arrivals)
        received = batches.status(batches.out_batches(log, arrivals)[0], after)
        batches.record_arrival(b["key"], by="QA", scenario_date=after, path=arrivals, undo=True)
        undone = batches.status(batches.out_batches(log, arrivals)[0], after)
        out["timeline"] += [("A confirmed batch is tracked against its booked return date", b["back"] == date.fromisoformat(target["eta_date"]), str(b["back"])),
                            ("The day before, on, and after the return date read as on track, due today, overdue",
                             statuses[1:] == ["due_today", "overdue"] and statuses[0] in ("on_track", "at_risk"), ", ".join(statuses)),
                            ("Mark received, then undo, restores the previous status", received == "received" and undone == "overdue", f"{received}, then {undone}"),
                            ("Arrivals are appended, never edited", len(arrivals.read_text().splitlines()) == 2, "2 lines")]
        lanes_ok = all(batches.status(x, after) in batches.STATUSES for x in batches.out_batches(log, arrivals))
        out["today"] += [("Every batch falls in exactly one board status", lanes_ok, ""),
                         ("Test extractions match the supplied inbox", fixture_ok, "")]
    return out


# Drawing ----------------------------------------------------------------------------

def feature_tab(key: str, checks, saved):
    f = FEATURES[key]
    left, right = st.columns([1, 1], gap="large")
    with left:
        html(f'<div class="title" style="font-size:1rem">Before</div><div class="meta" style="margin-bottom:0.4rem">{esc(f["was"])}</div>'
             f'<img src="{BEFORE}/{f["before"]}" alt="The screen before this change" style="width:100%;border-radius:0.8rem;border:1px solid var(--border)">')
    with right:
        html(f'<div class="title" style="font-size:1rem">Now</div><div class="meta" style="margin-bottom:0.6rem">{esc(f["now"])}</div>')
        st.button(f"Open {f['page']}", key=f"qa_open_{key}", icon=":material/open_in_new:",
                  on_click=lambda p=f["page"]: st.session_state.update(desk_page=p))
        passed = sum(ok for _, ok, _ in checks)
        html(f'<div class="title" style="font-size:1rem;margin-top:0.8rem">Automated checks {status_pill(f"{passed} of {len(checks)} pass", "ok" if passed == len(checks) else "risk")}</div>'
             '<ul class="gc-guards">' + "".join(
                 f'<li style="{"" if ok else "color:var(--coral-ink);background:rgba(245,111,103,.08)"}">{"Pass" if ok else "Fail"}: {esc(name)}'
                 f'{(" (" + esc(detail) + ")") if detail else ""}</li>' for name, ok, detail in checks) + "</ul>")
    html('<div class="title" style="font-size:1rem;margin-top:1.0667rem">Manual cases</div>'
         '<div class="meta">Do each step in the app and compare with the expected result, then mark it. Verdicts are shared with the team.</div>')
    for n, (step, expected) in enumerate(f["cases"], 1):
        case = f"{key}.{n}"
        mark = saved.get(case)
        cols = st.columns([0.06, 0.62, 0.32], vertical_alignment="center")
        cols[0].markdown(f"**{n}**")
        cols[1].markdown(f"{step}  \n:gray[Expected: {expected}]" + (f"  \n:gray[Last marked {mark['verdict']} by {mark['by']}, {mark['at'][:10]}]" if mark and mark.get("verdict") else ""))
        widget = f"qa_{case}"
        if widget not in st.session_state and mark:
            st.session_state[widget] = mark.get("verdict")
        cols[2].segmented_control("Verdict", ["Pass", "Fail"], key=widget, label_visibility="collapsed",
                                  on_change=save_verdict, args=(case, widget))


def render(workshops):
    html(guardrail_check.CSS)
    html('<div class="kicker"><span>QA checklist</span></div>'
         '<div class="home-title" style="margin-top:0.8rem">Check every Sprint 3 change</div>'
         '<div class="home-sub">For each change: the screen before it, automated checks that run here without any API call, and steps to try '
         'yourself with the expected result. Mark each step Pass or Fail; the team sees the same verdicts.</div>')
    saved = verdicts()
    with st.spinner("Running the automated checks"):
        auto = automated(guardrail_check.code_stamp())
    total_cases = sum(len(f["cases"]) for f in FEATURES.values())
    marked = [v for k, v in saved.items() if k.split(".")[0] in FEATURES and v.get("verdict")]
    auto_pass = sum(ok for checks in auto.values() for _, ok, _ in checks)
    auto_total = sum(len(checks) for checks in auto.values())
    top = st.columns([1, 1, 1, 1.3], vertical_alignment="bottom")
    tiles = [("Automated checks", f"{auto_pass}/{auto_total}"), ("Manual cases passed", f"{sum(v['verdict'] == 'Pass' for v in marked)}/{total_cases}"),
             ("Manual cases failed", str(sum(v["verdict"] == "Fail" for v in marked)))]
    for col, (label, value) in zip(top, tiles):
        col.markdown(f'<div class="kpi"><small>{esc(label)}</small><strong>{esc(value)}</strong></div>', unsafe_allow_html=True)
    top[3].text_input("Your name for verdicts", key="qa_tester", placeholder="For example: Apurwa")
    tabs = st.tabs(["Guardrails", *[f["title"] for f in FEATURES.values()]])
    with tabs[0]:
        guardrail_check.render(workshops, embedded=True)
    for tab, key in zip(tabs[1:], FEATURES):
        with tab:
            feature_tab(key, auto[key], saved)
