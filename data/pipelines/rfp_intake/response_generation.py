from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from data.pipelines.rfp_intake.evaluation import (
    MAX_GENERATION_ITERATIONS,
    EvaluationResult,
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
            return {
                "section_id": section_id,
                "department_id": department_id,
                "draft_content": draft_content,
                "evaluation_result": evaluation.to_dict(),
                "iterations": iteration,
                "needs_human_review": False,
            }

        feedback = evaluation.feedback_for_generator

    if evaluation is None:
        raise RuntimeError(
            f"{department_id} produced no evaluation result."
        )

    return {
        "section_id": section_id,
        "department_id": department_id,
        "draft_content": draft_content,
        "evaluation_result": evaluation.to_dict(),
        "iterations": MAX_GENERATION_ITERATIONS,
        "needs_human_review": True,
    }