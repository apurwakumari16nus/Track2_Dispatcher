# Simulator evaluation: winners, baseline wins, and ties

Seed: **5105**. Each policy runs on the same supplied orders under both scenarios.
Batches per run: **120**; pieces per run: **93500**.

All six simulator metrics use the exact arithmetic in `Simulator.report()`. CSV values are unrounded. Percentages use 0-100; `objective=none` identifies a supplied baseline or the earliest-finish heuristic. Every allocator preset starts with fresh history and a fresh shock monitor.

Lower is better for mean_days, p90_days, pct_late, pct_defect, total_cost, and max_share. Derived fairness is `100 - max_share`, so higher is better. It measures concentration of pieces, not equality relative to workshop capacity. Fairness wins duplicate max_share wins and are not independent evidence.

Comparisons use unrounded values within each scenario. Values equal within relative/absolute tolerance 1e-12 are ties, never wins. Report values use up to ten significant digits. Improvement is in days, model cost units, or percentage points, not a relative percentage reduction.

## Best policy for every metric (including all ties)

| shock | metric | best_value | best_policy_or_objective |
| --- | --- | --- | --- |
| False | mean_days | 8.054749297 | earliest_finish, allocator:lateness |
| False | p90_days | 13.69230769 | earliest_finish, allocator:lateness |
| False | pct_late | 1.666666667 | earliest_finish, allocator:lateness |
| False | pct_defect | 1.666666667 | allocator:defect |
| False | total_cost | 85960 | cheapest |
| False | max_share | 17.48663102 | allocator:fairness, allocator:robustness |
| False | fairness | 82.51336898 | allocator:fairness, allocator:robustness |
| True | mean_days | 8.383526711 | earliest_finish, allocator:lateness |
| True | p90_days | 15.38235294 | earliest_finish, allocator:lateness |
| True | pct_late | 1.666666667 | earliest_finish, allocator:lateness |
| True | pct_defect | 1.666666667 | allocator:defect |
| True | total_cost | 85960 | cheapest |
| True | max_share | 17.32620321 | allocator:robustness |
| True | fairness | 82.67379679 | allocator:robustness |

## Every case where a baseline or heuristic beats an allocator preset

Each row is one strict pairwise win. All four comparison policies are checked against every preset for every metric; no losing allocator setting is omitted.

### Normal: 64 strict metric comparisons

