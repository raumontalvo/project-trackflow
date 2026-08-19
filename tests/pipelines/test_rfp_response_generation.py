from types import SimpleNamespace

from data.pipelines.rfp_intake.evaluation import (
    ComplianceEvaluation,
    ReadabilityEvaluation,
    RelevanceEvaluation,
)
from data.pipelines.rfp_intake import generator
from data.pipelines.rfp_intake import response_generation


def test_warehouse_generator_agent(monkeypatch):
    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="Warehouse proposal in USD with 98% on-time delivery SLA."
                )
            )
        ]
    )

    class FakeCompletions:
        def create(self, **kwargs):
            return fake_response

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        generator,
        "openai_client",
        lambda: FakeClient(),
    )

    monkeypatch.setattr(
        generator,
        "generation_model",
        lambda: "test-model",
    )

    result = generator.generate_warehouse_section(
        metadata={
            "client_country": "US",
            "client_name": "Luna Cosmetics",
        },
        key_aspects={
            "requested_scope": ["warehousing"],
            "known_requirements": ["5,000 orders/month"],
        },
    )

    assert "Warehouse proposal" in result
    assert "USD" in result


def test_section_passes_first_iteration(
    monkeypatch,
):
    monkeypatch.setattr(
        response_generation,
        "generate_department_section",
        lambda **kwargs: "Good proposal draft",
    )

    monkeypatch.setattr(
        response_generation,
        "evaluate_readability",
        lambda draft: ReadabilityEvaluation(
            passed=True,
            score=60.0,
            details="Readable",
        ),
    )

    monkeypatch.setattr(
        response_generation,
        "evaluate_relevance",
        lambda *args, **kwargs: RelevanceEvaluation(
            passed=True,
            missing_aspects=[],
        ),
    )

    monkeypatch.setattr(
        response_generation,
        "evaluate_compliance",
        lambda *args, **kwargs: ComplianceEvaluation(
            passed=True,
            rule_ids=["currency"],
            violations=[],
        ),
    )

    result = response_generation.generate_and_evaluate_section(
        section_id="section-1",
        department_id="warehouse",
        metadata={
            "client_country": "US",
        },
        key_aspects={
            "requested_scope": [
                "warehousing"
            ],
        },
    )

    assert result["iterations"] == 1
    assert result["needs_human_review"] is False
    assert (
        result["evaluation_result"]["overall_pass"]
        is True
    )


def test_failed_section_retries_then_requires_human_review(
    monkeypatch,
):
    calls = {
        "generator": 0,
    }

    def fake_generator(**kwargs):
        calls["generator"] += 1
        return "Still bad draft"

    monkeypatch.setattr(
        response_generation,
        "generate_department_section",
        fake_generator,
    )

    monkeypatch.setattr(
        response_generation,
        "evaluate_readability",
        lambda draft: ReadabilityEvaluation(
            passed=True,
            score=60.0,
            details="Readable",
        ),
    )

    monkeypatch.setattr(
        response_generation,
        "evaluate_relevance",
        lambda *args, **kwargs: RelevanceEvaluation(
            passed=False,
            missing_aspects=[
                "Missing storage scope"
            ],
        ),
    )

    monkeypatch.setattr(
        response_generation,
        "evaluate_compliance",
        lambda *args, **kwargs: ComplianceEvaluation(
            passed=True,
            rule_ids=[],
            violations=[],
        ),
    )

    result = response_generation.generate_and_evaluate_section(
        section_id="section-2",
        department_id="warehouse",
        metadata={
            "client_country": "US",
        },
        key_aspects={},
    )

    assert calls["generator"] == 3
    assert result["iterations"] == 3
    assert result["needs_human_review"] is True
    assert (
        result["evaluation_result"]["overall_pass"]
        is False
    )


def test_trackflow_compliance_rejects_wrong_currency_and_returns_under_48h():
    from data.pipelines.rfp_intake.evaluators import (
        evaluate_compliance,
    )

    draft = """
Warehouse and Returns Proposal

Pricing: EUR 4.50 per order.

TrackFlow commits to a 98% on-time delivery SLA.

Returns will be processed within 24 hours.

Volume-based discount tier table:

| Monthly Volume | Discount |
| --- | --- |
| 1-5000 | 0% |
| 5001+ | 5% |
"""

    result = evaluate_compliance(
        department_id="reverse",
        draft_content=draft,
        metadata={
            "client_country": "US",
        },
    )

    assert result.passed is False

    joined = " ".join(
        result.violations
    )

    assert "USD" in joined
    assert "48 hours" in joined