"""Execution tracing for one request evaluation. Measurement only.

A trace is opened around one server-side evaluation (Dispatch, the guided demo,
or a benchmark run). Code inside it marks stages with span(name); spans nest,
so a tool call inside the allocator is a child of the allocation span.

Timing uses time.perf_counter_ns (monotonic). Each span records its inclusive
duration; summaries use self time (inclusive minus direct children), so nested
stages are never counted twice and the stage totals add up to the trace total.

Nothing here changes a decision: spans only read the clock and store labels.
Traces hold no API keys and no request text, only a short hash of the message.
They are written to records/traces.jsonl (git-ignored), keeping the newest
RETENTION traces.

What is not measured: the provider's internal inference time (only the whole
API call, network included, is visible), and browser rendering after the
server has finished.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

import portalocker

ROOT = Path(__file__).resolve().parents[1]
TRACE_LOG = ROOT / "records" / "traces.jsonl"
RETENTION = 500

# Stage groups shown in the UI. Every span belongs to exactly one group; anything not
# listed (the root's own time, preparation, preview assembly) is "other".
GROUPS = (
    ("llm", "Language model request", ("llm.call",)),
    ("parse", "Parsing and validation", ("llm.prepare", "llm.parse", "llm.validate", "validation")),
    ("engine", "Python decision engine", ("order_lookup", "allocation", "eligibility", "evidence", "verification", "tool:")),
    ("checks", "Evidence check", ("explanation_check",)),
)
OTHER = ("other", "Other processing")


@dataclass
class Span:
    name: str
    parent: int | None
    start_ns: int
    end_ns: int | None = None
    status: str = "ok"            # ok, error or skipped
    error: str | None = None      # error category, never a message with secrets
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def ms(self) -> float:
        return ((self.end_ns or self.start_ns) - self.start_ns) / 1e6


@dataclass
class Trace:
    trace_id: str
    started_utc: str
    meta: dict[str, Any]
    spans: list[Span] = field(default_factory=list)
    stack: list[int] = field(default_factory=list)
    status: str = "ok"
    error: str | None = None

    @property
    def total_ms(self) -> float:
        return self.spans[0].ms if self.spans else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "started_utc": self.started_utc, "status": self.status, "error": self.error,
                "total_ms": round(self.total_ms, 3), "meta": self.meta,
                "spans": [{**{k: v for k, v in asdict(s).items() if k not in ("start_ns", "end_ns")},
                           "ms": round(s.ms, 3), "offset_ms": round((s.start_ns - self.spans[0].start_ns) / 1e6, 3)}
                          for s in self.spans],
                "stages": stage_totals(self)}


_CURRENT: ContextVar[Trace | None] = ContextVar("execution_trace", default=None)


def current() -> Trace | None:
    return _CURRENT.get()


def message_digest(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:12]


@contextmanager
def trace(name: str = "evaluation", **meta):
    """Open a trace and its root span. The trace always closes, also when the body raises."""
    record = Trace(uuid4().hex[:12], datetime.now(timezone.utc).isoformat(), dict(meta))
    token = _CURRENT.set(record)
    record.spans.append(Span(name, None, time.perf_counter_ns()))
    record.stack.append(0)
    try:
        yield record
    except BaseException as error:
        record.status, record.error = "error", error_category(error)
        record.spans[0].status, record.spans[0].error = "error", record.error
        raise
    finally:
        record.spans[0].end_ns = time.perf_counter_ns()
        for index in record.stack[1:]:   # Close anything left open by an exception.
            record.spans[index].end_ns = record.spans[index].end_ns or record.spans[0].end_ns
        record.stack.clear()
        _CURRENT.reset(token)


@contextmanager
def span(name: str, **attrs):
    """Time one stage inside the current trace; a no-op when no trace is open."""
    record = _CURRENT.get()
    if record is None:
        yield None
        return
    item = Span(name, record.stack[-1] if record.stack else None, time.perf_counter_ns(), attrs=dict(attrs))
    record.spans.append(item)
    index = len(record.spans) - 1
    record.stack.append(index)
    try:
        yield item
    except BaseException as error:
        item.status, item.error = "error", error_category(error)
        raise
    finally:
        item.end_ns = time.perf_counter_ns()
        if record.stack and record.stack[-1] == index:
            record.stack.pop()


def skipped(name: str, reason: str) -> None:
    """Record a stage that did not run for this request (for example allocation after a clarification)."""
    record = _CURRENT.get()
    if record is not None:
        now = time.perf_counter_ns()
        record.spans.append(Span(name, record.stack[-1] if record.stack else None, now, now, "skipped", attrs={"reason": reason}))


def note(**values) -> None:
    """Attach metadata (source, model, token usage...) to the current trace."""
    record = _CURRENT.get()
    if record is not None:
        record.meta.update(values)


def error_category(error: BaseException) -> str:
    return getattr(error, "category", None) or type(error).__name__


def group_of(name: str) -> str:
    for key, _, prefixes in GROUPS:
        if any(name == p or (p.endswith(":") and name.startswith(p)) for p in prefixes):
            return key
    return OTHER[0]


def self_times(record: Trace) -> list[float]:
    """Each span's duration minus its direct children's: no double counting."""
    own = [s.ms for s in record.spans]
    for s in record.spans:
        if s.parent is not None:
            own[s.parent] -= s.ms
    return [max(0.0, value) for value in own]


def stage_totals(record: Trace) -> list[dict[str, Any]]:
    """Milliseconds per UI stage group, in display order; sums to the trace total."""
    totals = {key: 0.0 for key, _, _ in GROUPS} | {OTHER[0]: 0.0}
    for s, own in zip(record.spans, self_times(record)):
        totals[OTHER[0] if s.parent is None else group_of(s.name)] += own
    labels = {key: label for key, label, _ in GROUPS} | {OTHER[0]: OTHER[1]}
    return [{"key": key, "label": labels[key], "ms": round(ms, 3)} for key, ms in totals.items()]


def save(record: Trace | dict, path: Path | None = None) -> dict:
    """Append one trace and keep only the newest RETENTION entries."""
    row = record.to_dict() if isinstance(record, Trace) else record
    destination = Path(path or TRACE_LOG)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a+", encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_EX)
        try:
            stream.seek(0)
            lines = [line for line in stream.read().splitlines() if line.strip()]
            lines.append(json.dumps(row, ensure_ascii=False, default=str))
            if len(lines) > RETENTION:
                stream.seek(0)
                stream.truncate()
                stream.write("\n".join(lines[-RETENTION:]) + "\n")
            else:
                stream.write(lines[-1] + "\n")
            stream.flush()
        finally:
            portalocker.unlock(stream)
    return row


def load(path: Path | None = None) -> list[dict]:
    """Saved traces, oldest first. A malformed line is skipped and counted, not fatal: these are diagnostics."""
    source = Path(path or TRACE_LOG)
    if not source.exists():
        return []
    rows = []
    with source.open(encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_SH)
        try:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        finally:
            portalocker.unlock(stream)
    return rows