| metric | baseline_or_heuristic | baseline_value | allocator_objective | allocator_value | improvement |
| --- | --- | --- | --- | --- | --- |
| mean_days | random_choice | 21.5231547 | defect | 162.5138305 | 140.9906758 |
| mean_days | greedy_biggest | 49.02371324 | defect | 162.5138305 | 113.4901173 |
| mean_days | cheapest | 105.1263935 | defect | 162.5138305 | 57.387437 |
| mean_days | earliest_finish | 8.054749297 | defect | 162.5138305 | 154.4590812 |
| mean_days | earliest_finish | 8.054749297 | fairness | 19.20005422 | 11.14530492 |
| mean_days | earliest_finish | 8.054749297 | robustness | 19.20005422 | 11.14530492 |
| mean_days | earliest_finish | 8.054749297 | hybrid_lateness_fairness | 12.19680121 | 4.142051918 |
| mean_days | earliest_finish | 8.054749297 | hybrid_lateness_defect | 20.42361203 | 12.36886273 |
| p90_days | random_choice | 45.61538462 | defect | 282.1470588 | 236.5316742 |
| p90_days | random_choice | 45.61538462 | fairness | 54.57142857 | 8.956043956 |
| p90_days | random_choice | 45.61538462 | robustness | 54.57142857 | 8.956043956 |
| p90_days | greedy_biggest | 80.625 | defect | 282.1470588 | 201.5220588 |
| p90_days | cheapest | 192.8695652 | defect | 282.1470588 | 89.27749361 |
| p90_days | earliest_finish | 13.69230769 | defect | 282.1470588 | 268.4547511 |
| p90_days | earliest_finish | 13.69230769 | fairness | 54.57142857 | 40.87912088 |
| p90_days | earliest_finish | 13.69230769 | robustness | 54.57142857 | 40.87912088 |
| p90_days | earliest_finish | 13.69230769 | hybrid_lateness_fairness | 25.44117647 | 11.74886878 |
| p90_days | earliest_finish | 13.69230769 | hybrid_lateness_defect | 33.23076923 | 19.53846154 |
| pct_late | random_choice | 34.16666667 | defect | 95 | 60.83333333 |
| pct_late | greedy_biggest | 84.16666667 | defect | 95 | 10.83333333 |
| pct_late | cheapest | 93.33333333 | defect | 95 | 1.666666667 |
| pct_late | earliest_finish | 1.666666667 | defect | 95 | 93.33333333 |
| pct_late | earliest_finish | 1.666666667 | fairness | 23.33333333 | 21.66666667 |
| pct_late | earliest_finish | 1.666666667 | robustness | 23.33333333 | 21.66666667 |
| pct_late | earliest_finish | 1.666666667 | hybrid_lateness_fairness | 5 | 3.333333333 |
| pct_late | earliest_finish | 1.666666667 | hybrid_lateness_defect | 15.83333333 | 14.16666667 |
| pct_defect | random_choice | 4.166666667 | lateness | 5 | 0.8333333333 |
| pct_defect | random_choice | 4.166666667 | fairness | 5 | 0.8333333333 |
| pct_defect | random_choice | 4.166666667 | robustness | 5 | 0.8333333333 |
| pct_defect | random_choice | 4.166666667 | hybrid_lateness_fairness | 5 | 0.8333333333 |
| pct_defect | greedy_biggest | 4.166666667 | lateness | 5 | 0.8333333333 |
| pct_defect | greedy_biggest | 4.166666667 | fairness | 5 | 0.8333333333 |
| pct_defect | greedy_biggest | 4.166666667 | robustness | 5 | 0.8333333333 |
| pct_defect | greedy_biggest | 4.166666667 | hybrid_lateness_fairness | 5 | 0.8333333333 |
| total_cost | random_choice | 111780 | lateness | 115640 | 3860 |
| total_cost | random_choice | 111780 | defect | 129920 | 18140 |
| total_cost | random_choice | 111780 | fairness | 116045 | 4265 |
| total_cost | random_choice | 111780 | robustness | 116045 | 4265 |
| total_cost | random_choice | 111780 | hybrid_lateness_fairness | 113385 | 1605 |
| total_cost | greedy_biggest | 108430 | lateness | 115640 | 7210 |
| total_cost | greedy_biggest | 108430 | defect | 129920 | 21490 |
| total_cost | greedy_biggest | 108430 | fairness | 116045 | 7615 |
| total_cost | greedy_biggest | 108430 | robustness | 116045 | 7615 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_fairness | 113385 | 4955 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_defect | 109360 | 930 |
| total_cost | cheapest | 85960 | lateness | 115640 | 29680 |
| total_cost | cheapest | 85960 | defect | 129920 | 43960 |
| total_cost | cheapest | 85960 | fairness | 116045 | 30085 |
| total_cost | cheapest | 85960 | robustness | 116045 | 30085 |
| total_cost | cheapest | 85960 | hybrid_lateness_fairness | 113385 | 27425 |
| total_cost | cheapest | 85960 | hybrid_lateness_defect | 109360 | 23400 |
| total_cost | earliest_finish | 115640 | defect | 129920 | 14280 |
| total_cost | earliest_finish | 115640 | fairness | 116045 | 405 |
| total_cost | earliest_finish | 115640 | robustness | 116045 | 405 |
| max_share | random_choice | 22.62032086 | lateness | 25.56149733 | 2.941176471 |
| max_share | random_choice | 22.62032086 | defect | 70.16042781 | 47.54010695 |
| max_share | random_choice | 22.62032086 | hybrid_lateness_defect | 41.28342246 | 18.6631016 |
| max_share | earliest_finish | 25.56149733 | defect | 70.16042781 | 44.59893048 |
| max_share | earliest_finish | 25.56149733 | hybrid_lateness_defect | 41.28342246 | 15.72192513 |
| fairness | random_choice | 77.37967914 | lateness | 74.43850267 | 2.941176471 |
| fairness | random_choice | 77.37967914 | defect | 29.83957219 | 47.54010695 |
| fairness | random_choice | 77.37967914 | hybrid_lateness_defect | 58.71657754 | 18.6631016 |
| fairness | earliest_finish | 74.43850267 | defect | 29.83957219 | 44.59893048 |
| fairness | earliest_finish | 74.43850267 | hybrid_lateness_defect | 58.71657754 | 15.72192513 |

