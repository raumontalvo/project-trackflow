"""TrackFlow Part 3 department approvals and ticket completion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlmodel import Session, select

from data.pipelines.rfp_intake.approval_state import RFPApprovalState
from data.pipelines.rfp_intake.checkpointing import (
    approval_config,
    get_rfp_checkpointer,
)
from data.pipelines.rfp_intake.conflicts import (
    arbitrate_conflicts,
    detect_conflicts,
)
from data.pipelines.rfp_intake.final_document import (
    synthesize_final_document,
)
from data.pipelines.rfp_intake.persistence import (
    persist_approval_decision,
    persist_final_document,
    persist_generated_section,
    update_ticket_status,
)
from data.pipelines.rfp_intake.response_generation import (
    generate_and_evaluate_section,
)
from services.api.database import engine
from services.api.models import (
    DepartmentSection,
    FinalDocument,
    RFP,
    Ticket,
)


DEPARTMENT_APPROVERS = {
    "warehouse": "Ana Whitfield",
    "lastmile": "Carlos Vega",
    "reverse": "Sofía Ramos",
}

VALID_APPROVAL_ACTIONS = {
    "approve",
    "reject",
    "request_changes",
}

MAX_PART3_REVISIONS = 3


@dataclass
class AggregateApprovalSnapshot:
    """Compatibility view over all department approval threads."""

    values: dict[str, Any]
    tasks: tuple[Any, ...]
    next: tuple[str, ...]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Department-scoped approval graph
# ---------------------------------------------------------------------------


def route_department_entry(
    state: RFPApprovalState,
) -> str:
    """Choose normal approval or forced revision entry."""

    if state.get("entry_action") == "revise":
        return "revise"

    return "approve"


def human_approval_node(
    state: RFPApprovalState,
) -> dict[str, Any]:
    """Pause exactly one department thread for its named owner."""

    department_id = state["department_id"]
    section = state["section"]

    expected_approver = DEPARTMENT_APPROVERS.get(
        department_id
    )

    if expected_approver is None:
        raise ValueError(
            f"Unknown TrackFlow department: {department_id}"
        )

    decision = interrupt(
        {
            "type": "department_approval",
            "ticket_id": state["ticket_id"],
            "rfp_id": state["rfp_id"],
            "department_id": department_id,
            "approver": expected_approver,
            "section": {
                "draft_content": section.get(
                    "draft_content"
                ),
                "evaluation_results": section.get(
                    "evaluation_results"
                ),
                "key_aspects": section.get(
                    "key_aspects"
                ),
            },
            "allowed_actions": sorted(
                VALID_APPROVAL_ACTIONS
            ),
        }
    )

    if not isinstance(decision, dict):
        raise ValueError(
            "Approval response must be an object."
        )

    action = decision.get("action")
    approver = decision.get("approver")
    comment = decision.get("comment")

    if action not in VALID_APPROVAL_ACTIONS:
        raise ValueError(
            "Approval action must be approve, reject, "
            "or request_changes."
        )

    if approver != expected_approver:
        raise ValueError(
            f"{department_id} must be decided by "
            f"{expected_approver}."
        )

    timestamp = _utc_now_iso()

    result = {
        "department_id": department_id,
        "approver": approver,
        "action": action,
        "comment": comment,
        "decided_at": timestamp,
    }

    if action == "approve":
        persist_approval_decision(
            section["section_id"],
            approval_status="approved",
            approver=approver,
            approved_at=datetime.now(timezone.utc),
        )
        status = "approved"

    elif action == "reject":
        persist_approval_decision(
            section["section_id"],
            approval_status="rejected",
            approver=approver,
        )
        status = "rejected"

    else:
        persist_approval_decision(
            section["section_id"],
            approval_status="request_changes",
            approver=approver,
        )
        status = "waiting_for_approval"

    return {
        "approval_results": {
            department_id: result,
        },
        "decision_action": action,
        "status": status,
        "trace_events": [
            {
                "event": "human_approval",
                "department_id": department_id,
                "actor": approver,
                "action": action,
                "timestamp": timestamp,
            }
        ],
    }


def route_after_human_approval(
    state: RFPApprovalState,
) -> str:
    """Route one department after its human decision."""

    department_id = state["department_id"]

    result = state.get(
        "approval_results",
        {},
    ).get(
        department_id,
        {},
    )

    action = result.get("action")

    if action == "request_changes":
        return "revise"

    return "stop"


def _load_revision_metadata(
    rfp_id: str,
) -> dict[str, Any]:
    with Session(engine) as session:
        rfp = session.get(RFP, rfp_id)

        if rfp is None:
            raise ValueError(
                f"RFP not found: {rfp_id}"
            )

        return {
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


def revise_section_node(
    state: RFPApprovalState,
) -> dict[str, Any]:
    """Regenerate only this department and reevaluate it."""

    department_id = state["department_id"]
    section = state["section"]

    revision_counts = state.get(
        "revision_counts",
        {},
    )

    current_count = revision_counts.get(
        department_id,
        0,
    )

    if current_count >= MAX_PART3_REVISIONS:
        persist_approval_decision(
            section["section_id"],
            approval_status="rejected",
            approver=None,
        )

        return {
            "revision_outcome": "stop",
            "status": "rejected",
            "trace_events": [
                {
                    "event": "revision_limit_exceeded",
                    "department_id": department_id,
                    "revision_count": current_count,
                    "timestamp": _utc_now_iso(),
                }
            ],
        }

    next_count = current_count + 1

    metadata = _load_revision_metadata(
        state["rfp_id"]
    )

    result = generate_and_evaluate_section(
        section_id=section["section_id"],
        department_id=department_id,
        metadata=metadata,
        key_aspects=section.get(
            "key_aspects",
            {},
        ),
    )

    persist_generated_section(
        section_id=result["section_id"],
        draft_content=result["draft_content"],
        evaluation_result=result["evaluation_result"],
        iterations=result["iterations"],
        needs_human_review=result["needs_human_review"],
        commitments=result.get("commitments"),
    )

    revised_section = dict(section)
    revised_section["draft_content"] = result[
        "draft_content"
    ]
    revised_section["evaluation_results"] = {
        "evaluation": result["evaluation_result"],
        "commitments": result.get(
            "commitments",
            {},
        ),
        "iterations": result["iterations"],
        "needs_human_review": result[
            "needs_human_review"
        ],
    }

    timestamp = _utc_now_iso()

    if result["needs_human_review"]:
        persist_approval_decision(
            section["section_id"],
            approval_status="request_changes",
            approver=None,
        )

        outcome = "stop"
        status = "needs_human_review"

    else:
        persist_approval_decision(
            section["section_id"],
            approval_status="waiting_for_approval",
            approver=None,
        )

        outcome = "reapprove"
        status = "waiting_for_approval"

    return {
        "entry_action": "approve",
        "section": revised_section,
        "sections": {
            department_id: revised_section,
        },
        "section_commitments": {
            department_id: result.get(
                "commitments",
                {},
            ),
        },
        "revision_counts": {
            department_id: next_count,
        },
        "revision_outcome": outcome,
        "status": status,
        "trace_events": [
            {
                "event": "section_revised",
                "department_id": department_id,
                "revision_count": next_count,
                "timestamp": timestamp,
            }
        ],
    }


def route_after_revision(
    state: RFPApprovalState,
) -> str:
    if state.get("revision_outcome") == "reapprove":
        return "reapprove"

    return "stop"


def build_approval_graph(
    checkpointer=None,
):
    """Build one independent department approval graph."""

    builder = StateGraph(RFPApprovalState)

    builder.add_node(
        "human_approval",
        human_approval_node,
    )

    builder.add_node(
        "revise_section",
        revise_section_node,
    )

    builder.add_conditional_edges(
        START,
        route_department_entry,
        {
            "approve": "human_approval",
            "revise": "revise_section",
        },
    )

    builder.add_conditional_edges(
        "human_approval",
        route_after_human_approval,
        {
            "revise": "revise_section",
            "stop": END,
        },
    )

    builder.add_conditional_edges(
        "revise_section",
        route_after_revision,
        {
            "reapprove": "human_approval",
            "stop": END,
        },
    )

    return builder.compile(
        checkpointer=checkpointer
    )


# ---------------------------------------------------------------------------
# Ticket-level completion graph
# ---------------------------------------------------------------------------


def detect_conflicts_node(
    state: RFPApprovalState,
) -> dict[str, Any]:
    conflicts = detect_conflicts(
        client_country=state.get(
            "client_country"
        ),
        active_departments=state.get(
            "active_departments",
            [],
        ),
        section_commitments=state.get(
            "section_commitments",
            {},
        ),
    )

    return {
        "conflicts": conflicts,
        "trace_events": [
            {
                "event": "conflict_detection",
                "trigger_ids": [
                    item["trigger_id"]
                    for item in conflicts
                ],
                "timestamp": _utc_now_iso(),
            }
        ],
    }


def route_after_conflict_detection(
    state: RFPApprovalState,
) -> str:
    if state.get("conflicts"):
        return "arbitrate"

    return "clear"


def arbitration_node(
    state: RFPApprovalState,
) -> dict[str, Any]:
    """Apply TrackFlow's fixed, deterministic arbiters."""

    results = arbitrate_conflicts(
        state.get(
            "conflicts",
            [],
        )
    )

    return {
        "arbitration_results": results,
        "status": "waiting_for_approval",
        "trace_events": [
            {
                "event": "arbitration",
                "trigger_ids": [
                    item["trigger_id"]
                    for item in results
                ],
                "timestamp": _utc_now_iso(),
            }
        ],
    }


