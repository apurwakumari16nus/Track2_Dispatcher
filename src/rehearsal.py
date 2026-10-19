"""Labelled extraction sources for the dispatch app: live, recorded, synthetic.

Only the origin of the raw JSON extraction differs between sources. Schema
validation, Python post-checks, eligibility, estimates, scoring, selection and
the faithfulness check always run unchanged on whatever reply is returned.

live      The configured model (intake._call_llm). Each successful reply is also
          recorded with its exact request so it can be replayed in rehearsal.
cached    Replays a recorded MODEL reply whose system prompt (which includes the
          scenario date and catalogue) and message match exactly. Entries are
          integrity-checked by payload hash. Never calls the API.
fixture   The hand-written synthetic extraction used by the test suite for the
          30 unedited inbox lines. Not model output; labelled as such everywhere.

Recorded entries use the same file format as eval/run_inbox.py's CachedLLM, so
replies from a live inbox evaluation (eval/cache/) can also be replayed. App
recordings go to records/rehearsal_cache/ and never feed the inbox evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "eval") not in sys.path:
    sys.path.append(str(ROOT / "eval"))

import intake
from run_inbox import digest, write_json

RECORD_DIR = ROOT / "records" / "rehearsal_cache"
EVAL_CACHE_DIR = ROOT / "eval" / "cache"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "intake_extractions.json"
INBOX_PATH = ROOT / "data" / "dispatch_requests.txt"


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    badge: str
    description: str
    rehearsal: bool


SOURCES = {
    "live": Source("live", "Live model", "LIVE MODEL",
                   "Each request is read by the configured language model.", False),
    "cached": Source("cached", "Rehearsal · recorded", "REHEARSAL MODE · Verified cached extraction",
                     "Replays an earlier reply from the configured model for this exact request and date. No API call.", True),
    "fixture": Source("fixture", "Rehearsal · fixtures", "REHEARSAL MODE · Synthetic test fixture",
                      "Hand-written test extractions for the 30 inbox lines. Not model output; never evidence of language accuracy.", True),
}


class RehearsalMiss(intake.IntakeError):
    """The selected rehearsal source has no reply for this exact request."""


def live_status() -> dict:
    """Provider, model and readiness, without exposing any key value."""
    import os
    try:
        provider, model = intake.llm_settings()
    except intake.IntakeError as error:
        return {"ready": False, "provider": None, "model": None, "problem": str(error)}
    key_var, model_var = intake.PROVIDERS[provider]
    missing = [name for name, value in ((key_var, os.environ.get(key_var)), (model_var, model)) if not value]
    return {"ready": not missing, "provider": provider, "model": model or None,
            "problem": f"Set {' and '.join(missing)} in .env" if missing else None}


def _request(provider, model, prompt, message):
    """Same request shape as eval/run_inbox.py CachedLLM (live, non-fixture)."""
    return {"version": 1, "provider": provider, "model": model,
            "temperature": 0 if provider == "openai" else None,
            "system_prompt": prompt, "message": message, "fixture_hash": None}


def _entries(directories):
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            yield path, entry


def _verified(entry):
    """(request, payload) for an intact recorded model reply, else None."""
    request, payload = entry.get("request") or {}, entry.get("payload") or {}
    if (request.get("provider") in (None, "synthetic-fixture") or request.get("fixture_hash")
            or payload.get("error") or not payload.get("content")
            or entry.get("payload_hash") != digest(payload)):
        return None
    return request, payload


def find_recorded(prompt: str, message: str, directories=None, preferred_model=None):
    """Return (payload, request, path) for a verified recorded model reply, or None.

    Synthetic-fixture cache entries, recorded errors and entries whose payload
    hash does not match are skipped. Several matches prefer the configured
    model, then the lexically first model and file, for determinism.
    """
    matches = []
    for path, entry in _entries(directories or (RECORD_DIR, EVAL_CACHE_DIR)):
        verified = _verified(entry)
        if verified and verified[0].get("system_prompt") == prompt and verified[0].get("message") == message:
            request, payload = verified
            matches.append((request.get("model") != preferred_model, str(request.get("model")), str(path), payload, request, path))
    if not matches:
        return None
    _, _, _, payload, request, path = min(matches, key=lambda item: item[:3])
    return payload, request, path


def record(prompt: str, message: str, reply: intake.LLMReply, provider: str, model: str, directory=None) -> Path:
    request = _request(provider, model, prompt, message)
    payload = {"content": reply.content, "metadata": reply.metadata, "error": None}
    path = Path(directory or RECORD_DIR) / f"{digest(request)}.json"
    write_json(path, {"request": request, "payload": payload, "payload_hash": digest(payload)})
    return path


def inbox_lines() -> dict[str, str]:
    return {line.split()[0]: line for line in INBOX_PATH.read_text(encoding="utf-8").splitlines() if line.startswith("R")}


def fixture_reply(message: str) -> intake.LLMReply:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if fixture["dispatch_requests_sha256"] != hashlib.sha256(INBOX_PATH.read_bytes()).hexdigest():
        raise RehearsalMiss("The inbox changed since the synthetic fixtures were written; review them before rehearsal.")
    lines = inbox_lines()
    rid = message.split()[0] if message.split() else ""
    if lines.get(rid) != message or rid not in fixture["requests"]:
        raise RehearsalMiss("Synthetic fixtures exist only for the 30 unedited inbox requests. "
                            "Use Live model to interpret new or edited text.")
    raw = {**fixture["defaults"], **fixture["requests"][rid]}
    return intake.LLMReply(json.dumps(raw), {"provider": "synthetic-fixture", "model": "synthetic-fixture",
                                             "extraction_source": "fixture"})


def make_source(key: str, *, on_reply=None, record_live: bool = True):
    """Return call(prompt, message) for intake.extraction_source.

    on_reply() runs after the raw reply arrives and before Python validation,
    so the UI can show a real stage transition. It never sees the reply.
    """
    if key not in SOURCES:
        raise ValueError(f"Unknown extraction source {key!r}")

    def call(prompt, message):
        if key == "live":
            reply = intake._call_llm(prompt, message)
            reply.metadata = {**reply.metadata, "extraction_source": "live"}
            status = live_status()
            if record_live and status["provider"] and status["model"]:
                try:
                    record(prompt, message, reply, status["provider"], status["model"])
                except OSError:
                    pass  # Recording is a convenience for rehearsal, never a dispatch dependency.
        elif key == "cached":
            found = find_recorded(prompt, message, preferred_model=live_status()["model"])
            if found is None:
                raise RehearsalMiss("No recorded model reply exists for this exact request and scenario date. "
                                    "Dispatch it once in Live model mode, or run eval/run_inbox.py live, to record one.")
            payload, request, path = found
            reply = intake.LLMReply(payload["content"], {**(payload.get("metadata") or {}), "extraction_source": "cached",
                                                          "recorded_provider": request.get("provider"),
                                                          "recorded_model": request.get("model"),
                                                          "recorded_file": path.name})
        else:
            reply = fixture_reply(message)
        if on_reply:
            on_reply()
        return reply
    return call


def recorded_coverage(prompt: str, messages, directories=None) -> int:
    """How many of these messages have a verified recorded reply for this prompt."""
    wanted, found = set(messages), set()
    for _, entry in _entries(directories or (RECORD_DIR, EVAL_CACHE_DIR)):
        verified = _verified(entry)
        if verified and verified[0].get("system_prompt") == prompt and verified[0].get("message") in wanted:
            found.add(verified[0]["message"])
    return len(found)
