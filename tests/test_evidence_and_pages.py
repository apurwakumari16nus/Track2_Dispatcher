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
    at.button(key="demo_start").click().run()  # Guided demo loads R09; the dispatcher still evaluates it.
    assert "desk_preview" not in at.session_state and at.session_state["desk_message"].startswith("R09 ")
    assert "DEMO 1 OF 6" in " ".join(m.value for m in at.markdown)
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
    assert not at.exception and at.segmented_control(key="audit_log").value == "rehearsal"
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
    assert "Fastest for 1,500 tops" in text and "Suspended" in text and "can take this batch" in text
    at.segmented_control(key="net_category").set_value("ACCESSORIES").run()
    assert not at.exception and "can make accessories" in " ".join(m.value for m in at.markdown)
    at.radio(key="desk_page").set_value("Simulation Lab").run()
    assert not at.exception
    at.radio(key="desk_page").set_value("Audit Trail").run()
    assert not at.exception


def test_guided_demo_steps_through_real_cases_without_running_them(rehearsal_app):
    at, _ = rehearsal_app
    at.button(key="demo_start").click().run()
    seen = []
    for _ in range(5):
        seen.append(at.session_state["desk_message"].split(" ", 1)[0])
        assert "desk_preview" not in at.session_state  # The tour loads a case; it never evaluates or confirms it.
        at.button(key="demo_next").click().run()
        assert not at.exception
    assert seen == ["R09", "R01", "R08", "R02", "R30"]
    assert at.session_state["desk_page"] == "Audit Trail" and at.session_state["demo_step"] == 5
    assert not [b for b in at.button if b.key == "demo_next"]
    at.button(key="demo_prev").click().run()
    assert at.session_state["desk_page"] == "Dispatch" and at.session_state["desk_message"].startswith("R30 ")
    at.button(key="demo_exit").click().run()
    assert "demo_step" not in at.session_state and not [b for b in at.button if b.key == "demo_prev"]


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
    assert "Assign to Nimble Needle" in text and "Why this workshop?" in text  # The engine's choice, not a mock-up name.
    assert at.button(key="desk_confirm").label == "Assign to Nimble Needle" and not at.button(key="desk_confirm").disabled
    assert "SteadyHands" not in text.split("Why this workshop?")[0]
    at.button(key="desk_options").click().run()  # Opens the inspector on the alternatives; changes nothing.
    assert not at.exception and "desk_preview" in at.session_state and not desk.REHEARSAL_LOG.exists()
    at.segmented_control(key="inbox_filter").set_value("reviewed").run()
    assert [b.key for b in at.button if b.key and b.key.startswith("inbox_R")] == ["inbox_R09"]
    at.segmented_control(key="inbox_filter").set_value("pending").run()
    assert "inbox_R09" not in [b.key for b in at.button] and len([b for b in at.button if b.key and b.key.startswith("inbox_R")]) == 29
