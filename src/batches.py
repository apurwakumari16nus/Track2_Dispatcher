"""Batches out at workshops: when each is due back, and whether it has come back.

Workshops cannot report status to us, so a batch is tracked against the return
date booked when it was confirmed (the engine's estimate for that workshop), and
the dispatcher records its arrival. Arrivals are an append-only event log next
to the audit log: marking a batch received adds a line and never edits a
decision. Undoing an arrival adds another line, so the history stays complete.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

import portalocker

import records

ROOT = Path(__file__).resolve().parents[1]
RECEIVED_LOG = ROOT / "records" / "received.jsonl"
REHEARSAL_RECEIVED_LOG = ROOT / "records" / "rehearsal_received.jsonl"

STATUSES = {
    "overdue": "Overdue",          # past its booked return date and not received
    "due_today": "Due back today",
    "at_risk": "Back after the customer date",
    "on_track": "On track",
    "received": "Received",
}


def received_path(decisions_path) -> Path:
    """The arrival log that belongs to an audit log (live or rehearsal)."""
    return REHEARSAL_RECEIVED_LOG if decisions_path is not None and Path(decisions_path).name.startswith("rehearsal") else RECEIVED_LOG


def _day(value) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value else None


def _events(path: Path) -> list[dict]:
    try:
        stream = path.open(encoding="utf-8")
    except FileNotFoundError:
        return []
    with stream:
        portalocker.lock(stream, portalocker.LOCK_SH)
        return [json.loads(line) for line in stream if line.strip()]


def arrivals(path: Path) -> dict[str, dict]:
    """Batch key -> its latest arrival event, for batches currently marked received."""
    state = {}
    for event in _events(path):
        if event["event"] == "received":
            state[event["batch"]] = event
        elif event["event"] == "undo_received":
            state.pop(event["batch"], None)
    return state


def record_arrival(batch_key: str, *, by: str, scenario_date: date, path: Path, undo: bool = False) -> dict:
    """Append one arrival (or its undo). Who and when are kept; nothing else changes."""
    event = {"event": "undo_received" if undo else "received", "batch": batch_key, "by": by,
             "scenario_date": scenario_date.isoformat(), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_EX)
        try:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        finally:
            portalocker.unlock(stream)
    return event


def out_batches(decisions_path=None, received=None) -> list[dict]:
    """Every confirmed batch, one entry per workshop part, with its booked return date and arrival.

    A split gives one entry per part. An overridden decision is booked at the
    workshop the dispatcher chose, with that workshop's estimate.
    """
    arrived = arrivals(Path(received) if received else received_path(decisions_path))
    out = []
    for row in records.load(decisions_path):
        record, parsed = row.get("decision_record", {}), row.get("parsed_request", {})
        confirmation = record.get("constraints_applied", {}).get("confirmation", {})
        if not confirmation.get("confirmed"):
            continue
        chosen = next((c for c in record.get("candidates", []) if c["workshop_id"] == record.get("chosen_workshop")), None)
        split = (record.get("split_allocation") or {}).get("parts")
        parts = split or ([{"workshop_id": chosen["workshop_id"], "name": chosen["name"], "pieces": parsed.get("pieces"),
                            "eta_date": chosen["eta_date"]}] if chosen else [])
        token = confirmation.get("preview_token") or row.get("timestamp", "")
        override = record.get("constraints_applied", {}).get("override")
        for part in parts:
            key = f"{token}:{part['workshop_id']}"
            out.append({
                "key": key, "order_id": parsed.get("order_id"), "customer": parsed.get("customer"), "product": parsed.get("product"),
                "category": parsed.get("category"), "pieces": int(part.get("pieces") or 0), "workshop_id": part["workshop_id"], "workshop": part.get("name") or part["workshop_id"],
                "sent": _day(record.get("timestamp")), "back": _day(part.get("eta_date")), "due": _day(parsed.get("due_date")),
                "split": bool(split), "override": override, "channel": confirmation.get("channel") or "desk",
                "by": confirmation.get("confirmed_by"), "confirmed_at": row.get("timestamp"), "received": arrived.get(key)})
    return out


def status(batch: dict, today: date) -> str:
    """One of STATUSES. Arrival wins; then the booked date against today; then against the customer date."""
    if batch["received"]:
        return "received"
    if batch["back"] and batch["back"] < today:
        return "overdue"
    if batch["back"] == today:
        return "due_today"
    if batch["back"] and batch["due"] and batch["back"] > batch["due"]:
        return "at_risk"
    return "on_track"
