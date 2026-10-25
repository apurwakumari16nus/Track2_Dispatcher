"""V11 regressions: widget state lifecycle, provider failures, execution traces,
confirm once, audit log choice and the benchmark dry run. No test makes an API call."""

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx2
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import desk
import intake
import records
import rehearsal
import tracing
from allocator import Allocator
from objectives import PRESETS
from simulate import load_workshops
from ui import dispatch

ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-ant-test-not-a-real-key-0000"


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "live.jsonl")
    monkeypatch.setattr(desk, "REHEARSAL_LOG", tmp_path / "rehearsal.jsonl")
    monkeypatch.setattr(rehearsal, "RECORD_DIR", tmp_path / "cache")
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=60)
    at.session_state["desk_source"] = "fixture"
    return at.run()


@pytest.fixture
def data():
    return pd.read_csv(ROOT / "data/orders.csv"), load_workshops()


def page(at, name):
    at.radio(key="desk_page").set_value(name).run()
    assert not at.exception, name


# Widget state lifecycle --------------------------------------------------------------

def test_navigation_round_trips_never_lose_a_selection(app):
    """The V10 crashes: Audit to Dispatch to Audit raised KeyError: None; Network raised NoneType.lower."""
    for name in ["Audit Trail", "Dispatch", "Audit Trail", "Workshop Network", "Dispatch", "Workshop Network",
                 "Simulation Lab", "Audit Trail", "Workshop Network"]:
        page(app, name)
    assert app.session_state["audit_log"] in {"live", "rehearsal"}
    assert app.session_state["net_category"] in {"TOPS", "ACCESSORIES"}


def test_a_widget_that_reports_none_never_overwrites_the_domain_value(monkeypatch):
    """Streamlit's required segmented control deserializes a re-click on the selected option as None.
    That None reached the pages as the selection (KeyError: None in Audit, NoneType.lower in Network)."""
    from ui import state as bound
    fake = {}
    monkeypatch.setattr(bound.st, "session_state", fake)
    drawn = {}
    widget = lambda *args, key, on_change, **kw: drawn.update(key=key, on_change=on_change)
    fake["audit_log"] = "live"
    assert bound.bind(widget, "Log", ["live", "rehearsal"], key="audit_log", fallback="live") == "live"
    fake[drawn["key"]] = None            # What the frontend sends on the re-click.
    drawn["on_change"]()
    assert fake["audit_log"] == "live"
    fake[drawn["key"]] = "rehearsal"     # A real change still goes through.
    drawn["on_change"]()
    assert fake["audit_log"] == "rehearsal"
    fake["net_category"] = None          # allow_none: "nothing chosen yet" is a real state, kept as None.
    assert bound.bind(widget, "Category", ["TOPS"], key="net_category", fallback="TOPS", allow_none=True) is None
    fake["net_category"] = "BOTTOMS"     # Unknown values fall back.
    assert bound.bind(widget, "Category", ["TOPS"], key="net_category", fallback="TOPS") == "TOPS"


def test_corrupt_domain_values_fall_back_instead_of_crashing(app):
    app.session_state["audit_log"] = None
    app.session_state["audit_view"] = "something old"
    page(app, "Audit Trail")
    assert app.session_state["audit_log"] == "rehearsal" and app.session_state["audit_view"] == "decisions"


def test_unknown_category_from_dispatch_is_shown_not_swapped(app):
    from datetime import date
    app.session_state["net_handoff"] = {"category": "BOTTOMS", "pieces": 100, "due": date(2026, 4, 9), "label": "request R99"}
    page(app, "Workshop Network")
    text = " ".join(m.value for m in app.markdown)
    assert app.session_state["net_category"] is None and "Choose a category to route this batch" in text
    assert "BOTTOMS" in text


# Provider failures ------------------------------------------------------------------

def anthropic_client(monkeypatch, behaviour):
    import anthropic
    import dotenv

    class Client:
        def __init__(self, **kwargs):
            self.beta = SimpleNamespace(messages=SimpleNamespace(create=behaviour))
        def __enter__(self): return self
        def __exit__(self, *args): pass

    monkeypatch.setattr(anthropic, "Anthropic", Client)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setenv("ANTHROPIC_INTAKE_MODEL", "claude-sonnet-5-5")


REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, code):
    return cls("provider said no", response=httpx2.Response(code, request=REQUEST), body=None)


@pytest.mark.parametrize("make, category, retry", [
    (lambda a: a.APITimeoutError(request=REQUEST), "timeout", True),
    (lambda a: a.APIConnectionError(request=REQUEST), "connection", True),
    (lambda a: status_error(a.AuthenticationError, 401), "auth", False),
    (lambda a: status_error(a.RateLimitError, 429), "rate_limit", True),
    (lambda a: status_error(a.InternalServerError, 529), "provider_unavailable", True),
    (lambda a: status_error(a.BadRequestError, 400), "bad_request", False),
])
def test_provider_failures_are_classified_and_never_leak_the_key(make, category, retry, data, monkeypatch):
    import anthropic

    def fail(**kwargs):
        raise make(anthropic)
    anthropic_client(monkeypatch, fail)
    with pytest.raises(intake.ProviderError) as caught:
        intake.parse_request("R09 [08:33] Boss: ORD-045, 150 vests.", desk.TODAY, *data)
    error = caught.value
    assert error.category == category and intake.ERROR_CATEGORIES[category][2] is retry
    shown = dispatch.describe_error(error)
    assert shown["kind"] == category and shown["retry"] is retry and shown["title"]
    assert SECRET not in json.dumps(error.llm_metadata, default=str) + str(error) + json.dumps(shown)


def test_invalid_json_and_engine_and_unknown_errors_have_distinct_outcomes(data, monkeypatch):
    monkeypatch.setattr(intake, "_call_llm", lambda *a: intake.LLMReply("not JSON", {}))
    with pytest.raises(intake.IntakeError) as bad:
        intake.parse_request("ORD-045 please", desk.TODAY, *data)
    assert bad.value.category == "invalid_output" and dispatch.describe_error(bad.value)["retry"]
    assert dispatch.describe_error(ValueError("queue mismatch"))["kind"] == "engine"
    assert dispatch.describe_error(RuntimeError("boom"))["kind"] == "system"


