from datetime import date, datetime
import json

import pytest

from agent import AgentResponse
from intake import ParsedRequest
import records


@pytest.fixture
def response():
    constraint = {"text": "Boss says avoid QuickStitch", "imposed_by": "Boss", "relayed_by": "Ravi"}
    parsed = ParsedRequest("R12", "Ravi", "request", due_date=date(2026, 4, 10), constraints=[constraint])
    record = {"timestamp": "2026-04-01T00:00:00", "candidates": [{"total_cost": 100}],
              "constraints_applied": {"statements": [constraint], "reported_by": "Ravi", "exclude": ["W1"]}}
    return AgentResponse(record, parsed, "Cost 100.", False, None, {"passed": True})


def test_append_load_preserve_evidence_date_sender_and_attribution(tmp_path, response):
    path = tmp_path / "records" / "decisions.jsonl"
    assert records.load(path) == [] and not path.exists()
    first = records.append(response, path)
    second = records.append(response, path)
    assert records.load(path) == [first, second]
    assert len(path.read_text().splitlines()) == 2
    assert datetime.fromisoformat(first["timestamp"]).utcoffset().total_seconds() == 0
    assert first["sender"] == "Ravi"
    assert first["constraints"]["statements"][0]["imposed_by"] == "Boss"
    assert first["constraints"]["statements"][0]["relayed_by"] == "Ravi"
    assert first["parsed_request"]["due_date"] == "2026-04-10"
    assert first["faithfulness"]["passed"]
    assert json.loads(path.read_text().splitlines()[0]) == first


def test_default_path_is_project_relative(tmp_path, response, monkeypatch):
    assert records.DEFAULT_PATH.parent.name == "records" and records.DEFAULT_PATH.name == "decisions.jsonl"
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "decisions.jsonl")
    records.append(response)
    assert len(records.load()) == 1


def test_tampered_or_nonfinite_record_is_rejected_before_file_write(tmp_path, response):
    path = tmp_path / "decisions.jsonl"
    response.explanation_text += " Invented discount 999."
    with pytest.raises(ValueError, match="unfaithful"):
        records.append(response, path)
    assert not path.exists()
    response.explanation_text = "Cost 100."
    response.decision_record["candidates"][0]["invalid"] = float("nan")
    with pytest.raises(ValueError):
        records.append(response, path)
    assert not path.exists()


@pytest.mark.parametrize("bad", ["{broken", "[1,2]", "null"])
def test_corrupt_log_reports_line_number(tmp_path, bad):
    path = tmp_path / "decisions.jsonl"
    path.write_text('{}\n' + bad + '\n')
    with pytest.raises(ValueError, match="line 2"):
        records.load(path)
