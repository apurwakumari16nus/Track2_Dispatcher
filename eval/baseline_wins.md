# Simulator evaluation: winners, baseline wins, and ties

Mean over **10 paired seeds**, starting at **5105**. Each policy uses the same orders and matching normal/shock seeds; stages mode is off.
Batches per run: **120**; pieces per run: **93500**.

All eight simulator metrics use the official `Simulator.metrics()` arithmetic. CSV values are unrounded. Percentages use 0-100; `objective=none` identifies a supplied baseline or the earliest-finish heuristic. Every allocator preset starts with fresh history and a fresh shock monitor.

Lower is better for mean_days, p90_days, pct_late, late_days, pct_defect, pct_defect_pieces, total_cost, and max_share. Derived fairness is `100 - max_share`, so higher is better. It measures concentration of pieces, not equality relative to workshop capacity. Fairness wins duplicate max_share wins and are not independent evidence.

Comparisons use unrounded values within each scenario. Values equal within relative/absolute tolerance 1e-12 are ties, never wins. Report values use up to ten significant digits. Improvement is in days, model cost units, or percentage points, not a relative percentage reduction.

## Best policy for every metric (including all ties)

| shock | metric | best_value | best_policy_or_objective |
| --- | --- | --- | --- |
| False | mean_days | 8.259823327 | earliest_finish, allocator:lateness |
| False | p90_days | 14.36968326 | earliest_finish, allocator:lateness |
| False | pct_late | 1.666666667 | earliest_finish, allocator:lateness |
| False | late_days | 0.1783333333 | earliest_finish, allocator:lateness |
| False | pct_defect | 2.583333333 | allocator:defect |
| False | pct_defect_pieces | 2.914438503 | allocator:defect |
| False | total_cost | 85960 | cheapest |
| False | max_share | 17.39572193 | allocator:robustness |
| False | fairness | 82.60427807 | allocator:robustness |
| True | mean_days | 8.509129897 | earliest_finish, allocator:lateness |
| True | p90_days | 15.33823529 | earliest_finish, allocator:lateness |
| True | pct_late | 1.916666667 | earliest_finish, allocator:lateness |
| True | late_days | 0.1908333333 | earliest_finish, allocator:lateness |
| True | pct_defect | 2.583333333 | allocator:defect |
| True | pct_defect_pieces | 2.914438503 | allocator:defect |
| True | total_cost | 85960 | cheapest |
| True | max_share | 17.90374332 | allocator:fairness |
| True | fairness | 82.09625668 | allocator:fairness |

## Every case where a baseline or heuristic beats an allocator preset

Each row is one strict pairwise win. All four comparison policies are checked against every preset for every metric; no losing allocator setting is omitted.

### Normal: 83 strict metric comparisons

