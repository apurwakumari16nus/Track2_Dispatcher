# Hybrid weight sweep: seeds 6105-6114

## Normal (mean over seeds)

| setting | pct_late | late_days | max_share | pct_defect_pieces | total_cost |
| --- | --- | --- | --- | --- | --- |
| random | 35.33 | 6.13 | 22.62 | 5.54 | 111,780.00 |
| earliest finish | 1.75 | 0.15 | 26.75 | 6.61 | 115,705.00 |
| lateness 1.0 / fairness 0.0 | 1.75 | 0.15 | 26.75 | 6.61 | 115,705.00 |
| lateness 0.9 / fairness 0.1 | 4.67 | 0.37 | 19.81 | 5.58 | 113,305.00 |
| lateness 0.8 / fairness 0.2 | 6.58 | 0.49 | 20.33 | 5.26 | 113,224.00 |
| lateness 0.7 / fairness 0.3 | 7.25 | 0.55 | 20.90 | 4.93 | 113,179.00 |
| lateness 0.6 / fairness 0.4 | 7.42 | 0.53 | 20.76 | 5.45 | 113,113.00 |
| lateness 0.5 / fairness 0.5 | 8.00 | 0.49 | 20.08 | 5.30 | 113,154.50 |
| lateness 0.4 / fairness 0.6 | 9.08 | 0.58 | 20.57 | 5.44 | 113,318.00 |
| lateness 0.3 / fairness 0.7 | 11.92 | 0.70 | 20.39 | 4.95 | 113,413.50 |
| lateness 0.2 / fairness 0.8 | 15.17 | 1.00 | 20.66 | 5.73 | 113,494.00 |
| lateness 0.1 / fairness 0.9 | 15.67 | 1.91 | 19.24 | 5.39 | 114,149.00 |
| lateness 0.0 / fairness 1.0 | 24.50 | 7.22 | 17.49 | 5.14 | 116,045.00 |

## Shock (mean over seeds)

| setting | pct_late | late_days | max_share | pct_defect_pieces | total_cost |
| --- | --- | --- | --- | --- | --- |
| random | 39.00 | 7.20 | 22.62 | 5.54 | 111,780.00 |
| earliest finish | 2.17 | 0.16 | 27.07 | 6.73 | 115,245.00 |
| lateness 1.0 / fairness 0.0 | 2.17 | 0.16 | 27.07 | 6.73 | 115,245.00 |
| lateness 0.9 / fairness 0.1 | 9.08 | 0.68 | 19.48 | 5.76 | 113,179.00 |
| lateness 0.8 / fairness 0.2 | 10.08 | 0.75 | 19.61 | 5.78 | 113,059.00 |
| lateness 0.7 / fairness 0.3 | 10.92 | 0.82 | 19.73 | 5.96 | 113,102.00 |
| lateness 0.6 / fairness 0.4 | 11.58 | 0.90 | 20.19 | 5.96 | 113,071.00 |
| lateness 0.5 / fairness 0.5 | 11.08 | 0.82 | 19.52 | 5.30 | 112,999.00 |
| lateness 0.4 / fairness 0.6 | 12.25 | 0.88 | 19.85 | 6.00 | 113,126.00 |
| lateness 0.3 / fairness 0.7 | 14.33 | 1.00 | 19.57 | 5.79 | 113,206.00 |
| lateness 0.2 / fairness 0.8 | 18.25 | 1.35 | 20.30 | 5.78 | 113,288.50 |
| lateness 0.1 / fairness 0.9 | 20.33 | 2.14 | 19.91 | 5.67 | 113,822.50 |
| lateness 0.0 / fairness 1.0 | 27.25 | 6.00 | 18.28 | 5.36 | 115,065.00 |

## Selection (rule fixed in advance)

Tolerance 5.0 pp over lateness-only: **chosen fairness share = 0.1**

Sensitivity of the rule to the tolerance:

- tolerance  2.0 pp: fairness share None
- tolerance  3.0 pp: fairness share 0.1
- tolerance  5.0 pp: fairness share 0.1
- tolerance  8.0 pp: fairness share 0.1
- tolerance 10.0 pp: fairness share 0.1
- tolerance 15.0 pp: fairness share 0.9
