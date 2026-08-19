"""Evaluation tests for the TrackFlow LangGraph agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.agent import graph as agent_graph_module


def test_invalid_question_stops_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An invalid question should terminate before retrieval or generation."""
    monkeypatch.setattr(
        agent_graph_module,
        "record_trace",
        lambda **kwargs: kwargs,
    )

    retrieve_called = False

    def fail_retrieve(*args, **kwargs):
        nonlocal retrieve_called
        retrieve_called = True
        raise AssertionError(
            "Retrieval should not run for an invalid question."
        )

    monkeypatch.setattr(
        "services.agent.nodes.retrieve",
        fail_retrieve,
    )

    result = agent_graph_module.run_agent("   ")

    assert result["error"] == "Question cannot be empty."
    assert result["answer"] == ""
    assert retrieve_called is False


def test_valid_question_retrieves_then_generates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A grounded question should follow retrieve -> generate."""
    retrieved_chunks = [
        {
            "id": "point-1",
            "score": 0.91,
            "company": "trackflow",
            "source_document": "returns-policy",
            "section": "Returns Policy",
            "language": "en",
            "chunk_index": 2,
            "text": "Standard return window: 30 days from delivery.",
        }
    ]

    monkeypatch.setattr(
        "services.agent.nodes.retrieve",
        lambda question, k, min_score: retrieved_chunks,
    )

    monkeypatch.setattr(
        "services.agent.nodes.generate_answer",
        lambda question, context: (
            "The standard return window is 30 days from delivery."
        ),
    )

    recorded = {}

    def fake_record_trace(**kwargs):
        recorded.update(kwargs)
        return kwargs

    monkeypatch.setattr(
        agent_graph_module,
        "record_trace",
        fake_record_trace,
    )

    result = agent_graph_module.run_agent(
        "What is the standard return window?"
    )

    assert "30 days" in result["answer"]
    assert "30 days from delivery" in result["context"]

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "retrieve_context",
        "generate_answer",
    ]


def test_no_context_uses_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No retrieved context should route to the safe fallback node."""
    monkeypatch.setattr(
        "services.agent.nodes.retrieve",
        lambda question, k, min_score: [],
    )

    def fail_generation(*args, **kwargs):
        raise AssertionError(
            "Generation should not run when retrieval returns no context."
        )

    monkeypatch.setattr(
        "services.agent.nodes.generate_answer",
        fail_generation,
    )

    recorded = {}

    def fake_record_trace(**kwargs):
        recorded.update(kwargs)
        return kwargs

    monkeypatch.setattr(
        agent_graph_module,
        "record_trace",
        fake_record_trace,
    )

    result = agent_graph_module.run_agent(
        "Can I offer an undocumented discount?"
    )

    assert "couldn't find enough approved TrackFlow information" in (
        result["answer"]
    )

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "retrieve_context",
        "no_context",
    ]


def test_trace_file_is_queryable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A completed run should be serializable as structured trace data."""
    trace_path = tmp_path / "trace.jsonl"

    monkeypatch.setattr(
        "services.agent.trace.TRACE_FILE",
        trace_path,
    )

    monkeypatch.setattr(
        "services.agent.trace.TRACE_DIR",
        tmp_path,
    )

    from services.agent.trace import get_trace, record_trace

    trace = record_trace(
        run_id="run-123",
        question="What is the return window?",
        result={
            "answer": "30 days",
        },
        events=[
            {
                "node": "validate_question",
                "output": {
                    "question": "What is the return window?"
                },
            },
            {
                "node": "retrieve_context",
                "output": {
                    "context": "Standard return window: 30 days."
                },
            },
        ],
    )

    saved = get_trace("run-123")

    assert trace["run_id"] == "run-123"
    assert saved is not None
    assert saved["run_id"] == "run-123"
    assert saved["events"][0]["node"] == "validate_question"


def test_checkpoint_can_be_inspected_after_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed run should leave inspectable LangGraph checkpoint state."""
    retrieved_chunks = [
        {
            "id": "point-1",
            "score": 0.91,
            "company": "trackflow",
            "source_document": "returns-policy",
            "section": "Returns Policy",
            "language": "en",
            "chunk_index": 2,
            "text": "Standard return window: 30 days from delivery.",
        }
    ]

    monkeypatch.setattr(
        "services.agent.nodes.retrieve",
        lambda question, k, min_score: retrieved_chunks,
    )

    monkeypatch.setattr(
        "services.agent.nodes.generate_answer",
        lambda question, context: (
            "The standard return window is 30 days from delivery."
        ),
    )

    monkeypatch.setattr(
        agent_graph_module,
        "record_trace",
        lambda **kwargs: kwargs,
    )

    result = agent_graph_module.run_agent(
        "What is the standard return window?"
    )

    config = {
        "configurable": {
            "thread_id": result["run_id"],
        }
    }

    checkpoint = agent_graph_module.agent_graph.get_state(config)

    assert checkpoint.values["question"] == (
        "What is the standard return window?"
    )
    assert checkpoint.values["answer"] == (
        "The standard return window is 30 days from delivery."
    )
    assert "30 days from delivery" in checkpoint.values["context"]