| metric | baseline_or_heuristic | baseline_value | allocator_objective | allocator_value | improvement |
| --- | --- | --- | --- | --- | --- |
| mean_days | random_choice | 21.86567452 | defect | 164.364986 | 142.4993115 |
| mean_days | greedy_biggest | 50.30266544 | defect | 164.364986 | 114.0623206 |
| mean_days | cheapest | 106.1999512 | defect | 164.364986 | 58.16503477 |
| mean_days | earliest_finish | 8.259823327 | defect | 164.364986 | 156.1051627 |
| mean_days | earliest_finish | 8.259823327 | fairness | 19.46906038 | 11.20923705 |
| mean_days | earliest_finish | 8.259823327 | robustness | 18.91288689 | 10.65306357 |
| mean_days | earliest_finish | 8.259823327 | hybrid_lateness_fairness | 11.65213724 | 3.392313911 |
| mean_days | earliest_finish | 8.259823327 | hybrid_lateness_defect | 20.42970211 | 12.16987879 |
| p90_days | random_choice | 46.72637363 | defect | 285.8478992 | 239.1215255 |
| p90_days | random_choice | 46.72637363 | fairness | 54.1 | 7.373626374 |
| p90_days | random_choice | 46.72637363 | robustness | 53.97142857 | 7.245054945 |
| p90_days | greedy_biggest | 82.425 | defect | 285.8478992 | 203.4228992 |
| p90_days | cheapest | 195.6521739 | defect | 285.8478992 | 90.19572525 |
| p90_days | earliest_finish | 14.36968326 | defect | 285.8478992 | 271.4782159 |
| p90_days | earliest_finish | 14.36968326 | fairness | 54.1 | 39.73031674 |
| p90_days | earliest_finish | 14.36968326 | robustness | 53.97142857 | 39.60174531 |
| p90_days | earliest_finish | 14.36968326 | hybrid_lateness_fairness | 24.72853911 | 10.35885585 |
| p90_days | earliest_finish | 14.36968326 | hybrid_lateness_defect | 33.71955398 | 19.34987072 |
| pct_late | random_choice | 34.16666667 | defect | 95.08333333 | 60.91666667 |
| pct_late | greedy_biggest | 84.25 | defect | 95.08333333 | 10.83333333 |
| pct_late | cheapest | 91.83333333 | defect | 95.08333333 | 3.25 |
| pct_late | earliest_finish | 1.666666667 | defect | 95.08333333 | 93.41666667 |
| pct_late | earliest_finish | 1.666666667 | fairness | 24.41666667 | 22.75 |
| pct_late | earliest_finish | 1.666666667 | robustness | 23 | 21.33333333 |
| pct_late | earliest_finish | 1.666666667 | hybrid_lateness_fairness | 5.083333333 | 3.416666667 |
| pct_late | earliest_finish | 1.666666667 | hybrid_lateness_defect | 18.5 | 16.83333333 |
| late_days | random_choice | 6.1325 | defect | 139.8683333 | 133.7358333 |
| late_days | random_choice | 6.1325 | fairness | 7.195 | 1.0625 |
| late_days | random_choice | 6.1325 | robustness | 6.839166667 | 0.7066666667 |
| late_days | greedy_biggest | 26.52833333 | defect | 139.8683333 | 113.34 |
| late_days | cheapest | 81.91583333 | defect | 139.8683333 | 57.9525 |
| late_days | earliest_finish | 0.1783333333 | defect | 139.8683333 | 139.69 |
| late_days | earliest_finish | 0.1783333333 | fairness | 7.195 | 7.016666667 |
| late_days | earliest_finish | 0.1783333333 | robustness | 6.839166667 | 6.660833333 |
| late_days | earliest_finish | 0.1783333333 | hybrid_lateness_fairness | 0.4333333333 | 0.255 |
| late_days | earliest_finish | 0.1783333333 | hybrid_lateness_defect | 1.785 | 1.606666667 |
| pct_defect | random_choice | 5.166666667 | lateness | 6.583333333 | 1.416666667 |
| pct_defect | random_choice | 5.166666667 | fairness | 5.75 | 0.5833333333 |
| pct_defect | random_choice | 5.166666667 | robustness | 5.583333333 | 0.4166666667 |
| pct_defect | random_choice | 5.166666667 | hybrid_lateness_fairness | 5.5 | 0.3333333333 |
| pct_defect | greedy_biggest | 5.166666667 | lateness | 6.583333333 | 1.416666667 |
| pct_defect | greedy_biggest | 5.166666667 | fairness | 5.75 | 0.5833333333 |
| pct_defect | greedy_biggest | 5.166666667 | robustness | 5.583333333 | 0.4166666667 |
| pct_defect | greedy_biggest | 5.166666667 | hybrid_lateness_fairness | 5.5 | 0.3333333333 |
| pct_defect_pieces | random_choice | 5.598930481 | lateness | 7.181818182 | 1.582887701 |
| pct_defect_pieces | random_choice | 5.598930481 | fairness | 6.50802139 | 0.9090909091 |
| pct_defect_pieces | random_choice | 5.598930481 | robustness | 6.43315508 | 0.8342245989 |
| pct_defect_pieces | random_choice | 5.598930481 | hybrid_lateness_fairness | 6.219251337 | 0.6203208556 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | lateness | 7.181818182 | 1.903743316 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | fairness | 6.50802139 | 1.229946524 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | robustness | 6.43315508 | 1.155080214 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | hybrid_lateness_fairness | 6.219251337 | 0.9411764706 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | hybrid_lateness_defect | 5.582887701 | 0.3048128342 |
| total_cost | random_choice | 111780 | lateness | 115566.5 | 3786.5 |
| total_cost | random_choice | 111780 | defect | 129920 | 18140 |
| total_cost | random_choice | 111780 | fairness | 116028 | 4248 |
| total_cost | random_choice | 111780 | robustness | 115741.5 | 3961.5 |
| total_cost | random_choice | 111780 | hybrid_lateness_fairness | 113172 | 1392 |
| total_cost | greedy_biggest | 108430 | lateness | 115566.5 | 7136.5 |
| total_cost | greedy_biggest | 108430 | defect | 129920 | 21490 |
| total_cost | greedy_biggest | 108430 | fairness | 116028 | 7598 |
| total_cost | greedy_biggest | 108430 | robustness | 115741.5 | 7311.5 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_fairness | 113172 | 4742 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_defect | 109319.5 | 889.5 |
| total_cost | cheapest | 85960 | lateness | 115566.5 | 29606.5 |
| total_cost | cheapest | 85960 | defect | 129920 | 43960 |
| total_cost | cheapest | 85960 | fairness | 116028 | 30068 |
| total_cost | cheapest | 85960 | robustness | 115741.5 | 29781.5 |
| total_cost | cheapest | 85960 | hybrid_lateness_fairness | 113172 | 27212 |
| total_cost | cheapest | 85960 | hybrid_lateness_defect | 109319.5 | 23359.5 |
| total_cost | earliest_finish | 115566.5 | defect | 129920 | 14353.5 |
| total_cost | earliest_finish | 115566.5 | fairness | 116028 | 461.5 |
| total_cost | earliest_finish | 115566.5 | robustness | 115741.5 | 175 |
| max_share | random_choice | 22.62032086 | lateness | 26.28342246 | 3.663101604 |
| max_share | random_choice | 22.62032086 | defect | 70.16042781 | 47.54010695 |
| max_share | random_choice | 22.62032086 | hybrid_lateness_defect | 40.75935829 | 18.13903743 |
| max_share | earliest_finish | 26.28342246 | defect | 70.16042781 | 43.87700535 |
| max_share | earliest_finish | 26.28342246 | hybrid_lateness_defect | 40.75935829 | 14.47593583 |
| fairness | random_choice | 77.37967914 | lateness | 73.71657754 | 3.663101604 |
| fairness | random_choice | 77.37967914 | defect | 29.83957219 | 47.54010695 |
| fairness | random_choice | 77.37967914 | hybrid_lateness_defect | 59.24064171 | 18.13903743 |
| fairness | earliest_finish | 73.71657754 | defect | 29.83957219 | 43.87700535 |
| fairness | earliest_finish | 73.71657754 | hybrid_lateness_defect | 59.24064171 | 14.47593583 |

