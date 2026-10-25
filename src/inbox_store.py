"""Live messages from the group chat and the desk, with what happened to each.

The 30 supplied requests stay in data/dispatch_requests.txt. New requests, from
the Telegram bot or composed on the desk, are appended here with their channel,
sender and time; every step afterwards (recommended, answered, confirmed,
escalated) is appended as an event on the same message. The Dispatch inbox reads
this file, so a request posted in the chat appears on the desk with its history.

Append-only JSONL with a file lock, like the audit log. It holds message text and
names, never credentials. records/*.jsonl is git-ignored.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import portalocker

PATH = Path(__file__).resolve().parents[1] / "records" / "messages.jsonl"


def _write(row: dict, path: Path | None = None) -> dict:
    destination = Path(path or PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_EX)
        try:
            stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            stream.flush()
        finally:
            portalocker.unlock(stream)
    return row


def _rows(path: Path | None = None) -> list[dict]:
    source = Path(path or PATH)
    if not source.exists():
        return []
    rows = []
    with source.open(encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_SH)
        try:
            for line in stream:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue   # A torn line never hides the rest of the history.
        finally:
            portalocker.unlock(stream)
    return rows


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_message(channel: str, sender: str, text: str, path: Path | None = None) -> str:
    """Record a new request; returns its ID (L1, L2, ...), unique within the file."""
    count = sum(1 for r in _rows(path) if r.get("type") == "message")
    message_id = f"L{count + 1}"
    _write({"type": "message", "id": message_id, "channel": channel, "sender": sender, "text": text, "at": now()}, path)
    return message_id


def add_event(message_id: str, event: str, detail: str = "", by: str | None = None, path: Path | None = None) -> None:
    """Something that happened to a message: recommended, needs reply, answered, confirmed, split, escalated."""
    if message_id:
        _write({"type": "event", "id": message_id, "event": event, "detail": detail, "by": by, "at": now()}, path)


def threads(path: Path | None = None) -> list[dict]:
    """Each message with its events, newest message first. status is the latest event, or "Received"."""
    messages, events = {}, {}
    for row in _rows(path):
        if row.get("type") == "message":
            messages[row["id"]] = {**row, "events": []}
        elif row.get("type") == "event":
            events.setdefault(row["id"], []).append(row)
    for message_id, items in events.items():
        if message_id in messages:
            messages[message_id]["events"] = items
    for thread in messages.values():
        thread["status"] = thread["events"][-1]["event"] if thread["events"] else "Received"
    return sorted(messages.values(), key=lambda t: t["at"], reverse=True)


def engine_text(thread: dict) -> str:
    """The text the engine reads for a live message: the sender's name, then what they wrote (same as the bot)."""
    return f"{thread['sender']}: {thread['text']}"