### Shock: 56 strict metric comparisons

| metric | baseline_or_heuristic | baseline_value | allocator_objective | allocator_value | improvement |
| --- | --- | --- | --- | --- | --- |
| mean_days | random_choice | 23.36368038 | defect | 165.0020308 | 141.6383504 |
| mean_days | greedy_biggest | 51.03658088 | defect | 165.0020308 | 113.9654499 |
| mean_days | cheapest | 103.8843367 | defect | 165.0020308 | 61.11769413 |
| mean_days | earliest_finish | 8.383526711 | defect | 165.0020308 | 156.6185041 |
| mean_days | earliest_finish | 8.383526711 | fairness | 20.17487105 | 11.79134434 |
| mean_days | earliest_finish | 8.383526711 | robustness | 18.61289386 | 10.22936715 |
| mean_days | earliest_finish | 8.383526711 | hybrid_lateness_fairness | 13.77330042 | 5.389773705 |
| mean_days | earliest_finish | 8.383526711 | hybrid_lateness_defect | 19.71658466 | 11.33305794 |
| p90_days | random_choice | 48.35294118 | defect | 285.1176471 | 236.7647059 |
| p90_days | random_choice | 48.35294118 | fairness | 56.71428571 | 8.361344538 |
| p90_days | greedy_biggest | 81.25 | defect | 285.1176471 | 203.8676471 |
| p90_days | cheapest | 190.0434783 | defect | 285.1176471 | 95.0741688 |
| p90_days | earliest_finish | 15.38235294 | defect | 285.1176471 | 269.7352941 |
| p90_days | earliest_finish | 15.38235294 | fairness | 56.71428571 | 41.33193277 |
| p90_days | earliest_finish | 15.38235294 | robustness | 47.71428571 | 32.33193277 |
| p90_days | earliest_finish | 15.38235294 | hybrid_lateness_fairness | 31.42857143 | 16.04621849 |
| p90_days | earliest_finish | 15.38235294 | hybrid_lateness_defect | 34 | 18.61764706 |
| pct_late | random_choice | 39.16666667 | defect | 95 | 55.83333333 |
| pct_late | greedy_biggest | 86.66666667 | defect | 95 | 8.333333333 |
| pct_late | cheapest | 91.66666667 | defect | 95 | 3.333333333 |
| pct_late | earliest_finish | 1.666666667 | defect | 95 | 93.33333333 |
| pct_late | earliest_finish | 1.666666667 | fairness | 26.66666667 | 25 |
| pct_late | earliest_finish | 1.666666667 | robustness | 25.83333333 | 24.16666667 |
| pct_late | earliest_finish | 1.666666667 | hybrid_lateness_fairness | 15.83333333 | 14.16666667 |
| pct_late | earliest_finish | 1.666666667 | hybrid_lateness_defect | 21.66666667 | 20 |
| pct_defect | random_choice | 4.166666667 | lateness | 5 | 0.8333333333 |
| pct_defect | greedy_biggest | 4.166666667 | lateness | 5 | 0.8333333333 |
| total_cost | random_choice | 111780 | lateness | 115805 | 4025 |
| total_cost | random_choice | 111780 | defect | 129920 | 18140 |
| total_cost | random_choice | 111780 | fairness | 116045 | 4265 |
| total_cost | random_choice | 111780 | robustness | 115750 | 3970 |
| total_cost | random_choice | 111780 | hybrid_lateness_fairness | 113195 | 1415 |
| total_cost | greedy_biggest | 108430 | lateness | 115805 | 7375 |
| total_cost | greedy_biggest | 108430 | defect | 129920 | 21490 |
| total_cost | greedy_biggest | 108430 | fairness | 116045 | 7615 |
| total_cost | greedy_biggest | 108430 | robustness | 115750 | 7320 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_fairness | 113195 | 4765 |
| total_cost | greedy_biggest | 108430 | hybrid_lateness_defect | 109180 | 750 |
| total_cost | cheapest | 85960 | lateness | 115805 | 29845 |
| total_cost | cheapest | 85960 | defect | 129920 | 43960 |
| total_cost | cheapest | 85960 | fairness | 116045 | 30085 |
| total_cost | cheapest | 85960 | robustness | 115750 | 29790 |
| total_cost | cheapest | 85960 | hybrid_lateness_fairness | 113195 | 27235 |
| total_cost | cheapest | 85960 | hybrid_lateness_defect | 109180 | 23220 |
| total_cost | earliest_finish | 115805 | defect | 129920 | 14115 |
| total_cost | earliest_finish | 115805 | fairness | 116045 | 240 |
| max_share | random_choice | 22.62032086 | lateness | 26.14973262 | 3.529411765 |
| max_share | random_choice | 22.62032086 | defect | 70.16042781 | 47.54010695 |
| max_share | random_choice | 22.62032086 | hybrid_lateness_defect | 40.53475936 | 17.9144385 |
| max_share | earliest_finish | 26.14973262 | defect | 70.16042781 | 44.01069519 |
| max_share | earliest_finish | 26.14973262 | hybrid_lateness_defect | 40.53475936 | 14.38502674 |
| fairness | random_choice | 77.37967914 | lateness | 73.85026738 | 3.529411765 |
| fairness | random_choice | 77.37967914 | defect | 29.83957219 | 47.54010695 |
| fairness | random_choice | 77.37967914 | hybrid_lateness_defect | 59.46524064 | 17.9144385 |
| fairness | earliest_finish | 73.85026738 | defect | 29.83957219 | 44.01069519 |
| fairness | earliest_finish | 73.85026738 | hybrid_lateness_defect | 59.46524064 | 14.38502674 |

