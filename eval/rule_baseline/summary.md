# Rule-only readers against the LLM reader

Same labels, same reference allocator. keywords_seen is an upper bound: its author had read the messages.

| Set | Reader | Behaviour | Decision |
|---|---|---:|---:|
| dev | id_only | 22/30 | 19/30 |
| dev | keywords_seen | 29/30 | 29/30 |
| dev | keywords_blind | 19/30 | 17/30 |
| dev | Sonnet 5.5 with guards | 30/30 | 29/30 |
| heldout | id_only | 10/16 | 8/16 |
| heldout | keywords_seen | 16/16 | 16/16 |
| heldout | keywords_blind | 8/16 | 8/16 |
| heldout | Sonnet 5.5 with guards | 15/16 | 15/16 |

| redteam | id_only | 9/16 | 9/16 |
| redteam | keywords_seen | 9/16 | 9/16 |
| redteam | keywords_blind | 8/16 | 8/16 |
| redteam | Sonnet 5.5 with guards | 16/16 | 13/16 |
