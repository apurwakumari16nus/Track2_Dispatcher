"""Evaluate the chat inbox with cached extraction and independent reference checks.

Live by default; --mock is an explicitly synthetic dry run, not LLM accuracy.
All requests use 2026-04-01, fresh agent.handle() history and the same queue0
snapshot. Human labels are never generated or changed by this script.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import traceback
from unittest.mock import patch

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "harness")]

import agent
import faithfulness
from heuristic import earliest_finish
import intake
from objectives import PRESETS
from simulate import eligible_workshops, load_workshops

TODAY = date(2026, 4, 1)
BEHAVIOURS = ("allocate", "clarify", "refuse", "decline")
CHECKS = ("behaviour_correct", "decision_correct", "faithfulness_passed",
          "constraint_honoured", "already_late_flagged_when_needed")
COLUMNS = ["request_id", "expected_behaviour", "actual_behaviour", *CHECKS, "notes"]
LABEL_COLUMNS = ["request_id", "expected_behaviour", "expected_order_id", "expected_pieces",
                 "expected_category", "expected_due", "issue", "constraint", "notes"]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_json(path: Path, value):
    """Atomic replacement; no partial cache entry on an interrupted write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class CachedLLM:
    """Cache raw provider replies, not parsed requests, decisions or gold labels.

    Key includes full prompt/schema/catalog/today, message, model, temperature,
    provider mode and cache format. Mock fixtures have a distinct namespace and
    content hash. Cache hits require no API key. Corrupt entries fail visibly;
    they never silently trigger a paid replacement call. Transport/configuration
    failures are not cached. Provider refusals with response evidence are cached.
    """
    def __init__(self, directory, model, *, call=None, offline=False, fixture=None, provider="anthropic"):
        self.directory = Path(directory)
        self.model = model
        self.provider = provider
        self.call = call or intake._call_llm
        self.offline = offline
        self.fixture = fixture
        self.hits = self.misses = 0
        self.last_key = None

    def __call__(self, prompt, message):
        if not self.model:
            model_var = intake.PROVIDERS[self.provider][1]
            raise intake.IntakeError(f"{model_var} is not configured; no live evaluation was performed")
        request = {"version": 1, "provider": "synthetic-fixture" if self.fixture else self.provider,
                   "model": self.model, "temperature": 0 if self.fixture or self.provider == "openai" else None, "system_prompt": prompt, "message": message,
                   "fixture_hash": digest(self.fixture) if self.fixture else None}
        key = self.last_key = digest(request)
        path = self.directory / f"{key}.json"
        if path.exists():
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry.get("request") != request or entry.get("payload_hash") != digest(entry.get("payload")):
                raise ValueError(f"Cache integrity check failed: {path.name}")
            payload = entry["payload"]
            self.hits += 1
        else:
            if self.offline:
                raise intake.IntakeError(f"Cache miss in offline mode: {key}")
            self.misses += 1
            try:
                if self.fixture:
                    rid = message.split()[0]
                    raw = {**deepcopy(self.fixture["defaults"]), **deepcopy(self.fixture["requests"][rid])}
                    reply = intake.LLMReply(json.dumps(raw), {"model": self.model, "temperature": 0})
                else:
                    reply = self.call(prompt, message)
                payload = {"content": reply.content, "metadata": reply.metadata, "error": None}
            except intake.IntakeError as error:
                if not error.llm_metadata.get("response_id"):
                    raise  # Missing setup has no provider response to cache.
                payload = {"content": error.raw_llm_response, "metadata": error.llm_metadata,
                           "error": str(error)}
            write_json(path, {"request": request, "payload": payload, "payload_hash": digest(payload)})
        if payload.get("error"):
            raise intake.IntakeError(payload["error"], raw_response=payload["content"], metadata=payload["metadata"])
        return intake.LLMReply(payload["content"], payload["metadata"])


def inbox_messages(path: Path) -> dict[str, str]:
    messages = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = re.match(r"^(R\d+)\s+\[", line)
        if not match or match[1] in messages:
            raise ValueError("Inbox must contain uniquely identified Rxx chat lines")
        messages[match[1]] = line
    return messages


