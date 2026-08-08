"""Structured trace storage for TrackFlow agent runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


TRACE_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
TRACE_FILE = TRACE_DIR / "agent_traces.jsonl"

_trace_lock = Lock()


def record_trace(
    *,
    run_id: str,
    question: str,
    result: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist a structured, queryable trace for one complete agent run."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    trace = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "question": question,
        "events": events,
        "final_state": result,
    }

    with _trace_lock:
        with TRACE_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")

    return trace


def get_trace(run_id: str) -> dict[str, Any] | None:
    """Return a previously recorded trace by run ID."""
    if not TRACE_FILE.exists():
        return None

    with TRACE_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            trace = json.loads(line)

            if trace.get("run_id") == run_id:
                return trace

    return None