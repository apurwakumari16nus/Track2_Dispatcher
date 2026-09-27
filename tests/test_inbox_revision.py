"""v3 data regression facts; synthetic extractions are not human gold labels."""
from datetime import date
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import agent
import intake
from objectives import PRESETS
from simulate import load_workshops

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evaluate(monkeypatch):
    fixture = json.loads((ROOT / 'tests/fixtures/intake_extractions.json').read_text())
    source = ROOT / 'data/dispatch_requests.txt'
    assert fixture['dispatch_requests_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    messages = {line.split()[0]: line for line in source.read_text().splitlines() if line.startswith('R')}
    def fake(prompt, message):
        payload = {**fixture['defaults'], **fixture['requests'][message.split()[0]]}
        return intake.LLMReply(json.dumps(payload), {'model': 'synthetic-v3', 'temperature': 0})
    monkeypatch.setattr(intake, '_call_llm', fake)
    workshops = load_workshops()
    orders = pd.read_csv(ROOT / 'data/orders.csv')
    return lambda rid: agent.handle(messages[rid], date(2026, 4, 1), orders, workshops,
                                    {wid: w.queue0 for wid, w in workshops.items()}, PRESETS['lateness'])


@pytest.mark.parametrize('rid,order,pieces,due', [
    ('R04','ORD-041',600,'2026-04-21'), ('R06','ORD-096',1000,'2026-04-17'),
    ('R07','ORD-063',100,'2026-04-29'), ('R16','ORD-024',300,'2026-04-15'),
    ('R17','ORD-017',800,'2026-04-10'), ('R22','ORD-040',1200,'2026-04-21'),
    ('R23','ORD-005',500,'2026-04-20'), ('R26','ORD-010',1000,'2026-04-25'),
    ('R27','ORD-095',800,'2026-04-26'),
])
def test_nine_revised_messages_extract_current_facts_and_have_on_time_options(evaluate, rid, order, pieces, due):
    response = evaluate(rid)
    parsed = response.parsed_request
    assert (parsed.order_id, parsed.pieces, parsed.due_date.isoformat()) == (order, pieces, due)
    assert parsed.behaviour == 'allocate'
    assert not response.already_late and response.awkward_case is None
    assert any(c['days_to_spare'] >= 0 for c in response.decision_record['candidates'])
    assert response.faithfulness['passed']
    if rid == 'R27':
        assert parsed.preference == 'lowest_defect'
    if rid == 'R23':
        assert parsed.split_allowed


@pytest.mark.parametrize('rid,shop,eta,spare,already_late', [
    ('R20','W2','2026-04-17',-13,False),
    ('R28','W1','2026-04-09',-11,True),
    ('R30','W1','2026-04-11',-6,False),
])
def test_three_impossible_deadlines_have_numerical_warnings_options_and_no_commit(evaluate, rid, shop, eta, spare, already_late):
    response = evaluate(rid)
    record = response.decision_record
    chosen = next(c for c in record['candidates'] if c['workshop_id'] == record['chosen_workshop'])
    assert (record['chosen_workshop'], chosen['eta_date'], chosen['days_to_spare']) == (shop, eta, spare)
    assert response.awkward_case == 'none_makes_date' and response.already_late == already_late
    assert 'No eligible whole-batch option meets the deadline' in response.explanation_text and eta in response.explanation_text
    assert record['options'] and not response.allocation_committed
    assert response.faithfulness['passed']