def read_labels(path: Path, ids) -> dict[str, dict]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != LABEL_COLUMNS or not frame.request_id.is_unique or set(frame.request_id) != set(ids):
        raise ValueError("labels.csv must have the agreed columns and exactly one row per inbox ID")
    if not set(frame.expected_behaviour) <= set(BEHAVIOURS) | {""}:
        raise ValueError("Invalid expected_behaviour in labels.csv")
    for row in frame.to_dict("records"):
        if row["expected_pieces"] and (not row["expected_pieces"].isdigit() or int(row["expected_pieces"]) <= 0):
            raise ValueError(f"Invalid expected_pieces for {row['request_id']}")
        if row["expected_category"] not in {"", "TOPS", "ACCESSORIES"}:
            raise ValueError(f"Invalid expected_category for {row['request_id']}")
        if row["expected_due"]:
            date.fromisoformat(row["expected_due"])
    return frame.set_index("request_id").to_dict("index")


def contains(text, phrase):
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I) is not None


def reference(message, label, orders, workshops) -> dict:
    """Independent, limited literal reference resolver for this supplied inbox.

    Human factual labels override literal message/CSV fallbacks. This resolver
    never reads ParsedRequest, allocator candidates, scores or mock fixtures.
    It is an evaluation oracle for explicit names, product plurals and deadlines,
    not a second general-purpose intake. Unresolved facts stay unscored.
    """
    text = message.casefold()
    customers = [c for c in orders.customer.unique() if contains(message, c)]
    aliases = {p: [p, "scarves" if p.casefold() == "scarf" else p + "s"] for p in orders["product"].unique()}
    products = [p for p, names in aliases.items() if any(contains(message, a) for a in names)]
    ids = re.findall(r"\bORD-\d+\b", message, re.I)
    order_id = label["expected_order_id"] or (ids[0].upper() if len(ids) == 1 else None)
    matches = orders[orders.status == "IN_PROGRESS"]
    if customers:
        matches = matches[matches.customer.isin(customers)]
    if products:
        matches = matches[matches["product"].isin(products)]
    candidates = sorted(matches.order_id.tolist()) if not ids else []
    if not order_id and not ids and len(matches) == 1:
        order_id = str(matches.iloc[0].order_id)
    known = orders[orders.order_id == order_id]
    row = known.iloc[0] if len(known) == 1 else None
    product_pattern = "|".join(re.escape(a) for names in aliases.values() for a in names)
    quantity = re.search(r"\b(\d[\d,]*)\s+(?:pieces?\b|(?:" + product_pattern + r")(?!\w))", message, re.I)
    pieces = int(label["expected_pieces"]) if label["expected_pieces"] else (int(quantity[1].replace(",", "")) if quantity else (int(row.pieces) if row is not None else None))
    category = label["expected_category"] or (str(row.category) if row is not None else None)
    unconfirmed = label["issue"] == "date_not_confirmed" or bool(re.search(r"(?:will confirm|date.*not confirmed|date.*to follow)", text))
    explicit_date = re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,?\s+\d{4})?\b|\b\d{4}-\d{2}-\d{2}\b", message, re.I)
    due = None
    if label["expected_due"]:
        due = date.fromisoformat(label["expected_due"])
    elif not unconfirmed:
        if explicit_date:
            literal = explicit_date[0].replace(",", "")
            for fmt, value in [("%Y-%m-%d", literal), ("%b %d %Y", literal), ("%B %d %Y", literal),
                               ("%b %d %Y", literal + f" {TODAY.year}"), ("%B %d %Y", literal + f" {TODAY.year}")]:
                try:
                    due = datetime.strptime(value, fmt).date()
                    break
                except ValueError:
                    pass
        elif re.search(r"(?:due|deadline|back by)\s+today", text):
            due = TODAY
        elif row is not None and pd.notna(row.due_date):
            due = date.fromisoformat(str(row.due_date))

    constraint_text = text + " " + label["constraint"].casefold()
    exclusions = []
    for wid, shop in workshops.items():
        name = rf"(?:{re.escape(shop.name)}|{re.escape(wid)})\b"
        if re.search(r"(?:nothing new to|keep (?:it )?away from|avoid|not|exclude[sd]?)\s*[:=]?\s*" + name, constraint_text, re.I):
            exclusions.append(wid)
    preference = ("cheapest" if "cheapest" in constraint_text else "lowest_defect" if re.search(r"lowest[ _-]defect", constraint_text)
                  else "fastest" if re.search(r"fastest|quickest|cost (?:doesn't|does not) matter", constraint_text) else None)
    must_date = preference == "cheapest" or bool(re.search(r"must.make.date|\bmake (?:[a-z]+ \d|the date|deadline)|needs to ship|must.*(?:date|deadline)", constraint_text))
    split = bool(re.search(r"\bsplit\b", constraint_text))
    named_shops = [wid for wid, shop in workshops.items() if contains(message, wid) or contains(message, shop.name)]
    label_constraint = label["constraint"].strip().casefold()
    understood = label_constraint in {"", "none", "no constraints", "no special requirements"} or bool(exclusions or preference or must_date or split)
    sender = message.split("]", 1)[-1].split(":", 1)[0].strip()
    imposed_by = "Boss" if "boss says" in text else sender
    return {"order_id": order_id, "pieces": pieces, "category": category, "due_date": due,
            "candidate_order_ids": candidates, "has_explicit_id": bool(ids or label["expected_order_id"]),
            "unconfirmed_date": unconfirmed, "packing": row is not None and row.current_stage == "PACKING",
            "exclude": exclusions, "preference": preference, "must_make_date": must_date,
            "split_allowed": split, "constraint_reference_complete": understood,
            "suggested_workshops": [wid for wid in named_shops if wid not in exclusions],
            "imposed_by": imposed_by, "sender": sender}


