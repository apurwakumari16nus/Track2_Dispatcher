# Teams

Roles and contribution breakdown. DSS5105 Capstone, Track 2, Group 01.

<div class="note">
<strong>Draft. Do not submit as it stands.</strong> The percentages are for the team to agree. The task lists come from the Git history and the evaluation records. Yin Ning has no commits or named records in the repository, so that row needs their own entry.
</div>

## Members and contribution

| Member | Student ID | Role | Contribution |
|---|---|---|---:|
| Aditya Vijindra Pandhari | A0328872R | Product and mobile lead | TO AGREE |
| Apurwa Kumari | A0333260R | Pipeline and data lead | TO AGREE |
| Vanshika Dhamija | A0333989H | Evaluation lead | TO AGREE |
| Yin Ning | A0274857L | TO CONFIRM | TO AGREE |

## Individual responsibilities and tasks completed

### Aditya Vijindra Pandhari

- Rebranded and redesigned the desk as Threadline: design system, Dispatch, Workshop Network, Simulation Lab, Audit Trail.
- Added tracing, guided demo, benchmarking tools and the Sprint 2 demo.
- One-tap dispatcher answers, split and escalation, the inbox batch run, and the Telegram channel.
- Sprint 3: native iPhone app, Siri, Live Activities, desk API, two-way workshop loop, recovery plans, guardrails v2, speech measurement, TestFlight build.
- Sprint 3 film and deck.

### Apurwa Kumari

- Started the repository and built the first dispatch app, intake pipeline, tools and evaluations.
- Wrote the team handbook and setup documentation.
- Migrated the project to course Data v3 and moved evaluation to ten seeds.
- Second reviewer for the 30 inbox labels. Moved the intake to the Anthropic API.

### Vanshika Dhamija

- Sprint 1 architecture diagram, working notes and deck.
- First reviewer for the 30 inbox labels. Ran reconciliation and froze the labels.
- Live inbox evaluation, per-request timing, and the date-reader fix.
- Hybrid weight sweep and its pre-declared selection rule.
- Held-out set, one-shot Haiku run, three-model comparison, send-date field, date-conflict check, rule version 2, results and failure write-up.

### Yin Ning

- TO CONFIRM: tasks completed.

## Git record

| Author | Commits on `main` to 25 October 2026 |
|---|---:|
| Vanshika Dhamija | 18 |
| Aditya Vijindra Pandhari | 15 |
| Apurwa Kumari | 7 |

Commit counts are a weak measure of work and leave out meetings, labelling time, deck work and everything done outside Git. Line counts are not shown, because recorded result files distort them. The Sprint 3 work was not yet committed when this count was taken.

## Collaboration dynamics

- **Division of work.** Each person owned one part of the chain: pipeline, evaluation, product. That let us work in parallel, with the evaluation kept apart from the code it measures.
- **Independent review.** Two reviewers labelled the requests alone before comparing, and agreed on 27 of 30 behaviours. Disagreements are logged in `eval/labeling/reconciliation.md`.
- **Separation of duties, partly.** The held-out set was frozen with fingerprints before it was run. The planned second round, written by someone who did not build the guards, has not been done.
- **Branches.** Evaluation work was done on a branch and merged through pull requests.
- **AI assistance.** We used an AI coding assistant (Claude Code) for code, tests, labelling drafts, documents and the film. Where AI drafted evaluation material, the evaluation report says so.
- **What was hard.** TO CONFIRM with the team: one honest sentence on where collaboration went badly, and what you changed.
