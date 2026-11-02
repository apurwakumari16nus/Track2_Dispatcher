"""Sprint 3: override with a reason, and batches tracked until they come back (desk.confirm_override, batches.py)."""

from datetime import date
import hashlib
import json
from pathlib import Path

import pytest

from allocator import Allocator
import batches
import desk
import intake
from objectives import PRESETS
import records

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(batches, "RECEIVED_LOG", tmp_path / "received.jsonl")
    return tmp_path


def preview_for(rid):
    data = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    assert data["dispatch_requests_sha256"] == hashlib.sha256((ROOT / "data/dispatch_requests.txt").read_bytes()).hexdigest()
    orders, shops, messages = desk.load_inputs()
    message = next(m for m in messages if m.startswith(rid))
    reply = intake.LLMReply(json.dumps({**data["defaults"], **data["requests"][rid]}), {"model": "test"})
    queues = {wid: w.queue0 for wid, w in shops.items()}
    with intake.extraction_source(lambda prompt, text: reply):
        preview = desk.make_preview(message, desk.TODAY, PRESETS["lateness"], orders, shops, queues, Allocator(PRESETS["lateness"]))
    return preview, shops, queues


def other_candidate(preview):
    record = preview.response.decision_record
    return next(c for c in record["candidates"] if c["workshop_id"] != record["chosen_workshop"])


# Override ------------------------------------------------------------------------------

def test_an_override_books_the_chosen_workshop_and_keeps_the_engines_pick(logs):
    preview, shops, queues = preview_for("R09")
    engine = preview.response.decision_record["chosen_workshop"]
    target = other_candidate(preview)
    saved = {}
    row, next_queues, _ = desk.confirm_override(preview, preview.signature, saved, target["workshop_id"], "Quality concern", "",
                                                shops, queues, Allocator(PRESETS["lateness"]))
    record = row["decision_record"]
    assert record["chosen_workshop"] == target["workshop_id"]
    assert record["constraints_applied"]["override"] == {"engine_pick": engine, "chosen": target["workshop_id"],
                                                         "reason": "Quality concern", "note": "", "by": None}
    assert next_queues[target["workshop_id"]] > queues[target["workshop_id"]] and next_queues[engine] == queues[engine]
    assert row["faithfulness"]["passed"]
    assert len(records.load()) == 1
    replayed, _, confirmed = desk.queues_from_log(shops)
    assert confirmed == 1 and replayed[target["workshop_id"]] == pytest.approx(next_queues[target["workshop_id"]])


@pytest.mark.parametrize("pick, reason, note, message", [
    ("engine", "Quality concern", "", "different workshop"),
    ("W7", "Quality concern", "", "different workshop"),          # suspended, so never a candidate
    ("other", "", "", "reason"),
    ("other", "Other", "  ", "note"),
])
def test_an_override_needs_a_permitted_workshop_and_a_reason(pick, reason, note, message, logs):
    preview, shops, queues = preview_for("R09")
    workshop = {"engine": preview.response.decision_record["chosen_workshop"], "other": other_candidate(preview)["workshop_id"]}.get(pick, pick)
    with pytest.raises(ValueError, match=message):
        desk.confirm_override(preview, preview.signature, {}, workshop, reason, note, shops, queues, Allocator(PRESETS["lateness"]))
    assert records.load() == []


def test_an_override_is_written_once(logs):
    preview, shops, queues = preview_for("R09")
    target, saved = other_candidate(preview)["workshop_id"], {}
    for _ in range(2):
        desk.confirm_override(preview, preview.signature, saved, target, "Customer asked for it", "", shops, queues, Allocator(PRESETS["lateness"]))
    assert len(records.load()) == 1


# Tracking ------------------------------------------------------------------------------

def test_a_confirmed_batch_is_tracked_against_its_booked_return_date(logs):
    preview, _, _ = preview_for("R09")
    desk.confirm_preview(preview, preview.signature, {})
    [batch] = batches.out_batches()
    chosen = next(c for c in preview.response.decision_record["candidates"]
                  if c["workshop_id"] == preview.response.decision_record["chosen_workshop"])
    assert batch["back"] == date.fromisoformat(chosen["eta_date"]) and batch["order_id"] == "ORD-045"
    assert batches.status(batch, desk.TODAY) == "on_track"
    assert batches.status(batch, batch["back"]) == "due_today"
    assert batches.status(batch, date(2026, 4, 30)) == "overdue"


def test_marking_received_appends_an_event_and_undo_restores_it(logs):
    preview, _, _ = preview_for("R09")
    desk.confirm_preview(preview, preview.signature, {})
    [batch] = batches.out_batches()
    path = batches.received_path(None)
    batches.record_arrival(batch["key"], by="Dispatcher", scenario_date=date(2026, 4, 30), path=path)
    [batch] = batches.out_batches()
    assert batches.status(batch, date(2026, 4, 30)) == "received" and batch["received"]["by"] == "Dispatcher"
    batches.record_arrival(batch["key"], by="Dispatcher", scenario_date=date(2026, 4, 30), path=path, undo=True)
    [batch] = batches.out_batches()
    assert batches.status(batch, date(2026, 4, 30)) == "overdue"
    assert len(path.read_text().splitlines()) == 2   # nothing edited, two lines appended


def test_a_batch_booked_after_its_customer_date_is_at_risk():
    batch = {"received": None, "back": date(2026, 4, 12), "due": date(2026, 4, 9)}
    assert batches.status(batch, date(2026, 4, 1)) == "at_risk"
