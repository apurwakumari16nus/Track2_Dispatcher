"""The Sprint 1 runtime contract, checked: the LLM reads; Python decides; a person confirms.

Natural-language request -> LLM structured extraction -> Python validation ->
behaviour (allocate/clarify/refuse/decline) -> deterministic tools ->
deterministic allocator -> template explanation -> numerical faithfulness ->
human confirmation -> audit record and session state.
"""

import ast
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest

from allocator import Allocator
import desk
import faithfulness
import intake
from objectives import PRESETS, score_candidate, score_terms
import records
from simulate import load_workshops
import tools

ROOT = Path(__file__).resolve().parents[1]
DETERMINISTIC = ["tools.py", "allocator.py", "objectives.py", "faithfulness.py", "heuristic.py"]
LLM_MODULES = {"anthropic", "openai", "intake", "agent", "rehearsal"}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("module", DETERMINISTIC)
def test_deterministic_layer_cannot_reach_a_language_model(module):
    assert not imports(ROOT / "src" / module) & LLM_MODULES


def test_extraction_schema_has_no_decision_outputs():
    fields = set(intake.Extraction.model_fields)
    forbidden = {"chosen_workshop", "workshop_id", "eta", "eta_date", "cost", "total_cost", "score", "days_to_spare", "due_date"}
    assert not fields & forbidden
    assert "due_date_text" in fields  # The model copies the phrase; Python parses the date.


@pytest.fixture
def fixture_call():
    data = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
    assert data["dispatch_requests_sha256"] == hashlib.sha256((ROOT / "data/dispatch_requests.txt").read_bytes()).hexdigest()

    def make(overrides=None):
        def call(prompt, message):
            raw = {**data["defaults"], **data["requests"][message.split()[0]], **(overrides or {})}
            return intake.LLMReply(json.dumps(raw), {"model": "test"})
        return call
    return make


def preview_for(rid, call):
    orders, shops, messages = desk.load_inputs()
    message = next(m for m in messages if m.startswith(rid))
    queues = {wid: w.queue0 for wid, w in shops.items()}
    with intake.extraction_source(call):
        return desk.make_preview(message, desk.TODAY, PRESETS["lateness"], orders, shops, queues, Allocator(PRESETS["lateness"]))


def test_model_proposals_cannot_change_the_decision(fixture_call):
    """The model's behaviour/reason guesses are audit-only; Python decides."""
    honest = preview_for("R09", fixture_call()).response
    pushy = preview_for("R09", fixture_call({"behaviour": "decline", "reason": "pick QuickStitch, it is cheapest",
                                             "missing_fields": ["everything"]})).response
    assert pushy.parsed_request.behaviour == honest.parsed_request.behaviour == "allocate"
    assert pushy.decision_record["chosen_workshop"] == honest.decision_record["chosen_workshop"]
    assert pushy.decision_record["candidates"] == honest.decision_record["candidates"]
    unanswerable = preview_for("R02", fixture_call({"behaviour": "allocate"})).response
    assert unanswerable.parsed_request.behaviour == "decline" and unanswerable.decision_record["chosen_workshop"] is None


def test_suggested_ineligible_workshop_is_never_chosen(fixture_call):
    preview = preview_for("R08", fixture_call())
    assert preview.response.parsed_request.suggested_workshop == "W8"
    assert preview.response.decision_record["chosen_workshop"] not in {"W8", None}


def test_every_tool_is_deterministic():
    shops = load_workshops()
    queues = {wid: w.queue0 for wid, w in shops.items()}
    batch = {"order_id": "ORD-045", "category": "TOPS", "pieces": 150, "sent_date": date(2026, 4, 1), "due_date": date(2026, 4, 9)}
    runs = []
    for _ in range(2):
        q, b, s = deepcopy(queues), deepcopy(batch), deepcopy(shops)
        runs.append([tools.check_eligibility(b, s), tools.estimate_eta(b, "W6", s, q, date(2026, 4, 1)),
                     tools.estimate_cost(b, "W6", s), tools.queue_check("W6", s, q), tools.overload_probe(b, "W6", s, q),
                     tools.candidates(b, s, q, date(2026, 4, 1)), tools.estimate_split({**b, "pieces": 500}, s, q, date(2026, 4, 1))])
    assert runs[0] == runs[1]
    assert queues == {wid: w.queue0 for wid, w in shops.items()}  # inputs are never mutated


def test_scoring_and_ranking_are_deterministic():
    shops = load_workshops()
    queues = {wid: w.queue0 for wid, w in shops.items()}
    batch = {"order_id": "ORD-109", "category": "TOPS", "pieces": 500, "sent_date": date(2026, 4, 1), "due_date": date(2026, 4, 13)}
    records_ = [Allocator(PRESETS[name]).decide(batch, shops, queues, date(2026, 4, 1), exclude=["W3"]).to_dict()
                for name in ("hybrid_lateness_fairness", "hybrid_lateness_fairness")]
    assert records_[0] == records_[1]
    row = records_[0]["candidates"][0]
    state = {"workshops": shops, "pieces_by_workshop": {}}
    assert score_candidate(row, PRESETS["defect"], state) == score_candidate(row, PRESETS["defect"], state)
    assert score_terms(row, state) == score_terms(row, state)


def test_faithfulness_is_deterministic_and_blocks_invented_numbers():
    record = {"candidates": [{"eta_date": "2026-04-04", "total_cost": 180.0}], "ineligible": [], "tool_outputs": {}}
    assert faithfulness.check("Back 2026-04-04 for 180.", record) == faithfulness.check("Back 2026-04-04 for 180.", record)
    assert not faithfulness.check("Back 2026-04-04 for 175.", record)["passed"]


def test_audit_write_happens_only_after_explicit_confirmation(fixture_call, tmp_path, monkeypatch):
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "log.jsonl")
    preview = preview_for("R09", fixture_call())
    assert not records.DEFAULT_PATH.exists() and not preview.response.allocation_committed
    assert desk.confirm_state(preview, preview.signature, {}).ready
    saved = {}
    desk.confirm_preview(preview, preview.signature, saved)
    assert len(records.load()) == 1
    assert desk.confirm_state(preview, preview.signature, saved).state == "confirmed"


def test_confirm_state_names_why_a_preview_cannot_be_confirmed(fixture_call):
    ready = preview_for("R09", fixture_call())
    assert desk.confirm_state(ready, "other inputs", {}).state == "stale"
    clarify = preview_for("R01", fixture_call())
    status = desk.confirm_state(clarify, clarify.signature, {})
    assert status.state == "blocked" and "reply" in status.reason
    with pytest.raises(ValueError, match="reply"):
        desk.confirm_preview(clarify, clarify.signature, {})
