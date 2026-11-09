# Teams

Roles, tasks and contribution. DSS5105 Capstone, Track 2, Group 01.

<div class="note">
<strong>Draft for the team to complete.</strong> Fill in every cell marked <strong>Add</strong>. Work outside the tables, such as meetings, research, reviews and rehearsals, is not listed yet. Tasks marked "To do" are assigned for the rest of Sprint 3: change each one to done once it is finished, and remove any that are not done by submission.
</div>

## Members and contribution

| Member | Student ID | Role | Contribution |
|---|---|---|---:|
| Aditya Vijindra Pandhari | A0328872R | App development and design lead | 31% |
| Apurwa Kumari | A0333260R | Core system and data lead | 31% |
| Vanshika Dhamija | A0333989H | Architecture and evaluation lead | 31% |
| Yin Ning | A0274857L | Testing and review support | 7% |

Aditya, Apurwa and Vanshika contributed about equally and share most of the work. Yin Ning's share covers attending the sprint presentations and the testing and review tasks in Sprint 3.

## Tasks by sprint

We met in person through each sprint and divided the work evenly between the three of us. Where a task names two or three people, they did it together.

### Sprint 1: problem, first system and architecture

| Task | Owner | When or source |
|---|---|---|
| Set up the repository and project structure | Apurwa Kumari | 14 Sep |
| First dispatch app (Streamlit) | Apurwa Kumari, Aditya Vijindra Pandhari | 18 Sep |
| Intake pipeline: AI reads the chat message into fields | Apurwa Kumari, Vanshika Dhamija | 18 Sep |
| Eight calculation tools and the allocator | Aditya Vijindra Pandhari, Vanshika Dhamija | 18 Sep |
| First evaluations: simulator runs and inbox checks | Vanshika Dhamija, Apurwa Kumari | 18 Sep |
| Team handbook and setup documentation | Apurwa Kumari, Aditya Vijindra Pandhari | 18 Sep |
| Simulation dashboard | Aditya Vijindra Pandhari | 25 Sep |
| Moved the project to course Data v3, with ten-seed evaluation | Apurwa Kumari, Vanshika Dhamija | 27 Sep |
| Data v3 validation notes | Vanshika Dhamija, Aditya Vijindra Pandhari | 27 Sep |
| Architecture diagram | Vanshika Dhamija, Aditya Vijindra Pandhari | 9 Oct and 21 Oct |
| Sprint 1 working document: problem statement, objectives, risks, first results | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija | 9 Oct |
| Moved the intake to the Anthropic API | Apurwa Kumari, Aditya Vijindra Pandhari | 15 Oct |
| Sprint 1 deck and presentation script | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija | 21 Oct |
| Research on the problem and the course data | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija | Sprint 1 |
| Presented Sprint 1 in person | All four | Sprint 1 deck, slide 1 |

### Sprint 2: the product and its first tests

The owners match the Sprint 2 slides we submitted (slides 5 and 6). The last rows of each table were not on the slides, and we added them here.

#### Product

| Feature | What it does | Owner |
|---|---|---|
| Dispatch desk | Recommendation in about 2.5 s, every step shown | Apurwa Kumari, Vanshika Dhamija |
| Why this decision | Shows why the pick won and why the runner-up lost | Apurwa Kumari, Vanshika Dhamija |
| Workshop network map | The decision as a route, with reasons for exclusions | Apurwa Kumari, Vanshika Dhamija |
| Telegram bot | Recommend and confirm inside the team chat | Aditya Vijindra Pandhari |
| Ask, don't guess | Missing date taken from the file, a calendar or typing | Aditya Vijindra Pandhari |
| Split or escalate | Split across up to two workshops, or pass to a manager | Aditya Vijindra Pandhari |
| Audit trail | Every confirmation saved with who, when and why | Aditya Vijindra Pandhari |
| One inbox | Chat and desk requests together, with their history | Vanshika Dhamija |
| Workshop queues | Live view of every workshop's booked work | Apurwa Kumari |
| Simulation lab | Tests decision rules before we use them | Vanshika Dhamija |
| Video | Demo video done | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija |
| Threadline design | Redesigned the interface from UI v2 to V11 and rebranded it as Threadline by Sweater Co | Aditya Vijindra Pandhari |
| Tracing and guided demo | Execution tracing, a guided demo and benchmark tools | Aditya Vijindra Pandhari, Apurwa Kumari |
| Sprint 2 deck | Slides and speaker notes | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija |
| Sprint 2 presentation | Presented in person | All four |

