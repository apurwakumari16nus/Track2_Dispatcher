# Final demo checklist (V11.1)

Status on 23 October 2026, branch `product-ui-v2`. Nothing in this pass was committed.

## 1. Verified automatically in this pass

| Check | Command or method | Result |
|---|---|---|
| Unit and app tests | `uv run pytest -q` | 325 passed, 1 skipped (the skip is the human-label accuracy test: 0 of 30 labels) |
| Course evidence fingerprint | included in the suite (`test_course_evidence_matches_code`) | Passes: allocator, objectives, heuristic, tools and simulator unchanged |
| Official ten-seed results | `uv run python eval/run_simulator.py --output-dir <scratch>`, then byte comparison | `results.csv`, `results_per_seed.csv`, `objective_checks.csv`, `shock_changes.csv`, `shock_changes_per_seed.csv` reproduce **byte for byte** |
| Recording path (R09 to Lab) | Playwright, presentation mode, recorded replies, 1920 × 1080 and 1440 × 900 | Completes at both sizes; one rehearsal audit record per confirmation; no console errors |
| Journeys: allocation, clarification, refusal (R08), impossible deadline (R30), unanswerable (R02), Network, guided demo | Playwright, 1920 × 1080 and 1440 × 900 | All pass, no exceptions or console errors |
| No duplicate confirmation | Tests `test_confirm_writes_once_updates_the_queue_once_and_opens_that_record` and the journeys | One record, one queue update; the button is replaced after the click; reruns and navigation write nothing |
| Navigation crash regressions | Playwright repro across all four pages, plus tests | No exceptions |
| Truncated text | Playwright scan of every demo screen at both sizes | None after the fixes below |
| Benchmark dry run | `uv run python benchmarks/run_models.py` | 43 cases × 2 models × 3 trials = 258 calls, estimated USD 1.41; no request sent |

## 2. Fixed in this pass (recording problems only)

* Changing page kept the old scroll position, so Network and Simulation Lab opened halfway
  down with their headers hidden. Each page now opens at the top (not during the guided
  demo, which scrolls to its own target).
* The Dispatch title wrapped to three lines and pushed the result below the fold. Page
  titles now use one size and fit on two lines.
* Progress-step names were truncated at 1440 × 900 ("Underst…"). They no longer truncate.
* "Route this batch" was truncated at 1440 × 900. The button column is wider.
* The sidebar status read "Recorded…" / "Test fixtur…". It now says "Recorded" / "Fixtures".
* Benchmark: accuracy against the 30 agreed human labels is now computed once all 30
  exist (previously a placeholder), and becomes part of the decision rule.
* New `eval/labeling/compare_reviews.py`: completeness, schema problems, agreement and
  every differing field between the two reviewers. Reads only; writes no label.

The theme, backgrounds, palette, type, materials and edge lighting are unchanged.
No animation was added. The routing playback was checked: it shows "Evaluating" while
running, then the three filtered workshops with their reasons, then "Routed" to the
engine's choice, matching the Dispatch recommendation.

## 3. Still requires a person

| Item | Why |
|---|---|
| Two independent human label passes (`eval/labeling/reviewer_1.csv`, `reviewer_2.csv`) | 0 of 30 rows filled in all three files. Only people can do this; see `eval/labeling/README.md` |
| Reconciliation and freeze (`reconciliation.md`, `eval/labels.csv`) | Run `uv run python eval/labeling/compare_reviews.py` after both passes; discuss each difference; fill `labels.csv` by hand; record the commit |
| Paid Sonnet 5.5 vs Haiku 5.5 run | After the labels are frozen: `uv run python benchmarks/run_models.py --execute` (about USD 1.41). Until then, report "not yet measured" |
| Watch one full take | Pacing, voice and cursor movement cannot be judged by a script |
| Audio level and microphone | Manual |
| Recorded replies on the recording machine | `records/rehearsal_cache/` is git-ignored. This machine has replies for 7 of 30 requests, including R09. On another machine, run R09 once in Live model mode first |
| Pushing to the team repo | `origin` does not yet have the V11 commits; only `github-nus` does |

## 4. Remaining issues, most severe first

1. **No measured language accuracy.** Human labels are 0 of 30, so no accuracy figure may
   be claimed for the model's reading of requests. (Evidence gap, not a bug.)
2. **Sonnet vs Haiku not measured.** Tooling ready; paid run waits for labels.
3. **Recorded replies are local.** A fresh clone has no R09 recording; the demo then needs
   Live model (about 4 s per evaluation) or test fixtures (labelled as such on screen).
4. **At 1440 × 900 the network map starts below the fold.** One scroll is needed. At
   1920 × 1080 the map and panel are visible together.
5. **Guided demo coach covers part of the map** on its Network step at wide screens.
   Not used in the recording.
6. **Inbox filter "Reviewed" wraps to a second row** at 1440 × 900. Cosmetic.
7. **Dispatch shows the workshop photo without an "illustrative" label** since commit
   b99d02f; the Network page footer still says the photos are illustrative.
8. **Tradeoffs radar** is dominated by the quality-only objective, so the other shapes look
   small. The table beside it gives the exact values.
9. **`records/decisions.jsonl` (live log) holds 2 records** from earlier use (latest
   ORD-041, 23 Oct 05:22 UTC). The recording confirms into the rehearsal log and never
   shows the live log.

## 5. Click-by-click recording guide

Before recording:

1. `uv run streamlit run src/app.py`; open it in Chrome at 1920 × 1080, zoom 100%, full screen.
2. Sidebar → **System details** → choose **Rehearsal: recorded model replies**.
3. Same panel → turn on **Presentation mode**.
4. Same panel → **Reset demo session**. Click on empty page space to close the panel.
5. Confirm the ribbon says **Rehearsal mode** and the sidebar card shows **Confirmed 0**.
6. Do one silent rehearsal of steps 1 to 12 below, then **Reset demo session** again.

Recording (times from `final_demo_storyboard.md`):

1. 0:00 Hold on Dispatch for 10 seconds.
2. 0:10 Click **Boss, R09** in the inbox.
3. Click **Evaluate request**.
4. 0:24 Scroll down past the navy card; open **What Python checked**.
5. 0:38 Scroll back up to the navy card; click **Why this decision?**; after 5 seconds press **Esc**.
6. 0:54 Click **See it on the network**; wait for the route to finish (about 11 seconds).
7. Click the **FreshStart** node on the map.
8. 1:12 Click **Dispatch** in the sidebar; scroll to the card; click **Assign to Nimble Needle**.
9. 1:22 Click **View audit record**; hold.
10. 1:35 Press **Esc**; click **Simulation Lab** in the sidebar.
11. Hold on the official result until 2:00.
12. Stop recording.

If a take goes wrong: **System details** → **Reset demo session**, then start again from
step 1. The reset clears the rehearsal log and restores the 1 April queues; it never
touches the live log.
