"""Queue anomaly detection, recovery, allocator wiring and real shock tracing."""

import copy
import csv
import io
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

from allocator import Allocator
from objectives import PRESETS
from simulate import load_workshops
from tools import ShockMonitor


def test_unvisited_workshops_cannot_be_flagged():
    monitor = ShockMonitor()
    assert monitor.observe({"W1": 100.0, "W2": 200.0}, 30) == []
    assert monitor.expected_queue == {}
    assert not monitor.is_flagged("W1")


def test_observation_ages_prediction_and_logs_actual_jump():
    monitor = ShockMonitor()
    monitor.record_allocation("W2", 3.1, 32)
    queues = {"W2": 13.8, "W1": 100.0}
    events = monitor.observe(queues, 33)

    assert len(events) == 1
    assert events[0]["workshop_id"] == "W2"
    assert events[0]["expected"] == pytest.approx(2.1)
    assert events[0]["observed"] == 13.8
    assert events[0]["jump"] == pytest.approx(11.7)
    assert events[0]["flagged_on_day"] == 33
    assert monitor.is_flagged("W2")
    assert not monitor.is_flagged("W1")
    assert queues == {"W2": 13.8, "W1": 100.0}
    assert monitor.expected_queue["W2"] == 3.1  # Anchored after-allocation prediction.


def test_threshold_is_strict_and_same_day_observations_do_not_double_age():
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 5.0, 10)
    assert monitor.observe({"W1": 6.0}, 12) == []  # Expected 3, jump exactly 3.
    assert monitor.observe({"W1": 6.01}, 12)[0]["expected"] == 3.0
    original = copy.deepcopy(monitor.flags)
    assert monitor.observe({"W1": 6.01}, 12) == []
    assert monitor.flags == original


def test_flag_persists_without_rebasing_and_clears_when_queue_recovers():
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 5.0, 10)
    original = monitor.observe({"W1": 10.0}, 11)[0]
    assert monitor.observe({"W1": 9.0}, 12) == []
    assert monitor.flags["W1"] == original
    monitor.observe({"W1": 6.0}, 13)  # Expected 2, still four days behind.
    assert monitor.is_flagged("W1")
    monitor.observe({"W1": 4.0}, 14)  # Expected 1, back within the threshold.
    assert not monitor.is_flagged("W1")
    assert monitor.cleared_flags[0]["cleared_on_day"] == 14
    assert monitor.cleared_flags[0]["expected_on_clear"] == 1.0
    assert original["flagged_on_day"] == 11
    assert monitor.observe({"W1": 8.0}, 15)[0]["flagged_on_day"] == 15


def test_prediction_floors_at_zero_and_missing_observations_do_not_clear_flags():
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 2.0, 0)
    assert monitor.observe({"W1": 4.0}, 10)[0]["expected"] == 0.0
    monitor.observe({}, 11)
    assert monitor.is_flagged("W1")
    monitor.observe({"W1": 0.0}, 20)
    assert not monitor.is_flagged("W1")


def test_new_allocation_updates_expected_queue_and_day_anchor():
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 3.0, 0)
    monitor.observe({"W1": 2.0}, 1)
    monitor.record_allocation("W1", 4.0, 1)  # Two additional processing days.
    assert monitor.observe({"W1": 3.0}, 2) == []
    assert monitor.expected_queue["W1"] == 4.0


def test_sending_more_work_to_suspect_does_not_erase_unexplained_excess():
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 2.0, 0)
    monitor.observe({"W1": 12.0}, 0)
    # Probe says 12 observed + 1 processing; preserve the ten unexplained days.
    monitor.record_allocation("W1", 13.0, 0)
    assert monitor.expected_queue["W1"] == 3.0
    assert monitor.observe({"W1": 13.0}, 0) == []
    assert monitor.is_flagged("W1")
    monitor.observe({"W1": 0.0}, 13)
    assert not monitor.is_flagged("W1")


def test_explicit_clear_is_idempotent_and_retains_prediction():
    monitor = ShockMonitor()
    monitor.record_allocation("W1", 1.0, 0)
    monitor.observe({"W1": 8.0}, 0)
    monitor.clear("W1")
    monitor.clear("W1")
    assert not monitor.is_flagged("W1")
    assert monitor.expected_queue == {"W1": 1.0}


@pytest.mark.parametrize("threshold", [-1.0, float("nan"), float("inf")])
def test_threshold_must_be_finite_and_nonnegative(threshold):
    with pytest.raises(ValueError):
        ShockMonitor(threshold)


def test_custom_threshold_and_backwards_days():
    monitor = ShockMonitor(threshold=5)
    monitor.record_allocation("W1", 2.0, 0)
    assert monitor.observe({"W1": 4.0}, 2) == []
    with pytest.raises(ValueError, match="nondecreasing"):
        monitor.observe({"W1": 4.0}, 1)
    with pytest.raises(ValueError, match="nondecreasing"):
        monitor.record_allocation("W1", 3.0, 1)


