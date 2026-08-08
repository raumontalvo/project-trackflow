"""Unit tests for the TrackFlow RAG pipeline."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from data.pipelines import rag as pipeline_rag
from data.process import rag as process_rag


def test_load_chunks_covers_all_documents() -> None:
    chunks = process_rag.load_chunks()

    document_names = {chunk["source_document"] for chunk in chunks}

    assert document_names == {
        "sla-delivery",
        "returns-policy",
        "carrier-coverage",
        "storage-pricing",
    }
    assert len(chunks) == 18


def test_each_document_has_at_least_three_chunks() -> None:
    chunks = process_rag.load_chunks()
    counts: dict[str, int] = {}

    for chunk in chunks:
        source_document = chunk["source_document"]
        counts[source_document] = counts.get(source_document, 0) + 1

    assert all(count >= 3 for count in counts.values())


def test_deterministic_point_id_is_stable() -> None:
    first = process_rag._deterministic_point_id("sla-delivery", 0)
    second = process_rag._deterministic_point_id("sla-delivery", 0)
    different = process_rag._deterministic_point_id("sla-delivery", 1)

    assert first == second
    assert first != different


def test_embed_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="Cannot embed empty text"):
        process_rag.embed("   ")


def test_retrieve_returns_normalized_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline_rag,
        "embed",
        lambda question: [0.1, 0.2, 0.3],
    )

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                id="point-1",
                score=0.91,
                payload={
                    "company": "trackflow",
                    "source_document": "carrier-coverage",
                    "section": "Carrier Coverage",
                    "language": "en",
                    "chunk_index": 2,
                    "text": "SEUR offers the best coverage in rural Aragón.",
                },
            )
        ]
    )

    monkeypatch.setattr(
        pipeline_rag,
        "_qdrant_client",
        lambda: mock_qdrant,
    )
    monkeypatch.setattr(
        pipeline_rag,
        "_required_env",
        lambda name: "trackflow-knowledge-base",
    )

    results = pipeline_rag.retrieve(
        "Which carrier covers rural Aragón?",
        k=3,
        min_score=0.3,
    )

    assert len(results) == 1
    assert results[0]["source_document"] == "carrier-coverage"
    assert results[0]["chunk_index"] == 2
    assert results[0]["score"] == pytest.approx(0.91)
    assert "SEUR" in results[0]["text"]

    mock_qdrant.query_points.assert_called_once()


def test_query_generates_answer_from_retrieved_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieved_chunks = [
        {
            "id": "point-1",
            "score": 0.88,
            "company": "trackflow",
            "source_document": "returns-policy",
            "section": "Returns Policy",
            "language": "en",
            "chunk_index": 2,
            "text": (
                "Standard return window: 30 days from delivery, unless the "
                "client brand has configured a different window in its contract."
            ),
        }
    ]

    monkeypatch.setattr(
        pipeline_rag,
        "retrieve",
        lambda query, k, min_score: retrieved_chunks,
    )
    monkeypatch.setattr(
        pipeline_rag,
        "_required_env",
        lambda name: (
            "downtown-miami/openrouter/deepseek/deepseek-v4-flash"
            if name == "GENERATION_MODEL"
            else "unused"
        ),
    )

    mock_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        "The standard return window is 30 days from delivery, "
                        "unless the client contract specifies another window."
                    )
                )
            )
        ]
    )

    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_completion

    monkeypatch.setattr(
        pipeline_rag,
        "_openai_client",
        lambda: mock_openai,
    )

    result = pipeline_rag.query("What is the standard return window?")

    assert "30 days" in result

    call = mock_openai.chat.completions.create.call_args
    messages = call.kwargs["messages"]
    combined_prompt = " ".join(message["content"] for message in messages)

    assert "30 days from delivery" in combined_prompt
    assert "Retrieved TrackFlow context" in combined_prompt


def test_query_returns_safe_fallback_when_no_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline_rag,
        "retrieve",
        lambda query, k, min_score: [],
    )

    result = pipeline_rag.query(
        "Can I offer an undocumented storage discount?"
    )

    assert "couldn't find enough approved TrackFlow information" in result


def test_retrieve_passes_min_score_to_qdrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline_rag,
        "embed",
        lambda query: [0.1, 0.2, 0.3],
    )

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = SimpleNamespace(points=[])

    monkeypatch.setattr(
        pipeline_rag,
        "_qdrant_client",
        lambda: mock_qdrant,
    )
    monkeypatch.setattr(
        pipeline_rag,
        "_required_env",
        lambda name: "trackflow-knowledge-base",
    )

    results = pipeline_rag.retrieve(
        "What is the return window?",
        k=5,
        min_score=0.75,
    )

    assert results == []

    call = mock_qdrant.query_points.call_args
    assert call.kwargs["limit"] == 5
    assert call.kwargs["score_threshold"] == 0.75


def test_retrieve_can_return_fewer_than_k_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline_rag,
        "embed",
        lambda query: [0.1, 0.2, 0.3],
    )

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                id="point-1",
                score=0.92,
                payload={
                    "company": "trackflow",
                    "source_document": "sla-delivery",
                    "section": "Delivery SLA",
                    "language": "en",
                    "chunk_index": 1,
                    "text": "Standard shipping takes 3 to 5 business days.",
                },
            ),
            SimpleNamespace(
                id="point-2",
                score=0.81,
                payload={
                    "company": "trackflow",
                    "source_document": "sla-delivery",
                    "section": "Delivery SLA",
                    "language": "en",
                    "chunk_index": 3,
                    "text": "High-demand dates do not have a guaranteed SLA.",
                },
            ),
        ]
    )

    monkeypatch.setattr(
        pipeline_rag,
        "_qdrant_client",
        lambda: mock_qdrant,
    )
    monkeypatch.setattr(
        pipeline_rag,
        "_required_env",
        lambda name: "trackflow-knowledge-base",
    )

    results = pipeline_rag.retrieve(
        "What is the delivery SLA?",
        k=5,
        min_score=0.30,
    )

    assert len(results) == 2
    assert len(results) < 5
