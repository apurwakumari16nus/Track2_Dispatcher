"""Controlled extraction benchmark: Claude Sonnet 5.5 against Claude Haiku 5.5.

Same requests, system prompt, JSON schema, order and workshop data and
deterministic engine for both models; only the model ID changes. Each call runs
the whole evaluation (desk.make_preview) inside a trace, so it measures both the
model call and the full server-side evaluation. Nothing is written to the
operational audit logs, the session queues or records/traces.jsonl: every call
uses a fresh allocator and the 1 April queue snapshot, and results go only to
benchmarks/results/<run id>/.

Dry run is the default and makes no API call:

    uv run python benchmarks/run_models.py                 # plan and cost estimate
    uv run python benchmarks/run_models.py --execute       # paid run (asks for nothing else)
    uv run python benchmarks/run_models.py --summarize benchmarks/results/<run id>

Model settings are the production ones (intake._call_anthropic): structured
JSON output, no temperature, each model's default effort (Sonnet 5.5: high,
Haiku 5.5: medium), server-side fallback only where the model supports it
(Sonnet 5.5 yes, Haiku 5.5 no). --effort sets the same effort for both models
for a sensitivity run. Prompt caching is not used in production, so every call
is cold with respect to prompt caching; calls are sequential (concurrency 1)
and the model order is shuffled per trial with a fixed seed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import csv
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "harness")]

from allocator import Allocator  # noqa: E402
import desk  # noqa: E402
import intake  # noqa: E402
from objectives import PRESETS  # noqa: E402
import rehearsal  # noqa: E402
import tracing  # noqa: E402

MODELS = ("claude-sonnet-5-5", "claude-haiku-5-5")
HERE = Path(__file__).resolve().parent
PRICING = json.loads((HERE / "pricing.json").read_text())
STRESS = json.loads((HERE / "stress_cases.json").read_text())
# Recorded usage of one real Sonnet 5.5 call of this exact request shape (records/rehearsal_cache), used only for the dry-run estimate.
ESTIMATE_TOKENS = {"input": 3981, "output": 247}
CRITICAL = ("behaviour", "order_id", "pieces", "category", "due_date", "excluded_workshops")
FIELDS = CRITICAL + ("preference",)

# Pre-registered acceptance rule for switching the default extraction model to Haiku 5.5.
# Fixed before any results were seen; see benchmarks/README.md for the reasoning.
RULE = {
    "non_inferiority_margin_pp": 2.0,       # Haiku critical-field accuracy >= Sonnet - 2 points (reviewed cases)
    "max_unresolved_critical_errors": 0,    # no critical extraction error left unexplained
    "clarification_recall": 1.0,            # every case that needs a clarification gets one (no guessing)
    "min_schema_valid_rate": 0.99,
    "min_e2e_median_speedup": 0.30,         # median full evaluation at least 30% faster
    "max_cost_ratio": 0.50,                 # mean cost per successful extraction at most half of Sonnet's
}


def cases(include):
    out = []
    if "official" in include:
        for rid, line in rehearsal.inbox_lines().items():
            out.append({"id": rid, "set": "official", "kind": "inbox", "message": line, "expected": None})
    if "stress" in include:
        out += [{**c, "set": "stress"} for c in STRESS["cases"]]
    return out


def price(model: str, usage: dict | None) -> float | None:
    if not usage:
        return None
    rates = PRICING["models"].get(model)
    if rates is None:
        return None
    prompt = (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0)
    if prompt > rates.get("long_prompt_threshold_tokens", math.inf):
        rates = rates["long_prompt"]
    creation = usage.get("cache_creation") or {}
    write_1h = creation.get("ephemeral_1h_input_tokens") or 0
    write_5m = (usage.get("cache_creation_input_tokens") or 0) - write_1h
    return ((usage.get("input_tokens") or 0) * rates["input"] + write_5m * rates["cache_write_5m"] + write_1h * rates["cache_write_1h"]
            + (usage.get("cache_read_input_tokens") or 0) * rates["cache_read"] + (usage.get("output_tokens") or 0) * rates["output"]) / 1e6


def plan(args):
    chosen = cases(args.sets)
    calls = len(chosen) * len(args.models) * args.trials
    per_model = {m: price(m, {"input_tokens": ESTIMATE_TOKENS["input"], "output_tokens": ESTIMATE_TOKENS["output"]}) for m in args.models}
    total = sum(per_model[m] * len(chosen) * args.trials for m in args.models)
    return {"cases": len(chosen), "sets": args.sets, "models": list(args.models), "trials": args.trials, "calls": calls,
            "estimated_cost_usd": round(total, 4), "estimated_cost_per_call_usd": {m: round(v, 5) for m, v in per_model.items()},
            "estimate_basis": f"{ESTIMATE_TOKENS['input']} input and {ESTIMATE_TOKENS['output']} output tokens per call (recorded Sonnet 5.5 usage); "
                              "Haiku's tokenizer and thinking can change this. Adaptive thinking tokens are billed as output.",
            "effort": args.effort or "model default"}


def run_one(case, model, trial, position, effort, orders, workshops):
    """One full evaluation with this model reading the request. Never persists anything."""
    def source(prompt, message):
        reply = intake._call_anthropic(model, prompt, message, effort=effort)
        reply.metadata = {**reply.metadata, "extraction_source": "benchmark"}
        return reply

    queues = {wid: w.queue0 for wid, w in workshops.items()}
    row = {"case": case["id"], "set": case["set"], "kind": case["kind"], "model": model, "trial": trial, "position": position,
           "started_utc": datetime.now(timezone.utc).isoformat()}
    record = None
    try:
        with tracing.trace("benchmark", kind="benchmark", model=model, case=case["id"]) as record, intake.extraction_source(source):
            preview = desk.make_preview(case["message"], desk.TODAY, PRESETS["lateness"], orders, workshops, queues,
                                        Allocator(PRESETS["lateness"]), 0, "live")
        parsed, decision = preview.response.parsed_request, preview.response.decision_record
        row.update(status="ok", schema_valid=True, behaviour=parsed.behaviour, order_id=parsed.order_id, pieces=parsed.pieces,
                   category=parsed.category, due_date=parsed.due_date.isoformat() if parsed.due_date else None,
                   preference=parsed.preference, excluded_workshops=sorted(parsed.excluded_workshops),
                   chosen_workshop=decision.get("chosen_workshop"), faithful=bool((preview.response.faithfulness or {}).get("passed")))
        llm = parsed.llm_metadata
    except intake.IntakeError as error:
        llm = error.llm_metadata or {}
        row.update(status="error", error=error.category, schema_valid=error.category not in {"invalid_output", "incomplete"})
    except Exception as error:  # Engine-side failure on this extraction: recorded, never hidden.
        llm = (record.meta.get("llm") if record else None) or {}
        row.update(status="error", error=type(error).__name__, schema_valid=True)
    usage = llm.get("usage") or {}
    row.update(served_model=llm.get("served_model") or llm.get("model"), fallback=bool(llm.get("fallback")),
               provider_ms=llm.get("provider_ms"), attempts=len(llm.get("attempts") or []), usage=usage,
               cost_usd=price(model, usage), total_ms=round(record.total_ms, 3) if record else None,
               stages={s["key"]: s["ms"] for s in tracing.stage_totals(record)} if record else {},
               cold_connection=True)   # A new HTTP client per call, as in production.
    return row


def execute(args):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        intake.llm_settings()  # Loads .env.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set; nothing was sent.")
    orders, workshops, _ = desk.load_inputs()
    chosen = cases(args.sets)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = HERE / "results" / run_id
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": run_id, "plan": plan(args), "prompt_sha256": tracing.message_digest(intake.build_system_prompt(desk.TODAY, orders, workshops)),
                "schema_sha256": tracing.message_digest(json.dumps(intake.JSON_SCHEMA, sort_keys=True)),
                "inbox_sha256": tracing.message_digest((ROOT / "data/dispatch_requests.txt").read_text()),
                "stress_version": STRESS["version"], "seed": args.seed, "rule": RULE, "settings": {
                    "max_tokens": 4096, "temperature": None, "effort": args.effort or "model default",
                    "fallbacks": {m: m in intake.SERVER_FALLBACK_MODELS for m in args.models},
                    "timeout_s": intake.ANTHROPIC_TIMEOUT_S, "max_retries": intake.ANTHROPIC_MAX_RETRIES, "concurrency": 1}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rng = random.Random(args.seed)
    with (out / "calls.jsonl").open("w") as stream:
        for trial in range(1, args.trials + 1):
            order = [(c, m) for c in chosen for m in args.models]
            rng.shuffle(order)
            for position, (case, model) in enumerate(order):
                row = run_one(case, model, trial, position, args.effort, orders, workshops)
                stream.write(json.dumps(row, default=str) + "\n")
                stream.flush()
                print(f"trial {trial} {position + 1}/{len(order)} {model} {case['id']}: {row['status']} "
                      f"{row.get('provider_ms') or 0:.0f} ms", flush=True)
                time.sleep(args.pause)
    summary = summarize(out)
    print(json.dumps(summary["models"], indent=2))


# Analysis -------------------------------------------------------------------------

def pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    k = (len(values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def wilson(successes, n, z=1.96):
    if not n:
        return None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(centre - half, 4), round(centre + half, 4)]


def reference_decisions():
    """Decisions from the hand-written test fixtures for the 30 inbox lines. A reference, not human ground truth."""
    orders, workshops, _ = desk.load_inputs()
    out = {}
    for rid, line in rehearsal.inbox_lines().items():
        with intake.extraction_source(rehearsal.make_source("fixture")):
            preview = desk.make_preview(line, desk.TODAY, PRESETS["lateness"], orders, workshops,
                                        {wid: w.queue0 for wid, w in workshops.items()}, Allocator(PRESETS["lateness"]), 0, "fixture")
        p = preview.response.parsed_request
        out[rid] = {"behaviour": p.behaviour, "order_id": p.order_id, "pieces": p.pieces, "category": p.category,
                    "due_date": p.due_date.isoformat() if p.due_date else None, "excluded_workshops": sorted(p.excluded_workshops),
                    "preference": p.preference, "chosen_workshop": preview.response.decision_record.get("chosen_workshop")}
    return out


def human_labels():
    """Agreed human labels (eval/labels.csv), only rows with an expected behaviour."""
    path = ROOT / "eval" / "labels.csv"
    rows = {}
    with path.open() as stream:
        for row in csv.DictReader(stream):
            if row.get("expected_behaviour"):
                rows[row["request_id"]] = row
    return rows


def field_scores(rows, expected_for):
    by_field, critical_errors, n_cases = defaultdict(lambda: [0, 0]), [], 0
    for row in rows:
        exp = expected_for(row)
        if exp is None:
            continue
        n_cases += 1
        for field in FIELDS:
            want = exp.get(field)
            if want is None and field != "excluded_workshops":
                continue
            got = row.get(field) if row["status"] == "ok" else "<error>"
            ok = (sorted(got or []) == sorted(want or [])) if field == "excluded_workshops" else got == want
            by_field[field][0] += ok
            by_field[field][1] += 1
            if not ok and field in CRITICAL:
                critical_errors.append({"case": row["case"], "trial": row["trial"], "field": field, "expected": want, "got": got})
    return {f: {"correct": c, "n": n, "rate": round(c / n, 4) if n else None, "ci95": wilson(c, n)} for f, (c, n) in by_field.items()}, critical_errors, n_cases


def summarize(out: Path) -> dict:
    rows = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines() if line.strip()]
    stress = {c["id"]: c["expected"] for c in STRESS["cases"]}
    fixture = reference_decisions()
    labels = human_labels()
    models = {}
    for model in sorted({r["model"] for r in rows}):
        mine = [r for r in rows if r["model"] == model]
        ok = [r for r in mine if r["status"] == "ok"]
        provider = [r["provider_ms"] for r in mine if r.get("provider_ms") is not None]
        e2e = [r["total_ms"] for r in ok if r.get("total_ms") is not None]
        costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
        stress_scores, stress_errors, stress_n = field_scores([r for r in mine if r["set"] == "stress"], lambda r: stress.get(r["case"]))
        agree_scores, _, _ = field_scores([r for r in mine if r["set"] == "official"], lambda r: fixture.get(r["case"]))
        decisions = [r for r in mine if r["set"] == "official"]
        agree_decision = sum(r["status"] == "ok" and r.get("behaviour") == fixture[r["case"]]["behaviour"]
                             and r.get("chosen_workshop") == fixture[r["case"]]["chosen_workshop"] for r in decisions)
        clarify_cases = [r for r in mine if r["set"] == "stress" and stress[r["case"]]["behaviour"] in {"clarify", "decline"}]
        clarified = sum(r["status"] == "ok" and r.get("behaviour") in {"clarify", "decline"} for r in clarify_cases)
        critical = [stress_scores[f] for f in CRITICAL if f in stress_scores]
        models[model] = {
            "calls": len(mine), "successful": len(ok), "error_rate": round(1 - len(ok) / len(mine), 4) if mine else None,
            "errors": {k: sum(r.get("error") == k for r in mine) for k in {r.get("error") for r in mine if r.get("error")}},
            "schema_valid_rate": round(sum(bool(r.get("schema_valid")) for r in mine) / len(mine), 4) if mine else None,
            "retry_rate": round(sum((r.get("attempts") or 0) > 1 for r in mine) / len(mine), 4) if mine else None,
            "fallback_served": sum(bool(r.get("fallback")) for r in mine),
            "llm_ms": {"mean": round(statistics.mean(provider), 1) if provider else None, "p50": pct(provider, .5), "p90": pct(provider, .9),
                       "p95": pct(provider, .95) if len(provider) >= 20 else None, "min": min(provider, default=None), "max": max(provider, default=None)},
            "e2e_ms": {"mean": round(statistics.mean(e2e), 1) if e2e else None, "p50": pct(e2e, .5), "p90": pct(e2e, .9),
                       "p95": pct(e2e, .95) if len(e2e) >= 20 else None, "min": min(e2e, default=None), "max": max(e2e, default=None)},
            "tokens": {"input_mean": round(statistics.mean([r["usage"].get("input_tokens", 0) for r in ok if r.get("usage")]), 1) if ok else None,
                       "output_mean": round(statistics.mean([r["usage"].get("output_tokens", 0) for r in ok if r.get("usage")]), 1) if ok else None},
            "cost": {"mean_per_success_usd": round(statistics.mean(costs), 6) if costs else None,
                     "per_100_usd": round(statistics.mean(costs) * 100, 4) if costs else None,
                     "per_1000_usd": round(statistics.mean(costs) * 1000, 3) if costs else None},
            "stress_accuracy": {"review_status": STRESS["review_status"], "cases": stress_n, "fields": stress_scores,
                                "critical_field_rate": round(sum(s["correct"] for s in critical) / max(1, sum(s["n"] for s in critical)), 4) if critical else None,
                                "critical_errors": stress_errors, "clarification_recall": round(clarified / len(clarify_cases), 4) if clarify_cases else None},
            "official_agreement_with_fixture": {"note": "Agreement with the hand-written test fixtures, not accuracy: no human labels exist yet.",
                                                "fields": agree_scores, "decision_agreement": round(agree_decision / len(decisions), 4) if decisions else None,
                                                "decision_ci95": wilson(agree_decision, len(decisions))},
            "official_accuracy_vs_human_labels": None if not labels else "computed when eval/labels.csv is filled",
        }
    summary = {"run": out.name, "generated_utc": datetime.now(timezone.utc).isoformat(), "models": models,
               "human_labels": f"{len(labels)} of 30 inbox requests labelled", "decision": decide(models)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    with (out / "calls.csv").open("w", newline="") as stream:
        keys = ["case", "set", "kind", "model", "trial", "position", "status", "error", "behaviour", "order_id", "pieces", "category",
                "due_date", "preference", "chosen_workshop", "served_model", "fallback", "attempts", "provider_ms", "total_ms", "cost_usd"]
        writer = csv.DictWriter(stream, keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return summary


def decide(models) -> dict:
    """Apply the pre-registered rule. Without human-reviewed labels the accuracy conditions cannot pass."""
    s, h = models.get("claude-sonnet-5-5"), models.get("claude-haiku-5-5")
    if not (s and h):
        return {"verdict": "incomplete", "reason": "Both models must be measured."}
    checks = {}
    sa, ha = s["stress_accuracy"]["critical_field_rate"], h["stress_accuracy"]["critical_field_rate"]
    checks["critical_accuracy_non_inferior"] = None if sa is None or ha is None else ha >= sa - RULE["non_inferiority_margin_pp"] / 100
    checks["no_critical_errors"] = len(h["stress_accuracy"]["critical_errors"]) <= RULE["max_unresolved_critical_errors"]
    checks["clarifies_instead_of_guessing"] = (h["stress_accuracy"]["clarification_recall"] or 0) >= RULE["clarification_recall"]
    checks["schema_valid"] = (h["schema_valid_rate"] or 0) >= RULE["min_schema_valid_rate"]
    se, he = s["e2e_ms"]["p50"], h["e2e_ms"]["p50"]
    checks["faster_end_to_end"] = bool(se and he and he <= se * (1 - RULE["min_e2e_median_speedup"]))
    sc, hc = s["cost"]["mean_per_success_usd"], h["cost"]["mean_per_success_usd"]
    checks["cheaper"] = bool(sc and hc and hc <= sc * RULE["max_cost_ratio"])
    passed = all(v is True for v in checks.values())
    return {"checks": checks, "accuracy_evidence": "author-labelled stress set only; the 30 inbox requests have no human labels",
            "verdict": ("Haiku meets the rule on this sample, but accuracy rests on unreviewed labels: keep Sonnet as the default "
                        "until the human labels are complete and the run is repeated." if passed else
                        "Keep Sonnet 5.5 as the default: Haiku does not meet every condition of the rule.")}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Send real, paid API requests.")
    parser.add_argument("--summarize", type=Path, help="Recompute summary.json for an existing run directory.")
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--sets", nargs="+", default=["official", "stress"], choices=["official", "stress"])
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--seed", type=int, default=5105)
    parser.add_argument("--pause", type=float, default=0.5, help="Seconds between calls.")
    args = parser.parse_args()
    if args.summarize:
        print(json.dumps(summarize(args.summarize)["decision"], indent=2))
        return
    print(json.dumps(plan(args), indent=2))
    if args.execute:
        execute(args)
    else:
        print("\nDry run: no API request was sent. Add --execute to run it.")


if __name__ == "__main__":
    main()