def benchmark(ref, workshops, queues) -> dict | None:
    """Heuristic under the same restrictions, independently of allocator scores.

    Earliest finish breaks ties after cost/defect preferences. Date-constrained
    choices consider on-time shops if any. If all are late, use earliest finish
    as the explicit least-late fallback regardless of preference, like the public
    allocation contract. Profile eligibility comes from the shared harness.
    """
    if any(ref[k] is None for k in ("order_id", "pieces", "category", "due_date")):
        return None
    batch = {k: ref[k] for k in ("order_id", "pieces", "category", "due_date")}
    batch["sent_date"] = TODAY
    eligible = [w for w in eligible_workshops(batch, workshops) if w.workshop_id not in ref["exclude"]]
    totals = {w.workshop_id: queues[w.workshop_id] + ref["pieces"] / w.capacity + w.lead_days for w in eligible}
    spare = {wid: (ref["due_date"] - (TODAY + timedelta(days=round(total)))).days for wid, total in totals.items()}
    on_time = [w for w in eligible if spare[w.workshop_id] >= 0]
    allowed = on_time if ref["must_make_date"] and on_time else eligible
    if on_time and allowed and ref["preference"] in {"cheapest", "lowest_defect"}:
        field = "cost" if ref["preference"] == "cheapest" else "defect_rate"
        best = min(getattr(w, field) for w in allowed)
        allowed = [w for w in allowed if getattr(w, field) == best]
    chosen = earliest_finish(batch, {w.workshop_id: w for w in allowed}, queues) if allowed else None
    return {"chosen_workshop": chosen, "eligible_ids": [w.workshop_id for w in eligible],
            "days_to_spare": spare, "all_late": bool(eligible) and not on_time,
            "queue_snapshot": dict(queues)}


