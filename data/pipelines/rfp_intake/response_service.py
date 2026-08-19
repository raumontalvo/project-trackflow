"""Part 2 response-generation service and Part 3 handoff."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlmodel import Session, select

from data.pipelines.rfp_intake.approval_service import (
    start_ticket_approval,
)
from data.pipelines.rfp_intake.persistence import (
    persist_generated_section,
    update_ticket_status,
)
from data.pipelines.rfp_intake.response_generation import (
    generate_and_evaluate_section,
)
from services.api.database import engine
from services.api.models import (
    DepartmentSection,
    RFP,
    Ticket,
)


def generate_ticket_response(
    ticket_id: str,
) -> dict:
    """
    Generate and evaluate every active department section.

    Successful Part 2 completion continues directly into the persisted
    Part 3 human-approval workflow using the same ticket.
    """

    update_ticket_status(
        ticket_id,
        "drafting",
    )

    with Session(engine) as session:
        ticket = session.get(
            Ticket,
            ticket_id,
        )

        if ticket is None:
            raise ValueError(
                f"RFP ticket not found: {ticket_id}"
            )

        if not ticket.rfp_id:
            raise ValueError(
                "Ticket has no accepted RFP."
            )

        rfp = session.get(
            RFP,
            ticket.rfp_id,
        )

        if rfp is None:
            raise ValueError(
                f"RFP not found: {ticket.rfp_id}"
            )

        sections = list(
            session.exec(
                select(DepartmentSection).where(
                    DepartmentSection.rfp_id
                    == rfp.rfp_id
                )
            ).all()
        )

        metadata = {
            "client_name": rfp.client_name,
            "client_country": rfp.client_country,
            "services_requested": rfp.services_requested,
            "monthly_volume": rfp.monthly_volume,
            "deadline": (
                rfp.deadline.isoformat()
                if rfp.deadline
                else None
            ),
            "budget_range": rfp.budget_range,
            "departments_needed": rfp.departments_needed,
        }

        section_inputs = [
            {
                "section_id": section.id,
                "department_id": section.department_id,
                "key_aspects": section.key_aspects,
            }
            for section in sections
        ]

    if not section_inputs:
        raise ValueError(
            "Accepted RFP has no department sections."
        )

    update_ticket_status(
        ticket_id,
        "under_evaluation",
    )

    def process_section(
        section_input: dict,
    ) -> dict:
        result = generate_and_evaluate_section(
            section_id=section_input["section_id"],
            department_id=section_input["department_id"],
            metadata=metadata,
            key_aspects=section_input["key_aspects"],
        )

        persist_generated_section(
            section_id=result["section_id"],
            draft_content=result["draft_content"],
            evaluation_result=result["evaluation_result"],
            iterations=result["iterations"],
            needs_human_review=result["needs_human_review"],
            commitments=result.get("commitments"),
        )

        return result

    max_workers = max(
        1,
        len(section_inputs),
    )

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
        results = list(
            executor.map(
                process_section,
                section_inputs,
            )
        )

    needs_human_review = any(
        result["needs_human_review"]
        for result in results
    )

    if needs_human_review:
        update_ticket_status(
            ticket_id,
            "needs_human_review",
        )

        return {
            "ticket_id": ticket_id,
            "status": "needs_human_review",
            "sections": results,
        }

    # Part 2 passed for every active department.
    # Continue the SAME ticket directly into Part 3.
    approval_result = start_ticket_approval(
        ticket_id
    )

    return {
        "ticket_id": ticket_id,
        "status": "waiting_for_approval",
        "sections": results,
        "approval_result": approval_result,
    }