def final_document_node(
    state: RFPApprovalState,
) -> dict[str, Any]:
    """Generate and persist the final approved document."""

    active_departments = state.get(
        "active_departments",
        [],
    )

    approval_results = state.get(
        "approval_results",
        {},
    )

    for department_id in active_departments:
        result = approval_results.get(
            department_id,
            {},
        )

        if result.get("action") != "approve":
            raise ValueError(
                "Final document requires every active "
                f"department approval: {department_id}"
            )

    document_content, approved_sections = (
        synthesize_final_document(
            client_name=state.get("client_name"),
            currency=state["currency"],
            active_departments=active_departments,
            sections=state["sections"],
        )
    )

    persisted = persist_final_document(
        ticket_id=state["ticket_id"],
        sections=approved_sections,
        currency=state["currency"],
        document_content=document_content,
    )

    final_document = {
        "ticket_id": persisted.ticket_id,
        "sections": approved_sections,
        "currency": persisted.currency,
        "document_content": persisted.document_content,
        "generated_at": persisted.generated_at.isoformat(),
    }

    return {
        "final_document": final_document,
        "status": "done",
        "trace_events": [
            {
                "event": "final_document_generated",
                "ticket_id": state["ticket_id"],
                "departments": list(
                    active_departments
                ),
                "timestamp": _utc_now_iso(),
            }
        ],
    }