def assess(response, label, ref, orders, workshops, queues):
    """Return nullable metrics and evidence; never use a parsed fact as its oracle."""
    parsed, record = response.parsed_request, response.decision_record
    expected, actual = label["expected_behaviour"], parsed.behaviour
    chosen = record["chosen_workshop"]
    notes = []
    metrics = {key: None for key in CHECKS}
    metrics["behaviour_correct"] = actual == expected if expected else None
    if not expected:
        notes.append("Human behaviour unlabeled; decision check is conditional on actual behaviour, not end-to-end accuracy.")
    base = benchmark(ref, workshops, queues)
    target = expected or actual
    factual_mismatches = [key for key in ("order_id", "pieces", "category", "due_date")
                          if ref[key] is not None and getattr(parsed, key) != ref[key]]
    if factual_mismatches:
        notes.append("Reference fact mismatch: " + ", ".join(factual_mismatches))
    if target in {"allocate", "refuse"}:
        if base is not None:
            metrics["decision_correct"] = actual == target and chosen == base["chosen_workshop"] and not factual_mismatches
            notes.append(f"Heuristic-best under reference constraints: {base['chosen_workshop']}; actual: {chosen}.")
        else:
            notes.append("Decision unscored: reference order/quantity/category/deadline unresolved.")
    elif target == "decline":
        metrics["decision_correct"] = actual == "decline" and chosen is None and not response.allocation_committed
    elif target == "clarify":
        correct = actual == "clarify" and chosen is None and not response.allocation_committed
        if not ref["has_explicit_id"]:
            expected_ids = set(ref["candidate_order_ids"])
            options = record.get("tool_outputs", {}).get("order_options", [])
            correct &= {r["order_id"] for r in options} == expected_ids
            for row in orders[orders.order_id.isin(expected_ids)].itertuples(index=False):
                correct &= all(value in response.explanation_text for value in (row.order_id, row.product, str(row.pieces)))
            mentioned = set(re.findall(r"\bORD-\d+\b", response.explanation_text))
            correct &= mentioned == expected_ids
            notes.append("Reference clarification candidates: " + ", ".join(sorted(expected_ids)))
        if ref["unconfirmed_date"]:
            correct &= parsed.due_date is None and "confirm" in response.explanation_text.casefold()
        if ref["packing"]:
            correct &= "packing" in response.explanation_text.casefold()
        metrics["decision_correct"] = bool(correct)

    metrics["faithfulness_passed"] = faithfulness.check(response.explanation_text, record)["passed"]
    applied = record.get("constraints_applied", {})
    constraints_ok = (set(parsed.excluded_workshops) == set(ref["exclude"])
                      and parsed.preference == ref["preference"] and parsed.split_allowed == ref["split_allowed"])
    if chosen:
        constraints_ok &= chosen not in ref["exclude"] and (base is not None and chosen in base["eligible_ids"])
        if ref["preference"]:
            constraints_ok &= base is not None and chosen == base["chosen_workshop"]
        if ref["must_make_date"]:
            constraints_ok &= applied.get("must_make_date") is True and base is not None and base["days_to_spare"].get(chosen, -1) >= 0
            if base and base["all_late"]:
                notes.append("Date requirement infeasible: the least-late fallback still misses it, even if correctly disclosed.")
    if ref["must_make_date"]:
        constraints_ok &= applied.get("must_make_date") is True
    if ref["split_allowed"] and actual in {"allocate", "refuse"} and base is not None:
        split = record.get("tool_outputs", {}).get("split")
        constraints_ok &= split is not None
        if split and split.get("available"):
            constraints_ok &= sum(p["pieces"] for p in split["parts"]) == ref["pieces"]
            constraints_ok &= len({p["workshop_id"] for p in split["parts"]}) == 2
            for part in split["parts"]:
                legal = {w.workshop_id for w in eligible_workshops({"category": ref["category"], "pieces": part["pieces"]}, workshops)}
                constraints_ok &= part["workshop_id"] in legal and part["workshop_id"] not in ref["exclude"]
    if ref["exclude"]:
        imposed = {c.get("imposed_by") for c in parsed.constraints}
        constraints_ok &= ref["imposed_by"] in imposed
    metrics["constraint_honoured"] = bool(constraints_ok) if ref["constraint_reference_complete"] else None
    if not ref["constraint_reference_complete"]:
        notes.append("Constraint unscored: human constraint text is outside the documented literal reference grammar.")
    needs_late = ref["due_date"] <= TODAY if ref["due_date"] else None
    if needs_late is not None:
        metrics["already_late_flagged_when_needed"] = (response.already_late and "ALREADY LATE" in response.explanation_text) if needs_late else True
    else:
        notes.append("Late flag unscored: reference deadline unresolved.")
    return metrics, notes, base, factual_mismatches


