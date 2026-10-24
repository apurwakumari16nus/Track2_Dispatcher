"""Run the inbox evaluation (eval/run_inbox.py, unchanged) with per-request timing.

Each agent.handle() call is wrapped in src/tracing.py's trace(), which already
times the stages marked inside intake and agent. Nothing about the evaluation,
its scoring or the cache changes; this only reads the clock.

Writes <output-dir>/inbox_timing.csv, one row per request:
  total_ms      whole request on the server (LLM + Python)
  llm_ms        the language-model call (llm.call span; network included)
  parse_ms      prompt building, JSON parsing, schema and data validation
  engine_ms     Python decision engine: order lookup, allocation, tools
  checks_ms     explanation number check
  other_ms      everything else (root span's own time)
  cache         miss = a real API call this run; hit = replayed from cache
plus model, input/output tokens, and any error category.

Timings are only meaningful on cache MISSES: a cache hit replays a stored reply,
so its llm_ms is near zero. Usage: same arguments as run_inbox.py, e.g.
  uv run python eval/run_inbox_timed.py --model claude-haiku-5-5
"""

from __future__ import annotations

import csv
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE)]

import run_inbox as ri  # noqa: E402
import tracing  # noqa: E402

ROWS: dict[str, dict] = {}
_original_call = ri.CachedLLM.__call__
_original_handle = ri.agent.handle


def _rid(message: str) -> str:
    return message.split()[0]


def timed_call(self, prompt, message):
    hits_before, started = self.hits, time.perf_counter_ns()
    try:
        reply = _original_call(self, prompt, message)
        meta = reply.metadata or {}
        return reply
    except Exception as error:  # still record the timing, then re-raise
        meta = getattr(error, "llm_metadata", {}) or {}
        raise
    finally:
        row = ROWS.setdefault(_rid(message), {})
        usage = meta.get("usage") or {}
        row.update(cache="hit" if self.hits > hits_before else "miss",
                   call_wall_ms=round((time.perf_counter_ns() - started) / 1e6, 1),
                   model=meta.get("served_model") or meta.get("model") or "",
                   input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", "")),
                   output_tokens=usage.get("output_tokens", usage.get("completion_tokens", "")))


class _Recorder:
    """Wraps handle so the trace is read after it closes, also on errors."""

    def __call__(self, message, *args, **kwargs):
        rid = _rid(message)
        record = None
        try:
            with tracing.trace("inbox_request", request_id=rid) as record:
                return _original_handle(message, *args, **kwargs)
        finally:
            if record is not None:
                stages = {s["key"]: s["ms"] for s in tracing.stage_totals(record)}
                ROWS.setdefault(rid, {}).update(
                    total_ms=round(record.total_ms, 1), llm_ms=round(stages.get("llm", 0.0), 1),
                    parse_ms=round(stages.get("parse", 0.0), 1), engine_ms=round(stages.get("engine", 0.0), 1),
                    checks_ms=round(stages.get("checks", 0.0), 1), other_ms=round(stages.get("other", 0.0), 1),
                    error=record.error or "")


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = Path(argv[argv.index("--output-dir") + 1]) if "--output-dir" in argv else HERE
    ri.CachedLLM.__call__ = timed_call
    ri.agent.handle = _Recorder()
    try:
        ri.main(argv)
    finally:
        ri.CachedLLM.__call__, ri.agent.handle = _original_call, _original_handle
    cols = ["request_id", "total_ms", "llm_ms", "parse_ms", "engine_ms", "checks_ms", "other_ms",
            "cache", "model", "input_tokens", "output_tokens", "error"]
    rows = [{"request_id": rid, **{c: ROWS[rid].get(c, "") for c in cols[1:]}} for rid in sorted(ROWS)]
    path = out_dir / "inbox_timing.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    live = [r for r in rows if r["cache"] == "miss" and r["total_ms"] != ""]
    print(f"\nTiming written to {path} ({len(rows)} requests; {len(live)} cache misses, "
          f"i.e. real API calls unless --mock).")
    if live:
        tot = [r["total_ms"] for r in live]; llm = [r["llm_ms"] for r in live]
        q = statistics.quantiles(tot, n=10)[-1] if len(tot) >= 2 else tot[0]
        print(f"Per request (real calls only): median {statistics.median(tot) / 1000:.2f}s, "
              f"p90 {q / 1000:.2f}s, max {max(tot) / 1000:.2f}s; "
              f"LLM share of total {sum(llm) / sum(tot):.0%}; "
              f"Python engine median {statistics.median(r['engine_ms'] for r in live):.0f} ms.")


if __name__ == "__main__":
    main()