## Ties between comparison policies and allocator presets

| shock | metric | baseline_or_heuristic | baseline_value | allocator_objective | allocator_value |
| --- | --- | --- | --- | --- | --- |
| False | mean_days | earliest_finish | 8.054749297 | lateness | 8.054749297 |
| False | p90_days | earliest_finish | 13.69230769 | lateness | 13.69230769 |
| False | pct_late | earliest_finish | 1.666666667 | lateness | 1.666666667 |
| False | pct_defect | random_choice | 4.166666667 | hybrid_lateness_defect | 4.166666667 |
| False | pct_defect | greedy_biggest | 4.166666667 | hybrid_lateness_defect | 4.166666667 |
| False | pct_defect | earliest_finish | 5 | lateness | 5 |
| False | pct_defect | earliest_finish | 5 | fairness | 5 |
| False | pct_defect | earliest_finish | 5 | robustness | 5 |
| False | pct_defect | earliest_finish | 5 | hybrid_lateness_fairness | 5 |
| False | total_cost | earliest_finish | 115640 | lateness | 115640 |
| False | max_share | greedy_biggest | 70.16042781 | defect | 70.16042781 |
| False | max_share | cheapest | 70.16042781 | defect | 70.16042781 |
| False | max_share | earliest_finish | 25.56149733 | lateness | 25.56149733 |
| False | fairness | greedy_biggest | 29.83957219 | defect | 29.83957219 |
| False | fairness | cheapest | 29.83957219 | defect | 29.83957219 |
| False | fairness | earliest_finish | 74.43850267 | lateness | 74.43850267 |
| True | mean_days | earliest_finish | 8.383526711 | lateness | 8.383526711 |
| True | p90_days | earliest_finish | 15.38235294 | lateness | 15.38235294 |
| True | pct_late | earliest_finish | 1.666666667 | lateness | 1.666666667 |
| True | pct_defect | random_choice | 4.166666667 | fairness | 4.166666667 |
| True | pct_defect | random_choice | 4.166666667 | hybrid_lateness_fairness | 4.166666667 |
| True | pct_defect | greedy_biggest | 4.166666667 | fairness | 4.166666667 |
| True | pct_defect | greedy_biggest | 4.166666667 | hybrid_lateness_fairness | 4.166666667 |
| True | pct_defect | cheapest | 5 | lateness | 5 |
| True | pct_defect | earliest_finish | 5 | lateness | 5 |
| True | total_cost | earliest_finish | 115805 | lateness | 115805 |
| True | max_share | greedy_biggest | 70.16042781 | defect | 70.16042781 |
| True | max_share | cheapest | 70.16042781 | defect | 70.16042781 |
| True | max_share | earliest_finish | 26.14973262 | lateness | 26.14973262 |
| True | fairness | greedy_biggest | 29.83957219 | defect | 29.83957219 |
| True | fairness | cheapest | 29.83957219 | defect | 29.83957219 |
| True | fairness | earliest_finish | 73.85026738 | lateness | 73.85026738 |

