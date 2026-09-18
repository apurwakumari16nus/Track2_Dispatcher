# Human labeling: 30 dispatch requests

**Status: blank templates, awaiting two independent human reviews.** Only request
IDs have been populated automatically. No expected answers have been supplied.
The intake is already implemented. The requested sequence of freezing labels
before intake development was not completed; do not claim otherwise. Complete
the independent reviews and reconciliation now, record the actual timing and
prior exposure to system outputs, and freeze labels before final scoring.
Additional unseen requests should be reserved for held-out evaluation.

## Files and roles

| File | Use |
|---|---|
| `reviewer_1.csv` | First person's independent labels |
| `reviewer_2.csv` | Second person's independent labels |
| `../labels.csv` | Final agreed labels, populated after comparison |
| `reconciliation.md` | Reviewer identities, disagreements, evidence, and evaluation-method paragraph |

Open `../../data/dispatch_requests.txt` beside `../../data/orders.csv`. Keep
`../../data/workshops.csv` and `../../data/data_dictionary.md` available for
restrictions and field meanings. In VS Code, use Split Editor to keep the
request and order files visible together. Each reviewer fills only their own
CSV, without seeing the other person's answers. Do not use the intake's output
to decide what the expected answer should have been.

Prior AI-generated study material or request-level discussion may influence a
reviewer's expectations. Use the original data and this labeling rubric for the
independent pass rather than copying those suggestions. Record whether either
reviewer previously saw such discussion or system outputs; do not claim an
entirely unaided review if that is inaccurate.

## Exact schema

```text
request_id,expected_behaviour,expected_order_id,expected_pieces,expected_category,expected_due,issue,constraint,notes
```

- Keep all 30 IDs, `R01` through `R30`, with one row per request.
- `expected_behaviour`: exactly `allocate`, `clarify`, `refuse`, or `decline`.
- `expected_order_id`: the uniquely identified order, when established. Do not
  select arbitrarily from multiple possible orders; put the alternatives in notes.
- `expected_pieces`: an integer when established; leave blank when unresolved.
- `expected_category`: `TOPS` or `ACCESSORIES` when established; otherwise blank.
- `expected_due`: `YYYY-MM-DD` when established; otherwise blank. Do not substitute
  the old date for an explicitly unconfirmed changed date.
- `issue`: exactly one value from the list below. Choose the primary issue by
  applying the ordered checks. Document additional issues and any uncertainty in
  `notes`; agree on precedence during reconciliation.
- `constraint`: preserve the instruction and who imposed it. Distinguish the
  message's speaker from a different person whose instruction they relay.
- `notes`: evidence, source row/fields, message-versus-data mismatches, secondary
  problems, required clarification or refusal explanation, and agreed rationale.

Allowed issues:

```text
none
no_order_id
multiple_matches
order_not_found
due_date_passed
due_date_today_or_impossible
already_in_packing
ineligible_suggested_workshop
no_such_data
date_not_confirmed
none_makes_date
```

Blank answer cells currently mean **unlabeled**, not `none` or agreement. In
completed rows, reviewers may leave unresolved factual fields blank, but must
fill `expected_behaviour`, `issue`, and enough notes to explain the decision.
Record an absent constraint consistently as `none` in the final agreed file.
If a field conflicts between the message and CSV, record both values and why
your expected response should clarify or accept one; do not silently repair it.
CSV text containing commas or newlines must be enclosed in double quotes.

## Ordered checks for each request

Use **2026-04-01** as today for all 30 requests, not the computer's current date
and not the simulator's historical dispatch date.

1. Does the message name an order ID? If not, can customer plus product identify
   exactly one **in-progress** order? Several matches require clarification.
2. Does the named order exist? If not, use `decline` / `order_not_found`.
3. Do the message's quantity and product agree with the CSV? Record mismatches.
4. Is the requested deadline before or on today? The expected response must
   explicitly acknowledge the date problem, not silently allocate. Distinguish
   `due_date_passed` from `due_date_today_or_impossible`.
5. Is the order already in `PACKING`? At minimum require clarification rather
   than silently sending nearly finished work outside.
6. Does a suggested workshop pass `makes`, `status`, and `max_batch_pieces`?
   If it cannot take the job, expect refusal with the specific reason.
7. Is the requested information absent from the data, such as pre-January-2026
   allocation history, customer selling prices, or worker names? Expect decline.
8. Record constraints such as exclusions, cheapest subject to date, lowest
   defects, splitting, or fastest regardless of cost, including who imposed them.

Do not invent a new issue value for an uncovered situation. Record it in notes
and discuss how to apply the agreed rubric. Where multiple checks apply, retain
all relevant response obligations in notes even though the schema allows only
one primary behaviour and issue. A known order can still require clarification,
refusal, or decline; known facts do not automatically imply `allocate`.

`none_makes_date` needs numerical evidence under an explicitly stated queue
snapshot and today's date. Record the queue assumption and hand calculation if
you use that issue. Do not guess capacity or use a different queue state for
different reviewers without recording that difference.

## Compare, reconcile, and freeze

1. Record names and independent-pass completion dates in `reconciliation.md`.
2. Compare every column for each request. Count agreement on behaviour and issue
   separately, and note factual-field or constraint disagreements too.
3. Preserve both independent CSVs unchanged after that comparison. Discuss each
   disagreement against the source files and ordered checks.
4. Record each disagreement, both interpretations, source evidence, the agreed
   answer, and why it was chosen. Then fill the final row in `../labels.csv`.
5. Confirm all 30 final rows are reviewed. Record the consensus date and commit
   the completed labeling files before final evaluation. Record the resulting
   commit ID and the intake version already present at labeling as evidence of
   the actual timing; this is not a pre-implementation label freeze.
6. Later corrections must retain a change log and data-based reason. Do not
   change labels merely to make the system's score improve. Disclose development
   use, and reserve additional unseen requests for held-out evaluation.

Complete the evaluation-method paragraph with the team's actual process and
disagreements. It is a template, not a claim that labeling has already occurred.
