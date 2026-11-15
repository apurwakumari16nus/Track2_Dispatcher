# Threadline

DSS5105 Data Science Projects, Capstone Track 2 (The Quick-Response Subcontracting Desk), Group 01.

Threadline is a dispatch desk for Sweater Co. A language model reads each chat request into a fixed form, plain Python checks it against the order book and chooses a workshop, and the dispatcher approves every dispatch from a native iPhone app or the team's Telegram chat. Workshops stay on Telegram and can reply in English, Hindi, Hinglish or Mandarin.

## Submission

| File | What it is |
|---|---|
| [`submission/Readme.pdf`](submission/Readme.pdf) | How to install, run and check Threadline |
| [`submission/Documentation.pdf`](submission/Documentation.pdf) | Problem, architecture, technical stack, features and limits |
| [`submission/Evaluation.pdf`](submission/Evaluation.pdf) | How we know it works, and where it does not |
| [`submission/Strategic_Recommendations.pdf`](submission/Strategic_Recommendations.pdf) | Where else generative AI can help |
| [`submission/Teams.pdf`](submission/Teams.pdf) | Roles, tasks and contribution |
| [`submission/Slide.pptx`](submission/Slide.pptx) | The final deck |

The demo video (Video.mp4) is in the submitted zip only, because it is larger than GitHub's 100 MB file limit. The decks for all three sprints are in [`presentations/`](presentations/).

## Quick start

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and Git. No API key is needed for the checks below.

```bash
git clone https://github.com/apurwakumari16nus/Track2_Dispatcher.git
cd Track2_Dispatcher
uv sync
cp .env.example .env
uv run pytest -q
uv run streamlit run src/app.py
```

The iPhone app, Telegram set-up, live reading with an API key and the commands that reproduce every evaluation number are in [`submission/Readme.pdf`](submission/Readme.pdf).

## Where things are

| Path | What it holds |
|---|---|
| `src/` | Desk: intake, guards, tools, allocator, control, API, Telegram, web UI |
| `ios/` | iPhone app, widgets, Siri intents |
| `harness/`, `data/` | Unchanged course simulator and data, plus held-out and red-team requests |
| `eval/` | Evaluation runners, labels and recorded results |
| `tests/` | Automated tests. No model calls by default |
| `benchmarks/`, `config/` | Model timing tools and a custom objective example |
| `docs/` | Design and specification notes. Start with `docs/design/mobile_app.md` |
| `submission/` | The final reports and deck |
| `presentations/` | Sprint 1, 2 and 3 decks |