### Shock: 80 strict metric comparisons

| metric | baseline_or_heuristic | baseline_value | allocator_objective | allocator_value | improvement |
| --- | --- | --- | --- | --- | --- |
| mean_days | random_choice | 23.27539674 | defect | 166.9783193 | 143.7029226 |
| mean_days | greedy_biggest | 51.84266544 | defect | 166.9783193 | 115.1356539 |
| mean_days | cheapest | 108.4049512 | defect | 166.9783193 | 58.5733681 |
| mean_days | earliest_finish | 8.509129897 | defect | 166.9783193 | 158.4691894 |
| mean_days | earliest_finish | 8.509129897 | fairness | 19.60062212 | 11.09149223 |
| mean_days | earliest_finish | 8.509129897 | robustness | 18.14388182 | 9.634751926 |
| mean_days | earliest_finish | 8.509129897 | hybrid_lateness_fairness | 12.35595361 | 3.846823713 |
| mean_days | earliest_finish | 8.509129897 | hybrid_lateness_defect | 20.32913979 | 11.82000989 |
| p90_days | random_choice | 49.03535595 | defect | 289.0823529 | 240.046997 |
| p90_days | random_choice | 49.03535595 | fairness | 54.89159664 | 5.85624069 |
| p90_days | greedy_biggest | 83.86176471 | defect | 289.0823529 | 205.2205882 |
| p90_days | cheapest | 198.4521739 | defect | 289.0823529 | 90.63017903 |
| p90_days | earliest_finish | 15.33823529 | defect | 289.0823529 | 273.7441176 |
| p90_days | earliest_finish | 15.33823529 | fairness | 54.89159664 | 39.55336134 |
| p90_days | earliest_finish | 15.33823529 | robustness | 47.26370394 | 31.92546865 |
| p90_days | earliest_finish | 15.33823529 | hybrid_lateness_fairness | 26.18626374 | 10.84802844 |
| p90_days | earliest_finish | 15.33823529 | hybrid_lateness_defect | 33.85833872 | 18.52010343 |
| pct_late | random_choice | 38.16666667 | defect | 95.08333333 | 56.91666667 |
| pct_late | greedy_biggest | 84.91666667 | defect | 95.08333333 | 10.16666667 |
| pct_late | cheapest | 91.83333333 | defect | 95.08333333 | 3.25 |
| pct_late | earliest_finish | 1.916666667 | defect | 95.08333333 | 93.16666667 |
| pct_late | earliest_finish | 1.916666667 | fairness | 26.08333333 | 24.16666667 |
| pct_late | earliest_finish | 1.916666667 | robustness | 22.75 | 20.83333333 |
| pct_late | earliest_finish | 1.916666667 | hybrid_lateness_fairness | 8.5 | 6.583333333 |
| pct_late | earliest_finish | 1.916666667 | hybrid_lateness_defect | 20.91666667 | 19 |
| late_days | random_choice | 7.165833333 | defect | 142.4816667 | 135.3158333 |
| late_days | greedy_biggest | 28.04666667 | defect | 142.4816667 | 114.435 |
| late_days | cheapest | 84.12 | defect | 142.4816667 | 58.36166667 |
| late_days | earliest_finish | 0.1908333333 | defect | 142.4816667 | 142.2908333 |
| late_days | earliest_finish | 0.1908333333 | fairness | 7.148333333 | 6.9575 |
| late_days | earliest_finish | 0.1908333333 | robustness | 5.9975 | 5.806666667 |
| late_days | earliest_finish | 0.1908333333 | hybrid_lateness_fairness | 0.6258333333 | 0.435 |
| late_days | earliest_finish | 0.1908333333 | hybrid_lateness_defect | 1.908333333 | 1.7175 |
| pct_defect | random_choice | 5.166666667 | lateness | 6.583333333 | 1.416666667 |
| pct_defect | random_choice | 5.166666667 | fairness | 5.833333333 | 0.6666666667 |
| pct_defect | random_choice | 5.166666667 | robustness | 5.5 | 0.3333333333 |
| pct_defect | random_choice | 5.166666667 | hybrid_lateness_fairness | 5.833333333 | 0.6666666667 |
| pct_defect | greedy_biggest | 5.166666667 | lateness | 6.583333333 | 1.416666667 |
| pct_defect | greedy_biggest | 5.166666667 | fairness | 5.833333333 | 0.6666666667 |
| pct_defect | greedy_biggest | 5.166666667 | robustness | 5.5 | 0.3333333333 |
| pct_defect | greedy_biggest | 5.166666667 | hybrid_lateness_fairness | 5.833333333 | 0.6666666667 |
| pct_defect_pieces | random_choice | 5.598930481 | lateness | 7.117647059 | 1.518716578 |
| pct_defect_pieces | random_choice | 5.598930481 | fairness | 6.721925134 | 1.122994652 |
| pct_defect_pieces | random_choice | 5.598930481 | robustness | 6.090909091 | 0.4919786096 |
| pct_defect_pieces | random_choice | 5.598930481 | hybrid_lateness_fairness | 6.561497326 | 0.9625668449 |
| pct_defect_pieces | random_choice | 5.598930481 | hybrid_lateness_defect | 5.786096257 | 0.1871657754 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | lateness | 7.117647059 | 1.839572193 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | fairness | 6.721925134 | 1.443850267 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | robustness | 6.090909091 | 0.8128342246 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | hybrid_lateness_fairness | 6.561497326 | 1.28342246 |
| pct_defect_pieces | greedy_biggest | 5.278074866 | hybrid_lateness_defect | 5.786096257 | 0.5080213904 |
| total_cost | random_choice | 111780 | lateness | 115459.5 | 3679.5 |
| total_cost | random_choice | 111780 | defect | 129920 | 18140 |
| total_cost | random_choice | 111780 | fairness | 115537 | 3757 |
| total_cost | random_choice | 111780 | robustness | 115097.5 | 3317.5 |
| total_cost | random_choice | 111780 | hybrid_lateness_fairness | 113185 | 1405 |
| total_cost | greedy_biggest | 108430 | lateness | 115459.5 | 7029.5 |
| total_cost | greedy_biggest | 108430 | defect | 129920 | 21490 |
| total_cost | greedy_biggest | 108430 | fairness | 115537 | 7107 |
| total_cost | greedy_biggest | 108430 | robustness | 115097.5 | 6667.5 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_fairness | 113185 | 4755 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_defect | 108975 | 545 |
| total_cost | cheapest | 85960 | lateness | 115459.5 | 29499.5 |
| total_cost | cheapest | 85960 | defect | 129920 | 43960 |
| total_cost | cheapest | 85960 | fairness | 115537 | 29577 |
| total_cost | cheapest | 85960 | robustness | 115097.5 | 29137.5 |
| total_cost | cheapest | 85960 | hybrid_lateness_fairness | 113185 | 27225 |
| total_cost | cheapest | 85960 | hybrid_lateness_defect | 108975 | 23015 |
| total_cost | earliest_finish | 115459.5 | defect | 129920 | 14460.5 |
| total_cost | earliest_finish | 115459.5 | fairness | 115537 | 77.5 |
| max_share | random_choice | 22.62032086 | lateness | 26.52406417 | 3.903743316 |
| max_share | random_choice | 22.62032086 | defect | 70.16042781 | 47.54010695 |
| max_share | random_choice | 22.62032086 | hybrid_lateness_defect | 40.26737968 | 17.64705882 |
| max_share | earliest_finish | 26.52406417 | defect | 70.16042781 | 43.63636364 |
| max_share | earliest_finish | 26.52406417 | hybrid_lateness_defect | 40.26737968 | 13.74331551 |
| fairness | random_choice | 77.37967914 | lateness | 73.47593583 | 3.903743316 |
| fairness | random_choice | 77.37967914 | defect | 29.83957219 | 47.54010695 |
| fairness | random_choice | 77.37967914 | hybrid_lateness_defect | 59.73262032 | 17.64705882 |
| fairness | earliest_finish | 73.47593583 | defect | 29.83957219 | 43.63636364 |
| fairness | earliest_finish | 73.47593583 | hybrid_lateness_defect | 59.73262032 | 13.74331551 |

