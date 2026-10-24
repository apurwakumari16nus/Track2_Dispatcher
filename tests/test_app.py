"""Preview/confirmation safety and real Streamlit reruns, with no live API calls."""

from copy import deepcopy
from datetime import date
import json
import hashlib
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import app
from allocator import Allocator
import intake
from objectives import PRESETS
import records
import rehearsal
from simulate import load_workshops
import tools

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(monkeypatch, tmp_path):
    fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    assert fixture["dispatch_requests_sha256"] == hashlib.sha256((ROOT / "data/dispatch_requests.txt").read_bytes()).hexdigest()
    calls = []
    def fake(prompt, message):
        calls.append(message)
        raw = {**deepcopy(fixture["defaults"]), **deepcopy(fixture["requests"][message.split()[0]])}
        return intake.LLMReply(json.dumps(raw), {"model": "synthetic-fixture"})
    monkeypatch.setattr(intake, "_call_llm", fake)
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "records/decisions.jsonl")
    monkeypatch.setattr(rehearsal, "RECORD_DIR", tmp_path / "rehearsal_cache")
    orders, shops, messages = app.load_inputs()
    return orders, shops, {wid: w.queue0 for wid, w in shops.items()}, {m.split()[0]: m for m in messages}, calls


def prepare(setup, request="R30"):
    orders, shops, queues, messages, _ = setup
    allocator = Allocator(PRESETS["lateness"])
    preview = app.make_preview(messages[request], app.TODAY, PRESETS["lateness"], orders, shops, queues, allocator)
    return preview, allocator


def test_preview_never_commits_or_writes_and_confirmation_only_appends_once(setup):
    preview, allocator = prepare(setup)
    assert allocator.pieces_by_workshop == {} and not records.DEFAULT_PATH.exists()
    assert not preview.response.allocation_committed
    saved = {}
    first = app.confirm_preview(preview, preview.signature, saved)
    assert first["allocation_committed"] and first["constraints"]["confirmation"]["accepted_lateness"]
    assert first["explanation_text"].startswith("CONFIRMED ALLOCATION")
    second = app.confirm_preview(preview, preview.signature, saved)
    assert first == second and len(records.load()) == 1
    assert allocator.pieces_by_workshop == {}  # Controller adopts only after append succeeds.
    assert sum(preview.accepted_allocator.pieces_by_workshop.values()) == 1500


def test_stale_or_nonallocating_preview_cannot_write(setup):
    preview, _ = prepare(setup)
    with pytest.raises(ValueError, match="Inputs changed"):
        app.confirm_preview(preview, "changed", {})
    for rid in ("R01", "R02", "R05"):
        preview, _ = prepare(setup, rid)
        with pytest.raises(ValueError):
            app.confirm_preview(preview, preview.signature, {})
    assert not records.DEFAULT_PATH.exists()


def test_append_error_preserves_unconfirmed_state(setup):
    preview, allocator = prepare(setup)
    saved = {}
    def fail(response):
        raise OSError("test disk failure")
    with pytest.raises(OSError):
        app.confirm_preview(preview, preview.signature, saved, append=fail)
    assert saved == {} and allocator.pieces_by_workshop == {}


def test_candidates_include_physically_eligible_user_exclusions_and_complete_trace(setup):
    preview, _ = prepare(setup, "R12")
    record = preview.response.decision_record
    inventory = record["tool_outputs"]["ui_candidate_inventory"]
    w1 = next(r for r in inventory if r["workshop_id"] == "W1")
    assert w1["exclusion_reason"] == "Excluded by request" and isinstance(w1["score"], float)
    assert "W1" not in {r["workshop_id"] for r in record["candidates"]}
    assert [r["score"] for r in inventory] == sorted(r["score"] for r in inventory)
    calls = record["tool_outputs"]["call_trace"]
    names = {c["tool"] for c in calls}
    assert {"check_eligibility", "estimate_eta", "estimate_cost", "candidates", "queue_check", "overload_probe", "ShockMonitor.observe"} <= names
    assert all("output" in c for c in calls)
    assert json.loads(json.dumps(calls, allow_nan=False)) == calls


def test_register_queue_projection_and_refusal_alternative_confirmation(setup):
    preview, _ = prepare(setup, "R08")
    assert preview.response.parsed_request.behaviour == "refuse" and preview.block_reason is None
    entry = app.confirm_preview(preview, preview.signature, {})
    assert entry["constraints"]["confirmation"]["accepted_alternative"]
    wid = preview.response.decision_record["chosen_workshop"]
    assert wid != "W8"
    assert preview.accepted_queues[wid] > setup[2][wid]
    assert app.projected_queues({"W1": 5.0, "W2": 1.0}, app.TODAY, date(2026, 4, 3)) == {"W1": 3.0, "W2": 0.0}
    with pytest.raises(ValueError):
        app.projected_queues(setup[2], app.TODAY, date(2026, 3, 31))


def test_filtered_log_is_newest_first_and_combines_filters():
    rows = [dict(sender="Mei", decision_record={"chosen_workshop": "W1"}, timestamp="a"),
            dict(sender="Ravi", decision_record={"chosen_workshop": "W2"}, timestamp="b"),
            dict(sender="Mei", decision_record={"chosen_workshop": "W2"}, timestamp="c")]
    assert [r["timestamp"] for r in app.filtered_records(rows)] == ["c", "b", "a"]
    assert app.filtered_records(rows, "W2", "Mei") == [rows[2]]