def build_completion_graph(
    checkpointer=None,
):
    """Build the ticket-level conflict/finalization graph."""

    builder = StateGraph(RFPApprovalState)

    builder.add_node(
        "detect_conflicts",
        detect_conflicts_node,
    )

    builder.add_node(
        "arbitrate",
        arbitration_node,
    )

    builder.add_node(
        "final_document",
        final_document_node,
    )

    builder.add_edge(
        START,
        "detect_conflicts",
    )

    builder.add_conditional_edges(
        "detect_conflicts",
        route_after_conflict_detection,
        {
            "arbitrate": "arbitrate",
            "clear": "final_document",
        },
    )

    builder.add_edge(
        "arbitrate",
        END,
    )

    builder.add_edge(
        "final_document",
        END,
    )

    return builder.compile(
        checkpointer=checkpointer
    )


def _completion_config(
    ticket_id: str,
) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": (
                f"rfp-approval-{ticket_id}-completion"
            )
        }
    }


# ---------------------------------------------------------------------------
# Aggregate state helpers
# ---------------------------------------------------------------------------


def _database_ticket_state(
    ticket_id: str,
) -> dict[str, Any]:
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

        rows = list(
            session.exec(
                select(DepartmentSection).where(
                    DepartmentSection.rfp_id
                    == rfp.rfp_id
                )
            ).all()
        )

        sections: dict[str, dict[str, Any]] = {}
        commitments: dict[str, dict[str, Any]] = {}

        for row in rows:
            evaluation = row.evaluation_results or {}

            sections[row.department_id] = {
                "section_id": row.id,
                "department_id": row.department_id,
                "owner": row.owner,
                "key_aspects": row.key_aspects,
                "draft_content": row.draft_content,
                "evaluation_results": row.evaluation_results,
            }

            commitments[row.department_id] = (
                evaluation.get(
                    "commitments",
                    {},
                )
            )

        final_document_row = session.get(
            FinalDocument,
            ticket_id,
        )

        final_document = None

        if final_document_row is not None:
            final_document = {
                "ticket_id": final_document_row.ticket_id,
                "sections": final_document_row.sections,
                "currency": final_document_row.currency,
                "document_content": (
                    final_document_row.document_content
                ),
                "generated_at": (
                    final_document_row.generated_at.isoformat()
                ),
            }

        return {
            "ticket_id": ticket_id,
            "rfp_id": rfp.rfp_id,
            "client_name": rfp.client_name,
            "client_country": rfp.client_country,
            "currency": (
                "USD"
                if rfp.client_country == "US"
                else "EUR"
            ),
            "active_departments": list(
                rfp.departments_needed or []
            ),
            "sections": sections,
            "section_commitments": commitments,
            "status": ticket.status,
            "error": ticket.error_message,
            "final_document": final_document,
        }


