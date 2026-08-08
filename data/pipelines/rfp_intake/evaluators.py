from __future__ import annotations

import json
import re

from data.pipelines.rfp_intake.document import calculate_readability
from data.pipelines.rfp_intake.evaluation import (
    COMPLIANCE_RULES,
    ComplianceEvaluation,
    ReadabilityEvaluation,
    RelevanceEvaluation,
    expected_currency,
)
from data.pipelines.rfp_intake.llm import generation_model, openai_client


READABILITY_MIN_SCORE = 40.0


def evaluate_readability(
    draft_content: str,
) -> ReadabilityEvaluation:
    metrics = calculate_readability(draft_content)

    score = metrics.get("flesch_reading_ease")

    passed = (
        score is not None
        and score >= READABILITY_MIN_SCORE
    )

    details = (
        f"Flesch Reading Ease: {score}; "
        f"word_count: {metrics.get('word_count')}"
    )

    return ReadabilityEvaluation(
        passed=passed,
        score=score,
        details=details,
    )


def evaluate_relevance(
    department_id: str,
    draft_content: str,
    metadata: dict,
    key_aspects: dict,
) -> RelevanceEvaluation:
    system_prompt = """
You are a TrackFlow proposal relevance evaluator.

Review exactly one department proposal section.

Compare the draft only against:
- the shared RFP metadata
- that department's Part 1 key_aspects

Do not invent requirements.

Identify material requirements or requested aspects the draft failed
to address.

Return ONLY valid JSON:

{
  "pass": true,
  "missing_aspects": []
}
""".strip()

    user_prompt = f"""
DEPARTMENT:
{department_id}

RFP METADATA:
{json.dumps(metadata, ensure_ascii=False)}

PART 1 KEY ASPECTS:
{json.dumps(key_aspects, ensure_ascii=False)}

DRAFT:
{draft_content}

Evaluate whether the draft addresses the requested department scope.
""".strip()

    response = openai_client().chat.completions.create(
        model=generation_model(),
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            f"{department_id} relevance evaluator returned an empty response."
        )

    raw = json.loads(content)

    missing_aspects = raw.get(
        "missing_aspects",
        [],
    )

    passed = bool(
        raw.get(
            "pass",
            not missing_aspects,
        )
    )

    if missing_aspects:
        passed = False

    return RelevanceEvaluation(
        passed=passed,
        missing_aspects=missing_aspects,
    )


def evaluate_compliance(
    department_id: str,
    draft_content: str,
    metadata: dict,
) -> ComplianceEvaluation:
    violations: list[str] = []

    text = draft_content.lower()

    currency = expected_currency(
        metadata.get("client_country")
    )

    if not currency:
        violations.append(
            "currency: client country does not map to a TrackFlow currency."
        )
    else:
        currency_lower = currency.lower()

        if currency_lower not in text:
            violations.append(
                f"currency: proposal must quote pricing in {currency}."
            )

        wrong_currency = (
            "eur"
            if currency == "USD"
            else "usd"
        )

        if wrong_currency in text:
            violations.append(
                f"currency: proposal contains {wrong_currency.upper()} "
                f"but the required currency is {currency}."
            )

    sla_pattern = re.compile(
        r"(on[- ]time|delivery).{0,60}\b\d{1,3}(?:\.\d+)?\s*%",
        re.IGNORECASE | re.DOTALL,
    )

    if not sla_pattern.search(draft_content):
        violations.append(
            "delivery_sla: state TrackFlow's on-time delivery SLA "
            "as a percentage."
        )

    under_48_pattern = re.compile(
        r"(returns?|return processing|turnaround).{0,80}"
        r"(under|less than|within)\s+(?:[0-3]?\d|4[0-7])\s*hours?",
        re.IGNORECASE | re.DOTALL,
    )

    if under_48_pattern.search(draft_content):
        violations.append(
            "returns_minimum_48h: returns processing may not be "
            "promised in under 48 hours."
        )

    discount_terms = (
        "volume-based discount",
        "volume based discount",
        "discount tier",
        "volume tier",
    )

    has_discount_language = any(
        term in text
        for term in discount_terms
    )

    has_table = (
        "|" in draft_content
        or "tier 1" in text
        or "tier 2" in text
    )

    if not (
        has_discount_language
        and has_table
    ):
        violations.append(
            "volume_discount_table: include a volume-based "
            "discount tier table."
        )

    carrier_disclosure_patterns = (
        r"(fedex|ups|dhl|usps).{0,50}"
        r"(negotiated|internal|wholesale|carrier rate)",
        r"(negotiated|internal|wholesale).{0,50}"
        r"(fedex|ups|dhl|usps)",
    )

    if any(
        re.search(
            pattern,
            draft_content,
            re.IGNORECASE | re.DOTALL,
        )
        for pattern in carrier_disclosure_patterns
    ):
        violations.append(
            "carrier_rate_confidentiality: do not disclose "
            "negotiated rates with specific carriers."
        )

    return ComplianceEvaluation(
        passed=not violations,
        rule_ids=list(COMPLIANCE_RULES.keys()),
        violations=violations,
    )