def hypothesis(row, detail):
    """A hypothesis, not a causal claim: use the earliest evidenced mismatch."""
    if detail.get("error"):
        return detail.get("error_layer", "LLM extraction") + ": execution failed; inspect the captured operational error."
    if detail.get("factual_mismatches"):
        parsed = detail["response"]["parsed_request"]
        raw = parsed.get("raw_llm_json", {})
        fields = detail["factual_mismatches"]
        layer = "LLM extraction" if any(raw.get(k) == parsed.get(k) for k in fields if k != "due_date") else "post-check"
        return layer + ": extracted or reconciled facts disagree with the independent reference."
    if row["behaviour_correct"] is False:
        return "post-check: final classification disagrees with the human label; review extraction and rule precedence."
    if row["decision_correct"] is False:
        if detail["response"]["parsed_request"]["behaviour"] == "clarify":
            return "post-check/template: clarification candidates or the displayed question differ from the independently matched orders."
        return "allocator: selected workshop or clarification options differ from the reference; inspect filtering, objective and template."
    if row["faithfulness_passed"] is False:
        return "template: explanation contains numbers absent from the recorded tool evidence."
    if row["constraint_honoured"] is False:
        if (detail.get("benchmark") or {}).get("all_late"):
            return "allocator: no eligible shop can meet the required date; the disclosed fallback still cannot satisfy it."
        return "LLM extraction: a requested constraint may have been lost or misattributed; check post-check and allocator propagation."
    return "post-check: the overdue flag was lost or the template did not surface it."


def error_layer(error):
    """Locate the failing application layer, without blaming evaluator errors on it."""
    if isinstance(error, intake.IntakeError):
        return "LLM extraction"
    if "unsupported numbers" in str(error):
        return "template"
    for frame in reversed(traceback.extract_tb(error.__traceback__)):
        name = Path(frame.filename).stem
        if (name == "run_inbox" and frame.name == "__call__") or (name == "intake" and frame.name == "_call_llm"):
            return "LLM extraction"
        if name in {"allocator", "tools"}:
            return "allocator"
        if name == "faithfulness" or (name == "agent" and frame.name.startswith("_")):
            return "template"
        if name == "intake" and frame.name != "_call_llm":
            return "post-check"
    return "LLM extraction"


def run_evaluation(messages, labels, orders, workshops, cache):
    queues = {wid: w.queue0 for wid, w in workshops.items()}
    rows, details = [], []
    for rid, message in messages.items():
        label = labels[rid]
        ref = reference(message, label, orders, workshops)
        detail = {"request_id": rid, "raw_message": message, "human_label": label,
                  "reference": {**ref, "due_date": ref["due_date"].isoformat() if ref["due_date"] else None},
                  "benchmark": benchmark(ref, workshops, queues)}
        row = dict.fromkeys(COLUMNS)
        row.update(request_id=rid, expected_behaviour=label["expected_behaviour"])
        cache.last_key = None
        try:
            # Single-threaded evaluator-only replacement, restored after every call.
            with patch.object(intake, "_call_llm", cache):
                response = agent.handle(message, TODAY, orders.copy(deep=True), deepcopy(workshops), dict(queues), PRESETS["lateness"])
        except Exception as error:
            # One bad request must not erase the remaining evaluation cases.
            # API error messages may echo request/credential details, so retain
            # the type/status only; known local IntakeErrors have safe messages.
            safe = str(error) if isinstance(error, (intake.IntakeError, ValueError, KeyError)) else type(error).__name__
            if getattr(error, "status_code", None):
                safe += f" (HTTP {error.status_code})"
            notes = [f"Operational error: {safe}; no AgentResponse was produced."]
            row.update(actual_behaviour="error", behaviour_correct=False if label["expected_behaviour"] else None,
                       decision_correct=False, faithfulness_passed=False)
            detail.update(error=safe, error_layer=error_layer(error))
        else:
            # An evaluator defect must fail the run, not become an agent failure.
            metrics, notes, base, mismatches = assess(response, label, ref, orders, workshops, queues)
            row.update(actual_behaviour=response.parsed_request.behaviour, **metrics)
            detail.update(response=response.to_dict(), benchmark=base, factual_mismatches=mismatches)
        row["notes"] = ("MOCK extraction; not live LLM evaluation. " if cache.fixture else "") + " ".join(notes)
        detail["cache_key"] = cache.last_key
        failed = [name for name in CHECKS if row[name] is False]
        detail["failed_checks"] = failed
        detail["hypothesis"] = hypothesis(row, detail) if failed else None
        rows.append(row)
        details.append(detail)
    frame = pd.DataFrame(rows, columns=COLUMNS)
    for column in CHECKS:
        frame[column] = frame[column].astype("boolean")
    return frame, details