def _child_state(
    initial_state: dict[str, Any],
    department_id: str,
) -> dict[str, Any]:
    section = initial_state[
        "sections"
    ][department_id]

    return {
        "ticket_id": initial_state["ticket_id"],
        "rfp_id": initial_state["rfp_id"],
        "client_name": initial_state.get(
            "client_name"
        ),
        "client_country": initial_state.get(
            "client_country"
        ),
        "currency": initial_state["currency"],
        "active_departments": initial_state.get(
            "active_departments",
            [],
        ),
        "department_id": department_id,
        "section": section,
        "sections": {
            department_id: section,
        },
        "section_commitments": {
            department_id: initial_state.get(
                "section_commitments",
                {},
            ).get(
                department_id,
                {},
            ),
        },
        "revision_counts": {
            department_id: initial_state.get(
                "revision_counts",
                {},
            ).get(
                department_id,
                0,
            ),
        },
        "approval_results": {},
        "trace_events": [],
        "entry_action": "approve",
        "status": "waiting_for_approval",
        "error": None,
    }


def _all_departments_approved(
    approval_results: dict[str, dict[str, Any]],
    active_departments: list[str],
) -> bool:
    return all(
        approval_results.get(
            department_id,
            {},
        ).get("action") == "approve"
        for department_id in active_departments
    )


