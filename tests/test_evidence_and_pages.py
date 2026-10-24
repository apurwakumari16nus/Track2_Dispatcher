"""Course evidence reads committed files honestly; every page renders in rehearsal."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import desk
import records
import rehearsal
from ui import audit, evidence

ROOT = Path(__file__).resolve().parents[1]


def test_course_evidence_matches_code_and_reports_ties():
    data = evidence.load()
    assert data["provenance"]["matches"], data["provenance"]["stale"]
    matrix = {(r["objective"], r["scenario"], r["comparator"]): r["outcome"] for r in evidence.check_matrix(data["results"], data["checks"])}
    assert matrix[("lateness", "normal", "earliest_finish")] == "tie"
    assert matrix[("lateness", "normal", "random_choice")] == "qualifying"
    assert all(matrix[("defect", s, c)] == "guardrail" for s in ("normal", "shock") for c in evidence.COMPARATORS)
    text = " ".join(f["text"] for f in evidence.findings(data["results"], data["checks"]))
    assert "ties earliest finish" in text and "A tie is not a win" in text and "fails the lateness guardrail" in text
    rows = evidence.primary_table(data["results"])
    assert [r["policy"] for r in rows] == ["random_choice", "greedy_biggest", "cheapest", "earliest_finish", "allocator"]


def test_language_status_never_claims_accuracy_without_labels():
    status = evidence.language_status()
    assert status["requests"] == 30 and sum(n for _, n in status["mix"]) == 30
    if status["final_labels"] < 30:
        assert not status["accuracy_reportable"]


def test_audit_search_combines_filters_newest_first():
    rows = [{"sender": "Mei", "timestamp": "2026-10-19T10:00:00+00:00", "decision_record": {"chosen_workshop": "W1", "constraints_applied": {}}},
            {"sender": "Ravi", "timestamp": "2026-10-20T10:00:00+00:00", "decision_record": {"chosen_workshop": "W2",
             "constraints_applied": {"confirmation": {"accepted_lateness": True}}}}]
    assert [r["sender"] for r in audit.search(rows)] == ["Ravi", "Mei"]
    assert audit.search(rows, kinds=["Late return accepted"]) == [rows[1]]
    assert audit.search(rows, query="mei", workshops=["W1"]) == [rows[0]]
    day = audit.logged_date(rows[0])
    assert audit.search(rows, dates=(day, day)) == [rows[0]]


@pytest.fixture
def rehearsal_app(monkeypatch, tmp_path):
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "live.jsonl")
    monkeypatch.setattr(desk, "REHEARSAL_LOG", tmp_path / "rehearsal.jsonl")
    monkeypatch.setattr(rehearsal, "RECORD_DIR", tmp_path / "cache")
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=60)
    at.session_state["desk_source"] = "fixture"
    return at.run(), tmp_path


def test_rehearsal_confirmations_stay_out_of_the_live_log(rehearsal_app):
    at, tmp = rehearsal_app
    assert "Rehearsal mode" in " ".join(m.value for m in at.markdown)  # the mode ribbon
    at.button(key="inbox_R09").click().run()  # Selecting a request loads it; the dispatcher still evaluates it.
    assert "desk_preview" not in at.session_state and at.session_state["desk_message"].startswith("R09 ")
    at.button(key="desk_dispatch").click().run()
    assert not at.exception and at.session_state["desk_preview"].source == "fixture"
    text = " ".join(m.value for m in at.markdown)
    assert "Not yet confirmed" in text and "Nimble Needle" in text and "Confirmed by you" not in text  # Suggested, not committed.
    at.button(key="desk_inspect").click().run()  # The inspector reads the preview; it never changes it.
    text = " ".join(m.value for m in at.markdown)
    assert not at.exception and "Why this decision" in text and "Final score, lower wins" in text
    assert not records.DEFAULT_PATH.exists() and not desk.REHEARSAL_LOG.exists()
    at.button(key="desk_confirm").click().run()
    assert not at.exception
    assert len(records.load(desk.REHEARSAL_LOG)) == 1 and not records.DEFAULT_PATH.exists()
    assert "Confirmed by you" in " ".join(m.value for m in at.markdown)  # Committed only after the explicit confirmation.
    saved = records.load(desk.REHEARSAL_LOG)[0]
    assert saved["decision_record"]["constraints_applied"]["confirmation"]["extraction_source"] == "fixture"
    assert saved["parsed_request"]["llm_metadata"]["model"] == "synthetic-fixture"
    at.radio(key="desk_page").set_value("Audit Trail").run()
    assert not at.exception and at.segmented_control(key="_w_audit_log").value == "rehearsal"
    assert "Nimble Needle" in " ".join(m.value for m in at.markdown)
    at.button(key="audit_open_0").click().run()
    text = " ".join(m.value for m in at.markdown)
    assert not at.exception and "Original request" in text and "Why this workshop" in text
    at.radio(key="desk_page").set_value("Dispatch").run()
    at.button(key="demo_reset").click().run()
    assert not at.exception and at.session_state["desk_saved"] == {} and not desk.REHEARSAL_LOG.exists()
    assert at.session_state["desk_source"] == "fixture"


def test_impossible_deadline_offers_real_split_preview(rehearsal_app):
    at, _ = rehearsal_app
    at.button(key="inbox_R30").click().run()
    at.button(key="desk_dispatch").click().run()
    assert "No eligible workshop can meet 5 Apr." in " ".join(m.value for m in at.markdown)
    assert at.button(key="desk_confirm").label == "Accept late return"
    at.button(key="desk_split").click().run()
    assert not at.exception
    split = next(iter(at.session_state["desk_splits"].values()))
    assert split["available"] and sum(p["pieces"] for p in split["parts"]) == 1500


def test_every_page_renders_and_network_answers_the_register_question(rehearsal_app):
    at, _ = rehearsal_app
    for rid in ("R01", "R02", "R23", "R28"):
        at.button(key=f"inbox_{rid}").click().run()
        at.button(key="desk_dispatch").click().run()
        assert not at.exception, rid
    at.radio(key="desk_page").set_value("Workshop Network").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Fastest for 1,500 tops" in text and "Suspended" in text and "can take 1,500 tops" in text
    at.segmented_control(key="_w_net_category").set_value("ACCESSORIES").run()
    assert not at.exception and "can make accessories" in " ".join(m.value for m in at.markdown)
    at.radio(key="desk_page").set_value("Simulation Lab").run()
    assert not at.exception
    at.radio(key="desk_page").set_value("Audit Trail").run()
    assert not at.exception


def test_guided_demo_walks_r09_from_inbox_to_audit_record(rehearsal_app):
    """The guide waits for real actions, confirms nothing itself and writes one rehearsal record."""
    at, _ = rehearsal_app
    at.button(key="inbox_R01").click().run()   # Work in progress, set aside by the demo and restored on exit.
    at.button(key="demo_start").click().run()
    at.button(key="guide_begin").click().run()
    guide = lambda: at.session_state["guide"]
    assert guide()["running"] and guide()["step"] == 0 and guide()["source"] in {"cached", "fixture"}
    assert at.session_state["desk_message"] == "" and "desk_preview" not in at.session_state
    assert not [b for b in at.button if b.key == "guide_next"]          # An event step: no Continue to skip it.
    at.button(key="inbox_R09").click().run()
    assert guide()["step"] == 1 and "desk_preview" not in at.session_state  # Loading is not evaluating.
    assert at.button(key="guide_next").disabled
    at.button(key="desk_dispatch").click().run()
    assert not at.exception and not at.button(key="guide_next").disabled
    at.button(key="guide_next").click().run()
    at.button(key="guide_next").click().run()
    assert guide()["step"] == 3
    at.button(key="desk_trace").click().run()
    assert at.session_state["desk_page"] == "Workshop Network" and guide()["step"] == 4
    assert at.button(key="guide_next").disabled                        # Inspect another workshop first.
    chosen = at.session_state["desk_preview"].response.decision_record["chosen_workshop"]
    other = next(w for w in ("W8", "W2", "W1") if w != chosen)
    at.button(key=f"node_{other}").click().run()
    at.button(key="guide_next").click().run()
    assert guide()["step"] == 5 and at.session_state["desk_page"] == "Dispatch"
    assert not desk.REHEARSAL_LOG.exists() and not records.DEFAULT_PATH.exists()  # Nothing saved until the user confirms.
    at.button(key="desk_confirm").click().run()
    assert not at.exception and guide()["step"] == 6
    saved = records.load(desk.REHEARSAL_LOG)
    assert len(saved) == 1 and not records.DEFAULT_PATH.exists()
    confirmation = saved[0]["decision_record"]["constraints_applied"]["confirmation"]
    assert confirmation["guided_demo"] is True and confirmation["trace_id"]
    assert at.button(key="guide_prev").disabled                         # Cannot step back past a confirmation.
    at.button(key="desk_view_audit").click().run()
    assert not at.exception and at.session_state["desk_page"] == "Audit Trail"
    assert at.session_state["audit_log"] == "rehearsal" and at.session_state["audit_opened"] == saved[0]["timestamp"]
    at.button(key="guide_next").click().run()
    assert guide()["step"] == 7 and "Human approval" in " ".join(m.value for m in at.markdown)
    assert len(records.load(desk.REHEARSAL_LOG)) == 1                   # Navigation never writes again.
    at.button(key="guide_exit").click().run()
    assert "guide" not in at.session_state and at.session_state["desk_message"].startswith("R01 ")


def test_scenario_library_loads_a_case_without_evaluating_it(rehearsal_app):
    at, _ = rehearsal_app
    at.button(key="demo_start").click().run()
    at.button(key="guide_scn_R30").click().run()
    assert not at.exception and "guide" not in at.session_state
    assert at.session_state["desk_message"].startswith("R30 ") and "desk_preview" not in at.session_state
    assert "Scenario R30." in " ".join(m.value for m in at.markdown)


def test_objective_scorecard_is_computed_from_committed_results():
    data = evidence.load()
    cards = {r["objective"]: r for r in evidence.objective_scorecard(data["results"], data["checks"])}
    assert cards["lateness"]["verdict"] == "Beats supplied baselines, ties earliest finish"
    assert cards["fairness"]["verdict"] == "Qualifies" and cards["robustness"]["verdict"] == "Qualifies"
    assert cards["defect"]["verdict"] == "Fails lateness guardrail" and cards["defect"]["tone"] == "risk"
    assert cards["hybrid_lateness_fairness"]["verdict"] == "Reported, no course pass rule"


def test_homepage_recommendation_uses_the_real_decision_and_filters_inbox(rehearsal_app):
    at, _ = rehearsal_app
    at.button(key="inbox_R09").click().run()
    at.button(key="desk_dispatch").click().run()
    text = " ".join(m.value for m in at.markdown)
    assert "Nimble Needle" in text and "Not yet confirmed" in text  # The engine's choice, not a mock-up name.
    assert at.button(key="desk_confirm").label == "Assign to Nimble Needle" and not at.button(key="desk_confirm").disabled
    at.button(key="desk_inspect").click().run()  # Opens the inspector; changes nothing.
    assert not at.exception and "desk_preview" in at.session_state and not desk.REHEARSAL_LOG.exists()
    at.segmented_control(key="_w_inbox_filter").set_value("reviewed").run()
    assert [b.key for b in at.button if b.key and b.key.startswith("inbox_R")] == ["inbox_R09"]
    at.segmented_control(key="_w_inbox_filter").set_value("pending").run()
    assert "inbox_R09" not in [b.key for b in at.button] and len([b for b in at.button if b.key and b.key.startswith("inbox_R")]) == 29
