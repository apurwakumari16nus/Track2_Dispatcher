"""Demo scenarios for screen recording. Scripted inputs, live engine.

Each scenario only chooses a batch (category, size, due date), which workshop to
spotlight at the end, and an outcome to play after routing. The eligibility,
ranking and recommendation are computed by the real engine for that batch, so a
scenario can never claim a result the engine did not produce. The outcome is a
playback of the plan under the simulator's rules (rework adds 50% processing,
a closure pauses work for 14 days), and the page labels it as demo playback.

Due dates are offsets from the scenario date so the stories hold for the
fresh 1 April queues; tests check each story against the engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoScenario:
    key: str
    title: str
    story: str
    category: str
    pieces: int
    due_in_days: int
    outcome: str = "plan"          # plan, rework or closure (simulator rules)
    spotlight: str | None = None   # workshop shown in the detail panel at the end; None keeps the routed one


SCENARIOS = [
    DemoScenario("normal", "Normal routing", "150 tops, 8 days. The engine routes it and it comes back on plan.",
                 "TOPS", 150, 8),
    DemoScenario("skill", "Skill mismatch", "400 accessories. Four tops-only workshops are filtered out, including the fastest one.",
                 "ACCESSORIES", 400, 13, spotlight="W1"),
    DemoScenario("suspended", "Suspended workshop", "200 accessories. OldMill has no queue and is cheap, but it is suspended.",
                 "ACCESSORIES", 200, 11, spotlight="W7"),
    DemoScenario("cheap_late", "Cheapest misses the date", "1,500 tops, 14 days. BudgetWorks is cheapest but returns a day late.",
                 "TOPS", 1500, 14, spotlight="W3"),
    DemoScenario("delayed", "Accepted, then delayed", "1,500 tops, 14 days. Routed on plan, then a two-week closure pauses work.",
                 "TOPS", 1500, 14, outcome="closure"),
    DemoScenario("rework", "Returned for rework", "600 tops, 7 days. Half the batch comes back for rework and the date slips.",
                 "TOPS", 600, 7, outcome="rework"),
    DemoScenario("full", "Nobody can make the date", "3,000 tops, 7 days. Over FreshStart's batch limit and too big for anyone's date.",
                 "TOPS", 3000, 7, spotlight="W8"),
]
BY_KEY = {s.key: s for s in SCENARIOS}
