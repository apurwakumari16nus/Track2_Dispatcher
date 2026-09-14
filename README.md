# track2-dispatch

Python project for subcontractor allocation using the shared Track 2 simulator.

## Project structure

```text
data/       Simulator input data
harness/    Shared simulator (simulate.py)
src/        Application and allocation logic
eval/       Evaluation code and results
docs/       Project documentation
tests/      Tests and import-path configuration
```

## Setup

Run these commands from the project root (the existing `Track2_dispatch/` directory).

1. Create and activate a virtual environment (macOS/Linux):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

   Set `OPENAI_API_KEY` in `.env` when adding OpenAI-powered functionality.
   The baseline simulator does not require an API key. Application code can use
   `python-dotenv` to load `.env`; copying the file alone does not load it.

4. Run the simulator's baseline policies:

   ```bash
   python harness/simulate.py
   ```

   Run with the workshop-closure shock:

   ```bash
   python harness/simulate.py --shock
   ```

The simulator reads `orders.csv` and `workshops.csv` from
`harness/../data/` (the project-root `data/` directory). Keep this relative layout.

`tests/conftest.py` adds `src/` and `harness/` to Python's import path during pytest
runs, so tests can import application modules and `simulate` directly. After adding
tests, run them with `pytest` from the project root.