def test_tool_traces_do_not_leak_across_contexts_or_change_results():
    shops = load_workshops()
    batch = {"category": "TOPS", "pieces": 400}
    expected = tools.check_eligibility(batch, shops)
    with tools.trace_calls() as outer:
        tools.check_eligibility(batch, shops)
        with tools.trace_calls() as inner:
            tools.check_eligibility({**batch, "pieces": 200}, shops)
        tools.check_eligibility(batch, shops)
    assert len(outer) == 2 and len(inner) == 1
    assert outer[0]["output"] == expected
    tools.check_eligibility(batch, shops)
    assert len(outer) == 2


def test_streamlit_load_click_dispatch_confirm_and_log_reruns(setup):
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=20)
    at.session_state["desk_page"] = "Dispatch"
    at.run()
    assert not at.exception
    assert len([b for b in at.button if b.key and b.key.startswith("inbox_R")]) == 30
    assert at.date_input(key="_w_desk_today").value == app.TODAY
    assert not records.DEFAULT_PATH.exists()
    at.button(key="inbox_R30").click().run()
    assert at.text_area(key="_w_desk_message__edit").value == setup[3]["R30"]
    at.button(key="desk_dispatch").click().run()
    assert not at.exception and not records.DEFAULT_PATH.exists()
    assert len(setup[4]) == 1
    assert "Least-late option" in " ".join(m.value for m in at.markdown)
    assert not at.button(key="desk_confirm").disabled
    at.button(key="desk_confirm").click().run()
    assert not at.exception and len(records.load()) == 1
    keys = [b.key for b in at.button]
    assert "desk_confirm" not in keys and "desk_view_audit" in keys  # Confirmed state replaces the action.
    at.run()
    assert len(records.load()) == 1 and len(setup[4]) == 1
    at.radio(key="desk_page").set_value("Audit Trail").run()
    assert not at.exception
    assert at.multiselect(key="_w_audit_sender").options == ["Mei"]
    at.radio(key="desk_page").set_value("Dispatch").run()
    assert not at.exception and len(records.load()) == 1
    assert at.date_input(key="_w_desk_today").value == app.TODAY
    assert at.text_area(key="_w_desk_message__edit").value == setup[3]["R30"]


@pytest.mark.parametrize("rid,verdict", [("R01", "I need one detail before I can continue."),
                                         ("R02", "not available in the supplied data"),
                                         ("R08", "cannot accept this batch")])
def test_streamlit_behaviour_banners_and_no_automatic_writes(setup, rid, verdict):
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=20)
    at.session_state["desk_page"] = "Dispatch"
    at.run()
    at.button(key="inbox_" + rid).click().run()
    at.button(key="desk_dispatch").click().run()
    assert not at.exception
    assert verdict in " ".join(m.value for m in at.markdown)
    confirm = [b for b in at.button if b.key == "desk_confirm"]
    if rid == "R08":
        assert confirm and not confirm[0].disabled and confirm[0].label == "Accept alternative"
    else:
        assert not confirm  # Replies, not allocations: there is nothing to confirm.
    assert not records.DEFAULT_PATH.exists()


def test_streamlit_editing_request_invalidates_old_confirmation(setup):
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=20)
    at.session_state["desk_page"] = "Dispatch"
    at.run()
    at.button(key="inbox_R30").click().run()
    at.button(key="desk_dispatch").click().run()
    at.text_area(key="_w_desk_message__edit").set_value("A different request").run()
    assert "desk_confirm" not in [b.key for b in at.button]
    assert "desk_preview" not in at.session_state
    assert not records.DEFAULT_PATH.exists()


def test_streamlit_date_and_objective_survive_log_navigation(setup):
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=20)
    at.session_state["desk_page"] = "Dispatch"
    at.run()
    at.date_input(key="_w_desk_today").set_value(date(2026, 4, 3)).run()
    at.selectbox(key="_w_desk_preset").set_value("fairness").run()
    at.radio(key="desk_page").set_value("Audit Trail").run()
    at.radio(key="desk_page").set_value("Dispatch").run()
    assert not at.exception
    assert at.date_input(key="_w_desk_today").value == date(2026, 4, 3)
    assert at.selectbox(key="_w_desk_preset").value == "fairness"


def test_register_explores_eligibility_without_calling_model_or_saving(setup):
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=20)
    at.session_state["desk_page"] = "Dispatch"
    at.run()
    at.radio(key="desk_page").set_value("Workshop Network").run()
    assert not at.exception
    assert "Suspended" in " ".join(m.value for m in at.markdown)
    at.number_input[0].set_value(100).run()
    assert not at.exception
    assert not setup[4] and not records.DEFAULT_PATH.exists()
    at.radio(key="desk_page").set_value("Dispatch").run()
    assert not at.exception
    assert at.date_input(key="_w_desk_today").value == app.TODAY


def test_inbox_search_preserves_selection_and_does_not_dispatch(setup):
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=20)
    at.session_state["desk_page"] = "Dispatch"
    at.run()
    at.text_input(key="_w_inbox_search").set_value("R09").run()
    assert [b.key for b in at.button if b.key and b.key.startswith("inbox_R")] == ["inbox_R09"]
    at.button(key="inbox_R09").click().run()
    assert at.text_area(key="_w_desk_message__edit").value == setup[3]["R09"]
    at.text_input(key="_w_inbox_search").set_value("no matching request").run()
    assert not at.exception and not setup[4]
    assert at.text_area(key="_w_desk_message__edit").value == setup[3]["R09"]
