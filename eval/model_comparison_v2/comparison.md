# After the two fixes: Haiku vs Sonnet vs Opus

**Fixes:** (1) separate send-date field in the template + date-conflict check; (2) team rule v2: speed and quality words count as a preference (and lowest defect must still make the date). Same 46 requests. Before = original system and labels. After = fixed system; scored against the original labels and against the v2 labels. All 'after' numbers are development results (the fixes and the rule were decided after seeing the held-out results). Cost is an estimate from benchmarks/pricing.json.

| Model | Set | Before: behaviour / decision | After, original labels | After, v2 labels | Any failed check (after, v2) | Median s | Max s | Est. cost (USD) |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |
| Haiku 5.5 | heldout (16) | 15/16 · 13/16 | 13/16 · 12/16 | **13/16 · 13/16** | 4 | 4.33 | 8.28 | 0.012 |
| Haiku 5.5 | dev (30) | 30/30 · 30/30 | 30/30 · 30/30 | **30/30 · 30/30** | 0 | 3.95 | 8.77 | 0.024 |
| Sonnet 5.5 | heldout (16) | 15/16 · 14/16 | 15/16 · 14/16 | **15/16 · 15/16** | 1 | 2.41 | 5.41 | 0.179 |
| Sonnet 5.5 | dev (30) | 30/30 · 30/30 | 30/30 · 30/30 | **30/30 · 30/30** | 2 | 2.43 | 4.46 | 0.335 |
| Opus 5.5 | heldout (16) | 15/16 · 14/16 | 15/16 · 14/16 | **15/16 · 15/16** | 1 | 4.30 | 8.09 | 0.390 |
| Opus 5.5 | dev (30) | 30/30 · 30/30 | 30/30 · 30/30 | **30/30 · 30/30** | 0 | 3.72 | 27.99 | 0.718 |

## Requests with any failed check (after the fixes, v2 labels)

- **Haiku / heldout:** R34 (behaviour, decision); R41 (constraint); R42 (behaviour, decision, constraint); R45 (behaviour, decision)
- **Haiku / dev:** none
- **Sonnet / heldout:** R34 (behaviour, decision)
- **Sonnet / dev:** R23 (constraint); R25 (constraint)
- **Opus / heldout:** R34 (behaviour, decision)
- **Opus / dev:** none