def summary_table(results, group_by="expected_behaviour"):
    """Group by the specified class; show denominators, excluding unscored cells."""
    def rate(series):
        values = series.dropna()
        return f"{values.mean():.1%} ({len(values)} scored)" if len(values) else "N/A (0 scored)"
    lines = [f"| {group_by.replace('_', ' ')} | n | behaviour accuracy | decision accuracy | faithfulness pass rate |",
             "| --- | ---: | --- | --- | --- |"]
    for behaviour in BEHAVIOURS:
        part = results[results[group_by] == behaviour]
        lines.append(f"| {behaviour} | {len(part)} | {rate(part.behaviour_correct)} | {rate(part.decision_correct)} | {rate(part.faithfulness_passed)} |")
    return "\n".join(lines)


def failure_report(results, details, mode):
    labeled = int(results.expected_behaviour.ne("").sum())
    failures = [detail for detail in details if detail["failed_checks"]]
    lines = ["# Inbox evaluation failures", "", f"Mode: **{mode}**. Today: **{TODAY}**. Objective: **lateness**.",
             f"Human behaviour labels: **{labeled}/{len(results)}**. Operational errors: **{int((results.actual_behaviour == 'error').sum())}**.", "",
             "Blank CSV checks mean unscored, never True. Unlabeled decision checks are conditional diagnostics, not end-to-end accuracy.",
             "Each request starts with the same workshop queue0 snapshot and fresh allocator history. Constraint-aware heuristic ties use workshop input order.",
             "Cheapest/lowest-defect preferences filter the heuristic candidates; an infeasible required date is an unsatisfied constraint even when the fallback is honestly explained.",
             "Numerical faithfulness checks support, not semantic correctness. Number-free responses can pass vacuously.", "", summary_table(results), "",
             "Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):", "",
             summary_table(results, "actual_behaviour"), "",
             f"Rows with at least one False check: **{len(failures)}**."]
    if mode == "mock":
        lines.extend(["", "**Synthetic extraction fixtures were used. These are not measured live LLM results or human labels.**"])
    for detail in failures:
        label, ref = detail["human_label"], detail["reference"]
        response = detail.get("response")
        expected = label["expected_behaviour"] or "Unlabeled: human expected behaviour is still pending"
        should = f"Human behaviour: {expected}."
        if detail.get("benchmark"):
            should += f" Constraint-aware heuristic choice: {detail['benchmark']['chosen_workshop']}."
        if ref["candidate_order_ids"] and not ref["has_explicit_id"]:
            should += f" Clarification candidate IDs, if clarification is appropriate: {ref['candidate_order_ids']}."
        should += f" Reference exclusions: {ref['exclude']}; preference: {ref['preference']}; due: {ref['due_date']}."
        if label["notes"]:
            should += " Human notes: " + label["notes"]
        actual = response["explanation_text"] if response else "No response. " + detail["error"]
        lines.extend(["", f"## {detail['request_id']}", "", "Failed checks: " + ", ".join(detail["failed_checks"]), "",
                      "Raw message:", "", "> " + detail["raw_message"].replace("\n", "\n> "), "",
                      "What the system did:", "", "> " + actual.replace("\n", "\n> "), "",
                      "What it should have done:", "", should, "",
                      "Layer hypothesis: " + detail["hypothesis"]])
    pending = results[results[list(CHECKS)].isna().any(axis=1)]
    lines.extend(["", "## Unscored checks", "", "Requests with at least one missing reference/check: " + (", ".join(pending.request_id) or "none") + ".",
                  "See CSV notes and inbox_audit.json for per-request evidence. Missing labels were not filled by this evaluator."])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "eval")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "eval/cache")
    parser.add_argument("--labels", type=Path, default=ROOT / "eval/labels.csv")
    parser.add_argument("--requests", type=Path, default=ROOT / "data/dispatch_requests.txt",
                        help="Request file (default: the supplied 30-request inbox); use it for a held-out set")
    parser.add_argument("--model", help="Intake model; overrides the LLM_PROVIDER's *_INTAKE_MODEL")
    parser.add_argument("--offline", action="store_true", help="Reuse existing matching cache only; never call the API")
    parser.add_argument("--mock", action="store_true", help="Explicit synthetic-fixture dry run; not live LLM evaluation")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    default_requests = ROOT / "data/dispatch_requests.txt"
    messages = inbox_messages(args.requests)
    if args.requests == default_requests and len(messages) != 30:
        raise ValueError("Expected the supplied 30-request inbox")
    labels = read_labels(args.labels, messages)
    fixture = None
    if args.mock:
        fixture = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
        if fixture["dispatch_requests_sha256"] != hashlib.sha256((ROOT / "data/dispatch_requests.txt").read_bytes()).hexdigest():
            raise ValueError("Inbox changed; review the synthetic fixture before using mock mode")
    provider, model = intake.llm_settings()
    if args.model:
        os.environ[intake.PROVIDERS[provider][1]] = model = args.model
    model = "synthetic-fixture" if args.mock else model
    cache = CachedLLM(args.cache_dir, model, offline=args.offline, fixture=fixture, provider=provider)
    orders, workshops = pd.read_csv(ROOT / "data/orders.csv"), load_workshops()
    results, details = run_evaluation(messages, labels, orders, workshops, cache)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output_dir / "inbox_results.csv", index=False, na_rep="")
    mode = "mock" if args.mock else "live/cache-only" if args.offline else "live/cached"
    (args.output_dir / "failure_cases.md").write_text(failure_report(results, details, "mock" if args.mock else mode), encoding="utf-8")
    write_json(args.output_dir / "inbox_audit.json", {
        "mode": mode, "provider": "synthetic-fixture" if args.mock else provider, "model": model, "today": TODAY.isoformat(), "objective": "lateness",
        "queue_policy": "workshops.csv current_queue_days as the 2026-04-01 snapshot; independent per request",
        "input_hashes": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
            "inbox": args.requests, "orders": ROOT / "data/orders.csv",
            "workshops": ROOT / "data/workshops.csv", "labels": args.labels}.items()},
        "requests": details})
    temperature = 0 if args.mock or provider == "openai" else "provider default (Claude rejects temperature=0)"
    print(f"Mode: {mode}; model: {model}; human labels: {results.expected_behaviour.ne('').sum()}/{len(results)}; temperature: {temperature}")
    print("Grouped by human expected behaviour; each rate shows its scored denominator. Missing human labels are not accuracy measurements.")
    print(summary_table(results))
    print("Diagnostic breakdown by actual behaviour (unlabeled checks are conditional):")
    print(summary_table(results, "actual_behaviour"))
    errors = int((results.actual_behaviour == "error").sum())
    print(f"Operational errors outside behaviour classes: {errors}. Cache hits: {cache.hits}; misses: {cache.misses}.")
    print(f"Saved inbox_results.csv, failure_cases.md and inbox_audit.json in {args.output_dir}")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
