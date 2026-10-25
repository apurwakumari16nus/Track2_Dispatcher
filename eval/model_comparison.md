# Intake model: Sonnet 5.5 against Haiku 5.5

Same 30 inbox requests, same frozen human labels (`eval/labels.csv`), same prompt,
schema and Python checks, scenario date 1 April 2026, lateness objective. Each model was
run once, live, with no cache (30 real API calls each).

* Haiku 5.5: `eval/inbox_timing.csv` and `eval/inbox_results.csv` (live run, before the
  date-reader fix); `eval/inbox_after_date_fix/` (the same Haiku replies re-scored with
  the current code).
* Sonnet 5.5: `eval/inbox_sonnet/` (live run, 25 October 2026, current code).

## Results

| Measure | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Behaviour correct (current code) | 30 / 30 | 30 / 30 |
| Decision correct (current code) | 30 / 30 | 30 / 30 |
| Explanation numbers verified | 30 / 30 | 30 / 30 |
| Late deadlines flagged | 21 / 21 | 21 / 21 |
| Constraint honoured | 29 / 30 (R23) | 28 / 30 (R23, R15) |
| Model call, median | 3.96 s | **2.24 s** |
| Model call, 90th percentile | 5.00 s | **2.60 s** |
| Slowest call | 7.38 s | 4.42 s |
| Tokens per call, in / out | 3,988 / 693 | 3,988 / 243 |
| Estimated cost per request | **US$0.00075** | US$0.0104 |
| Estimated cost per 1,000 requests | **US$0.75** | US$10.41 |

Cost uses the official prices in `benchmarks/pricing.json` (Haiku 5.5: $0.10 in / $0.50 out;
Sonnet 5.5: $2 in / $10 out, per million tokens).

The constraint misses are not model errors:
* **R23** ("split it across two shops if that gets it back faster"): the evaluated allocator
  always picks one workshop, so neither model's reading can be honoured there. The desk
  offers the split as a choice.
* **R15** ("asap", which also needs a clarification): Sonnet recorded the "asap" as a
  fastest-turnaround preference and the scorer counts that against it. Both models asked
  the same clarifying question, so the outcome is identical.

The validated readings differ on 3 requests (R01 and R29: Sonnet also fills in the product
category; R15: the preference above). None changes a behaviour or a decision.

**Why Haiku is not faster here:** it writes almost three times as many output tokens (693
against 243) at its default effort, and output is what takes time.

## Can Haiku match Sonnet with fewer tokens?

Haiku's extra output is its step-by-step thinking, which is billed and timed as output; the final
JSON is about the same size for both models. Lowering Haiku's effort (how much it thinks) was
tested on the same 30 requests (`eval/inbox_haiku_low/`, 25 October 2026):

| | Haiku 5.5, medium (default) | Haiku 5.5, low | Sonnet 5.5, high (default) |
|---|---|---|---|
| Behaviour and decision correct | 30 / 30 | 30 / 30 | 30 / 30 |
| Output tokens, median | 692 | 583 | 238 |
| Model call, median | 3.96 s | 3.37 s | **2.24 s** |
| Model call, 90th percentile | 5.00 s | 5.20 s | **2.60 s** |
| Cost per 1,000 requests | US$0.75 | **US$0.68** | US$10.41 |

Low effort keeps the accuracy and trims about 15% of the tokens, but Haiku still thinks longer than
Sonnet does on this short, factual task and stays about 1.1 seconds slower per request. Haiku
writes each token faster; it simply writes more than twice as many. The decision does not change.

## At scale: time saved against money spent

Mean time per request (whole request, model plus Python) and cost, per 1,000 requests:

| | Sonnet 5.5 | Haiku 5.5, default | Haiku 5.5, low effort |
|---|---|---|---|
| Time for 1,000 requests | 39.6 min | 68.3 min | 58.4 min |
| Cost for 1,000 requests | US$10.41 | US$0.75 | US$0.68 |

| Requests | Waiting saved by Sonnet (vs Haiku default) | Extra cost of Sonnet |
|---|---|---|
| 1,000 | 0.5 h | US$9.66 |
| 10,000 | 4.8 h | US$96.63 |
| 100,000 | 47.8 h | US$966 |
| 1,000,000 | 478 h | US$9,663 |

Sonnet buys back waiting time at about **US$20 per hour** against default Haiku (US$31 per hour
against low-effort Haiku), at every scale. Whether that is worth it depends only on whether a
person is waiting: on the desk and in the chat a dispatcher waits for each reply, so the time is
real; in background work (the whole-inbox run, overnight batches) nobody waits, so it is not.

## Limits

One run per model, on different days, so network conditions differ. Quality is measured on
the same 30 development requests the team labelled; no unseen requests yet. A controlled,
interleaved comparison (3 trials per model plus 13 stress cases) is ready in
`benchmarks/run_models.py` (about US$1.41) if a stronger claim is needed.

## Decision rule (fixed in `benchmarks/README.md` before testing)

Switch to Haiku only if it is (1) no worse on accuracy, (2) at least 30% faster at the
median, and (3) at most half the cost, with valid output and correct clarifications.

| Condition | Haiku result | Met? |
|---|---|---|
| No worse on accuracy | Equal: 30 / 30 on both | Yes |
| At least 30% faster | 77% **slower** (3.96 s against 2.24 s) | No |
| At most half the cost | About 7% of the cost | Yes |

**Decision: keep Sonnet 5.5 as the default intake model.** Quality is the same, Sonnet answers
about 1.7 seconds sooner per request, and the cost difference is small at desk volume (about
US$0.52 against $0.04 for 50 requests a day). Haiku at low effort was also tested and is still slower (see above). Revisit only if
volume reaches tens of thousands of requests a month, where the 14-fold cost gap starts to
matter.

## Applied in the app (25 October 2026)

* Desk and Telegram (a person waits for the reply): the configured model, Claude Sonnet 5.5.
* Whole-inbox run and other background work (nobody waits): Claude Haiku 5.5 at low effort
  (`intake.BACKGROUND_MODEL`, `intake.model_override`).
* The model that answered is shown on screen: in the desk's timing bar ("read by Claude Sonnet 5.5")
  and in the whole-inbox run's banner and result ("read by Claude Haiku 5.5").
