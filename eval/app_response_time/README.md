# App response time, end to end (25 October 2026)

Measured in the running desk (Streamlit, live model Claude Sonnet 5.5), not only on the server:
time from clicking **Evaluate request** to the answer card and timing bar being on screen,
for all 30 inbox requests, one run, headless Chrome at a 1600x900 window. Nothing was confirmed.

| Measure | App (click to answer on screen) | Server (from the timing bar) |
|---|---:|---:|
| Median | 2.52 s | 2.43 s |
| 90th percentile | 2.68 s | 2.55 s |
| Slowest | 5.84 s (R16) | 5.73 s |
| Under 10 s | 30 / 30 | 30 / 30 |

The screen adds about 0.1 s; nearly all the time is the model call. Raw numbers: `app_timing.csv`.
Script: `run_app_timing.py` (expects the desk on port 8503).