def test_all_null_extraction_asks_instead_of_guessing(data, monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    keep = {"behaviour", "question_topic", "reason"}   # Required by the schema; every data field is null.
    payload = {k: (v if k in keep or isinstance(v, (list, bool)) else None) for k, v in fixture["defaults"].items()}
    payload["behaviour"] = "allocate"                    # The model claims it can allocate; Python must not agree.
    monkeypatch.setattr(intake, "_call_llm", lambda *a: intake.LLMReply(json.dumps(payload), {"model": "test"}))
    first = intake.parse_request("Send the usual batch out", desk.TODAY, *data)
    again = intake.parse_request("Send the usual batch out", desk.TODAY, *data)
    assert first.behaviour == "clarify" and first.order_id is None
    strip = lambda r: {k: v for k, v in vars(r).items() if k != "llm_metadata"}
    assert strip(first) == strip(again)  # Repeatable: the same reply gives the same validated request.


# Execution traces -------------------------------------------------------------------

def run_preview(rid="R09", source="fixture"):
    orders, workshops, _ = desk.load_inputs()
    line = rehearsal.inbox_lines()[rid]
    with intake.extraction_source(rehearsal.make_source(source)):
        return desk.make_preview(line, desk.TODAY, PRESETS["lateness"], orders, workshops,
                                 {w: s.queue0 for w, s in workshops.items()}, Allocator(PRESETS["lateness"]), 0, source)


def test_trace_stages_are_non_negative_and_add_up_without_double_counting(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    line = rehearsal.inbox_lines()["R09"]
    with tracing.trace(source="fixture", request_id="R09", message_sha=tracing.message_digest(line)) as run:
        preview = run_preview()
    row = run.to_dict()
    assert preview.trace_id == row["trace_id"] and row["status"] == "ok"
    assert all(s["ms"] >= 0 for s in row["stages"]) and all(s["ms"] >= 0 for s in row["spans"])
    assert abs(sum(s["ms"] for s in row["stages"]) - row["total_ms"]) < 0.05
    names = {s["name"] for s in row["spans"]}
    assert {"llm.call", "validation", "order_lookup", "allocation", "eligibility", "explanation_check"} <= names
    dumped = json.dumps(row, default=str)
    assert SECRET not in dumped and line not in dumped and "Cotton Club" not in dumped   # Digest only, no raw text.


def test_failed_evaluation_still_produces_a_closed_trace():
    with pytest.raises(rehearsal.RehearsalMiss):
        with tracing.trace(source="fixture") as run, intake.extraction_source(rehearsal.make_source("fixture")):
            orders, workshops, _ = desk.load_inputs()
            desk.make_preview("Typed request with no fixture", desk.TODAY, PRESETS["lateness"], orders, workshops,
                              {w: s.queue0 for w, s in workshops.items()}, Allocator(PRESETS["lateness"]), 0, "fixture")
    row = run.to_dict()
    assert row["status"] == "error" and row["error"] == "rehearsal_miss"
    assert all(s["ms"] >= 0 for s in row["spans"])


def test_tracing_does_not_change_the_decision():
    plain = run_preview()
    with tracing.trace(source="fixture"):
        traced = run_preview()
    assert plain.trace_id is None and traced.trace_id
    assert plain.response.decision_record["chosen_workshop"] == traced.response.decision_record["chosen_workshop"]
    assert plain.response.decision_record["candidates"] == traced.response.decision_record["candidates"]


def test_trace_log_keeps_only_the_newest_entries(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, "RETENTION", 5)
    path = tmp_path / "t.jsonl"
    for i in range(8):
        tracing.save({"trace_id": str(i), "meta": {}, "stages": [], "spans": []}, path)
    assert [r["trace_id"] for r in tracing.load(path)] == ["3", "4", "5", "6", "7"]


def test_one_evaluation_writes_one_trace_and_reruns_add_none(app):
    app.button(key="inbox_R09").click().run()
    app.button(key="desk_dispatch").click().run()
    first = tracing.load()
    assert len(first) == 1 and first[0]["meta"]["source"] == "fixture" and first[0]["meta"]["request_id"] == "R09"
    page(app, "Audit Trail")
    page(app, "Dispatch")
    assert len(tracing.load()) == 1


# Confirm once, the right log, the right record ----------------------------------------

def test_confirm_writes_once_updates_the_queue_once_and_opens_that_record(app):
    app.button(key="inbox_R09").click().run()
    app.button(key="desk_dispatch").click().run()
    preview = app.session_state["desk_preview"]
    chosen = preview.response.decision_record["chosen_workshop"]
    before = app.session_state["desk_queues"][chosen]
    app.button(key="desk_confirm").click().run()
    after = app.session_state["desk_queues"][chosen]
    assert after > before and len(records.load(desk.REHEARSAL_LOG)) == 1
    assert "desk_confirm" not in [b.key for b in app.button]           # The button is gone: no second write possible.
    for _ in range(2):
        app.run()
    assert app.session_state["desk_queues"][chosen] == after and len(records.load(desk.REHEARSAL_LOG)) == 1
    saved = records.load(desk.REHEARSAL_LOG)[0]
    assert saved["decision_record"]["constraints_applied"]["confirmation"]["trace_id"] == preview.trace_id
    app.button(key="desk_view_audit").click().run()
    assert not app.exception and app.session_state["desk_page"] == "Audit Trail"
    assert app.session_state["audit_log"] == "rehearsal" and app.session_state["audit_opened"] == saved["timestamp"]
    assert "audit_focus" not in app.session_state                      # Opened once, not on every rerun.
    assert not records.DEFAULT_PATH.exists()


def test_audit_log_choice_keeps_demo_and_rehearsal_out_of_the_live_log():
    assert desk.audit_path("live") is None and desk.audit_log_name("live") == "live"
    assert desk.audit_path("live", demo=True) == desk.REHEARSAL_LOG and desk.audit_log_name("live", demo=True) == "rehearsal"
    for source in ("cached", "fixture"):
        assert desk.audit_path(source) == desk.REHEARSAL_LOG and desk.audit_log_name(source) == "rehearsal"


def test_performance_view_is_separate_and_says_not_yet_measured(app, monkeypatch, tmp_path):
    from ui import performance
    monkeypatch.setattr(performance, "RESULTS", tmp_path / "no-results")
    app.button(key="inbox_R09").click().run()
    app.button(key="desk_dispatch").click().run()
    page(app, "Audit Trail")
    app.segmented_control(key="_w_audit_view").set_value("performance").run()
    text = " ".join(m.value for m in app.markdown)
    assert not app.exception and "Execution traces" in text and "Not yet measured." in text
    assert "Planned run (dry run)" in text and "Confirmed decisions" not in text


# Benchmark ---------------------------------------------------------------------------

def test_benchmark_dry_run_sends_nothing_and_writes_nothing(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC", "OPENAI"))}
    results = ROOT / "benchmarks" / "results"
    existed = results.exists()
    out = subprocess.run([sys.executable, str(ROOT / "benchmarks/run_models.py")], capture_output=True, text=True, env=env, timeout=120)
    assert out.returncode == 0, out.stderr
    plan = json.loads(out.stdout.split("\n\nDry run")[0])
    assert plan["calls"] == plan["cases"] * 2 * 3 and plan["cases"] == 43
    assert "Dry run: no API request was sent." in out.stdout
    assert results.exists() == existed


def test_benchmark_cost_and_decision_rule():
    sys.path.insert(0, str(ROOT / "benchmarks"))
    import run_models
    assert run_models.price("claude-sonnet-5-5", {"input_tokens": 3981, "output_tokens": 247}) == pytest.approx(0.010432)
    assert run_models.price("claude-haiku-5-5", {"input_tokens": 3981, "output_tokens": 247}) == pytest.approx(0.0005216)
    assert run_models.price("claude-haiku-5-5", {"input_tokens": 200_000, "output_tokens": 0}) == pytest.approx(0.1)  # Long prompt rate.
    base = {"stress_accuracy": {"critical_field_rate": .95, "critical_errors": [], "clarification_recall": 1.0},
            "schema_valid_rate": 1.0, "e2e_ms": {"p50": 1000.0}, "cost": {"mean_per_success_usd": .01}}
    slow = {**base, "e2e_ms": {"p50": 900.0}, "cost": {"mean_per_success_usd": .001}}
    verdict = run_models.decide({"claude-sonnet-5-5": base, "claude-haiku-5-5": slow})
    assert verdict["checks"]["faster_end_to_end"] is False and verdict["verdict"].startswith("Keep Sonnet 5.5")
    fast = {**slow, "e2e_ms": {"p50": 500.0}}
    verdict = run_models.decide({"claude-sonnet-5-5": base, "claude-haiku-5-5": fast})
    assert all(verdict["checks"].values()) and "keep Sonnet as the default until the human labels" in verdict["verdict"]


def test_choosing_a_clarification_option_evaluates_again_without_a_second_click(app):
    app.button(key="inbox_R01").click().run()
    app.button(key="desk_dispatch").click().run()
    options = [b.key for b in app.button if b.key and b.key.startswith("desk_option_")]
    assert options and len(tracing.load()) == 1
    original = app.session_state["desk_message"]
    app.button(key=options[0]).click().run()
    order = options[0].removeprefix("desk_option_")
    assert app.session_state["desk_message"] == original          # The message is never rewritten.
    assert len(tracing.load()) == 2                                # Read again in the same click.
    parsed = app.session_state["desk_preview"].response.parsed_request
    assert parsed.order_id == order and parsed.answers_applied[0]["field"] == "order_id"
    assert parsed.answers_applied[0]["by"] == "dispatcher" and parsed.answers_applied[0]["at"]


def test_confirmed_deadline_answer_is_applied_by_python_and_kept_in_the_record(app):
    app.button(key="inbox_R05").click().run()
    app.button(key="desk_dispatch").click().run()
    assert app.session_state["desk_preview"].response.parsed_request.behaviour == "clarify"
    assert "qa_date_file" in [b.key for b in app.button]           # The date on file is offered as a one-tap answer.
    app.date_input(key="qa_date_pick").set_value(__import__("datetime").date(2026, 4, 20)).run()
    app.button(key="qa_date_use").click().run()
    preview = app.session_state["desk_preview"]
    parsed = preview.response.parsed_request
    assert parsed.behaviour == "allocate" and parsed.due_date.isoformat() == "2026-04-20"
    change = parsed.answers_applied[0]
    assert (change["field"], change["previous"], change["value"], change["previous_source"]) == ("due_date", "2026-04-26", "2026-04-20", "orders.csv")
    app.button(key="desk_confirm").click().run()
    saved = records.load(desk.REHEARSAL_LOG)[0]
    assert saved["decision_record"]["constraints_applied"]["confirmation"]["changes"][0]["value"] == "2026-04-20"


def test_split_and_escalation_are_explicit_choices_with_their_own_records(app):
    app.button(key="inbox_R30").click().run()
    app.button(key="desk_dispatch").click().run()
    queues = dict(app.session_state["desk_queues"])
    app.button(key="desk_confirm_split").click().run()
    saved = records.load(desk.REHEARSAL_LOG)
    assert not app.exception and len(saved) == 1
    split = saved[0]["decision_record"]["split_allocation"]
    assert sum(p["pieces"] for p in split["parts"]) == 1500 and saved[0]["decision_record"]["constraints_applied"]["confirmation"]["split"]
    changed = {w for w in queues if app.session_state["desk_queues"][w] != queues[w]}
    assert changed == {p["workshop_id"] for p in split["parts"]}   # Each part loads only its own workshop.
    app.button(key="inbox_R28").click().run()
    app.button(key="desk_dispatch").click().run()
    before = dict(app.session_state["desk_queues"])
    app.button(key="desk_escalate").click().run()
    rows = records.load(desk.REHEARSAL_LOG)
    assert len(rows) == 2 and rows[1]["decision_record"]["constraints_applied"]["confirmation"]["escalated"]
    assert app.session_state["desk_queues"] == before              # Escalating allocates nothing.


def test_inbox_batch_run_previews_everything_and_confirms_only_on_request(app):
    page(app, "Audit Trail")
    app.segmented_control(key="_w_audit_view").set_value("batch").run()
    app.button(key="batch_run_btn").click().run()
    batch = app.session_state["batch_run"]
    assert len(batch["rows"]) == 30 and not desk.REHEARSAL_LOG.exists()   # A preview only.
    ready = [r for r in batch["rows"] if r["outcome"] == "ready"]
    assert ready and all(r["evidence"] for r in ready)
    app.button(key="batch_confirm").click().run()
    saved = records.load(desk.REHEARSAL_LOG)
    assert len(saved) == len(ready) and all(r["decision_record"]["constraints_applied"]["confirmation"]["batch_review"] for r in saved)
    assert not records.DEFAULT_PATH.exists()


def test_benchmark_scores_against_human_labels_only_when_all_30_exist():
    sys.path.insert(0, str(ROOT / "benchmarks"))
    import run_models
    # Synthetic test rows, not labels: they exercise the scoring code only.
    labels = {f"R{i:02d}": {"expected_behaviour": "clarify", "expected_order_id": "", "expected_pieces": "",
                            "expected_category": "", "expected_due": ""} for i in range(1, 31)}
    rows = [{"case": "R01", "trial": 1, "status": "ok", "behaviour": "clarify"},
            {"case": "R02", "trial": 1, "status": "ok", "behaviour": "allocate"}]
    assert run_models.human_accuracy(rows, dict(list(labels.items())[:29])) is None   # Partial labels are not a reference.
    scored = run_models.human_accuracy(rows, labels)
    assert scored["behaviour_rate"] == 0.5 and scored["cases"] == 2 and len(scored["critical_errors"]) == 1
    assert "excluded_workshops" not in scored["fields"]
