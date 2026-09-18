# Human label reconciliation

Status: not started. Do not replace these placeholders with invented review
results. Keep the two independent CSVs as the original evidence.

## Review metadata

| Item | Human entry |
|---|---|
| Reviewer 1 name | |
| Reviewer 1 independent pass completed | |
| Reviewer 2 name | |
| Reviewer 2 independent pass completed | |
| Prior exposure to AI-generated request discussion, by reviewer | |
| Source data version / commit | |
| Shared queue assumption, if feasibility is assessed | |
| Reconciliation date | |
| Final labels commit ID (before intake implementation) | |
| Expected-behaviour agreement before discussion, out of 30 | |
| Primary-issue agreement before discussion, out of 30 | |
| Requests with any field disagreement before discussion | |

## Disagreement log

Copy this block for each actual disagreement. If there were no disagreements,
say so only after both independent reviews and the comparison are complete.

### Request: [request_id]

- Fields that differed:
- Reviewer 1's original label and reasoning:
- Reviewer 2's original label and reasoning:
- Evidence from the request and source data:
- Agreed behaviour, primary issue, and factual fields:
- Constraints and their source/person:
- Secondary issues the response must still address:
- Why the team chose this interpretation:
- Reviewers confirming the resolution and date:

## Paragraph for Evaluation.pdf

Fill this in after the work is done; remove brackets and any claims that are not
true. Include actual disagreement examples rather than a generic statement.

> Before implementing the intake, [reviewer 1] and [reviewer 2] independently
> labeled all 30 supplied requests using [source data version] and 1 April 2026
> as the fixed current date. They used the same ordered rubric and [queue
> assumptions, if applicable]. Their prior exposure to AI-generated discussion
> was [describe accurately]. Before reconciliation, they agreed on expected
> behaviour for [n]/30 requests and primary issue for [m]/30 requests. They
> disagreed on [actual requests/fields]: [explain the competing interpretations
> and why the source evidence supported the resolution]. Both original label
> files were preserved, and the agreed labels were frozen on [date/commit]
> before intake development. Labels were based on the requests and source data,
> rather than adjusted to the system's predictions. Development use and later
> corrections were [describe], and held-out evaluation used [describe only what
> was actually reserved and evaluated, or state that it remains pending].

## Changes after the labels were frozen

| Date | Request | Original label | Revised label | Source-based reason | Reviewers |
|---|---|---|---|---|---|
