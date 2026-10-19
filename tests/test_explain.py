"""Explanations read the recorded decision; they never re-decide it."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import desk
import intake
from objectives import PRESETS
from allocator import Allocator
from ui import explain

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def previews():
    fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    assert fixture["dispatch_requests_sha256"] == hashlib.sha256((ROOT / "data/dispatch_requests.txt").read_bytes()).hexdigest()

    def fake(prompt, message):
        return intake.LLMReply(json.dumps({**fixture["defaults"], **fixture["requests"][message.split()[0]]}),
                               {"model": "synthetic-fixture", "extraction_source": "fixture"})

    orders, shops, messages = desk.load_inputs()
    queues = {wid: w.queue0 for wid, w in shops.items()}
    out = {}
    with intake.extraction_source(fake):
        for message in messages:
            out[message.split()[0]] = desk.make_preview(message, desk.TODAY, PRESETS["lateness"], orders, shops, queues,
                                                        Allocator(PRESETS["lateness"]))
    return out, shops


def test_selection_order_reproduces_every_recorded_choice(previews):
    items, _ = previews
    checked = 0
    for preview in items.values():
        record = preview.response.decision_record
        if record["chosen_workshop"]:
            assert explain.selection_order(record)[0]["workshop_id"] == record["chosen_workshop"]
            checked += 1
    assert checked >= 15


def test_why_won_uses_recorded_values_and_names_runner_up(previews):
    items, _ = previews
    won = explain.why_won(items["R09"].response.decision_record)
    assert won["kind"] == "score" and won["chosen"]["name"] == "Nimble Needle"
    assert won["runner_up"]["name"] in won["sentence"] and "days before" in won["sentence"]
    late = explain.why_won(items["R30"].response.decision_record)
    assert late["kind"] == "least_late" and "6 days late" in late["sentence"] and "11 Apr" in late["sentence"]
    cheapest = explain.why_won(items["R21"].response.decision_record)
    assert "cheapest permitted workshop that still makes" in cheapest["sentence"]
    for rid in ("R01", "R02"):
        assert explain.why_won(items[rid].response.decision_record) is None


def test_score_breakdown_sums_to_recorded_score(previews):
    items, _ = previews
    record = items["R09"].response.decision_record
    for item in explain.score_breakdown(record["candidates"], explain.effective_config(record["objective_name"])):
        assert sum(part["contribution"] for part in item["parts"]) == pytest.approx(item["score"], abs=1e-15)
        assert [p["active"] for p in item["parts"]] == [True, False, False, False, False]


def test_why_not_gives_deterministic_reasons(previews):
    items, shops = previews
    r12 = items["R12"].response.decision_record
    excluded = explain.why_not(r12, "W1", shops)
    assert excluded["status"] == "excluded" and "Boss" in " ".join(excluded["detail"])
    r08 = items["R08"].response.decision_record
    assert explain.why_not(r08, "W8", shops)["headline"] == "Trial batch cap exceeded"
    assert "400 pieces against a cap of 300" in explain.why_not(r08, "W8", shops)["detail"][0]
    assert explain.why_not(r08, "W7", shops)["headline"].startswith("Suspended")
    r21 = items["R21"].response.decision_record
    assert any(explain.why_not(r21, wid, shops)["status"] == "misses_date" for wid in shops)
    r30 = items["R30"].response.decision_record
    assert explain.why_not(r30, "W5", shops)["status"] == "later"
    r09 = items["R09"].response.decision_record
    outscored = explain.why_not(r09, "W8", shops)
    assert outscored["status"] == "outscored" and "Lower is better" in outscored["detail"][0]
    assert explain.why_not(r09, r09["chosen_workshop"], shops)["status"] == "chosen"
    assert explain.why_not(items["R01"].response.decision_record, "W1", shops)["status"] == "not_evaluated"


def test_trace_reports_only_steps_that_ran(previews):
    items, _ = previews
    preview = items["R01"]
    steps = explain.trace_steps(preview.response.to_dict(), agent_calls=preview.agent_calls, replayed=False,
                                confirmed=False, block_reason=preview.block_reason)
    status = {s["key"]: s["status"] for s in steps}
    assert status["extract"] == "done" and status["eligibility"] == "skipped" and status["select"] == "skipped"
    assert status["confirm"] == "skipped" and steps[0]["actor"] == "fixture"
    preview = items["R09"]
    steps = explain.trace_steps(preview.response.to_dict(), agent_calls=preview.agent_calls, replayed=True,
                                confirmed=False, block_reason=None)
    assert [s for s in steps if s["key"] == "replay"][0]["status"] == "done"
    assert [s for s in steps if s["key"] == "confirm"][0]["status"] == "pending"
    stages = explain.stage_status(steps)
    assert [k for k, _, _, _ in stages] == ["understand", "validate", "evaluate", "decide", "verify"]  # confirmation is separate
    assert all(v == "done" for _, _, _, v in stages)
    clarify = {k: v for k, _, _, v in explain.stage_status(explain.trace_steps(
        items["R01"].response.to_dict(), agent_calls=items["R01"].agent_calls, replayed=False, confirmed=False, block_reason="x"))}
    assert clarify["evaluate"] == "skipped" and clarify["decide"] == "skipped" and clarify["understand"] == "done"


def test_same_inputs_produce_the_same_decision(previews):
    """The architectural contract: identical inputs and history give the identical choice."""
    items, shops = previews
    orders, _, messages = desk.load_inputs()
    queues = {wid: w.queue0 for wid, w in shops.items()}
    fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())

    def fake(prompt, message):
        return intake.LLMReply(json.dumps({**fixture["defaults"], **fixture["requests"][message.split()[0]]}), {})

    message = next(m for m in messages if m.startswith("R25"))
    with intake.extraction_source(fake):
        again = [desk.make_preview(message, desk.TODAY, PRESETS["lateness"], orders, shops, dict(queues),
                                   Allocator(PRESETS["lateness"])) for _ in range(2)]
    first, second = (deepcopy(p.response.decision_record) for p in again)
    for record in (first, second):
        record["tool_outputs"].pop("call_trace")
    assert first == second
    assert first["chosen_workshop"] == items["R25"].response.decision_record["chosen_workshop"]


def test_deciding_metrics_show_only_what_the_rule_used(previews):
    items, _ = previews
    record = items["R09"].response.decision_record
    chosen, other = explain.chosen_row(record), explain.runner_up(record)
    rows = explain.deciding_metrics(record, chosen, other)
    assert [r["label"] for r in rows] == ["Total time", "Back by"]
    assert rows[0]["winner"] == f"{chosen['total_days']:.1f} days" and rows[0]["better"] is True
    late = items["R30"].response.decision_record
    assert explain.deciding_metrics(late, explain.chosen_row(late), explain.runner_up(late))[0]["label"] == "Days late"
    cheap = items["R21"].response.decision_record
    assert explain.deciding_metrics(cheap, explain.chosen_row(cheap), explain.runner_up(cheap))[0]["label"] == "Cost per piece"


def test_clarify_prompt_asks_the_right_question(previews):
    items, _ = previews
    r01 = items["R01"].response
    prompt = explain.clarify_prompt(r01.parsed_request.to_dict(), r01.decision_record["tool_outputs"]["order_options"])
    assert prompt["question"] == "Which Harbor Knits order do you mean?"
    assert {o["order_id"] for o in prompt["options"]} == {"ORD-061", "ORD-108"}
    r05 = items["R05"].response
    assert "confirmed new deadline" in explain.clarify_prompt(r05.parsed_request.to_dict(), [])["question"]


def test_reason_text_keeps_tool_numbers():
    assert explain.reason_text("batch of 400 exceeds 300-piece cap") == "Trial batch cap exceeded: 400 pieces against a cap of 300."
    assert explain.reason_text("cannot make ACCESSORIES") == "It is not equipped to make accessories."
    assert explain.reason_text("suspended").startswith("Suspended")
