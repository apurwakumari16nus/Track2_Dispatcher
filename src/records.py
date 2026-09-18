"""Explicit local JSONL persistence for the UI; importing creates no files."""

from datetime import datetime, timezone
import json
from pathlib import Path

import portalocker

from agent import AgentResponse
import faithfulness

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "records" / "decisions.jsonl"


def append(response: AgentResponse, path: str | Path | None = None) -> dict:
    """Append one JSON object and return it, including UTC logging timestamp.

    The decision timestamp separately retains the supplied business date.
    Constraints keep imposed_by/relayed_by from intake; unknown attribution stays
    unknown. No invented author, API key, or environment configuration is logged.
    Invalid/unfaithful records fail before opening the output file. Logging is
    explicit; a UI should append once per handled response, not on each rerender.
    """
    row = response.to_dict()
    audit = faithfulness.check(row["explanation_text"], row["decision_record"])
    if not audit["passed"]:
        raise ValueError(f"Cannot log an unfaithful explanation: {audit['unmatched']}")
    row.update(timestamp=datetime.now(timezone.utc).isoformat(),
               sender=response.parsed_request.sender,
               constraints=row["decision_record"]["constraints_applied"], faithfulness=audit)
    line = json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
    destination = Path(path) if path is not None else DEFAULT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Cooperating readers/writers lock on Windows as well as macOS/Linux.
    with destination.open("a", encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_EX)
        try:
            stream.write(line)
            stream.flush()
        finally:
            portalocker.unlock(stream)
    return row


def load(path: str | Path | None = None) -> list[dict]:
    """Return logged rows in append order, or [] before the first log exists.

    Malformed rows raise a line-numbered ValueError instead of silently dropping
    evidence. A shared advisory lock keeps reads clear of an in-progress append.
    """
    source = Path(path) if path is not None else DEFAULT_PATH
    try:
        stream = source.open(encoding="utf-8")
    except FileNotFoundError:
        return []
    with stream:
        portalocker.lock(stream, portalocker.LOCK_SH)
        rows = []
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("record must be a JSON object")
            except ValueError as error:
                raise ValueError(f"Invalid decision record in {source} at line {number}") from error
            rows.append(row)
        return rows