## Ties between comparison policies and allocator presets

| shock | metric | baseline_or_heuristic | baseline_value | allocator_objective | allocator_value |
| --- | --- | --- | --- | --- | --- |
| False | mean_days | earliest_finish | 8.259823327 | lateness | 8.259823327 |
| False | p90_days | earliest_finish | 14.36968326 | lateness | 14.36968326 |
| False | pct_late | earliest_finish | 1.666666667 | lateness | 1.666666667 |
| False | late_days | earliest_finish | 0.1783333333 | lateness | 0.1783333333 |
| False | pct_defect | earliest_finish | 6.583333333 | lateness | 6.583333333 |
| False | pct_defect_pieces | earliest_finish | 7.181818182 | lateness | 7.181818182 |
| False | total_cost | earliest_finish | 115566.5 | lateness | 115566.5 |
| False | max_share | greedy_biggest | 70.16042781 | defect | 70.16042781 |
| False | max_share | cheapest | 70.16042781 | defect | 70.16042781 |
| False | max_share | earliest_finish | 26.28342246 | lateness | 26.28342246 |
| False | fairness | greedy_biggest | 29.83957219 | defect | 29.83957219 |
| False | fairness | cheapest | 29.83957219 | defect | 29.83957219 |
| False | fairness | earliest_finish | 73.71657754 | lateness | 73.71657754 |
| True | mean_days | earliest_finish | 8.509129897 | lateness | 8.509129897 |
| True | p90_days | earliest_finish | 15.33823529 | lateness | 15.33823529 |
| True | pct_late | earliest_finish | 1.916666667 | lateness | 1.916666667 |
| True | late_days | earliest_finish | 0.1908333333 | lateness | 0.1908333333 |
| True | pct_defect | earliest_finish | 6.583333333 | lateness | 6.583333333 |
| True | pct_defect_pieces | earliest_finish | 7.117647059 | lateness | 7.117647059 |
| True | total_cost | earliest_finish | 115459.5 | lateness | 115459.5 |
| True | max_share | greedy_biggest | 70.16042781 | defect | 70.16042781 |
| True | max_share | cheapest | 70.16042781 | defect | 70.16042781 |
| True | max_share | earliest_finish | 26.52406417 | lateness | 26.52406417 |
| True | fairness | greedy_biggest | 29.83957219 | defect | 29.83957219 |
| True | fairness | cheapest | 29.83957219 | defect | 29.83957219 |
| True | fairness | earliest_finish | 73.47593583 | lateness | 73.47593583 |

