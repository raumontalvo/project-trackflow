"""Unit tests for TrackFlow RFP department workers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from data.pipelines.rfp_intake.nodes import worker


def _mock_client(payload: dict) -> MagicMock:
    """Create an OpenAI-compatible mocked worker client."""

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


def test_warehouse_worker_preserves_sku_count_without_inventing_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warehouse worker should preserve known figures and surface missing ones."""

    client = _mock_client(
        {
            "requested_scope": [
                "Storage of approximately 15,000 SKUs",
                "ERP integration via API",
            ],
            "known_requirements": [
                "Warehouse near Zaragoza",
                "Approximately 15,000 SKUs",
            ],
            "quantitative_requirements": {
                "sku_count": 15000,
            },
            "open_questions": [
                "What is the expected monthly inbound and outbound volume?",
            ],
            "relevant_extracts": [
                "Almacenamiento de aproximadamente 15.000 SKUs",
                "Integración con nuestro ERP vía API",
            ],
        }
    )

    monkeypatch.setattr(
        worker,
        "openai_client",
        lambda: client,
    )
    monkeypatch.setattr(
        worker,
        "generation_model",
        lambda: "test-model",
    )

    metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "Spain",
        "monthly_volume": None,
        "services_requested": [
            "warehousing",
            "returns",
        ],
    }

    extracts = [
        "Almacenamiento de aproximadamente 15.000 SKUs",
        "Integración con nuestro ERP vía API",
    ]

    result = worker.analyze_department(
        department_id="warehouse",
        metadata=metadata,
        extracts=extracts,
    )

    assert result.department_id == "warehouse"
    assert result.owner == "Ana Whitfield"

    assert result.quantitative_requirements["sku_count"] == 15000

    assert "monthly_volume" not in result.quantitative_requirements
    assert "monthly_order_volume" not in result.quantitative_requirements

    assert any(
        "monthly" in question.lower()
        and "volume" in question.lower()
        for question in result.open_questions
    )

    call = client.chat.completions.create.call_args
    messages = call.kwargs["messages"]
    combined_prompt = " ".join(
        message["content"]
        for message in messages
    )

    assert "ModaViva" in combined_prompt
    assert "15.000 SKUs" in combined_prompt
    assert "warehouse" in combined_prompt.lower()


def test_worker_uses_trackflow_owner_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker owner should come from controlled TrackFlow configuration."""

    client = _mock_client(
        {
            "requested_scope": ["Returns processing"],
            "known_requirements": ["Inspection and restocking"],
            "quantitative_requirements": {},
            "open_questions": [],
            "relevant_extracts": [
                "Gestión de devoluciones"
            ],
        }
    )

    monkeypatch.setattr(
        worker,
        "openai_client",
        lambda: client,
    )
    monkeypatch.setattr(
        worker,
        "generation_model",
        lambda: "test-model",
    )

    result = worker.analyze_department(
        department_id="reverse",
        metadata={
            "client_name": "ModaViva, S.L.",
        },
        extracts=[
            "Gestión de devoluciones"
        ],
    )

    assert result.department_id == "reverse"
    assert result.owner == "Sofía Ramos"


def test_worker_rejects_unknown_department() -> None:
    """The LLM must never create arbitrary department identifiers."""

    with pytest.raises(
        ValueError,
        match="Unknown TrackFlow department",
    ):
        worker.analyze_department(
            department_id="finance",
            metadata={},
            extracts=[],
        )


def test_parallel_worker_node_returns_mergeable_department_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One fan-out branch should return one keyed department result."""

    monkeypatch.setattr(
        worker,
        "analyze_department",
        lambda department_id, metadata, extracts: (
            worker.DepartmentKeyAspects(
                department_id="lastmile",
                owner="Carlos Vega",
                requested_scope=[
                    "US last-mile shipping",
                ],
                known_requirements=[
                    "5,000 orders per month",
                ],
                quantitative_requirements={
                    "monthly_order_volume": 5000,
                },
                open_questions=[],
                relevant_extracts=extracts,
            )
        ),
    )

    result = worker.department_worker_node(
        {
            "department_id": "lastmile",
            "rfp_metadata": {
                "client_name": "Luna Cosmetics",
            },
            "department_extract": [
                "We just crossed 5,000 orders a month."
            ],
        }
    )

    assert list(result["department_results"]) == [
        "lastmile"
    ]

    lastmile = result["department_results"]["lastmile"]

    assert lastmile["owner"] == "Carlos Vega"
    assert (
        lastmile["quantitative_requirements"][
            "monthly_order_volume"
        ]
        == 5000
    )