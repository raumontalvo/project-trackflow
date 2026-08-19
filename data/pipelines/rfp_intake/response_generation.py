from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from data.pipelines.rfp_intake.evaluation import (
    MAX_GENERATION_ITERATIONS,
    EvaluationResult,
    expected_currency,
)
from data.pipelines.rfp_intake.evaluators import (
    evaluate_compliance,
    evaluate_readability,
    evaluate_relevance,
)
from data.pipelines.rfp_intake.generator import (
    generate_department_section,
)


def build_feedback(
    readability,
    relevance,
    compliance,
) -> str:
    feedback: list[str] = []

    if not readability.passed:
        feedback.append(
            "Improve readability. "
            f"{readability.details}"
        )

    if not relevance.passed:
        if relevance.missing_aspects:
            feedback.append(
                "Address these missing RFP aspects: "
                + "; ".join(relevance.missing_aspects)
            )
        else:
            feedback.append(
                "Revise the section so it directly answers "
                "the department's requested RFP scope."
            )

    if not compliance.passed:
        feedback.append(
            "Fix these TrackFlow compliance violations: "
            + "; ".join(compliance.violations)
        )

    if not feedback:
        return "No changes required."

    return " ".join(feedback)


def evaluate_section(
    section_id: str,
    department_id: str,
    draft_content: str,
    metadata: dict,
    key_aspects: dict,
) -> EvaluationResult:
    with ThreadPoolExecutor(
        max_workers=3
    ) as executor:
        readability_future = executor.submit(
            evaluate_readability,
            draft_content,
        )

        relevance_future = executor.submit(
            evaluate_relevance,
            department_id,
            draft_content,
            metadata,
            key_aspects,
        )

        compliance_future = executor.submit(
            evaluate_compliance,
            department_id,
            draft_content,
            metadata,
        )

        readability = readability_future.result()
        relevance = relevance_future.result()
        compliance = compliance_future.result()

    overall_pass = (
        readability.passed
        and relevance.passed
        and compliance.passed
    )

    feedback = build_feedback(
        readability,
        relevance,
        compliance,
    )

    return EvaluationResult(
        section_id=section_id,
        department_id=department_id,
        readability=readability,
        relevance=relevance,
        compliance=compliance,
        overall_pass=overall_pass,
        feedback_for_generator=feedback,
    )


def generate_and_evaluate_section(
    section_id: str,
    department_id: str,
    metadata: dict,
    key_aspects: dict,
) -> dict:
    feedback: str | None = None
    draft_content = ""
    evaluation: EvaluationResult | None = None

    for iteration in range(
        1,
        MAX_GENERATION_ITERATIONS + 1,
    ):
        draft_content = generate_department_section(
            department_id=department_id,
            metadata=metadata,
            key_aspects=key_aspects,
            feedback=feedback,
        )

        evaluation = evaluate_section(
            section_id=section_id,
            department_id=department_id,
            draft_content=draft_content,
            metadata=metadata,
            key_aspects=key_aspects,
        )

        if evaluation.overall_pass:
            commitments = extract_section_commitments(
                department_id=department_id,
                draft_content=draft_content,
                metadata=metadata,
                key_aspects=key_aspects,
            )

            return {
                "section_id": section_id,
                "department_id": department_id,
                "draft_content": draft_content,
                "evaluation_result": evaluation.to_dict(),
                "commitments": commitments,
                "iterations": iteration,
                "needs_human_review": False,
            }

        feedback = evaluation.feedback_for_generator

    if evaluation is None:
        raise RuntimeError(
            f"{department_id} produced no evaluation result."
        )

    commitments = extract_section_commitments(
        department_id=department_id,
        draft_content=draft_content,
        metadata=metadata,
        key_aspects=key_aspects,
    )

    return {
        "section_id": section_id,
        "department_id": department_id,
        "draft_content": draft_content,
        "evaluation_result": evaluation.to_dict(),
        "commitments": commitments,
        "iterations": MAX_GENERATION_ITERATIONS,
        "needs_human_review": True,
    }

def extract_section_commitments(
    department_id: str,
    draft_content: str,
    metadata: dict,
    key_aspects: dict,
) -> dict:
    """
    Normalize proposal commitments into structured state for Part 3.

    Unknown values remain None.
    """

    import re

    currency = expected_currency(
        metadata.get("client_country")
    )

    returns_turnaround_hours = None
    capacity_limit = None
    committed_volume = None

    if department_id == "reverse":
        match = re.search(
            r"(?:turnaround|returns?|return processing)"
            r".{0,100}?\b(\d{1,3})\s*hours?",
            draft_content,
            re.IGNORECASE | re.DOTALL,
        )

        if match:
            returns_turnaround_hours = int(
                match.group(1)
            )

    quantitative = (
        key_aspects.get(
            "quantitative_requirements",
            {},
        )
        or {}
    )

    if department_id == "warehouse":
        capacity_limit = (
            quantitative.get("capacity_limit")
            or quantitative.get("warehouse_capacity")
            or quantitative.get("monthly_capacity")
        )

    if department_id == "lastmile":
        committed_volume = (
            quantitative.get("committed_volume")
            or quantitative.get("monthly_volume")
            or metadata.get("monthly_volume")
        )

    return {
        "currency": currency,
        "returns_turnaround_hours": returns_turnaround_hours,
        "capacity_limit": capacity_limit,
        "committed_volume": committed_volume,
    }