def _aggregate_with_graph(
    *,
    graph,
    ticket_state: dict[str, Any],
) -> AggregateApprovalSnapshot:
    tasks: list[Any] = []
    next_nodes: list[str] = []

    approval_results: dict[
        str,
        dict[str, Any],
    ] = {}

    revision_counts: dict[str, int] = {}
    trace_events: list[dict[str, Any]] = []

    conflicts: list[dict[str, Any]] = []
    arbitration_results: list[dict[str, Any]] = []

    for department_id in ticket_state[
        "active_departments"
    ]:
        snapshot = graph.get_state(
            approval_config(
                ticket_state["ticket_id"],
                department_id,
            )
        )

        if snapshot is None:
            continue

        tasks.extend(
            snapshot.tasks or ()
        )

        next_nodes.extend(
            snapshot.next or ()
        )

        values = snapshot.values or {}

        approval_results.update(
            values.get(
                "approval_results",
                {},
            )
        )

        revision_counts.update(
            values.get(
                "revision_counts",
                {},
            )
        )

        trace_events.extend(
            values.get(
                "trace_events",
                [],
            )
        )

    return AggregateApprovalSnapshot(
        values={
            **ticket_state,
            "approval_results": approval_results,
            "revision_counts": revision_counts,
            "trace_events": trace_events,
            "conflicts": conflicts,
            "arbitration_results": arbitration_results,
        },
        tasks=tuple(tasks),
        next=tuple(next_nodes),
    )


# ---------------------------------------------------------------------------
# Public compatibility API
# ---------------------------------------------------------------------------


def start_approval_workflow(
    initial_state: dict[str, Any],
) -> dict[str, Any]:
    """Start one independent persisted thread per active department."""

    interrupts: list[Any] = []

    with get_rfp_checkpointer() as checkpointer:
        graph = build_approval_graph(
            checkpointer=checkpointer
        )

        for department_id in initial_state[
            "active_departments"
        ]:
            result = graph.invoke(
                _child_state(
                    initial_state,
                    department_id,
                ),
                config=approval_config(
                    initial_state["ticket_id"],
                    department_id,
                ),
            )

            interrupts.extend(
                result.get(
                    "__interrupt__",
                    (),
                )
            )

    return {
        **initial_state,
        "status": "waiting_for_approval",
        "__interrupt__": interrupts,
    }


def get_approval_workflow_state(
    ticket_id: str,
) -> AggregateApprovalSnapshot:
    """Return one compatibility snapshot across department threads."""

    ticket_state = _database_ticket_state(
        ticket_id
    )

    with get_rfp_checkpointer() as checkpointer:
        graph = build_approval_graph(
            checkpointer=checkpointer
        )

        aggregate = _aggregate_with_graph(
            graph=graph,
            ticket_state=ticket_state,
        )

        completion = build_completion_graph(
            checkpointer=checkpointer
        ).get_state(
            _completion_config(ticket_id)
        )

        if completion is not None:
            values = completion.values or {}

            if values:
                aggregate.values["conflicts"] = (
                    values.get(
                        "conflicts",
                        [],
                    )
                )
                aggregate.values[
                    "arbitration_results"
                ] = values.get(
                    "arbitration_results",
                    [],
                )

                aggregate.values[
                    "trace_events"
                ].extend(
                    values.get(
                        "trace_events",
                        [],
                    )
                )

                if values.get("final_document"):
                    aggregate.values[
                        "final_document"
                    ] = values[
                        "final_document"
                    ]

    return aggregate


def _trigger_arbitration_revisions(
    *,
    graph,
    ticket_state: dict[str, Any],
    arbitration_results: list[dict[str, Any]],
) -> list[Any]:
    """Start revisions only for departments named by arbitration."""

    affected: set[str] = set()

    for result in arbitration_results:
        if result.get("action") != "request_changes":
            continue

        affected.update(
            result.get(
                "affected_departments",
                [],
            )
        )

    interrupts: list[Any] = []

    for department_id in sorted(affected):
        section = ticket_state[
            "sections"
        ].get(
            department_id
        )

        if section is None:
            raise ValueError(
                "Arbitration references missing section: "
                f"{department_id}"
            )

        persist_approval_decision(
            section["section_id"],
            approval_status="request_changes",
            approver=None,
        )

        result = graph.invoke(
            {
                "entry_action": "revise",
                "ticket_id": ticket_state["ticket_id"],
                "rfp_id": ticket_state["rfp_id"],
                "client_name": ticket_state.get(
                    "client_name"
                ),
                "client_country": ticket_state.get(
                    "client_country"
                ),
                "currency": ticket_state["currency"],
                "active_departments": ticket_state[
                    "active_departments"
                ],
                "department_id": department_id,
                "section": section,
                "sections": {
                    department_id: section,
                },
                "section_commitments": {
                    department_id: ticket_state.get(
                        "section_commitments",
                        {},
                    ).get(
                        department_id,
                        {},
                    ),
                },
                "trace_events": [
                    {
                        "event": "arbitration_revision_started",
                        "department_id": department_id,
                        "timestamp": _utc_now_iso(),
                    }
                ],
            },
            config=approval_config(
                ticket_state["ticket_id"],
                department_id,
            ),
        )

        interrupts.extend(
            result.get(
                "__interrupt__",
                (),
            )
        )

    update_ticket_status(
        ticket_state["ticket_id"],
        "waiting_for_approval",
    )

    return interrupts