#### Evaluation

| Test | Result | Owner |
|---|---|---|
| Built a test set | 30 real inbox requests, answers agreed by 2 people | Apurwa Kumari, Vanshika Dhamija |
| Added unseen requests | 16 new requests, sealed before testing, run once | Vanshika Dhamija |
| Accuracy, test set | 28 of 30 right first time. 30 of 30 after one fix | Vanshika Dhamija |
| Accuracy, unseen set | 15 of 16 right action, 15 of 16 right workshop | Vanshika Dhamija |
| Compared 3 AI models | Sonnet as accurate as the others and the fastest | Apurwa Kumari |
| Learned from mistakes | 14 mistakes studied, 2 causes fixed | Apurwa Kumari |
| Against simple rules | 1.7% late against 34% for random. Ties earliest finish | Aditya Vijindra Pandhari |
| Surprise closure | Late orders only rise from 1.7% to 1.9% | Aditya Vijindra Pandhari |
| Speed against fairness | 90/10 mix: busiest workshop 26% to 20%, 5.1% late | Aditya Vijindra Pandhari |
| Response time | About 2.5 s per request. All 30 under 10 s | All four |
| Label freeze | Labels reconciled and frozen, later changes logged | Vanshika Dhamija, Apurwa Kumari |

The slides also listed four items planned for Sprint 3: dispatcher override, a usability test, a second unseen test and re-routing after a closure. They are in the Sprint 3 table below.

### Sprint 3: iPhone app, testing and submission

| Task | Owner | When or source |
|---|---|---|
| Native iPhone app (SwiftUI): voice capture, recommendation card, recovery plan, messages | Aditya Vijindra Pandhari | 2 Nov |
| Siri, Live Activities and Lock Screen widgets | Aditya Vijindra Pandhari, Vanshika Dhamija | 2 Nov |
| Desk API that the app and Telegram share | Aditya Vijindra Pandhari, Apurwa Kumari | 2 Nov |
| Two-way workshop loop on Telegram: replies, partner messages, escalation | Aditya Vijindra Pandhari, Vanshika Dhamija | 2 Nov |
| Recovery plans after a workshop closes (re-routing, planned in Sprint 2) | Vanshika Dhamija, Aditya Vijindra Pandhari | 2 Nov |
| Dispatcher override with the reason saved (planned in Sprint 2) | Apurwa Kumari, Aditya Vijindra Pandhari | 2 Nov |
| Guardrails v2 around the AI reading | Aditya Vijindra Pandhari, Apurwa Kumari | 2 Nov |
| Speech-to-text measurement (whisper.cpp) | Apurwa Kumari, Vanshika Dhamija | 2 Nov |
| Red-team request set and run | Vanshika Dhamija | 2 Nov |
| Rule-based reader baselines | Apurwa Kumari, Vanshika Dhamija | 2 Nov |
| Explanation review of all 46 answers | Vanshika Dhamija, Aditya Vijindra Pandhari | 2 Nov |
| Second reading of the explanation review, as an independent human reader | Apurwa Kumari | To do |
| TestFlight build | Aditya Vijindra Pandhari, Apurwa Kumari | Sprint 3 |
| Sprint 3 deck and 5-minute video | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija | 2 Nov |
| Readme | Apurwa Kumari | 2 Nov |
| Documentation | Aditya Vijindra Pandhari, Vanshika Dhamija | 2 Nov |
| Evaluation report | Vanshika Dhamija, Apurwa Kumari | 2 Nov |
| Strategic Recommendations | Aditya Vijindra Pandhari, Apurwa Kumari, Vanshika Dhamija | 2 Nov |
| Round 2 unseen test: 34 new requests (AI-drafted, rephrased by the team), sealed, run once on Sonnet, and the two fixes that followed | Vanshika Dhamija | 7 Nov |
| Usability test with three stand-in dispatchers: time, mistakes, confidence | Apurwa Kumari | To do |
| Demo video for the zip, separate from the presentation video | Aditya Vijindra Pandhari | To do |
| Open each source marked "search summary" in Strategic Recommendations and confirm the figure | Yin Ning | To do |
| Follow the Readme on a fresh clone on their own laptop and report any step that fails | Yin Ning | To do |
| Proofread the five submission documents for typos and broken links | Yin Ning | To do |
| Act as a stand-in dispatcher in the usability test | Yin Ning | To do |
| Present Sprint 3 in person, 13 November | All four | To do |