def test_allocator_updates_monitor_logs_detection_and_keeps_old_records_stable():
    source = load_workshops()
    workshops = {
        "W1": replace(source["W1"], capacity=100, lead_days=1),
        "W2": replace(source["W2"], capacity=100, lead_days=2),
    }
    day0 = date(2026, 4, 1)
    batch = {
        "order_id": "TRACE", "category": "TOPS", "pieces": 100,
        "sent_date": day0, "due_date": date(2026, 4, 30),
    }
    allocator = Allocator(PRESETS["robustness"])
    first = allocator.decide(batch, workshops, {"W1": 0.0, "W2": 0.0}, day0)
    assert first.chosen_workshop == "W1"
    assert allocator.shock_monitor.expected_queue == {"W1": 1.0}  # No transport.

    second = allocator.decide(
        batch, workshops, {"W1": 8.0, "W2": 0.0}, day0 + timedelta(days=1)
    )
    assert second.chosen_workshop == "W2"
    assert second.shock_flags == [{
        "workshop_id": "W1", "expected": 0.0, "observed": 8.0,
        "jump": 8.0, "flagged_on_day": 1,
    }]
    assert second.shock_events[0]["status"] == "suspect"
    w1 = next(cand for cand in second.candidates if cand["workshop_id"] == "W1")
    assert w1["shock_flagged"] is True
    assert w1["score_terms"]["robustness"] == 1.0
    saved = second.to_dict()

    recovered = allocator.decide(
        batch, workshops, {"W1": 0.0, "W2": 0.0}, day0 + timedelta(days=10)
    )
    assert recovered.shock_flags == []
    assert recovered.shock_events[0]["status"] == "cleared"
    assert recovered.shock_events[0]["cleared_on_day"] == 10
    assert second.to_dict() == saved
    assert json.loads(json.dumps(saved, allow_nan=False)) == saved


def test_real_shock_trace_emits_clean_csv_and_detects_without_target_input(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    events_path = tmp_path / "events.json"
    result = subprocess.run(
        [sys.executable, str(project_root / "eval" / "shock_trace.py"), "--events", str(events_path)],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    evidence = json.loads(events_path.read_text(encoding="utf-8"))
    detections = [event for event in evidence["events"] if event["status"] == "suspect"]
    recoveries = [event for event in evidence["events"] if event["status"] == "cleared"]

    assert evidence["shocked_workshop_id"] == "W2"
    assert evidence["shocked_workshop_name"] == "SteadyHands"
    # v3 adds a future mid-job closure to the queue immediately: evidence is
    # visible on day 26, before closure begins. Preserve/disclose this limitation.
    assert detections[0]["flagged_on_day"] == 26
    assert detections[0]["workshop_id"] == "W2"
    assert detections[0]["expected"] == pytest.approx(9.441176470588232)
    assert detections[0]["observed"] == pytest.approx(23.441176470588232)
    assert detections[0]["jump"] == pytest.approx(14)
    assert recoveries[0]["cleared_on_day"] == 47
    assert "future closure" in evidence["caveat"]
    assert [int(row["day"]) for row in rows] == list(range(len(rows)))
    assert sum(int(row["ours_pieces_while_suspect"]) for row in rows) == 0
    while_closed = [row for row in rows if 30 <= int(row["day"]) < 44]
    assert sum(int(row["random_pieces"]) for row in while_closed) > 0
    assert sum(int(row["ours_pieces"]) for row in while_closed) == 0
    assert int(rows[26]["ours_pieces"]) > 0  # Allocation preceding same-day detection.
    assert "W2 flagged on day 26" in result.stderr


def test_trace_labels_match_actual_harness_target_across_ten_seeds():
    import importlib.util
    import random
    from simulate import Simulator
    spec = importlib.util.spec_from_file_location("trace_review", Path(__file__).resolve().parents[1] / "eval/shock_trace.py")
    trace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trace)
    for seed in range(5105, 5115):
        # Independent observation: probe each workshop with a defect-free job
        # starting on day 31. Only the actual target incurs the closure delay.
        sim = Simulator(shock=True, seed=seed)
        source = sim.workshops
        sim.workshops = {wid: replace(w, defect_rate=0, queue0=0) for wid, w in source.items()}
        day0 = date(2026, 1, 1)
        sim.batches = [{"order_id": "START", "category": "TOPS", "pieces": 1, "sent_date": day0, "due_date": day0 + timedelta(days=100)},
                       {"order_id": "PROBE", "category": "TOPS", "pieces": 1, "sent_date": day0 + timedelta(days=31), "due_date": day0 + timedelta(days=100)}]
        delayed = []
        for wid, w in sim.workshops.items():
            if w.status != "ACTIVE":
                continue
            sim.batches[0]["category"] = sim.batches[1]["category"] = next(iter(w.makes))
            out = sim.run(lambda batch, workshops, queues: wid, "probe")
            if out[1]["turnaround"] > w.lead_days + 1 / w.capacity + 1:
                delayed.append(wid)
        result = trace.run_trace(seed)
        assert delayed == [result["shocked_workshop_id"]]


def test_official_mid_job_closure_pauses_work_and_keeps_defect_stream_paired():
    from simulate import Simulator
    day0 = date(2026, 1, 1)
    outputs = []
    for shock in (False, True):
        sim = Simulator(shock=shock, seed=5105)
        sim.workshops = {"W2": replace(sim.workshops["W2"], capacity=100, queue0=0, defect_rate=0, lead_days=0)}
        sim.batches = [{"order_id": "START", "category": "TOPS", "pieces": 100, "sent_date": day0, "due_date": day0 + timedelta(days=100)},
                       {"order_id": "CROSS", "category": "TOPS", "pieces": 600, "sent_date": day0 + timedelta(days=28), "due_date": day0 + timedelta(days=100)}]
        outputs.append(sim.run(lambda batch, workshops, queues: "W2", "fixed"))
    assert outputs[0][1]["turnaround"] == 6
    assert outputs[1][1]["turnaround"] == 20  # Finish on day 48, not day 34.
    normal, shocked = Simulator(), Simulator(shock=True)
    normal.workshops = {wid: replace(w, defect_rate=.5) for wid, w in normal.workshops.items()}
    shocked.workshops = dict(normal.workshops)
    from heuristic import earliest_finish
    assert [o["defective"] for o in normal.run(earliest_finish, "fixed-risk")] == [o["defective"] for o in shocked.run(earliest_finish, "fixed-risk")]
