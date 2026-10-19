"""Rehearsal sources are labelled, integrity-checked and never fabricate replies."""

import json

import pytest

import desk
import intake
import rehearsal
from run_inbox import digest


@pytest.fixture
def inbox():
    orders, shops, messages = desk.load_inputs()
    return orders, shops, {m.split()[0]: m for m in messages}


def test_fixture_source_is_labelled_and_limited_to_unedited_inbox(inbox):
    _, _, messages = inbox
    call = rehearsal.make_source("fixture")
    reply = call("prompt", messages["R09"])
    assert json.loads(reply.content)["order_id"] == "ORD-045"
    assert reply.metadata["extraction_source"] == "fixture" and reply.metadata["model"] == "synthetic-fixture"
    with pytest.raises(rehearsal.RehearsalMiss):
        call("prompt", messages["R09"] + " Reply from dispatcher: ORD-045")
    with pytest.raises(rehearsal.RehearsalMiss):
        call("prompt", "Send 400 hoodies somewhere")


def test_recorded_reply_round_trip_and_integrity(tmp_path, inbox):
    orders, shops, messages = inbox
    prompt = intake.build_system_prompt(desk.TODAY, orders, shops)
    reply = intake.LLMReply('{"order_id": "ORD-045"}', {"model": "claude-test", "response_id": "msg_1"})
    path = rehearsal.record(prompt, messages["R09"], reply, "anthropic", "claude-test", directory=tmp_path)
    payload, request, found = rehearsal.find_recorded(prompt, messages["R09"], directories=[tmp_path])
    assert found == path and payload["content"] == reply.content and request["model"] == "claude-test"
    assert rehearsal.recorded_coverage(prompt, messages.values(), directories=[tmp_path]) == 1
    # A different scenario date changes the prompt, so the reply does not match.
    assert rehearsal.find_recorded(prompt.replace("2026-04-01", "2026-04-02"), messages["R09"], directories=[tmp_path]) is None
    entry = json.loads(path.read_text())
    entry["payload"]["content"] = '{"order_id": "ORD-999"}'  # tampered, hash no longer matches
    path.write_text(json.dumps(entry))
    assert rehearsal.find_recorded(prompt, messages["R09"], directories=[tmp_path]) is None


def test_synthetic_cache_entries_are_never_replayed_as_model_output(tmp_path, inbox):
    orders, shops, messages = inbox
    prompt = intake.build_system_prompt(desk.TODAY, orders, shops)
    payload = {"content": "{}", "metadata": {}, "error": None}
    request = {"version": 1, "provider": "synthetic-fixture", "model": "synthetic-fixture", "temperature": 0,
               "system_prompt": prompt, "message": messages["R09"], "fixture_hash": "abc"}
    (tmp_path / "x.json").write_text(json.dumps({"request": request, "payload": payload, "payload_hash": digest(payload)}))
    assert rehearsal.find_recorded(prompt, messages["R09"], directories=[tmp_path]) is None


def test_cached_source_misses_cleanly(monkeypatch, tmp_path, inbox):
    _, _, messages = inbox
    monkeypatch.setattr(rehearsal, "RECORD_DIR", tmp_path / "a")
    monkeypatch.setattr(rehearsal, "EVAL_CACHE_DIR", tmp_path / "b")
    with pytest.raises(rehearsal.RehearsalMiss, match="No recorded model reply"):
        rehearsal.make_source("cached")("prompt", messages["R09"])


def test_live_source_records_reply_and_reports_progress(monkeypatch, tmp_path, inbox):
    _, _, messages = inbox
    monkeypatch.setattr(rehearsal, "RECORD_DIR", tmp_path)
    monkeypatch.setattr(rehearsal, "live_status", lambda: {"ready": True, "provider": "anthropic", "model": "m", "problem": None})
    monkeypatch.setattr(intake, "_call_llm", lambda prompt, message: intake.LLMReply("{}", {"model": "m"}))
    seen = []
    reply = rehearsal.make_source("live", on_reply=lambda: seen.append(True))("prompt", messages["R09"])
    assert seen == [True] and reply.metadata["extraction_source"] == "live"
    assert rehearsal.find_recorded("prompt", messages["R09"], directories=[tmp_path]) is not None


def test_extraction_source_is_context_local():
    marker = object()
    assert intake._EXTRACTION_SOURCE.get() is None
    with intake.extraction_source(marker):
        assert intake._EXTRACTION_SOURCE.get() is marker
    assert intake._EXTRACTION_SOURCE.get() is None
