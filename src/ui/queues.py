"""Workshop queues: the shared workload, live.

Every workshop's queue is the 1 April snapshot plus every confirmed decision in
the audit log for the current mode, replayed with the engine's own queue tool
(desk.queues_from_log). Confirmations from the desk and from the group chat land
in the same log, so this page shows both. It re-reads the log every few seconds,
so a confirmation tapped in Telegram appears here without a reload.
"""

from __future__ import annotations

from datetime import timedelta
import math

import streamlit as st

import desk
import records
import rehearsal
from ui import explain
from ui.components import esc, html, icon

REFRESH_SECONDS = 5
CHANNELS = {"telegram": "Telegram", "desk": "Desk"}


def batches_by_workshop(path) -> tuple[dict, dict | None]:
    """Confirmed work per workshop from the log, oldest first, and the latest confirmation."""
    out, latest = {}, None
    for row in records.load(path):
        record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
        confirmation = record.get("constraints_applied", {}).get("confirmation", {})
        if not confirmation.get("confirmed"):
            continue
        split = (record.get("split_allocation") or {}).get("parts")
        chosen = next((c for c in record.get("candidates", []) if c["workshop_id"] == record.get("chosen_workshop")), None)
        parts = split or ([{"workshop_id": record.get("chosen_workshop"), "pieces": parsed.get("pieces"),
                            "eta_date": chosen["eta_date"] if chosen else None}] if record.get("chosen_workshop") else [])
        for part in parts:
            out.setdefault(part["workshop_id"], []).append({
                "order": parsed.get("order_id"), "pieces": part.get("pieces") or 0, "back": part.get("eta_date"),
                "channel": confirmation.get("channel") or "desk", "by": confirmation.get("confirmed_by"),
                "at": (row.get("timestamp") or "")[11:16], "split": bool(split)})
        latest = row
    return out, latest


def render(workshops):
    state = st.session_state
    source = state.get("desk_source", "live")
    log = desk.audit_log_name(source)
    html('<div class="kicker"><span>Workshop queues</span></div>'
         '<div class="home-title" style="margin-top:0.8rem">Who is busy, and until when</div>'
         f'<div class="home-sub">Each queue is the 1 April snapshot plus every decision confirmed in the {esc(log)} log, from the desk '
         f'and the group chat. Updates on its own every {REFRESH_SECONDS} seconds.</div>')
    st.fragment(board, run_every=REFRESH_SECONDS)(workshops, source)


def board(workshops, source):
    path = desk.audit_path(source)
    queues, _, confirmed = desk.queues_from_log(workshops, path)
    batches, latest = batches_by_workshop(path)
    if latest:
        confirmation = latest["decision_record"]["constraints_applied"]["confirmation"]
        who = f' by {confirmation["confirmed_by"]}' if confirmation.get("confirmed_by") else ""
        last = (f'Last change {latest["timestamp"][11:16]} UTC via {CHANNELS.get(confirmation.get("channel") or "desk", "Desk")}{who}: '
                f'{latest["parsed_request"].get("order_id") or "a request"}.')
    else:
        last = "No confirmed decisions yet: every queue is the 1 April snapshot."
    html(f'<div class="qb-sum">{icon("sync")}<span><b>{confirmed}</b> confirmed decision{"s" if confirmed != 1 else ""} · {esc(last)}</span></div>')
    longest = max(max(queues.values()), 7.0)
    rows = []
    for wid, w in sorted(workshops.items(), key=lambda kv: (kv[1].status != "ACTIVE", queues[kv[0]])):
        q, base = queues[wid], w.queue0
        added = q - base
        free = desk.TODAY + timedelta(days=math.ceil(q))
        state = ("Suspended" if w.status != "ACTIVE" else f"On trial, up to {w.max_batch:,} pieces" if w.max_batch else "Active")
        tone = "down" if w.status != "ACTIVE" else ("hot" if q >= 7 else "warm" if q >= 4 else "ok")
        chips = "".join(f'<span class="qb-chip {esc(b["channel"])}"><b>{esc(b["order"] or "")}</b> {int(b["pieces"]):,} pcs'
                        f'{" (split)" if b["split"] else ""} · back {esc(explain.short_date(b["back"]) if b["back"] else "n/a")}'
                        f' · {esc(CHANNELS.get(b["channel"], b["channel"]))}{(" · " + esc(b["by"])) if b["by"] else ""} {esc(b["at"])}</span>'
                        for b in batches.get(wid, []))
        rows.append(
            f'<div class="qb-row {tone}"><div class="qb-name"><b>{esc(w.name)}</b><small>{esc(wid)} · {esc(state)} · {w.capacity:,} a day</small></div>'
            f'<div class="qb-bar"><i class="base" style="width:{base / longest * 100:.1f}%"></i>'
            f'<i class="add" style="width:{max(added, 0) / longest * 100:.1f}%"></i></div>'
            f'<div class="qb-num"><b>{q:.1f} days</b><small>{("+" + format(added, ".1f") + " from confirmations") if added > 0.05 else "snapshot only"}</small></div>'
            f'<div class="qb-free"><small>Free from</small><b>{esc(explain.short_date(free.isoformat())) if w.status == "ACTIVE" else "Closed"}</b></div>'
            + (f'<div class="qb-chips">{chips}</div>' if chips else "") + "</div>")
    html('<div class="qb-legend"><span><i class="base"></i>Queue on the 1 April snapshot</span><span><i class="add"></i>Added by confirmed decisions</span>'
         '<span class="hint">Queue days are processing already booked; transport is not included.</span></div>'
         f'<div class="qb">{"".join(rows)}</div>')
    if rehearsal.SOURCES[source].rehearsal:
        html('<div class="meta" style="margin-top:0.5333rem">Rehearsal mode reads the rehearsal log. Switch to Live model in System '
             'details to see decisions from the group chat.</div>')
