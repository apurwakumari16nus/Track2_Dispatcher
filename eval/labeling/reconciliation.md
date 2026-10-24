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
| Frozen at commit | [add after commit] |

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
