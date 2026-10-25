# Model comparison: Haiku 5.5 vs Sonnet 5.5 vs Opus 5.5

Same code, prompt, rules and frozen labels; only the model differs. Dev = 30 inbox requests (used in development); held-out = 16 team requests. Haiku dev results are after the date-reader fix. Timing and tokens come from each model's live run (one run each; Claude has no temperature control, so repeat runs may differ slightly). Cost is an estimate from `benchmarks/pricing.json` (Anthropic list prices), not a bill.

| Model | Set | Behaviour | Decision | No invented numbers | Requests with any failed check | Median s | p90 s | Tokens in / out | Est. cost (USD) |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| Haiku 5.5 | heldout (16) | 15/16 | 13/16 | 16/16 | 3 | 4.08 | 6.02 | 63,715 / 11,830 | 0.012 |
| Haiku 5.5 | dev (30) | 30/30 | 30/30 | 30/30 | 1 | 3.97 | 5.23 | 119,629 / 20,802 | 0.022 |
| Sonnet 5.5 | heldout (16) | 15/16 | 14/16 | 16/16 | 3 | 2.24 | 3.24 | 63,715 / 3,947 | 0.167 |
| Sonnet 5.5 | dev (30) | 30/30 | 30/30 | 30/30 | 3 | 2.41 | 3.25 | 119,629 / 7,387 | 0.313 |
| Opus 5.5 | heldout (16) | 15/16 | 14/16 | 16/16 | 3 | 3.93 | 7.35 | 63,715 / 5,769 | 0.370 |
| Opus 5.5 | dev (30) | 30/30 | 30/30 | 30/30 | 2 | 3.10 | 5.79 | 119,629 / 9,119 | 0.661 |

## Requests with any failed check

- **Haiku / heldout:** R34 (behaviour, decision); R36 (decision, constraint); R44 (decision)
- **Haiku / dev:** R23 (constraint)
- **Sonnet / heldout:** R32 (constraint); R34 (behaviour, decision); R44 (decision, constraint)
- **Sonnet / dev:** R15 (constraint); R16 (constraint); R23 (constraint)
- **Opus / heldout:** R34 (behaviour, decision); R38 (decision, constraint); R44 (constraint)
- **Opus / dev:** R15 (constraint); R23 (constraint)

Total estimated cost for the 46 requests: Haiku $0.035; Sonnet $0.480; Opus $1.031.