## What the strong heuristic adds to the interpretation

- Normal: earliest_finish ties allocator preset(s) **lateness** on all eight metrics. These results do not show those settings beating the simple earliest-finish heuristic.
- Shock: earliest_finish ties allocator preset(s) **lateness** on all eight metrics. These results do not show those settings beating the simple earliest-finish heuristic.

The allocator additionally supports configurable preferences, exclusions, decision evidence, and queue-anomaly monitoring. Those capabilities do not establish a scheduling improvement over a tied or better heuristic. Avoiding a suspect workshop in shock_trace.py is not itself proof of better aggregate turnaround.

## Scope and reproducibility

These are averages of per-run metrics over paired seeds, not a held-out natural-language evaluation or a statistical confidence claim. These supplied orders and seed 5105 have been used during development; report that use honestly. Additional seeds alone do not make these orders unseen. The final Evaluation.pdf still needs the chat evaluation and individual failure analysis.

The v3 harness uses a separate random stream for target selection; paired normal/shock runs use matching defect draws. Different choices can still produce different defect outcomes because workshop risks differ. The evaluator never passes the hidden target or closure dates to the allocator.

The p90 is `sorted_days[int(0.9 * n)]`, not an interpolated percentile. pct_late and pct_defect count batches; late_days averages lateness over all batches; pct_defect_pieces counts pieces in defective batches; max_share counts pieces. A lower unit-cost policy may win on spending while losing on delivery. There is no declared overall winner across conflicting metrics.

