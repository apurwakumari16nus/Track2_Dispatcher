"""Rebuild an extraction cache from a recorded inbox_audit.json, so new Python checks can be re-scored offline.

Each recorded model reply is stored under the cache key run_inbox.py would compute
today. That is only valid while the system prompt is unchanged: if the prompt
differs, the keys differ and run_inbox --offline reports cache misses instead of
silently scoring stale replies.

    python eval/replay_cache.py eval/inbox_sonnet/inbox_audit.json /tmp/sonnet_cache
    python eval/run_inbox.py --offline --cache-dir /tmp/sonnet_cache --model claude-sonnet-5-5 --output-dir ...
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "src"), str(ROOT / "harness")]

import intake
from run_inbox import TODAY, digest, write_json
from simulate import load_workshops


def main(audit_path: str, cache_dir: str) -> int:
    audit = json.loads(Path(audit_path).read_text())
    prompt = intake.build_system_prompt(TODAY, pd.read_csv(ROOT / "data/orders.csv"), load_workshops())
    written = 0
    for item in audit["requests"]:
        parsed = (item.get("response") or {}).get("parsed_request")
        if not parsed or not parsed.get("raw_llm_response"):
            continue   # an operational error or a guard that never called the model
        request = {"version": 1, "provider": audit["provider"], "model": audit["model"], "temperature": None,
                   "system_prompt": prompt, "message": item["raw_message"], "fixture_hash": None}
        payload = {"content": parsed["raw_llm_response"], "metadata": parsed["llm_metadata"], "error": None}
        write_json(Path(cache_dir) / f"{digest(request)}.json", {"request": request, "payload": payload, "payload_hash": digest(payload)})
        written += 1
    print(f"Wrote {written} cached replies from {audit_path} ({audit['model']}) to {cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
