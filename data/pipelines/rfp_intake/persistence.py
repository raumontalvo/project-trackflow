"""Persistence helpers for TrackFlow RFP intake."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlmodel import Session, select

from data.pipelines.rfp_intake.config import DEPARTMENTS
from services.api.database import engine
from services.api.models import DepartmentSection, RFP, Ticket


def get_ticket(ticket_id: str) -> Ticket | None:
    """Load one RFP ticket from PostgreSQL."""

    with Session(engine) as session:
        return session.get(Ticket, ticket_id)


def create_ticket(
    raw_pdf_path: str,
) -> Ticket:
    """Create a new Part 1 ticket in analyzing state."""

    ticket = Ticket(
        status="analyzing",
        raw_pdf_path=raw_pdf_path,
    )

    with Session(engine) as session:
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        return ticket


def update_ticket_status(
    ticket_id: str,
    status: str,
    *,
    rfp_id: str | None = None,
    error_message: str | None = None,
) -> Ticket:
    """Update ticket lifecycle state."""

    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)

        if ticket is None:
            raise ValueError(
                f"RFP ticket not found: {ticket_id}"
            )

        ticket.status = status
        ticket.updated_at = datetime.utcnow()

        if rfp_id is not None:
            ticket.rfp_id = rfp_id

        ticket.error_message = error_message

        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        return ticket


def persist_valid_rfp(
    ticket_id: str,
    metadata: dict[str, Any],
    department_results: dict[str, dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> RFP:
    """
    Persist accepted RFP metadata, department analyses, and final intake summary.

    PostgreSQL is the source of truth.
    """

    deadline_value = metadata.get("deadline")

    if isinstance(deadline_value, str):
        deadline_value = date.fromisoformat(deadline_value)

    rfp = RFP(
        client_name=metadata.get("client_name"),
        client_country=metadata.get("client_country"),
        services_requested=metadata.get(
            "services_requested",
            [],
        ),
        monthly_volume=metadata.get("monthly_volume"),
        deadline=deadline_value,
        budget_range=metadata.get("budget_range"),
        departments_needed=metadata.get(
            "departments_needed",
            [],
        ),
        readability_metrics=metadata.get(
            "readability_metrics",
            {},
        ),
        intake_summary=summary or {},
    )

    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)

        if ticket is None:
            raise ValueError(
                f"RFP ticket not found: {ticket_id}"
            )

        session.add(rfp)
        session.flush()

        for department_id, result in department_results.items():
            if department_id not in DEPARTMENTS:
                raise ValueError(
                    f"Unknown department result: {department_id}"
                )

            section = DepartmentSection(
                rfp_id=rfp.rfp_id,
                department_id=department_id,
                owner=DEPARTMENTS[department_id]["owner"],
                key_aspects=result,
            )

            session.add(section)

        ticket.rfp_id = rfp.rfp_id
        ticket.status = "intake_complete"
        ticket.error_message = None
        ticket.updated_at = datetime.utcnow()

        session.add(ticket)
        session.commit()
        session.refresh(rfp)

        return rfp


def mark_ticket_discarded(
    ticket_id: str,
) -> Ticket:
    """Mark a classifier-rejected document as discarded."""

    return update_ticket_status(
        ticket_id,
        "discarded",
    )


def mark_ticket_error(
    ticket_id: str,
    error_message: str,
) -> Ticket:
    """
    Keep the ticket truthful when processing fails.

    Part 1 defines no dedicated failure status, so the ticket remains
    analyzing with an error message instead of being mislabeled as discarded.
    """

    return update_ticket_status(
        ticket_id,
        "analyzing",
        error_message=error_message,
    )


def get_ticket_sections(
    rfp_id: str,
) -> list[DepartmentSection]:
    """Return all department sections for one RFP."""

    with Session(engine) as session:
        statement = select(DepartmentSection).where(
            DepartmentSection.rfp_id == rfp_id
        )

        return list(
            session.exec(statement).all()
        )


def get_rfp(
    rfp_id: str,
) -> RFP | None:
    """Load one accepted RFP."""

    with Session(engine) as session:
        return session.get(RFP, rfp_id)

def persist_generated_section(
    section_id: str,
    draft_content: str,
    evaluation_result: dict[str, Any],
    iterations: int,
    needs_human_review: bool,
) -> DepartmentSection:
    with Session(engine) as session:
        section = session.get(
            DepartmentSection,
            section_id,
        )

        if section is None:
            raise ValueError(
                f"RFP department section not found: {section_id}"
            )

        section.draft_content = draft_content
        section.evaluation_results = {
            "evaluation": evaluation_result,
            "iterations": iterations,
            "needs_human_review": needs_human_review,
        }
        section.updated_at = datetime.utcnow()

        session.add(section)
        session.commit()
        session.refresh(section)

        return section


def get_ticket(
    ticket_id: str,
) -> Ticket | None:
    with Session(engine) as session:
        return session.get(
            Ticket,
            ticket_id,
        )