Reproduce: `python eval/run_simulator.py --seed 5105 --seeds 10`. Use `--output-dir eval/seed_OTHER` to preserve separate experiments.

### Mean paired shock changes

Shock minus normal over matching seeds. Positive means worse; percentage changes are percentage points. A negative change can reflect rerouting, not a generally beneficial closure.

| policy | objective | delta_pct_late | delta_late_days |
| --- | --- | --- | --- |
| random_choice | none | 4 | 1.033333333 |
| greedy_biggest | none | 0.6666666667 | 1.518333333 |
| cheapest | none | 0 | 2.204166667 |
| earliest_finish | none | 0.25 | 0.0125 |
| allocator | lateness | 0.25 | 0.0125 |
| allocator | defect | 0 | 2.613333333 |
| allocator | fairness | 1.666666667 | -0.04666666667 |
| allocator | robustness | -0.25 | -0.8416666667 |
| allocator | hybrid_lateness_fairness | 3.416666667 | 0.1925 |
| allocator | hybrid_lateness_defect | 2.416666667 | 0.1233333333 |

### Course objective criteria and guardrails

Lateness uses both pct_late and late_days. Defects use pct_defect_pieces. Fairness uses max_share (a share tie can win with improved lateness). Robustness uses shock-minus-normal pct_late and late_days. Defect and fairness must not have higher pct_late than random in that scenario; robustness must not have higher normal pct_late than random. A qualifying win needs the required metric improvement AND its guardrail. Ties are not strict wins. Hybrid presets have no invented pass rule and remain fully reported above.

