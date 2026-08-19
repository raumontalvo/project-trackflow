"""Regression tests for the Part 3 approval revision limit."""

from __future__ import annotations

from data.pipelines.rfp_intake.approval_graph import (
    MAX_PART3_REVISIONS,
    revise_section_node,
)


def test_revision_limit_stops_additional_regeneration(
    monkeypatch,
) -> None:
    """
    A department cannot regenerate indefinitely after request_changes.

    Once MAX_PART3_REVISIONS is reached, the branch is rejected and
    terminates without calling the Part 2 generator again.
    """

    persisted: list[dict] = []

    def fake_persist_approval_decision(
        section_id: str,
        *,
        approval_status: str,
        approver,
        approved_at=None,
    ):
        persisted.append(
            {
                "section_id": section_id,
                "approval_status": approval_status,
                "approver": approver,
                "approved_at": approved_at,
            }
        )

    def fail_if_generator_runs(*args, **kwargs):
        raise AssertionError(
            "Generator must not run after the Part 3 "
            "revision limit is reached."
        )

    monkeypatch.setattr(
        "data.pipelines.rfp_intake.approval_graph."
        "persist_approval_decision",
        fake_persist_approval_decision,
    )

    monkeypatch.setattr(
        "data.pipelines.rfp_intake.approval_graph."
        "generate_and_evaluate_section",
        fail_if_generator_runs,
    )

    state = {
        "ticket_id": "revision-limit-ticket",
        "rfp_id": "revision-limit-rfp",
        "client_name": "Test Client",
        "client_country": "US",
        "currency": "USD",
        "active_departments": [
            "warehouse",
        ],
        "department_id": "warehouse",
        "section": {
            "section_id": "warehouse-section-001",
            "department_id": "warehouse",
            "key_aspects": {
                "requested_scope": [
                    "warehousing",
                ],
            },
            "draft_content": (
                "Warehouse proposal awaiting revision."
            ),
            "evaluation_results": {
                "evaluation": {
                    "overall_pass": True,
                },
                "iterations": 1,
                "needs_human_review": False,
            },
        },
        "revision_counts": {
            "warehouse": MAX_PART3_REVISIONS,
        },
        "approval_results": {},
        "trace_events": [],
        "entry_action": "revise",
        "status": "waiting_for_approval",
        "error": None,
    }

    result = revise_section_node(state)

    assert result["status"] == "rejected"
    assert result["revision_outcome"] == "stop"

    assert persisted == [
        {
            "section_id": "warehouse-section-001",
            "approval_status": "rejected",
            "approver": None,
            "approved_at": None,
        }
    ]

    trace = result["trace_events"]

    assert len(trace) == 1
    assert (
        trace[0]["event"]
        == "revision_limit_exceeded"
    )
    assert (
        trace[0]["department_id"]
        == "warehouse"
    )
    assert (
        trace[0]["revision_count"]
        == MAX_PART3_REVISIONS
    )
