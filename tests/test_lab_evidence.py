"""Simulation Lab verdicts come from the committed evidence and never overstate it."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from ui import evidence
from ui import lab_evidence as le

ROOT = Path(__file__).resolve().parents[1]


def test_lateness_is_a_tie_with_earliest_finish_never_a_win():
    data = evidence.load()
    for shock in (False, True):
        hero = le.hero(data, "lateness", shock)
        assert hero["ef_outcome"] == "tie" and le.OUTCOME["tie"][0] == "Tie"
        assert hero["overall"] == "Beats 3, ties 1" and "not a win" in hero["note"]
        assert sorted(hero["beats"]) == ["Biggest workshop", "Cheapest", "Random"]


def test_quality_fails_the_guardrail_and_hybrids_are_only_reported():
    data = evidence.load()
    defect = le.hero(data, "defect", False)
    assert defect["overall"] == "Fails the lateness guardrail" and defect["tone"] == "risk"
    assert set(defect["outcomes"].values()) == {"guardrail"}
    for objective in ("hybrid_lateness_fairness", "hybrid_lateness_defect"):
        assert le.hero(data, objective, False)["overall"] == "Reported only"
    for objective in ("fairness", "robustness"):
        assert le.hero(data, objective, False)["overall"] == "Qualifies against all four"


def test_claims_list_what_not_to_say():
    claims = le.claims(evidence.load())
    assert "That our policy beats earliest finish." in claims["Do not claim"]
    assert any("ties earliest finish" in c for c in claims["Ties"])
    assert any("guardrail" in c for c in claims["Fails"])


def test_lab_page_shows_the_tie_and_switches_objective():
    at = AppTest.from_file(str(ROOT / "src/app.py"), default_timeout=60)
    at.session_state["desk_page"] = "Simulation Lab"
    at.run()
    text = " ".join(m.value for m in at.markdown)
    assert not at.exception and "with earliest finish (1.67%)" in text
    at.segmented_control(key="lab_space").set_value("evidence").run()
    assert "Official ten-seed evidence" in " ".join(m.value for m in at.markdown)
    at.segmented_control(key="lab_space").set_value("tradeoffs").run()
    at.button(key="objbtn_defect").click().run()
    assert at.session_state["lab_focus"] == "defect"
    assert "Fails the lateness guardrail" in " ".join(m.value for m in at.markdown)
