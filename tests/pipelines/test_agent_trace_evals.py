"""Offline evaluations against a previously saved TrackFlow agent trace."""

from __future__ import annotations

import json
from pathlib import Path


TRACE_FILE = Path("data/eval/agent_trace_example.json")


def load_saved_trace() -> dict:
    """Load the exported trace without executing the graph again."""
    return json.loads(TRACE_FILE.read_text(encoding="utf-8"))


def test_saved_trace_retrieves_before_generation() -> None:
    """Retrieval must occur before answer generation."""
    trace = load_saved_trace()

    nodes = [event["node"] for event in trace["events"]]

    assert "retrieve_context" in nodes
    assert "generate_answer" in nodes
    assert nodes.index("retrieve_context") < nodes.index("generate_answer")


def test_saved_trace_uses_separate_retrieval_and_generation_nodes() -> None:
    """The agent must not collapse retrieval and generation into query()."""
    trace = load_saved_trace()

    nodes = [event["node"] for event in trace["events"]]

    assert "validate_question" in nodes
    assert "retrieve_context" in nodes
    assert "generate_answer" in nodes
    assert "query" not in nodes


def test_saved_trace_answer_is_grounded_in_returns_policy() -> None:
    """The saved answer must preserve the known TrackFlow return-window fact."""
    trace = load_saved_trace()

    answer = trace["final_state"]["answer"]
    chunks = trace["final_state"]["chunks"]

    source_documents = {
        chunk["source_document"]
        for chunk in chunks
    }

    retrieved_text = " ".join(
        chunk["text"]
        for chunk in chunks
    )

    assert trace["question"] == "What is the standard return window?"
    assert "returns-policy" in source_documents
    assert "30 days from delivery" in retrieved_text
    assert "30 days" in answer