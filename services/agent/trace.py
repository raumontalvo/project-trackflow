"""Structured trace and guardrail observability for TrackFlow agent runs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal


FailureType = Literal[
    "structural",
    "content",
    "security",
]


TRACE_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
TRACE_FILE = TRACE_DIR / "agent_traces.jsonl"
GUARDRAIL_FILE = TRACE_DIR / "guardrail_events.jsonl"

_trace_lock = Lock()
_guardrail_lock = Lock()


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
            file.write(
                json.dumps(
                    trace,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )

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


def normalize_failure_type(
    *,
    guardrail_type: str,
    reason: str,
) -> FailureType:
    """Map guardrail events to structural/content/security categories."""
    lowered_type = guardrail_type.lower()
    lowered_reason = reason.lower()

    if lowered_type == "structural":
        return "structural"

    if lowered_type in {
        "security",
        "authorization",
        "country_policy",
    }:
        return "security"

    if lowered_type in {
        "content",
        "sensitive_data",
        "personal_task",
        "casual",
        "general_question",
    }:
        return "content"

    if any(
        term in lowered_reason
        for term in (
            "prompt_injection",
            "authorization",
            "not_owned",
            "country_policy",
            "instruction_leak",
        )
    ):
        return "security"

    if any(
        term in lowered_reason
        for term in (
            "empty_answer",
            "missing_or_invalid_answer",
            "malformed",
            "invalid_structure",
        )
    ):
        return "structural"

    return "content"


def record_guardrail_event(
    *,
    run_id: str,
    question: str,
    guardrail_type: str,
    reason: str,
    action: str,
    failure_type: FailureType | None = None,
) -> dict[str, Any]:
    """Persist one guardrail trigger for observability."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    normalized_failure_type = (
        failure_type
        or normalize_failure_type(
            guardrail_type=guardrail_type,
            reason=reason,
        )
    )

    event = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "question": question,
        "guardrail_type": guardrail_type,
        "failure_type": normalized_failure_type,
        "reason": reason,
        "action": action,
    }

    with _guardrail_lock:
        with GUARDRAIL_FILE.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    event,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )

    return event


def get_guardrail_counts() -> dict[str, int]:
    """Return trigger counts grouped by guardrail type."""
    if not GUARDRAIL_FILE.exists():
        return {}

    counter: Counter[str] = Counter()

    with GUARDRAIL_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            event = json.loads(line)
            guardrail_type = event.get("guardrail_type")

            if guardrail_type:
                counter[str(guardrail_type)] += 1

    return dict(counter)


def get_guardrail_summary() -> dict[str, Any]:
    """Return a compact observability summary for all guardrail events."""
    if not GUARDRAIL_FILE.exists():
        return {
            "total_events": 0,
            "by_guardrail_type": {},
            "by_failure_type": {},
            "by_action": {},
        }

    guardrail_counter: Counter[str] = Counter()
    failure_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()

    total_events = 0

    with GUARDRAIL_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            event = json.loads(line)
            total_events += 1

            guardrail_type = str(
                event.get("guardrail_type") or "content"
            )

            reason = str(
                event.get("reason") or "unknown"
            )

            failure_type = (
                event.get("failure_type")
                or normalize_failure_type(
                    guardrail_type=guardrail_type,
                    reason=reason,
                )
            )

            action = event.get("action")

            guardrail_counter[guardrail_type] += 1

            if failure_type:
                failure_counter[str(failure_type)] += 1

            if action:
                action_counter[str(action)] += 1

    return {
        "total_events": total_events,
        "by_guardrail_type": dict(guardrail_counter),
        "by_failure_type": dict(failure_counter),
        "by_action": dict(action_counter),
    }