## Responsibilities in short

| Member | Main responsibilities |
|---|---|
| Aditya Vijindra Pandhari | Designed and built the apps. Aditya created the Threadline brand and design system and redesigned the web desk through every version from UI v2 to V11. He designed and built the iPhone app, from voice capture and the recommendation card to recovery plans, messages, Siri, Live Activities and widgets, and shipped it to TestFlight. He built the desk API that connects the phone and Telegram, the Telegram bot, and the features that keep a person in control: asking instead of guessing, split and escalation, dispatcher override and the audit trail. He ran the simulator tests against simple rules, a surprise closure and the trade-off between speed and fairness. In Sprint 1 he built the simulation dashboard and worked on the tools, the allocator and the architecture. In Sprint 3 he worked on the guardrails and co-wrote the deck, the video and the Documentation |
| Apurwa Kumari | Built the system underneath. Apurwa set up the repository and built the first dispatch app and the intake pipeline that everything else grew from. She moved us to course Data v3 and to the Anthropic API, co-built the dispatch desk, the decision explanation and the network map, and built the live workshop queues. She compared three AI models and studied 14 mistakes to fix two root causes. In Sprint 3 she worked on the desk API, dispatcher override and guardrails, ran the speech and rule-baseline measurements, wrote the Readme and co-wrote the Evaluation report |
| Vanshika Dhamija | Shaped the system and proved it works. Vanshika designed the architecture and led the Sprint 1 deck. She co-built the dispatch desk, the decision explanation and the network map, and built the shared inbox and the Simulation Lab. She designed the tests that every result in our evaluation rests on: the 30-request test set and its frozen labels, the 16 sealed unseen requests and both accuracy runs, including the fix that took the test set from 28 to 30 of 30. In Sprint 3 she wrote the red-team set, built the recovery plans and the workshop replies on Telegram with Aditya, led the explanation review and co-wrote the Evaluation report and Documentation |
| Yin Ning | Checks our work before submission: testing the setup steps, checking sources and proofreading. His tasks are in the Sprint 3 table |

## Collaboration dynamics

We met in person through each sprint, split the work there and often built it together at the same table. Each of us still led one part of the system, so we could work in parallel between meetings. Add: how often we met, and where we talked between meetings.

We kept the evaluation apart from the code it measures where we could. Two of us labelled the 30 requests alone before comparing answers, and we agreed on 27 of 30 behaviours. The disagreements are logged in `eval/labeling/reconciliation.md`. We froze the held-out set with fingerprints before running it, and did the same for the 34 requests in Round 2. An AI assistant drafted Round 2, so a round written by someone who did not build the guards is still to do.

We used an AI coding assistant (Claude Code) for code, tests, labelling drafts, the documents and the film. Where AI drafted evaluation material, the Evaluation report says so.

Add: one honest sentence on where collaboration went badly, and what we changed.
