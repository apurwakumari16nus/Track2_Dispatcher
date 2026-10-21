"""Workshop Network: derived from the real tools and allocator, never mutating session state."""

from datetime import date
from pathlib import Path

import desk
from objectives import PRESETS
import records
import rehearsal
from streamlit.testing.v1 import AppTest
from ui import network_model as nm

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 4, 1)


def model(category="TOPS", pieces=1500, due=date(2026, 4, 15)):
    orders, workshops, _ = desk.load_inputs()
    state = {}
    desk.init_session(state, workshops)
    queues = desk.projected_queues(state["desk_queues"], state["desk_queue_date"], TODAY)
    out = nm.evaluate({"category": category, "pieces": pieces, "due_date": due}, workshops, queues, TODAY,
                      state["desk_allocator"], PRESETS["lateness"], set())
    return out, state, workshops


def test_recommendation_comes_from_a_copy_of_the_allocator():
    out, state, _ = model()
    assert out["chosen"] == "W1" and out["rows"]["W1"]["fit"] == "recommended"
    assert state["desk_allocator"].pieces_by_workshop == {}  # The page never commits history.
    assert {r["id"] for r in out["unavailable"]} == {"W4", "W7", "W8"}
    assert out["rows"]["W7"]["fit"] == "down" and out["rows"]["W8"]["kind"] == "cap" and out["rows"]["W4"]["kind"] == "cannot"
    assert out["rows"]["W3"]["fit"] == "late" and "after QuickStitch" in out["rows"]["W3"]["reason"]


def test_capacity_outlook_and_scenarios_follow_the_simulator_rules():
    out, _, _ = model()
    row = out["rows"]["W1"]
    for week in row["outlook"]:
        assert abs(week["booked"] + week["batch"] + week["spare"] - 7) < 1e-9
    plan, rework, closure = (nm.plan(row, TODAY, s) for s in ("plan", "rework", "closure"))
    assert plan["back"] == date.fromisoformat(row["eta"]["eta_date"]) and plan["late"] < 0
    assert rework["back"] > plan["back"] and closure["back"] - plan["back"] >= __import__("datetime").timedelta(days=13)
    assert closure["state"] == "Delayed" and closure["late"] > 0


def test_dispatch_hands_the_batch_to_the_network_without_saving(monkeypatch, tmp_path):
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "live.jsonl")
    monkeypatch.setattr(desk, "REHEARSAL_LOG", tmp_path / "rehearsal.jsonl")
    monkeypatch.setattr(rehearsal, "RECORD_DIR", tmp_path / "cache")
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=60)
    at.session_state["desk_source"] = "fixture"
    at.run()
    at.button(key="inbox_R09").click().run()
    at.button(key="desk_dispatch").click().run()
    at.button(key="desk_trace").click().run()
    assert not at.exception and at.session_state["desk_page"] == "Workshop Network"
    assert at.number_input(key="net_pieces").value == 150 and at.session_state["net_target"] == "W6"
    assert at.session_state["net_phase"] == "idle" and at.session_state["net_playing"]  # The routing replay starts.
    phases = []
    for _ in range(10):  # Each rerun is one playback tick here; the browser ticks on a timer.
        at.run()
        phases.append(at.session_state["net_phase"])
        if not at.session_state["net_playing"]:
            break
    assert phases[-1] == "recommended" and "ranking" in phases and "filtering" in phases
    text = " ".join(m.value for m in at.markdown)
    assert "Sweater Co Factory" in text and "Routed to Nimble Needle" in text and "Why this workshop" in text and "Recommended for this batch" in text
    at.button(key="node_W5").click().run()
    assert at.session_state["net_pick"] == "W5"
    at.button(key="net_select").click().run()
    assert at.session_state["net_target"] == "W5"  # A routing preview; Dispatch's recommendation is untouched.
    assert at.session_state["desk_preview"].response.decision_record["chosen_workshop"] == "W6"
    assert not records.DEFAULT_PATH.exists() and not desk.REHEARSAL_LOG.exists()
    at.segmented_control(key="net_view").set_value("List").run()
    assert not at.exception and "first pass" in " ".join(m.value for m in at.markdown)


def test_routing_state_model_orders_phases_and_states():
    from ui import routing as rt
    out, _, workshops = model()
    seq = rt.sequence(out, out["chosen"], "closure")
    assert [p.value for p in seq] == ["idle", "evaluating", "filtering", "ranking", "recommended", "confirmed", "in_progress", "delayed"]
    assert rt.node_state(out["rows"]["W7"], rt.Phase.FILTERING, "W1") == rt.Node.SUSPENDED
    assert rt.node_state(out["rows"]["W3"], rt.Phase.RANKING, "W1") == rt.Node.REJECTED  # Late: filtered, still ranked.
    assert rt.node_state(out["rows"]["W1"], rt.Phase.IN_PROGRESS, "W1") == rt.Node.IN_PROGRESS
    assert rt.edge_state(rt.Node.SELECTED) == rt.Edge.WINNING
    late, _, _ = model(pieces=3000, due=date(2026, 4, 8))
    assert rt.sequence(late, late["chosen"])[-1] == rt.Phase.BLOCKED


def test_demo_scenarios_tell_the_story_the_engine_computes():
    from datetime import timedelta
    from ui.demo_scenarios import BY_KEY
    from ui import routing as rt
    expect = {"normal": ("W6", "completed"), "skill": ("W6", "completed"), "suspended": ("W6", "completed"),
              "cheap_late": ("W1", "completed"), "delayed": ("W1", "delayed"), "rework": ("W6", "returned"), "full": ("W5", "blocked")}
    for key, (chosen, end) in expect.items():
        s = BY_KEY[key]
        out, _, _ = model(s.category, s.pieces, TODAY + timedelta(days=s.due_in_days))
        assert out["chosen"] == chosen and rt.sequence(out, chosen, s.outcome)[-1].value == end, key
        if s.spotlight:
            assert out["rows"][s.spotlight]["fit"] != "recommended", key
    assert model("ACCESSORIES", 400, TODAY + timedelta(days=13))[0]["rows"]["W1"]["kind"] == "cannot"
    assert model("TOPS", 1500, TODAY + timedelta(days=14))[0]["rows"]["W3"]["fit"] == "late"
    rework_row = model("TOPS", 600, TODAY + timedelta(days=7))[0]["rows"]["W6"]
    assert nm.plan(rework_row, TODAY, "rework")["late"] > 0
