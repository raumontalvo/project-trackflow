from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data.pipelines.rfp_intake.config import COUNTRY_TO_CURRENCY


MAX_GENERATION_ITERATIONS = 3


@dataclass
class ReadabilityEvaluation:
    passed: bool
    score: float | None = None
    details: str = ""


@dataclass
class RelevanceEvaluation:
    passed: bool
    missing_aspects: list[str] = field(default_factory=list)


@dataclass
class ComplianceEvaluation:
    passed: bool
    rule_ids: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    section_id: str
    department_id: str
    readability: ReadabilityEvaluation
    relevance: RelevanceEvaluation
    compliance: ComplianceEvaluation
    overall_pass: bool
    feedback_for_generator: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "department_id": self.department_id,
            "readability": {
                "pass": self.readability.passed,
                "score": self.readability.score,
                "details": self.readability.details,
            },
            "relevance": {
                "pass": self.relevance.passed,
                "missing_aspects": self.relevance.missing_aspects,
            },
            "compliance": {
                "pass": self.compliance.passed,
                "rule_ids": self.compliance.rule_ids,
                "violations": self.compliance.violations,
            },
            "overall_pass": self.overall_pass,
            "feedback_for_generator": self.feedback_for_generator,
        }


COMPLIANCE_RULES = {
    "currency": "Pricing must use USD for US operations and EUR for Spain operations.",
    "delivery_sla": "Every proposal must state the on-time delivery SLA percentage.",
    "returns_minimum_48h": "No proposal may promise returns processing in under 48 hours.",
    "volume_discount_table": "Every proposal must include a volume-based discount tier table.",
    "carrier_rate_confidentiality": "Do not disclose negotiated carrier rates; only show final client pricing.",
}


def expected_currency(client_country: str | None) -> str | None:
    if not client_country:
        return None
    return COUNTRY_TO_CURRENCY.get(client_country)