## What the strong heuristic adds to the interpretation

- Normal: earliest_finish ties allocator preset(s) **lateness** on all six metrics. These results do not show those settings beating the ten-line heuristic.
- Shock: earliest_finish ties allocator preset(s) **lateness** on all six metrics. These results do not show those settings beating the ten-line heuristic.

The allocator additionally supports configurable preferences, exclusions, decision evidence, and queue-anomaly monitoring. Those capabilities do not establish a scheduling improvement over a tied or better heuristic. Avoiding a suspect workshop in shock_trace.py is not itself proof of better aggregate turnaround.

## Scope and reproducibility

This is one seeded simulator comparison, not a held-out natural-language evaluation or a statistical confidence claim. These supplied orders and seed 5105 have been used during development; report that use honestly. Additional seeds alone do not make these orders unseen. The final Evaluation.pdf still needs the chat evaluation and individual failure analysis.

Enabling shock consumes a random draw to select the target, shifting subsequent defect draws versus the normal run. Normal/shock differences therefore reflect both the closure and a changed rework sequence. The evaluator never passes the hidden target or closure dates to the allocator.

The p90 is `sorted_days[int(0.9 * n)]`, not an interpolated percentile. Late and defect rates count batches; max_share counts pieces. A lower unit-cost policy may win on spending while losing on delivery. There is no declared overall winner across conflicting metrics.

Reproduce: `python eval/run_simulator.py --seed 5105`. Use `--output-dir eval/seed_OTHER` to preserve separate experiments.

### Objective settings used

| preset | w_lateness | w_defect | w_fairness | w_robustness | w_cost | name |
| --- | --- | --- | --- | --- | --- | --- |
| lateness | 1 | 0 | 0 | 0 | 0 | lateness |
| defect | 0 | 1 | 0 | 0 | 0 | defect |
| fairness | 0 | 0 | 1 | 0 | 0 | fairness |
| robustness | 0 | 0 | 0 | 1 | 0 | robustness |
| hybrid_lateness_fairness | 0.7 | 0 | 0.3 | 0 | 0 | hybrid_lateness_fairness |
| hybrid_lateness_defect | 0.6 | 0.4 | 0 | 0 | 0 | hybrid_lateness_defect |

### Input and implementation fingerprints (SHA-256)

- `data/orders.csv`: `0880af9742fe7cc0923c5009e2de48a0bedb57b78cc294e35a1c9721fe0311f8`
- `data/workshops.csv`: `d7e1c97d3d338a2b5aef8e35f167e3582f22c4526e9c736c5b4c8125505ec59e`
- `harness/simulate.py`: `eee4780f8f550de70fec85d0698fa7176fe1918c14f9544b34fe022fc9ae9507`
- `src/tools.py`: `f9e8b0da476e7bdb2deebb166d0404448ec24f687947a9d1ae14f50df78526ed`
- `src/objectives.py`: `a0f018221e6b2c784b5520da0ad0b002ba2cd47ce4f3b884b2c2bbd37b111d3b`
- `src/allocator.py`: `c40638736d5cceeb7271fbad411d1375dcb8a7466779f72bf7bd385f9e231f2f`
- `src/heuristic.py`: `730c3cebb9c5279f904806a9bce1de398e709a3a630a352f05ee1f75f2a44469`
