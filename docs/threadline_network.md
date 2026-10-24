# Threadline Workshop Network

The page answers "who can take this batch, and what happens when it is routed?"
for an operations manager. It is read-only: nothing is allocated, saved or sent.

## Where every value comes from

| Shown | Source |
| --- | --- |
| Can take it, reasons it cannot | `tools.check_eligibility` (status, skill, batch cap) |
| Earliest finish, spare days, cost | `tools.estimate_eta`, `tools.estimate_cost` with the session queues |
| Recommended workshop and ranking numbers | `Allocator.decide` on a **copy** of the session allocator, with the objective set in Dispatch |
| Why this workshop | `explain.why_won` on that decision |
| Against the recommendation | The two estimates compared: days later or earlier, cost more or less |
| First-pass quality | `1 - defect_rate` from `workshops.csv` |
| Capacity outlook, 4 weeks | Queue days and this batch's processing days laid onto 7-day weeks (the simulator's model) |
| Operational risk | Suspended, suspect queue (shock monitor), no buffer, rework rate, long queue, trial cap, long transport |
| Scenarios | The simulator's written rules: rework adds 50% processing time; a closure pauses work for 14 days |

Fit levels: Recommended, Strong fit (2+ days spare), Tight fit (0 to 1 day),
Misses the date, Cannot take it, Suspended. Locations are not in the data, so
search covers name, ID, products, tags and the register note instead.

## Layout

Header with search and a Network or List toggle; a batch bar (category, size,
due date, the Dispatch objective, Route this batch); a one-line answer with five
chips (recommended, fastest, cheapest, most reliable, cannot take it); then the
map with the detail panel beside it, and the active batch route below.

The map puts Sweater Co Factory (the Threadline mark) at the centre with the eight
workshops as photo nodes. Ring colour is the fit, the number is the engine's rank,
an x marks a workshop that cannot take the batch, and the routed spoke is the only
blue beam. Clicking a node opens its detail panel. Select for routing previews a
different route; it never changes Dispatch's recommendation.

## Routing states (phase 2)

`src/ui/routing.py` holds the state model. A routing run moves through ordered
phases, and every visual is a pure function of (view model, phase, routed
workshop, outcome), so play, step and reset all draw the same frames.

| Phase | What the manager sees |
| --- | --- |
| idle | A "New batch" chip arrives at Sweater Co Factory; every node neutral |
| evaluating | Every spoke scans, every ring pulses; the panel lists the five checks |
| filtering | Rejected workshops dim with their reason: skill mismatch, suspended, over batch limit, misses due date |
| ranking | The engine's rank numbers pop in; the panel shows the ranked list |
| recommended | The winning route draws and glows, the batch travels to it, the detail panel switches to it |
| blocked | No workshop meets the date: the least-late route turns amber with "Needs decision" |
| confirmed, in_progress | The tracker advances; the routed node gets a spinning production ring |
| completed, delayed, returned | Green check, red delay, or the batch travels back for rework; the tracker marks the stage |

Node states: neutral, evaluating, shortlisted, selected, rejected, blocked,
suspended, in_progress, delayed, completed. Edge states: neutral, scanning,
shortlisted, rejected, winning, warning. Motion runs only while a run is live
and respects reduced motion.

Playback is a Streamlit fragment that reruns every 1.1 seconds while a run is
playing and advances one phase per tick, then stops itself. Without a run the
page shows the routed result.

## Demo mode

Turn on **Demo mode** (header, beside the view toggle). A navy control bar
appears with a scenario picker, **Play scenario**, previous step, next step,
reset, and the current step number. Scenarios live in `src/ui/demo_scenarios.py`
and only choose the batch, the outcome to play after routing, and the workshop
to spotlight at the end. Routing is always the live engine; tests check each
story against it.

| Scenario | Batch | What happens |
| --- | --- | --- |
| Normal routing | 150 tops, 8 days | Nimble Needle, back on plan |
| Skill mismatch | 400 accessories, 13 days | Four tops-only workshops filtered; spotlight on QuickStitch |
| Suspended workshop | 200 accessories, 11 days | Spotlight on OldMill, suspended |
| Cheapest misses the date | 1,500 tops, 14 days | Spotlight on BudgetWorks, a day late |
| Accepted, then delayed | 1,500 tops, 14 days | QuickStitch, then a 14-day closure; reassign option GiantWeave |
| Returned for rework | 600 tops, 7 days | Nimble Needle, half reworked, back late |
| Nobody can make the date | 3,000 tops, 7 days | Least-late GiantWeave needs a decision; spotlight on FreshStart over its limit |

Without demo mode, **Route this batch** plays the evaluation up to the route.
From Dispatch, **Trace on the network** opens the page with the batch prefilled
and plays the same run.

## Charts

The detail panel shows four small indicators (queue load, rework rate, a
four-week utilisation sparkline, risk level) and a capacity chart: one
horizontal stacked bar per week (already booked, this batch, spare) with the
pieces written on each segment and the booked share on the right. Operational
risks sit in a collapsed list under the actions.

## Images

`src/static/brand/workshops/W1.webp` to `W8.webp`, one per workshop ID, are
Unsplash photos under the Unsplash License, cropped to 4:3 and given one shared
grade. Credits and sources are in `src/static/brand/CREDITS.md`. They illustrate
each workshop's character and are labelled on the page as not being photographs
of these workshops. To swap one, replace the file with any 4:3 image of the same
name.