| objective | scenario | comparator | guardrail_passed | required_metric_win | qualifying_win |
| --- | --- | --- | --- | --- | --- |
| lateness | normal | random_choice | True | True | True |
| lateness | normal | greedy_biggest | True | True | True |
| lateness | normal | cheapest | True | True | True |
| lateness | normal | earliest_finish | True | False | False |
| lateness | shock | random_choice | True | True | True |
| lateness | shock | greedy_biggest | True | True | True |
| lateness | shock | cheapest | True | True | True |
| lateness | shock | earliest_finish | True | False | False |
| defect | normal | random_choice | False | True | False |
| defect | normal | greedy_biggest | False | True | False |
| defect | normal | cheapest | False | True | False |
| defect | normal | earliest_finish | False | True | False |
| defect | shock | random_choice | False | True | False |
| defect | shock | greedy_biggest | False | True | False |
| defect | shock | cheapest | False | True | False |
| defect | shock | earliest_finish | False | True | False |
| fairness | normal | random_choice | True | True | True |
| fairness | normal | greedy_biggest | True | True | True |
| fairness | normal | cheapest | True | True | True |
| fairness | normal | earliest_finish | True | True | True |
| fairness | shock | random_choice | True | True | True |
| fairness | shock | greedy_biggest | True | True | True |
| fairness | shock | cheapest | True | True | True |
| fairness | shock | earliest_finish | True | True | True |
| robustness | paired change | random_choice | True | True | True |
| robustness | paired change | greedy_biggest | True | True | True |
| robustness | paired change | cheapest | True | True | True |
| robustness | paired change | earliest_finish | True | True | True |

### Queue-anomaly limitation

The official harness immediately adds future closure delay to an affected queue. In the default robustness trace, the monitor flags W2 on day 26, before closure starts on day 30. This is a response to a simulated queue anomaly, not evidence of realistic advance detection. Rework can also trigger flags. Preserve the official harness and disclose this caveat.

### Objective settings used

| preset | w_lateness | w_defect | w_fairness | w_robustness | w_cost | name |
| --- | --- | --- | --- | --- | --- | --- |
| lateness | 1 | 0 | 0 | 0 | 0 | lateness |
| defect | 0 | 1 | 0 | 0 | 0 | defect |
| fairness | 0 | 0 | 1 | 0 | 0 | fairness |
| robustness | 0 | 0 | 0 | 1 | 0 | robustness |
| hybrid_lateness_fairness | 0.9 | 0 | 0.1 | 0 | 0 | hybrid_lateness_fairness |
| hybrid_lateness_defect | 0.6 | 0.4 | 0 | 0 | 0 | hybrid_lateness_defect |

### Input and implementation fingerprints (SHA-256)

- `data/orders.csv`: `0880af9742fe7cc0923c5009e2de48a0bedb57b78cc294e35a1c9721fe0311f8`
- `data/workshops.csv`: `d7e1c97d3d338a2b5aef8e35f167e3582f22c4526e9c736c5b4c8125505ec59e`
- `harness/simulate.py`: `b845804ad1229f593627b6ef1a6482258331178dbc4ec535274103fc3244593b`
- `src/tools.py`: `4f1621b079e3dc43a41879300aa2142c057b3b09586b85cf8eab2250644fa423`
- `src/objectives.py`: `a18f3033165daac69c23b826bd6f478c2d424bd9119740fa4606497af062926a`
- `src/allocator.py`: `c543eb93c93467669c90e81c83946abdf65ccd23f8acfadc8f93350b6aa0ae49`
- `src/heuristic.py`: `730c3cebb9c5279f904806a9bce1de398e709a3a630a352f05ee1f75f2a44469`
