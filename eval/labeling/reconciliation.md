# Label reconciliation

Final agreed labels: `../labels.csv`. The two independent passes are kept unchanged
in `reviewer_1.csv` and `reviewer_2.csv`. Labelling took place after the intake was built.

## Summary

| Item | Entry |
|---|---|
| Reviewer 1 | Vanshika Dhamija, completed 23–24 Oct 2026 |
| Reviewer 2 | Apurwa Kumari, completed 24 Oct 2026 |
| AI use | **Reviewer 1:** behaviour labels are her own. The other columns were drafted by an AI assistant from the rubric and data, then reviewed by her. She had discussed R03, R09 and R18 with the assistant beforehand, and R18 was corrected (`refuse` → `decline`) after an AI-assisted check, before the comparison. **Reviewer 2:** notes produced with AI; Reviewer 2 is also a developer of the intake code. |
| Data | Data v3 (commit 4215478); `dispatch_requests.txt` SHA-256 dd00a2db398e4acaea1becf82137b6d7526c746621c28af5534806105d50117a |
| Intake version at labelling | `main` aa27848 |
| Assumptions | Today = 2026-04-01; queues from `workshops.csv`; return date = today + round(queue + pieces ÷ capacity + lead days) |
| Agreement before discussion | Behaviour 27/30; issue 29/30 |
| Reconciled | 24 Oct 2026 |
| Frozen at commit | 47c0212 (24 Oct 2026) |
| Revised after freezing | R20, R28, R30 (see below) |

## Disagreements and resolutions

| Request | Reviewer 1 | Reviewer 2 | Agreed | Reason |
|---|---|---|---|---|
| R20, R28, R30 | `refuse` | `decline` | `refuse` | The request can't be accepted as asked, because no workshop meets the date. `decline` is kept for questions our data can't answer, and here the data does answer (it gives the earliest date). The response must state the earliest date and options* |
| R08, R11, R14, R24 | constraint `none` | suggested workshop as constraint | `none` | A suggested workshop is not an instruction; it is noted in `notes` |
| R01 | `multiple_matches` | `no_order_id` | `multiple_matches` | Customer + product match 2 orders* |
| R19 | constraint "quickest - Boss" | `none` | "whoever is quickest - Boss" | The preference is stated in the message* |
| R13 | quantity, category, due blank | filled from the order | blank | A price question needs no allocation fields |
| R09, R12, R21, R23, R25, R27 | same constraint, different wording | | one plain wording | Same meaning |

\* Suggested by the AI assistant; agreed by both reviewers in discussion.

**Process note:** a spreadsheet re-save removed the underscores from issue values and
changed the date format in Reviewer 1's file. These were fixed before the comparison,
with no content changes. The final notes in `labels.csv` were simplified by the AI assistant.

## Changes after freezing

| Date | Request | Change | Reason |
|---|---|---|---|
| 24 Oct 2026 | R20, R28, R30 | `refuse` → `allocate` (issues unchanged: `none_makes_date`, `due_date_passed`) | The data dictionary calls these "complete but impossible" and says to give the numbers, the earliest date and the options, and not to allocate silently. Recommending the least-late option while stating that the date is missed fits that better than refusing. Agreed by Vanshika Dhamija and Apurwa Kumari. **This change was made after seeing the system's answers** (the system answered `allocate` for all three). Agreement with the original frozen labels: 27/30. |

## Held-out set

Files: `data/heldout_requests.txt`, `eval/labels_heldout.csv`. Written 25 Oct 2026.

| Item | Entry |
|---|---|
| Requests | R31–R47: 16 remain. **R39 was removed before the run** (an order-status question that no behaviour fits) |
| Who wrote them | R31–R43 and R47 by the team. **R44–R46 were drafted by an AI assistant** and used unchanged |
| Labels | Drafted by an AI assistant from the rubric and data (system not run), then reviewed by the team. Same rules as `labels.csv` |
| Frozen before the run | File SHA-256 values saved before the first run in `eval/heldout_haiku/inputs_before_run.txt`; committed unchanged in 208b8bc |
| Evaluated | Once on Haiku 5.5 (15/16 behaviour, 13/16 decision); later also run on Sonnet 5.5 with the same files |

## Version 2 labels (team rule change, after seeing results)

Decided by the team on 25 Oct 2026, after the version 1 results, from the user's point of view:
**speed words (urgent, asap, rush, quick, faster, fastest) count as a "fastest" preference, and quality
words (quality, careful, few defects, a previous rejection) count as "lowest defect rate".** A remark that
only explains an exclusion stays an exclusion; pressure alone ("chasing", "already late") is not a preference.

Files: `eval/labels_v2.csv`, `eval/labels_heldout_v2.csv`. Version 1 files are unchanged.
Changed (constraint only; behaviours unchanged): dev R10, R15, R23; held-out R32, R38.
Results scored against version 2 are development results, not a clean held-out test.
