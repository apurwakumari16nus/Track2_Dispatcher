"""Evaluator tests use synthetic extractions, never API calls or human-label edits."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

import agent
import intake
from objectives import PRESETS
from simulate import load_workshops

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_inbox", ROOT / "eval/run_inbox.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def inputs():
    messages = runner.inbox_messages(ROOT / "data/dispatch_requests.txt")
    # Missing-label cases remain stable after the team supplies real labels.
    labels = {rid: {key: "" for key in runner.LABEL_COLUMNS if key != "request_id"} for rid in messages}
    orders = pd.read_csv(ROOT / "data/orders.csv")
    shops = load_workshops()
    fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    return messages, labels, orders, shops, fixture


def test_all_thirty_rows_cache_replay_and_missing_labels_are_not_passes(tmp_path, inputs):
    messages, labels, orders, shops, fixture = inputs
    before = (ROOT / "eval/labels.csv").read_bytes()
    cache = runner.CachedLLM(tmp_path, "synthetic-fixture", fixture=fixture)
    first, details = runner.run_evaluation(messages, labels, orders, shops, cache)
    assert list(first.columns) == runner.COLUMNS and len(first) == 30
    assert first.behaviour_correct.isna().all()
    assert first.actual_behaviour.isin(runner.BEHAVIOURS).all()
    assert first.faithfulness_passed.all()
    assert cache.misses == 30 and cache.hits == 0
    assert len(list(tmp_path.glob("*.json"))) == 30
    assert all(detail["cache_key"] and detail["response"] for detail in details)
    second_cache = runner.CachedLLM(tmp_path, "synthetic-fixture", fixture=fixture, offline=True)
    second, details2 = runner.run_evaluation(messages, labels, orders, shops, second_cache)
    assert second_cache.hits == 30 and second_cache.misses == 0
    pd.testing.assert_frame_equal(first, second)
    assert details == details2
    assert (ROOT / "eval/labels.csv").read_bytes() == before
    assert "N/A (0 scored)" in runner.summary_table(first)
    assert "not end-to-end accuracy" in runner.failure_report(first, details, "mock")


def test_live_cache_hits_do_not_call_provider_and_inputs_invalidate_cache(tmp_path):
    calls = []
    def call(prompt, message):
        calls.append((prompt, message))
        return intake.LLMReply('{"value": 1}', {"model": "requested-model", "temperature": 0})
    cache = runner.CachedLLM(tmp_path, "requested-model", call=call)
    assert cache("schema today catalog", "message").content == '{"value": 1}'
    assert cache("schema today catalog", "message").content == '{"value": 1}'
    assert len(calls) == 1
    cache("changed prompt", "message")
    cache("schema today catalog", "changed message")
    other = runner.CachedLLM(tmp_path, "other-model", call=call)
    other("schema today catalog", "message")
    assert len(calls) == 4
    offline = runner.CachedLLM(tmp_path, "requested-model", offline=True,
                               call=lambda *a: pytest.fail("cache must not call provider"))
    offline("schema today catalog", "message")
    with pytest.raises(intake.IntakeError, match="Cache miss"):
        offline("no cache", "message")
    path = tmp_path / f"{cache.last_key}.json"
    entry = json.loads(path.read_text())
    entry["payload"]["content"] = "tampered"
    path.write_text(json.dumps(entry))
    with pytest.raises(ValueError, match="integrity"):
        cache("schema today catalog", "changed message")


def test_refusals_with_provider_evidence_replay_but_configuration_errors_do_not_cache(tmp_path):
    def refused(*args):
        raise intake.IntakeError("provider refused", raw_response="", metadata={"response_id": "response-1"})
    cache = runner.CachedLLM(tmp_path, "model", call=refused)
    for _ in range(2):
        with pytest.raises(intake.IntakeError, match="provider refused"):
            cache("prompt", "message")
    assert cache.hits == 1 and cache.misses == 1
    missing = runner.CachedLLM(tmp_path, "", call=lambda *a: pytest.fail("no API call"))
    with pytest.raises(intake.IntakeError, match="not configured"):
        missing("prompt", "message")
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_reference_resolution_uses_source_not_parsed_requests(inputs):
    messages, labels, orders, shops, _ = inputs
    ref = runner.reference(messages["R01"], labels["R01"], orders, shops)
    expected = orders[(orders.customer == "Harbor Knits") & (orders["product"] == "Scarf") & (orders.status == "IN_PROGRESS")]
    assert ref["candidate_order_ids"] == sorted(expected.order_id.tolist())
    ref = runner.reference(messages["R12"], labels["R12"], orders, shops)
    assert ref["exclude"] == ["W1"] and ref["imposed_by"] == "Boss"
    ref = runner.reference(messages["R21"], labels["R21"], orders, shops)
    assert ref["preference"] == "cheapest" and ref["must_make_date"]
    ref = runner.reference(messages["R05"], labels["R05"], orders, shops)
    assert ref["due_date"] is None and ref["unconfirmed_date"]
    override = {**labels["R30"], "expected_pieces": "70", "expected_due": "2026-05-09"}
    ref = runner.reference(messages["R30"], override, orders, shops)
    assert ref["pieces"] == 70 and ref["due_date"] == date(2026, 5, 9)


def test_constraint_aware_heuristic_by_hand(inputs):
    _, _, _, source, _ = inputs
    shops = {"W1": replace(source["W1"], capacity=100, lead_days=0, cost=1, defect_rate=0.2),
             "W2": replace(source["W2"], capacity=100, lead_days=0, cost=2, defect_rate=0.01)}
    queues = {"W1": 5, "W2": 0}
    ref = dict(order_id="ORD-099", pieces=100, category="TOPS", due_date=date(2026, 4, 3),
               exclude=[], preference="cheapest", must_make_date=True)
    assert runner.benchmark(ref, shops, queues)["chosen_workshop"] == "W2"
    ref["due_date"] = date(2026, 5, 1)
    assert runner.benchmark(ref, shops, queues)["chosen_workshop"] == "W1"
    ref["preference"] = "lowest_defect"
    assert runner.benchmark(ref, shops, queues)["chosen_workshop"] == "W2"
    ref["exclude"] = ["W2"]
    assert runner.benchmark(ref, shops, queues)["chosen_workshop"] == "W1"
    ref["exclude"] = ["W1", "W2"]
    assert runner.benchmark(ref, shops, queues)["chosen_workshop"] is None


def test_independent_checks_catch_mutated_extraction_choice_template_and_late_flag(tmp_path, inputs):
    messages, labels, orders, shops, fixture = inputs
    cache = runner.CachedLLM(tmp_path, "synthetic-fixture", fixture=fixture)
    _, details = runner.run_evaluation(messages, labels, orders, shops, cache)
    d = next(d for d in details if d["request_id"] == "R30")
    value = d["response"]
    fields = deepcopy(value["parsed_request"])
    fields["due_date"] = date.fromisoformat(fields["due_date"])
    response = agent.AgentResponse(**{**value, "parsed_request": intake.ParsedRequest(**fields)})
    ref = runner.reference(messages["R30"], labels["R30"], orders, shops)
    queues = {wid: w.queue0 for wid, w in shops.items()}
    response.parsed_request.pieces += 123
    response.decision_record["chosen_workshop"] = "W7"
    response.explanation_text += " Discount 987654321."
    metrics, notes, _, mismatches = runner.assess(response, labels["R30"], ref, orders, shops, queues)
    assert metrics["decision_correct"] is False and metrics["constraint_honoured"] is False
    assert metrics["faithfulness_passed"] is False and "pieces" in mismatches
    ref["due_date"] = date(2026, 3, 1)
    response.already_late = False
    metrics, *_ = runner.assess(response, labels["R30"], ref, orders, shops, queues)
    assert metrics["already_late_flagged_when_needed"] is False


def test_failure_report_contains_each_failed_row_and_no_invented_gold(tmp_path, inputs):
    messages, labels, orders, shops, fixture = inputs
    # Deliberately wrong test-only label. Never write to the team's CSV.
    labels = deepcopy(labels)
    labels["R30"]["expected_behaviour"] = "decline"
    results, details = runner.run_evaluation(messages, labels, orders, shops,
        runner.CachedLLM(tmp_path, "synthetic-fixture", fixture=fixture))
    report = runner.failure_report(results, details, "mock")
    failed_ids = set(results[results[list(runner.CHECKS)].eq(False).any(axis=1)].request_id)
    import re
    assert set(re.findall(r"^## (R\d+)$", report, re.M)) == failed_ids
    assert "R30" in failed_ids and messages["R30"] in report
    assert "What the system did" in report and "What it should have done" in report
    assert "Layer hypothesis:" in report and "Synthetic extraction" in report


def test_operational_errors_preserve_all_rows_and_do_not_become_business_declines(tmp_path, inputs):
    messages, labels, orders, shops, _ = inputs
    results, details = runner.run_evaluation(messages, labels, orders, shops, runner.CachedLLM(tmp_path, ""))
    assert len(results) == 30 and set(results.actual_behaviour) == {"error"}
    assert not results.decision_correct.any() and not results.faithfulness_passed.any()
    assert results.behaviour_correct.isna().all()
    assert "Operational errors: **30**" in runner.failure_report(results, details, "live/cached")


def test_cli_mock_outputs_and_offline_replay(tmp_path, capsys, inputs):
    label_path = tmp_path / "labels.csv"
    pd.DataFrame([{"request_id": rid, **row} for rid, row in inputs[1].items()], columns=runner.LABEL_COLUMNS).to_csv(label_path, index=False)
    args = ["--mock", "--output-dir", str(tmp_path / "output"), "--cache-dir", str(tmp_path / "cache"), "--labels", str(label_path)]
    assert runner.main(args) == 0
    path = tmp_path / "output/inbox_results.csv"
    before = path.read_bytes()
    assert runner.main([*args, "--offline"]) == 0
    assert path.read_bytes() == before
    output = capsys.readouterr().out
    assert "Cache hits: 30; misses: 0" in output
    assert "human labels: 0/30" in output
    audit = json.loads((tmp_path / "output/inbox_audit.json").read_text())
    assert audit["mode"] == "mock" and len(audit["requests"]) == 30
    assert set(audit["input_hashes"]) == {"inbox", "orders", "workshops", "labels"}


def test_summary_denominators_include_misclassification_but_not_missing_gold():
    frame = pd.DataFrame([
        dict(expected_behaviour="allocate", actual_behaviour="allocate", behaviour_correct=True, decision_correct=True, faithfulness_passed=True),
        dict(expected_behaviour="allocate", actual_behaviour="decline", behaviour_correct=False, decision_correct=False, faithfulness_passed=True),
        dict(expected_behaviour="", actual_behaviour="allocate", behaviour_correct=None, decision_correct=True, faithfulness_passed=True),
    ])
    for column in ("behaviour_correct", "decision_correct", "faithfulness_passed"):
        frame[column] = frame[column].astype("boolean")
    assert "| allocate | 2 | 50.0% (2 scored) | 50.0% (2 scored) | 100.0% (2 scored) |" in runner.summary_table(frame)


def test_wrong_clarification_options_fail_without_trusting_record_evidence(tmp_path, inputs):
    messages, labels, orders, shops, fixture = inputs
    cache = runner.CachedLLM(tmp_path, "synthetic-fixture", fixture=fixture)
    from unittest.mock import patch
    with patch.object(intake, "_call_llm", cache):
        response = agent.handle(messages["R01"], runner.TODAY, orders, shops,
                                {wid: w.queue0 for wid, w in shops.items()}, PRESETS["lateness"])
    response.decision_record["tool_outputs"]["order_options"] = []
    ref = runner.reference(messages["R01"], labels["R01"], orders, shops)
    metrics, *_ = runner.assess(response, labels["R01"], ref, orders, shops, {wid: w.queue0 for wid, w in shops.items()})
    assert metrics["decision_correct"] is False


def test_unrecognized_human_constraint_is_unscored(inputs):
    messages, labels, orders, shops, _ = inputs
    label = {**labels["R30"], "constraint": "require specialist hand embroidery"}
    assert not runner.reference(messages["R30"], label, orders, shops)["constraint_reference_complete"]
