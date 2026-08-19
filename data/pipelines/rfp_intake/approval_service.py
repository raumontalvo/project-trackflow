"""DB-backed TrackFlow Part 3 approval service."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from data.pipelines.rfp_intake.approval_graph import (
    get_approval_workflow_state,
    resume_approval_workflow,
    start_approval_workflow,
)
from data.pipelines.rfp_intake.evaluation import (
    expected_currency,
)
from data.pipelines.rfp_intake.persistence import (
    persist_approval_decision,
    update_ticket_status,
)
from services.api.database import engine
from services.api.models import (
    DepartmentSection,
    RFP,
    Ticket,
)


def _build_section_commitments(
    *,
    rfp: RFP,
    section: DepartmentSection,
) -> dict[str, Any]:
    """Load only structured, known commitments."""

    key_aspects = section.key_aspects or {}

    quantitative = key_aspects.get(
        "quantitative_requirements",
        {},
    ) or {}

    evaluation_results = (
        section.evaluation_results
        or {}
    )

    stored = evaluation_results.get(
        "commitments",
        {},
    ) or {}

    commitments: dict[str, Any] = {
        "currency": stored.get(
            "currency",
            expected_currency(
                rfp.client_country
            ),
        ),
        "capacity_limit": stored.get(
            "capacity_limit"
        ),
        "committed_volume": stored.get(
            "committed_volume"
        ),
        "returns_turnaround_hours": stored.get(
            "returns_turnaround_hours"
        ),
    }

    if commitments["capacity_limit"] is None:
        commitments["capacity_limit"] = (
            quantitative.get(
                "capacity_limit"
            )
            or quantitative.get(
                "warehouse_capacity"
            )
            or quantitative.get(
                "monthly_capacity"
            )
        )

    if commitments["committed_volume"] is None:
        commitments["committed_volume"] = (
            quantitative.get(
                "committed_volume"
            )
            or quantitative.get(
                "monthly_volume"
            )
            or quantitative.get(
                "monthly_order_volume"
            )
            or (
                rfp.monthly_volume
                if section.department_id
                == "lastmile"
                else None
            )
        )

    return commitments


def build_approval_initial_state(
    ticket_id: str,
) -> dict[str, Any]:
    """Build Part 3 state from persisted Part 1/2 records."""

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

        if ticket.status not in {
            "under_evaluation",
            "needs_human_review",
            "waiting_for_approval",
        }:
            raise ValueError(
                "Part 3 approval requires a completed "
                "Part 2 ticket."
            )

        rfp = session.get(
            RFP,
            ticket.rfp_id,
        )

        if rfp is None:
            raise ValueError(
                f"RFP not found: {ticket.rfp_id}"
            )

        rows = list(
            session.exec(
                select(DepartmentSection).where(
                    DepartmentSection.rfp_id
                    == rfp.rfp_id
                )
            ).all()
        )

        by_department = {
            row.department_id: row
            for row in rows
        }

        active_departments = list(
            rfp.departments_needed or []
        )

        missing = [
            department_id
            for department_id
            in active_departments
            if department_id
            not in by_department
        ]

        if missing:
            raise ValueError(
                "Missing Part 2 sections for: "
                + ", ".join(missing)
            )

        sections: dict[
            str,
            dict[str, Any],
        ] = {}

        commitments: dict[
            str,
            dict[str, Any],
        ] = {}

        for department_id in active_departments:
            section = by_department[
                department_id
            ]

            if not section.draft_content:
                raise ValueError(
                    "Department section has no Part 2 draft: "
                    f"{department_id}"
                )

            sections[department_id] = {
                "section_id": section.id,
                "department_id": department_id,
                "owner": section.owner,
                "key_aspects": section.key_aspects,
                "draft_content": section.draft_content,
                "evaluation_results": (
                    section.evaluation_results
                ),
            }

            commitments[department_id] = (
                _build_section_commitments(
                    rfp=rfp,
                    section=section,
                )
            )

        rfp_id = rfp.rfp_id
        client_name = rfp.client_name
        client_country = rfp.client_country

    return {
        "ticket_id": ticket_id,
        "rfp_id": rfp_id,
        "client_name": client_name,
        "client_country": client_country,
        "currency": expected_currency(
            client_country
        ),
        "active_departments": active_departments,
        "sections": sections,
        "section_commitments": commitments,
        "revision_counts": {
            department_id: 0
            for department_id
            in active_departments
        },
        "approval_results": {},
        "conflicts": [],
        "arbitration_results": [],
        "trace_events": [],
        "final_document": None,
        "status": "waiting_for_approval",
        "error": None,
    }


def start_ticket_approval(
    ticket_id: str,
) -> dict[str, Any]:
    """Start independent approval threads for all active departments."""

    initial_state = build_approval_initial_state(
        ticket_id
    )

    for department_id in initial_state[
        "active_departments"
    ]:
        section = initial_state[
            "sections"
        ][department_id]

        persist_approval_decision(
            section["section_id"],
            approval_status="waiting_for_approval",
            approver=None,
        )

    update_ticket_status(
        ticket_id,
        "waiting_for_approval",
    )

    return start_approval_workflow(
        initial_state
    )


def get_pending_approvals(
    ticket_id: str,
) -> list[dict[str, Any]]:
    """Return unresolved interrupts from all department threads."""

    snapshot = get_approval_workflow_state(
        ticket_id
    )

    pending: list[dict[str, Any]] = []

    for task in snapshot.tasks:
        if task.result is not None:
            continue

        for item in task.interrupts:
            payload = item.value

            pending.append(
                {
                    "interrupt_id": item.id,
                    "department_id": payload.get(
                        "department_id"
                    ),
                    "approver": payload.get(
                        "approver"
                    ),
                    "allowed_actions": payload.get(
                        "allowed_actions",
                        [],
                    ),
                    "section": payload.get(
                        "section",
                        {},
                    ),
                }
            )

    return pending


def submit_approval_decision(
    *,
    ticket_id: str,
    interrupt_id: str,
    action: str,
    approver: str,
    comment: str | None = None,
) -> dict[str, Any]:
    """Resume exactly one department approval thread."""

    pending = get_pending_approvals(
        ticket_id
    )

    approval = next(
        (
            item
            for item in pending
            if item["interrupt_id"]
            == interrupt_id
        ),
        None,
    )

    if approval is None:
        raise ValueError(
            "Approval interrupt not found or already completed."
        )

    if approver != approval["approver"]:
        raise ValueError(
            f"{approval['department_id']} must be decided by "
            f"{approval['approver']}."
        )

    if action not in {
        "approve",
        "reject",
        "request_changes",
    }:
        raise ValueError(
            "Action must be approve, reject, or request_changes."
        )

    result = resume_approval_workflow(
        ticket_id,
        {
            interrupt_id: {
                "action": action,
                "approver": approver,
                "comment": comment,
            }
        },
    )

    snapshot = get_approval_workflow_state(
        ticket_id
    )

    return {
        "ticket_id": ticket_id,
        "department_id": approval[
            "department_id"
        ],
        "action": action,
        "approver": approver,
        "workflow_status": (
            result.get("status")
            or snapshot.values.get("status")
        ),
        "pending_approvals": (
            get_pending_approvals(
                ticket_id
            )
        ),
        "conflicts": snapshot.values.get(
            "conflicts",
            [],
        ),
        "arbitration_results": (
            snapshot.values.get(
                "arbitration_results",
                [],
            )
        ),
    }
