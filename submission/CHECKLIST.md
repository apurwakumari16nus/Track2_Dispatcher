# Group 01 checklist

Updated 9 November 2026, after building V14.

## 1. Sprint 3 presentation

Due **Friday 13 November, 3:00 PM**. Late uploads are accepted until 7:00 PM.

One member uploads both files to Canvas, under **Sprint 3 Presentation**.

| | What | Where | Who |
|---|---|---|---|
| ✅ | V14: the group-chat montage and stitched title, slide 1, the objective (slide 3) and the 92% case, then one day in the app: Siri, the 8:30 automation, the home card, the tabs, a Hindi order end to end (Dynamic Island, Lock Screen, Completed), an English request from the group chat with a split, a Mandarin order, the hard cases, and the native app on TestFlight. Then evaluation (lateness first, then what we add: reading 48 of 50 held-out requests against 24 for keyword rules, replies, what breaks it, limits) and the conclusion. Opening and objective 37 s, demo 2:57, evaluation 65 s, conclusion 20 s, total 4:59.2 | `demo_video/film/renders/Sprint3_Presentation_V14.mp4` (guide voice) | Claude |
| ✅ | Reviewed frame by frame: all 31 scene changes (no jumps, double phones or flashes; the V13 Work tab glitch is fixed at its cause), every highlight, every slide-to-approve finger against the real knob | same | Claude |
| ✅ | Deck: slides 4, 6 and 9 show the 50-request results (48/50, keyword rules 24/50, 80/80 replies with no invented numbers), and the stale speaker notes are rewritten. Slides 2 and 3 still say "7 to 14 days" (Factory Primer, urgent reorders) | `Presentation_Group01.pptx` and `submission/Group01/Slide.pptx` (identical) | Claude |
| ✅ | Reading script, every line with its start time | `demo_video/film/SCRIPT_SPRINT3_PRESENTATION.md` | Claude |
| ✅ | Silent picture lock to record against | `demo_video/film/renders/Sprint3_Presentation_V14_PictureLock.mp4` | Claude |
| ⬜ | Record the voice: one take from 0:00, Hindi line exactly as written, Siri's line left silent | send the WAV or M4A | Aditya |
| ⬜ | Lay the voice over the picture and check the timing, giving `Presentation_Group01.mp4` | | Claude |
| ⬜ | Upload the video to YouTube as unlisted, and copy the link | | Aditya |
| ⬜ | Deck slide 1: add the YouTube link. Confirm each member's attendance (all four say "Present (in person)" now). The link goes on the slide only, not in the video | `Presentation_Group01.pptx` | Aditya, then Claude |
| ⬜ | Open the GitHub link and the YouTube link in a private browser window | | Aditya |
| ⬜ | Upload `Presentation_Group01.mp4` and `Presentation_Group01.pptx` | Canvas | one member |
| ⬜ | Everyone can explain the whole system for the 2 minutes of Q&A | | all |

## 2. Final submission, Group01.zip

Due **Sunday 15 November, 11:59 PM**.

| | File | State | What is left |
|---|---|---|---|
| ✅ | `Readme.pdf` | Setup, requirements, running locally, and the iPhone app on a real phone. Round 2 commands added by Vanshika | Demo link |
| ✅ | `Documentation.pdf` | Under the 15-page limit. Round 2 added | Demo link |
| 🟨 | `Evaluation.pdf` | 18 failure cases (the brief asks for at least 10), with Round 2: 33 of 34 on behaviour, run once | Add one sentence: on Round 2 the blind keyword rules got 16 of 34 (now in `submission/Evaluation.md` and `eval/rule_baseline/summary.md`) |
| ✅ | `Teams.pdf` | Filled in by the team in `deliverables/Teams.docx`: no "Add:" or "Draft" left | Export to PDF |
| 🟨 | `Strategic_Recommendations.pdf` | 7 pages | Replace "We have not run the keyword rules on that set" with "the same keyword rules got 16 of 34" |
| ⬜ | `Slide.pptx` | The same deck we present on Friday | Copy it in after slide 1 is final |
| ⬜ | `Video.mp4` | A pure demo of the app, no slides, under 5 minutes. A 3:27 draft is built | Re-cut it from the V14 demo (English request, Mandarin, the new dissolves), then Aditya records its voice |

The team's edited Word files are in `deliverables/` (Vanshika, 7 November, with Round 2 and Teams filled in). They are now the source: make the last edits there and export each one to PDF. `submission/*.md` has the same Round 2 changes, so the two agree, but rebuilding from it would not carry the team's Word edits.

## 3. Repository

| | What |
|---|---|
| ✅ | The Sprint 3 code is pushed on branch `sprint3-submission` |
| ✅ | `round2-evaluation` merged into `sprint3-submission` and into `main` on this Mac. 592 tests pass |
| ✅ | Commit the latest changes (deck, documents, Round 2 keyword run, app build 2, docs reorganised) |
| ✅ | Push `sprint3-submission` and `main`, so the public repo shows Sprint 3 and Round 2 |
| ⬜ | Check that the repo is public and opens in a private window |
