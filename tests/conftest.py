"""Make application and simulator modules importable in tests."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "harness")]


import pytest


@pytest.fixture(autouse=True)
def _private_trace_log(monkeypatch, tmp_path):
    """Tests never append to the real records/traces.jsonl."""
    import tracing
    monkeypatch.setattr(tracing, "TRACE_LOG", tmp_path / "traces.jsonl")
