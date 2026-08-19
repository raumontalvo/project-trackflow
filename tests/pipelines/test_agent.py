"""Evaluation tests for the TrackFlow LangGraph agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.agent import graph as agent_graph_module


async def test_invalid_question_stops_before_retrieval(
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

    result = await agent_graph_module.run_agent("   ")

    assert result["error"] == "Question cannot be empty."
    assert result["answer"] == ""
    assert retrieve_called is False


async def test_valid_question_retrieves_then_generates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A grounded question should pass all guards before returning."""
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

    result = await agent_graph_module.run_agent(
        "What is the standard return window?"
    )

    assert "30 days" in result["answer"]
    assert "30 days from delivery" in result["context"]
    assert result["output_guard_allowed"] is True

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "guard_input",
        "tracking_authorization",
        "country_policy_guard",
        "route_request",
        "retrieve_context",
        "generate_answer",
        "output_guard",
    ]


async def test_no_context_uses_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No retrieved context should route to fallback and output validation."""
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

    result = await agent_graph_module.run_agent(
        "Can I offer an undocumented discount?"
    )

    assert "couldn't find enough approved TrackFlow information" in (
        result["answer"]
    )
    assert result["output_guard_allowed"] is True

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "guard_input",
        "tracking_authorization",
        "country_policy_guard",
        "route_request",
        "retrieve_context",
        "no_context",
        "output_guard",
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


async def test_checkpoint_can_be_inspected_after_run(
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

    result = await agent_graph_module.run_agent(
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
    assert checkpoint.values["output_guard_allowed"] is True
    assert "30 days from delivery" in checkpoint.values["context"]


async def test_ticket_question_routes_to_live_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ticket-status question should use the incident tool, not RAG."""
    from services.agent.tools import IncidentRecord, TicketLookupResult

    def fail_retrieve(*args, **kwargs):
        raise AssertionError(
            "RAG retrieval should not run for a ticket-only question."
        )

    monkeypatch.setattr(
        "services.agent.nodes.retrieve",
        fail_retrieve,
    )

    async def fake_lookup_ticket(payload):
        return TicketLookupResult(
            success=True,
            incident=IncidentRecord(
                id=1,
                title="Lost parcel at LA warehouse",
                description=(
                    "Customer parcel cannot be located after inbound scan."
                ),
                category="lost_parcel",
                status="in_progress",
                origin="branch",
                branch="la_warehouse",
                created_at="2026-07-06T23:31:47.205232+00:00",
                updated_at="2026-07-06T23:32:57.301961+00:00",
            ),
        )

    monkeypatch.setattr(
        "services.agent.nodes.lookup_ticket",
        fake_lookup_ticket,
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

    result = await agent_graph_module.run_agent(
        "What is the status of ticket 1?"
    )

    assert result["route"] == "ticket"
    assert result["incident_id"] == 1
    assert "in progress" in result["answer"]
    assert result["output_guard_allowed"] is True

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "guard_input",
        "tracking_authorization",
        "country_policy_guard",
        "route_request",
        "ticket_lookup",
        "generate_ticket_answer",
        "output_guard",
    ]


async def test_policy_question_routes_to_rag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A policy question should use RAG and should not call the ticket tool."""
    retrieved_chunks = [
        {
            "id": "point-policy",
            "score": 0.95,
            "company": "trackflow",
            "source_document": "returns-policy",
            "section": "Returns Policy",
            "language": "en",
            "chunk_index": 1,
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

    def fail_ticket_lookup(*args, **kwargs):
        raise AssertionError(
            "Ticket lookup should not run for a policy-only question."
        )

    monkeypatch.setattr(
        "services.agent.nodes.lookup_ticket",
        fail_ticket_lookup,
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

    result = await agent_graph_module.run_agent(
        "What is the standard return policy?"
    )

    assert result["route"] == "rag"
    assert "30 days" in result["answer"]
    assert result["output_guard_allowed"] is True

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "guard_input",
        "tracking_authorization",
        "country_policy_guard",
        "route_request",
        "retrieve_context",
        "generate_answer",
        "output_guard",
    ]


async def test_ticket_tool_failure_routes_to_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed incident call should recover and validate the fallback."""
    from services.agent.tools import TicketLookupResult

    async def fake_lookup_ticket(payload):
        return TicketLookupResult(
            success=False,
            error="The incident service is currently unavailable.",
        )

    monkeypatch.setattr(
        "services.agent.nodes.lookup_ticket",
        fake_lookup_ticket,
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

    result = await agent_graph_module.run_agent(
        "What is the status of ticket 482?"
    )

    assert result["route"] == "ticket"
    assert result["incident_id"] == 482
    assert result["answer"] == (
        "The incident service is currently unavailable."
    )
    assert result["output_guard_allowed"] is True

    executed_nodes = [
        event["node"]
        for event in recorded["events"]
    ]

    assert executed_nodes == [
        "validate_question",
        "guard_input",
        "tracking_authorization",
        "country_policy_guard",
        "route_request",
        "ticket_lookup",
        "ticket_fallback",
        "output_guard",
    ]