def resume_approval_workflow(
    ticket_id: str,
    resume_mapping: dict[str, Any],
) -> dict[str, Any]:
    """Resume only the department thread containing the interrupt ID."""

    if not resume_mapping:
        raise ValueError(
            "At least one interrupt response is required."
        )

    ticket_state = _database_ticket_state(
        ticket_id
    )

    target_interrupt_ids = set(
        resume_mapping
    )

    resumed = False

    with get_rfp_checkpointer() as checkpointer:
        approval_graph = build_approval_graph(
            checkpointer=checkpointer
        )

        for department_id in ticket_state[
            "active_departments"
        ]:
            config = approval_config(
                ticket_id,
                department_id,
            )

            snapshot = approval_graph.get_state(
                config
            )

            matched = False

            for task in snapshot.tasks or ():
                if task.result is not None:
                    continue

                for item in task.interrupts:
                    if item.id in target_interrupt_ids:
                        matched = True
                        break

                if matched:
                    break

            if not matched:
                continue

            approval_graph.invoke(
                Command(
                    resume=resume_mapping
                ),
                config=config,
            )

            resumed = True
            break

        if not resumed:
            raise ValueError(
                "Approval interrupt not found or already completed."
            )

        # Re-read all independent approval threads.
        ticket_state = _database_ticket_state(
            ticket_id
        )

        aggregate = _aggregate_with_graph(
            graph=approval_graph,
            ticket_state=ticket_state,
        )

        approval_results = aggregate.values.get(
            "approval_results",
            {},
        )

        if not _all_departments_approved(
            approval_results,
            ticket_state["active_departments"],
        ):
            update_ticket_status(
                ticket_id,
                "waiting_for_approval",
            )

            return {
                **aggregate.values,
                "__interrupt__": [
                    item
                    for task in aggregate.tasks
                    if task.result is None
                    for item in task.interrupts
                ],
            }

        # Every department approved. Run explicit completion graph.
        completion_graph = build_completion_graph(
            checkpointer=checkpointer
        )

        completion_state = {
            **ticket_state,
            "approval_results": approval_results,
            "revision_counts": aggregate.values.get(
                "revision_counts",
                {},
            ),
            "trace_events": [
                {
                    "event": "approval_convergence",
                    "active_departments": ticket_state[
                        "active_departments"
                    ],
                    "all_approved": True,
                    "timestamp": _utc_now_iso(),
                }
            ],
            "conflicts": [],
            "arbitration_results": [],
        }

        completion_result = completion_graph.invoke(
            completion_state,
            config=_completion_config(
                ticket_id
            ),
        )

        arbitration_results = (
            completion_result.get(
                "arbitration_results",
                [],
            )
        )

        if arbitration_results:
            # Completion graph explicitly arbitrated; send only affected
            # department threads back through revision + fresh approval.
            ticket_state = _database_ticket_state(
                ticket_id
            )

            new_interrupts = (
                _trigger_arbitration_revisions(
                    graph=approval_graph,
                    ticket_state=ticket_state,
                    arbitration_results=arbitration_results,
                )
            )

            return {
                **completion_result,
                "status": "waiting_for_approval",
                "__interrupt__": new_interrupts,
            }

        return completion_result
