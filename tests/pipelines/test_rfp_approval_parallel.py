"""Regression tests for independent department approval threads."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from data.pipelines.rfp_intake.approval_graph import (
    build_approval_graph,
)


def _department_state(
    *,
    ticket_id: str,
    department_id: str,
    section_id: str,
) -> dict:
    """Build minimal state for one department approval thread."""

    approver_sections = {
        "warehouse": "Warehouse proposal in USD.",
        "lastmile": "Last Mile proposal in USD.",
    }

    section = {
        "section_id": section_id,
        "department_id": department_id,
        "key_aspects": {
            "requested_scope": [
                department_id,
            ],
        },
        "draft_content": approver_sections[
            department_id
        ],
        "evaluation_results": {
            "evaluation": {
                "overall_pass": True,
            },
            "commitments": {
                "currency": "USD",
            },
            "iterations": 1,
            "needs_human_review": False,
        },
    }

    return {
        "ticket_id": ticket_id,
        "rfp_id": "test-rfp-001",
        "client_name": "Test Client",
        "client_country": "US",
        "currency": "USD",
        "active_departments": [
            "warehouse",
            "lastmile",
        ],
        "department_id": department_id,
        "section": section,
        "sections": {
            department_id: section,
        },
        "section_commitments": {
            department_id: {
                "currency": "USD",
            },
        },
        "revision_counts": {
            department_id: 0,
        },
        "approval_results": {},
        "trace_events": [],
        "entry_action": "approve",
        "status": "waiting_for_approval",
        "error": None,
    }


def _config(
    *,
    ticket_id: str,
    department_id: str,
) -> dict:
    """Return isolated checkpoint identity for one department."""

    return {
        "configurable": {
            "thread_id": (
                f"rfp-approval-{ticket_id}-"
                f"{department_id}"
            ),
        },
    }


def test_department_b_can_approve_while_department_a_is_interrupted(
    monkeypatch,
) -> None:
    """
    Last Mile can approve while Warehouse remains interrupted.

    This proves the approval flow uses independent checkpoint branches,
    rather than fake serial approval inside one shared interrupt step.
    """

    # Human approval persistence is tested separately.
    # Keep this graph-level test isolated from PostgreSQL.
    monkeypatch.setattr(
        "data.pipelines.rfp_intake.approval_graph."
        "persist_approval_decision",
        lambda *args, **kwargs: None,
    )

    checkpointer = InMemorySaver()

    graph = build_approval_graph(
        checkpointer=checkpointer,
    )

    ticket_id = "parallel-test-ticket"

    warehouse_config = _config(
        ticket_id=ticket_id,
        department_id="warehouse",
    )

    lastmile_config = _config(
        ticket_id=ticket_id,
        department_id="lastmile",
    )

    warehouse_result = graph.invoke(
        _department_state(
            ticket_id=ticket_id,
            department_id="warehouse",
            section_id="warehouse-section",
        ),
        config=warehouse_config,
    )

    lastmile_result = graph.invoke(
        _department_state(
            ticket_id=ticket_id,
            department_id="lastmile",
            section_id="lastmile-section",
        ),
        config=lastmile_config,
    )

    warehouse_interrupts = warehouse_result.get(
        "__interrupt__",
        (),
    )

    lastmile_interrupts = lastmile_result.get(
        "__interrupt__",
        (),
    )

    assert len(warehouse_interrupts) == 1
    assert len(lastmile_interrupts) == 1

    warehouse_interrupt_id = (
        warehouse_interrupts[0].id
    )

    lastmile_interrupt_id = (
        lastmile_interrupts[0].id
    )

    assert (
        warehouse_interrupt_id
        != lastmile_interrupt_id
    )

    # Approve only Last Mile.
    graph.invoke(
        Command(
            resume={
                lastmile_interrupt_id: {
                    "action": "approve",
                    "approver": "Carlos Vega",
                    "comment": (
                        "Last Mile approved."
                    ),
                }
            }
        ),
        config=lastmile_config,
    )

    # Warehouse must still be paused at its original interrupt.
    warehouse_snapshot = graph.get_state(
        warehouse_config
    )

    warehouse_pending = [
        item
        for task in warehouse_snapshot.tasks
        if task.result is None
        for item in task.interrupts
    ]

    assert len(warehouse_pending) == 1
    assert (
        warehouse_pending[0].id
        == warehouse_interrupt_id
    )

    assert (
        warehouse_pending[0]
        .value["department_id"]
        == "warehouse"
    )

    # Last Mile must be completed independently.
    lastmile_snapshot = graph.get_state(
        lastmile_config
    )

    assert lastmile_snapshot.next == ()

    approval_results = (
        lastmile_snapshot.values.get(
            "approval_results",
            {},
        )
    )

    assert (
        approval_results[
            "lastmile"
        ]["action"]
        == "approve"
    )
