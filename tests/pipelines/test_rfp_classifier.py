"""Unit tests for the TrackFlow RFP classifier."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from data.pipelines.rfp_intake.nodes import classify


def _mock_client(payload: dict) -> MagicMock:
    """Create an OpenAI-compatible mocked classifier client."""

    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(payload)
                )
            )
        ]
    )

    client = MagicMock()
    client.chat.completions.create.return_value = completion

    return client


def test_classifier_accepts_formal_rfp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A formal client RFP should be accepted."""

    client = _mock_client(
        {
            "is_rfp": True,
            "confidence": 0.98,
            "reason": (
                "Client requests warehousing and returns services."
            ),
        }
    )

    monkeypatch.setattr(
        classify,
        "openai_client",
        lambda: client,
    )
    monkeypatch.setattr(
        classify,
        "generation_model",
        lambda: "test-model",
    )

    markdown = """
    REQUEST FOR PROPOSAL

    ModaViva, S.L. requests a proposal for warehousing near
    Zaragoza and returns processing.

    ModaViva maintains its own last-mile carrier.
    """

    result = classify.classify_markdown(markdown)

    assert result.is_rfp is True
    assert result.confidence == pytest.approx(0.98)
    assert "warehousing" in result.reason.lower()

    call = client.chat.completions.create.call_args

    assert call.kwargs["temperature"] == 0


def test_classifier_accepts_informal_client_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An informal request can still be a legitimate TrackFlow RFP."""

    client = _mock_client(
        {
            "is_rfp": True,
            "confidence": 0.95,
            "reason": (
                "Prospective client requests warehousing and "
                "shipping services."
            ),
        }
    )

    monkeypatch.setattr(
        classify,
        "openai_client",
        lambda: client,
    )
    monkeypatch.setattr(
        classify,
        "generation_model",
        lambda: "test-model",
    )

    markdown = """
    Hi TrackFlow,

    We're Luna Cosmetics in Los Angeles. We just crossed
    5,000 orders a month and need someone to handle
    warehousing and shipping across the US.

    We also need help selecting carriers.
    """

    result = classify.classify_markdown(markdown)

    assert result.is_rfp is True
    assert result.confidence >= 0.9


def test_classifier_rejects_carrier_sales_pitch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A carrier selling services to TrackFlow must be rejected."""

    client = _mock_client(
        {
            "is_rfp": False,
            "confidence": 1.0,
            "reason": (
                "Carrier is offering its services to TrackFlow "
                "rather than requesting TrackFlow logistics services."
            ),
        }
    )

    monkeypatch.setattr(
        classify,
        "openai_client",
        lambda: client,
    )
    monkeypatch.setattr(
        classify,
        "generation_model",
        lambda: "test-model",
    )

    markdown = """
    RapidShip Carriers would like to become a preferred
    carrier partner for TrackFlow.

    We offer discounted shipping rates for volumes above
    10,000 packages per month.
    """

    result = classify.classify_markdown(markdown)

    assert result.is_rfp is False
    assert result.confidence == pytest.approx(1.0)


def test_classifier_rejects_empty_document() -> None:
    """Empty converted documents should never reach the model."""

    with pytest.raises(
        ValueError,
        match="Cannot classify an empty document",
    ):
        classify.classify_markdown("   ")


def test_classifier_node_sets_discard_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected classifier results should populate graph routing state."""

    monkeypatch.setattr(
        classify,
        "classify_markdown",
        lambda markdown: classify.ClassificationResult(
            is_rfp=False,
            confidence=0.99,
            reason="Vendor solicitation.",
        ),
    )

    result = classify.classify_rfp_node(
        {
            "markdown": "Vendor pitch",
        }
    )

    assert result["is_rfp"] is False
    assert result["rejection_reason"] == "Vendor solicitation."
    assert classify.route_after_classification(result) == "discarded"